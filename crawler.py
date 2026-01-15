import time
import sys
import os
import re
import pickle
import gspread
from google.auth.transport.requests import Request
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# --- 설정값 ---
BASE_URL = "https://www.k-icfr.org/sub/menu/"
SPREADSHEET_NAME = 'K-ICFR_Data'

def get_google_sheet_client():
    """구글 시트 인증 및 클라이언트 반환 (User Auth with token.pickle)"""
    creds = None
    token_path = os.path.join(os.path.dirname(__file__), 'token.pickle')
    
    if os.path.exists(token_path):
        with open(token_path, 'rb') as token:
            creds = pickle.load(token)
            
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("토큰 만료, 갱신 시도 중...")
            creds.refresh(Request())
        else:
            print("유효한 토큰(token.pickle)이 없습니다.")
            sys.exit(1)
            
    client = gspread.authorize(creds)
    return client

def open_worksheet(client, sheet_name, tab_name):
    """스프레드시트와 탭을 엽니다."""
    try:
        sh = client.open(sheet_name)
    except gspread.SpreadsheetNotFound:
        print(f"스프레드시트 '{sheet_name}'가 없어 새로 생성합니다.")
        sh = client.create(sheet_name)
        print("시트가 생성되었습니다.")

    try:
        worksheet = sh.worksheet(tab_name)
    except gspread.WorksheetNotFound:
        worksheet = sh.add_worksheet(title=tab_name, rows="100", cols="10")
        worksheet.append_row(['번호', '분류', '제목', '등록일', '작성자', '질문 본문', '답변 본문', '처리현황', 'URL'])
    
    return worksheet

def init_driver():
    """Selenium 드라이버 초기화 (실제 브라우저처럼 보이기)"""
    chrome_options = Options()
    # headless를 쓰면 차단될 확률이 높으므로 일단 보면서 실행 (필요 시 headless 추가)
    # chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--window-size=1280,800")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def crawl_board_selenium(driver, page_name, max_pages=3):
    """Selenium을 이용한 게시판 크롤링"""
    print(f"[{page_name}] 크롤링 시작...")
    results = []
    
    # page_name: 'qna.asp' or 'faq.asp'
    base_page_url = f"{BASE_URL}{page_name}"
    
    for page in range(1, max_pages + 1):
        print(f"  - {page} 페이지 이동 중...")
        # 페이지 이동 URL (ASP 파라미터 구조에 맞춤)
        # 예: qna.asp?rWork=TblList&rType=0&rGotoPage=1
        target_url = f"{base_page_url}?rWork=TblList&rType=0&rGotoPage={page}"
        driver.get(target_url)
        time.sleep(2) # 페이지 로딩 대기
        
        # 목록 파싱
        rows = driver.find_elements(By.CSS_SELECTOR, "table.board_list tbody tr")
        
        if not rows:
            print("    게시물이 없습니다.")
            break
            
        # 현재 페이지의 링크들을 수집 (StaleElementReferenceException 방지 위해 링크만 먼저 저장)
        items_to_crawl = []
        for row in rows:
            try:
                num = row.find_element(By.CSS_SELECTOR, "td.num").text.strip()
                if not num.isdigit(): continue # 공지 제외
                
                subject_elem = row.find_element(By.CSS_SELECTOR, "td.subject a")
                title = subject_elem.text.strip()
                link = subject_elem.get_attribute("href")
                date = row.find_element(By.CSS_SELECTOR, "td.date").text.strip()
                
                # Q&A 전용 필드
                try:
                   category = row.find_element(By.CSS_SELECTOR, "td.category").text.strip()
                except: category = ""
                
                try:
                    name = row.find_element(By.CSS_SELECTOR, "td.name").text.strip()
                except: name = ""
                
                try:
                    condition = row.find_element(By.CSS_SELECTOR, "td.condition").text.strip()
                except: condition = ""
                
                items_to_crawl.append({
                    'num': int(num),
                    'title': title,
                    'link': link,
                    'date': date,
                    'category': category,
                    'name': name,
                    'condition': condition
                })
            except Exception as e:
                print(f"ROW 파싱 에러: {e}")
                continue
        
        if not items_to_crawl:
            print("    수집할 항목이 없습니다.")
            break
            
        print(f"    {len(items_to_crawl)}개의 항목을 발견했습니다. 상세 수집 시작...")
        
        # 상세 페이지 순회
        for item in items_to_crawl:
            try:
                # 이미 수집된 번호인지 확인하는 로직은 구글 시트 업데이트 단계에서 수행하거나, 
                # 여기서 미리 체크해서 skip할 수도 있음. (지금은 일단 다 수집하여 넘김)
                
                driver.get(item['link'])
                time.sleep(1.5) # 부하 방지
                
                # 상세 페이지 내용 파싱
                # 구조를 모르므로 여러 가지 시도
                content_html = driver.page_source
                soup = BeautifulSoup(content_html, 'html.parser')
                
                # 1. 본문 찾기 시도
                # 보통 .board_read 혹은 .con_box 내부에 있음
                # 정확한 셀렉터를 모르므로 .board_view, .view_content 등 일반적인 이름 시도
                question_body = ""
                
                # 예상되는 본문 영역 후보군
                candidates = ['.board_view', '.view_content', '.con_box .board_read', '.board_read tr td', '.board_list'] 
                # (ASP 상세페이지가 table 구조일 수 있음)
                
                # 테이블 구조인 경우: <th>제목</th><td>내용</td> 구조일 가능성
                # 소스 확인 결과 목록이 table.board_list 였으므로 상세도 table.board_view 등의 클래스일 수 있음.
                
                # 좀 더 광범위하게 본문 텍스트 추출 시도 (임시)
                # K-ICFR 사이트 특성상 #contents 안의 내용을 긁는게 안전
                content_div = soup.select_one('#contents .board_view') or soup.select_one('#contents table')
                if content_div:
                     question_body = content_div.get_text(separator='\n').strip()
                else:
                    # 못 찾으면 메인 컨텐츠 영역 전체라도
                     c_box = soup.select_one('#contents')
                     if c_box: question_body = c_box.get_text(separator='\n').strip()
                
                # 답변 찾기
                answer_body = ""
                # 답변이 댓글 형태인지 본문 하단인지 불분명. 
                # "답변" 이라는 텍스트가 포함된 영역을 찾거나..
                # 일단 전체 본문에 포함되어 있을 가능성이 높음 (ASP 게시판은 보통 원글+답글이 별도 row거나 한 페이지에 보임)
                
                # 데이터 정제
                results.append({
                    '번호': item['num'],
                    '분류': item['category'],
                    '제목': item['title'],
                    '등록일': item['date'],
                    '작성자': item['name'],
                    '질문 본문': question_body,  # 분리가 안되면 전체 내용
                    '답변 본문': answer_body,     # 분리 로직 보완 필요
                    '처리현황': item['condition'],
                    'URL': item['link']
                })
                
            except Exception as e:
                print(f"    상세 페이지({item['num']}) 에러: {e}")
                
            # 다시 목록으로 돌아갈 필요 없음 (바로 다음 link로 get 하므로)
    
        # 다음 페이지 루프
        
    return results

def update_sheet_data(worksheet, new_data):
    """시트에 데이터 업데이트 (중복 방지)"""
    if not new_data:
        print("업데이트할 데이터가 없습니다.")
        return
    
    # 기존 데이터 로드
    existing_records = worksheet.get_all_records()
    existing_nums = set()
    for row in existing_records:
        if '번호' in row:
            existing_nums.add(str(row['번호']))
    
    to_add = []
    print(f"기존 {len(existing_nums)}건. 중복 확인 중...")
    
    count = 0
    for item in new_data:
        if str(item['번호']) not in existing_nums:
            row = [
                item['번호'],
                item['분류'],
                item['제목'],
                item['등록일'],
                item['작성자'],
                item['질문 본문'][:30000], # 셀 용량 제한 고려
                item['답변 본문'][:30000],
                item['처리현황'],
                item['URL']
            ]
            to_add.append(row)
            existing_nums.add(str(item['번호']))
            count += 1
            
    if to_add:
        # 역순 정렬해서 넣고 싶다면 여기서 sort. (보통 최신순 수집이니 그대로)
        worksheet.append_rows(to_add)
        print(f"{count}건 추가 완료.")
    else:
        print("추가된 데이터가 없습니다.")

def main():
    print("=== K-ICFR 크롤러 (Selenium) 시작 ===")
    
    driver = init_driver()
    client = get_google_sheet_client()
    
    try:
        # Q&A 처리
        print("\n>> Q&A 수집")
        ws_qna = open_worksheet(client, SPREADSHEET_NAME, 'Q&A')
        data_qna = crawl_board_selenium(driver, 'qna.asp', max_pages=3)
        update_sheet_data(ws_qna, data_qna)
        
        # FAQ 처리
        print("\n>> FAQ 수집")
        ws_faq = open_worksheet(client, SPREADSHEET_NAME, 'FAQ')
        data_faq = crawl_board_selenium(driver, 'faq.asp', max_pages=3)
        update_sheet_data(ws_faq, data_faq)
        
    finally:
        driver.quit()
        print("\n브라우저 종료 및 작업 완료.")

if __name__ == "__main__":
    main()

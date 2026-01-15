import requests
from bs4 import BeautifulSoup
import re

def check(name, url):
    print(f"--- Checking {name} ({url}) ---")
    try:
        res = requests.get(url)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 테이블 구조 확인
        # 그누보드 테마마다 테이블 클래스가 다름 (.tbl_head01, .tbl_wrap 등)
        table = soup.select_one('table')
        if table:
            print(f"  Table Class: {table.get('class')}")
            
        rows = soup.select('table tbody tr') 
        print(f"  Rows found: {len(rows)}")
        
        if len(rows) > 0:
            # 첫 번째 행 분석 (공지사항일 수도 있으니 몇 개 확인)
            target_row = rows[0]
            
            # 제목 셀 클래스 확인 (.td_subject)
            subject = target_row.select_one('.td_subject')
            print(f"  Has .td_subject: {subject is not None}")
            
            # 날짜 셀
            date_td = target_row.select_one('.td_date')
            print(f"  Has .td_date: {date_td is not None}")
            
            # 상세 페이지 링크
            link_tag = target_row.select_one('a[href*="wr_id="]')
            if link_tag:
                detail_url = link_tag['href']
                # &amp; 처리
                detail_url = detail_url.replace('&amp;', '&')
                print(f"  Detail URL: {detail_url}")
                
                # 상세 페이지 확인
                print("  >> Checking detail page...")
                res_d = requests.get(detail_url)
                soup_d = BeautifulSoup(res_d.text, 'html.parser')
                
                # 질문 본문 (보통 #bo_v_con)
                q_div = soup_d.select_one('#bo_v_con')
                print(f"  Has #bo_v_con (Question Body): {q_div is not None}")
                
                # 답변(댓글) 확인
                # 1. 댓글 영역 (#bo_vc)
                ans_container = soup_d.select_one('#bo_vc')
                print(f"  Has #bo_vc (Comment Container): {ans_container is not None}")
                
                if ans_container:
                    # 댓글 개별 요소 (article or .chk_box)
                    comments = ans_container.select('article')
                    print(f"  Comments (article tags): {len(comments)}")
                
                # 2. 뷰 페이지 내 답변이 있는지 (Q&A 게시판 특성상 본문에 답이 달리는 경우)
                # 관리자 답변 표시가 따로 있는지 확인
                admin_ans = soup_d.select('.view_answer') # 예시 클래스
                print(f"  Has .view_answer: {len(admin_ans) > 0}")

    except Exception as e:
        print(f"Error checking {name}: {e}")
    print("\n")

if __name__ == "__main__":
    check("FAQ", "https://www.k-icfr.org/bbs/board.php?bo_table=sub05_01")
    check("Q&A", "https://www.k-icfr.org/bbs/board.php?bo_table=sub05_02")

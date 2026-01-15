import requests

url = "https://www.k-icfr.org/bbs/board.php?bo_table=sub05_02"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}
try:
    res = requests.get(url, headers=headers)
    res.raise_for_status()
    with open('debug_page.html', 'w', encoding='utf-8') as f:
        f.write(res.text)
    print("Download complete.")
except Exception as e:
    print(f"Error: {e}")

import streamlit as st
import cloudscraper
from bs4 import BeautifulSoup
import datetime
import time
import re
import streamlit.components.v1 as components

# --- [1. 스마트 날짜 계산 함수 (2026년 공휴일 반영)] ---
def get_target_date():
    today = datetime.date.today()
    # 금요일이면 월요일(3일 뒤), 토요일이면 월요일(2일 뒤), 나머지는 다음날
    if today.weekday() == 4: target = today + datetime.timedelta(days=3)
    elif today.weekday() == 5: target = today + datetime.timedelta(days=2)
    else: target = today + datetime.timedelta(days=1)

    # 2026년 주요 공휴일 (대체공휴일 포함)
    holidays = [
        datetime.date(2026,1,1),   # 신정
        datetime.date(2026,2,16), datetime.date(2026,2,17), datetime.date(2026,2,18), # 설날
        datetime.date(2026,3,1), datetime.date(2026,3,2), # 삼일절 및 대체
        datetime.date(2026,5,5),   # 어린이날
        datetime.date(2026,5,24), datetime.date(2026,5,25), # 부처님오신날 및 대체
        datetime.date(2026,6,6),   # 현충일
        datetime.date(2026,8,15),  # 광복절
        datetime.date(2026,9,24), datetime.date(2026,9,25), datetime.date(2026,9,26), # 추석
        datetime.date(2026,10,3),  # 개천절
        datetime.date(2026,10,9),  # 한글날
        datetime.date(2026,12,25)  # 성탄절
    ]
    
    # 목표일이 공휴일이거나 주말이면 다음 평일로 이동
    while target in holidays or target.weekday() >= 5:
        target += datetime.timedelta(days=1)
    return target

# --- [2. 뉴스 스크립터] ---
class NewsScraper:
    def __init__(self):
        self.scraper = cloudscraper.create_scraper()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.naver.com/'
        }

    def fetch_news(self, start_d, end_d, keyword, max_articles):
        ds, de = start_d.strftime("%Y.%m.%d"), end_d.strftime("%Y.%m.%d")
        nso = f"so:dd,p:from{start_d.strftime('%Y%m%d')}to{end_d.strftime('%Y%m%d')}"
        
        all_results = []
        seen_links = set()
        query = f'"{keyword}"'
        max_pages = (max_articles // 10) + 1
        
        status_text = st.empty()
        progress_bar = st.progress(0)

        status_text.text("뉴스 수집 시작...")

        for page in range(1, max_pages + 1):
            if len(all_results) >= max_articles: break
            
            progress_bar.progress(min(page / max_pages, 1.0))
            status_text.text(f"⏳ {page}/{max_pages}페이지 분석 중... (현재 {len(all_results)}건)")
            
            start_index = (page - 1) * 10 + 1
            url = f"https://search.naver.com/search.naver?where=news&query={query}&sm=tab_pge&sort=1&photo=0&pd=3&ds={ds}&de={de}&nso={nso}&qdt=1&start={start_index}"
            
            try:
                response = self.scraper.get(url, headers=self.headers, timeout=10)
                if response.status_code != 200: continue

                soup = BeautifulSoup(response.content, 'html.parser')
                items = soup.select('a[data-heatmap-target=".tit"]') or soup.select('a.news_tit')
                
                if not items: break

                for t_tag in items:
                    if len(all_results) >= max_articles: break

                    title = t_tag.get_text(strip=True)
                    original_link = t_tag.get('href')
                    
                    card = None
                    curr = t_tag
                    for _ in range(5):
                        if curr.parent:
                            curr = curr.parent
                            if curr.select_one(".sds-comps-profile") or curr.select_one(".news_info") or 'bx' in curr.get('class', []):
                                card = curr
                                break
                    
                    final_link = original_link
                    is_naver = "n.news.naver.com" in original_link
                    press_name = "알 수 없음"
                    paper_info = ""
                    article_date = ""
                    is_paper = False

                    if card:
                        # 네이버 뉴스 링크 우선
                        naver_btn = card.select_one('a[href*="n.news.naver.com"]')
                        if naver_btn:
                            final_link = naver_btn.get('href')
                            is_naver = True
                        
                        # 언론사명
                        pre체 뉴스", o_news,  뉴스"








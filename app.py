import streamlit as st
import cloudscraper
from bs4 import BeautifulSoup
import datetime
import time
import pandas as pd

# --- [크롤링 로직 클래스] ---
class NewsScraper:
    def fetch_news(self, start_datetime, end_datetime, keyword, photo_value):
        ds, de = start_datetime.strftime("%Y.%m.%d"), end_datetime.strftime("%Y.%m.%d")
        nso = f"so:dd,p:from{start_datetime.strftime('%Y%m%d')}to{end_datetime.strftime('%Y%m%d')}"
        
        all_results = []
        seen_links = set()
        scraper = cloudscraper.create_scraper()
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

        # 웹 버전에서는 속도를 위해 3페이지(30건) 정도만 긁도록 설정 (조절 가능)
        for page in range(1, 4):
            start_index = (page - 1) * 10 + 1
            url = f"https://search.naver.com/search.naver?where=news&query=\"{keyword}\"&sm=tab_pge&sort=1&photo={photo_value}&pd=3&ds={ds}&de={de}&nso={nso}&start={start_index}"
            
            try:
                response = scraper.get(url, headers=headers, timeout=10)
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # SDS 디자인 대응 파싱
                sds_titles = soup.select('a[data-heatmap-target=".tit"]')
                if not sds_titles: break # 결과 없으면 종료

                for t_tag in sds_titles:
                    title = t_tag.get_text(strip=True)
                    link = t_tag.get('href')
                    if link in seen_links: continue
                    
                    # 카드 컨테이너 찾기 (언론사/시간 추출용)
                    card = t_tag.find_parent('div', class_=lambda c: c and ('api_subject_bx' in c or 'sds-comps' in c))
                    press = "알 수 없음"
                    date_text = "날짜 미상"
                    
                    if card:
                        press_el = card.select_one(".sds-comps-profile-info-title-text, .press_name")
                        if press_el: press = press_el.get_text(strip=True)
                        
                        subtexts = card.select(".sds-comps-profile-info-subtext, .info")
                        for sub in subtexts:
                            txt = sub.get_text(strip=True)
                            if '전' in txt or ('.' in txt and txt[0].isdigit()):
                                date_text = txt
                                break

                    seen_links.add(link)
                    all_results.append({'title': title, 'link': link, 'press': press, 'time': date_text})
                time.sleep(0.3)
            except: break
        return all_results

# --- [웹 UI 시작] ---
st.set_page_config(page_title="서울교통공사 뉴스스크랩", layout="wide")

# 모바일 최적화 스타일 추가
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stButton>button { width: 100%; border-radius: 10px; height: 3em; background-color: #007bff; color: white; }
    .news-card { background: white; padding: 15px; border-radius: 10px; border: 1px solid #ddd; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

st.title("🚇 실시간 뉴스 스크랩 (모바일)")

# 세션 상태 초기화 (스크랩 목록 저장용)
if 'scrap_list' not in st.session_state:
    st.session_state.scrap_list = []

# 검색 설정
with st.expander("🔍 검색 설정 (터치해서 열기)", expanded=True):
    keyword = st.text_input("검색어", value="서울교통공사")
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("시작일", datetime.date.today() - datetime.timedelta(days=1))
    with col2:
        end_date = st.date_input("종료일", datetime.date.today())

if st.button("🚀 뉴스 검색 시작"):
    scraper = NewsScraper()
    with st.spinner('네이버 뉴스를 읽어오는 중...'):
        results = scraper.fetch_news(start_date, end_date, keyword, 0)
        st.session_state.search_results = results

# 검색 결과 표시
if 'search_results' in st.session_state:
    st.subheader(f"✅ 검색 결과 ({len(st.session_state.search_results)}건)")
    for i, res in enumerate(st.session_state.search_results):
        with st.container():
            st.markdown(f"""
            <div class="news-card">
                <strong>[{res['press']}]</strong> {res['title']}<br>
                <small style="color:gray;">{res['time']}</small>
            </div>
            """, unsafe_allow_html=True)
            col_a, col_b = st.columns([0.8, 0.2])
            with col_a:
                st.link_button("기사 원문 보기", res['link'])
            with col_b:
                if st.button("➕ 추가", key=f"add_{i}"):
                    item = f"ㅇ {res['title']}_{res['press']}\n{res['link']}\n\n"
                    if item not in st.session_state.scrap_list:
                        st.session_state.scrap_list.append(item)
                        st.toast("목록에 추가되었습니다!")

# 스크랩 목록 (클립보드 복사용)
st.divider()
st.subheader("📋 최종 스크랩 목록")
if st.session_state.scrap_list:
    final_text = "".join(st.session_state.scrap_list)
    st.text_area("아래 내용을 복사해서 사용하세요", value=final_text, height=250)
    if st.button("🗑️ 목록 비우기"):
        st.session_state.scrap_list = []
        st.rerun()
else:
    st.info("추가 버튼을 눌러 기사를 담으세요.")
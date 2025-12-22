import streamlit as st
import cloudscraper
from bs4 import BeautifulSoup
import datetime
import time

# --- [뉴스 스크래퍼 클래스] ---
class NewsScraper:
    def fetch_news(self, start_datetime, end_datetime, keyword, photo_value):
        ds, de = start_datetime.strftime("%Y.%m.%d"), end_datetime.strftime("%Y.%m.%d")
        nso = f"so:dd,p:from{start_datetime.strftime('%Y%m%d')}to{end_datetime.strftime('%Y%m%d')}"
        
        all_results = []
        seen_links = set()
        scraper = cloudscraper.create_scraper()
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.naver.com/'
        }

        query = f'"{keyword}"'
        for page in range(1, 6):
            start_index = (page - 1) * 10 + 1
            url = f"https://search.naver.com/search.naver?where=news&query={query}&sm=tab_pge&sort=1&photo={photo_value}&pd=3&ds={ds}&de={de}&nso={nso}&start={start_index}"
            
            try:
                response = scraper.get(url, headers=headers, timeout=10)
                soup = BeautifulSoup(response.content, 'html.parser')
                items = soup.select('a[data-heatmap-target=".tit"]')
                if not items: break

                for t_tag in items:
                    title = t_tag.get_text(strip=True)
                    original_link = t_tag.get('href')
                    
                    card = None
                    curr = t_tag
                    for _ in range(5):
                        if curr.parent:
                            curr = curr.parent
                            if curr.select_one(".sds-comps-profile") or curr.select_one(".news_info"):
                                card = curr
                                break
                    
                    final_link = original_link
                    is_naver = "n.news.naver.com" in original_link
                    press_name = "알 수 없음"
                    date_text = "정보 없음"

                    if card:
                        naver_btn = card.select_one('a[href*="n.news.naver.com"]')
                        if naver_btn:
                            final_link = naver_btn.get('href'); is_naver = True
                        press_el = card.select_one(".sds-comps-profile-info-title-text, .press_name, .info.press")
                        if press_el: press_name = press_el.get_text(strip=True)
                        subtext_area = card.select_one(".sds-comps-profile-info-subtexts, .news_info")
                        if subtext_area:
                            for txt in subtext_area.stripped_strings:
                                if ('전' in txt and len(txt) < 15) or ('.' in txt and len(txt) < 15 and txt[0].isdigit()):
                                    date_text = txt; break

                    if final_link in seen_links: continue
                    seen_links.add(final_link)
                    all_results.append({'title': title, 'link': final_link, 'press': press_name, 'time': date_text, 'is_naver': is_naver})
                time.sleep(0.3)
            except: break
        return all_results

# --- [Streamlit 웹 UI] ---
st.set_page_config(page_title="서울교통공사 스크랩", layout="wide")

# 버튼 스타일 통일 및 카드 디자인 CSS
st.markdown("""
    <style>
    /* 모든 버튼 스타일 통일 */
    .stButton > button, .stLinkButton > a {
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        width: 100% !important;
        height: 40px !important;
        background-color: #f0f2f6 !important;
        color: #31333F !important;
        border: 1px solid #d1d5db !important;
        border-radius: 8px !important;
        text-decoration: none !important;
        font-size: 14px !important;
        font-weight: 500 !important;
        margin: 0 !important;
    }
    .stButton > button:hover, .stLinkButton > a:hover {
        border-color: #007bff !important;
        color: #007bff !important;
        background-color: #e7f3ff !important;
    }
    .news-card {
        background: white;
        padding: 14px;
        border-radius: 10px;
        border-left: 6px solid #007bff;
        margin-bottom: 8px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    </style>
    """, unsafe_allow_html=True)

if 'scrap_list' not in st.session_state: st.session_state.scrap_list = []
if 'search_results' not in st.session_state: st.session_state.search_results = []

st.title("🚇 뉴스 스크랩 (Mobile)")

# 1. 스크랩 목록 (최상단, 가변형)
st.subheader("📋 실시간 스크랩 목록")
if st.session_state.scrap_list:
    final_text = "".join(st.session_state.scrap_list)
    # 기사 개수에 따라 높이 조절 (최소 150, 최대 400)
    list_height = min(max(150, len(st.session_state.scrap_list) * 45), 450)
    st.text_area("내용 복사", value=final_text, height=list_height)
    if st.button("🗑️ 목록 비우기"):
        st.session_state.scrap_list = []
        st.rerun()
else:
    st.info("검색 후 '➕ 추가' 버튼을 눌러 기사를 담으세요.")

st.divider()

# 2. 검색 설정
with st.expander("🔍 검색 조건", expanded=True):
    keyword = st.text_input("키워드", value="서울교통공사")
    col1, col2 = st.columns(2)
    with col1: start_date = st.date_input("시작", datetime.date.today() - datetime.timedelta(days=1))
    with col2: end_date = st.date_input("종료", datetime.date.today())
    filter_choice = st.radio("검색 범위", ["네이버 기사", "언론사 자체기사", "모두 보기"], index=0, horizontal=True)

if st.button("🚀 뉴스 검색 실행", type="primary"):
    scraper = NewsScraper()
    with st.spinner('검색 중...'):
        results = scraper.fetch_news(start_date, end_date, keyword, 0)
        st.session_state.search_results = results

# 3. 검색 결과
if st.session_state.search_results:
    if filter_choice == "네이버 기사":
        display_results = [r for r in st.session_state.search_results if r['is_naver']]
    elif filter_choice == "언론사 자체기사":
        display_results = [r for r in st.session_state.search_results if not r['is_naver']]
    else:
        display_results = st.session_state.search_results

    st.subheader(f"✅ 결과: {len(display_results)}건")
    for i, res in enumerate(display_results):
        with st.container():
            st.markdown(f"""
            <div class="news-card">
                <strong>[{res['press']}]</strong> {res['title']}<br>
                <small style="color:gray;">{res['time']} {'(네이버)' if res['is_naver'] else ''}</small>
            </div>
            """, unsafe_allow_html=True)
            
            # 버튼 가로 배치 (디자인 통일)
            btn_col1, btn_col2 = st.columns(2)
            with btn_col1:
                st.link_button("🔗 원문보기", res['link'])
            with btn_col2:
                if st.button("➕ 추가", key=f"add_{i}"):
                    item = f"ㅇ {res['title']}_{res['press']}\n{res['link']}\n\n"
                    if item not in st.session_state.scrap_list:
                        st.session_state.scrap_list.append(item)
                        st.toast("추가되었습니다!")
                        st.rerun()
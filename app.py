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

        # 최대 5페이지 탐색
        for page in range(1, 6):
            start_index = (page - 1) * 10 + 1
            query = f'"{keyword}"'
            url = f"https://search.naver.com/search.naver?where=news&query={query}&sm=tab_pge&sort=1&photo={photo_value}&pd=3&ds={ds}&de={de}&nso={nso}&start={start_index}"
            
            try:
                response = scraper.get(url, headers=headers, timeout=10)
                soup = BeautifulSoup(response.content, 'html.parser')
                items = soup.select('a[data-heatmap-target=".tit"]')
                if not items: break

                for t_tag in items:
                    title = t_tag.get_text(strip=True)
                    original_link = t_tag.get('href')
                    
                    # 카드 컨테이너 탐색
                    card = None
                    curr = t_tag
                    for _ in range(5):
                        if curr.parent:
                            curr = curr.parent
                            if curr.select_one(".sds-comps-profile") or curr.select_one(".news_info"):
                                card = curr
                                break
                    
                    # [로직] 네이버 뉴스 링크 우선 탐색
                    final_link = original_link
                    is_naver = "n.news.naver.com" in original_link
                    
                    press_name = "알 수 없음"
                    date_text = "날짜 정보 없음"

                    if card:
                        # 네이버 인링크가 따로 있는지 확인
                        naver_btn = card.select_one('a[href*="n.news.naver.com"]')
                        if naver_btn:
                            final_link = naver_btn.get('href')
                            is_naver = True

                        press_el = card.select_one(".sds-comps-profile-info-title-text, .press_name, .info.press")
                        if press_el: press_name = press_el.get_text(strip=True)
                        
                        subtext_area = card.select_one(".sds-comps-profile-info-subtexts, .news_info")
                        if subtext_area:
                            for txt in subtext_area.stripped_strings:
                                if ('전' in txt and len(txt) < 15) or ('.' in txt and len(txt) < 15 and txt[0].isdigit()):
                                    date_text = txt
                                    break

                    if final_link in seen_links: continue
                    seen_links.add(final_link)
                    all_results.append({
                        'title': title, 'link': final_link, 
                        'press': press_name, 'time': date_text, 'is_naver': is_naver
                    })
                time.sleep(0.3)
            except: break
        return all_results

# --- [Streamlit 웹 UI] ---
st.set_page_config(page_title="서울교통공사 스크랩", layout="wide")

# 모바일 1줄 레이아웃 및 버튼 스타일 CSS
st.markdown("""
    <style>
    .stButton>button { border-radius: 5px; height: 32px; padding: 0px 10px; font-size: 13px !important; }
    .news-card { background: white; padding: 12px; border-radius: 8px; border-left: 5px solid #007bff; margin-bottom: 5px; }
    /* 버튼 1줄 정렬을 위한 가로 배열 */
    .button-row { display: flex; gap: 8px; margin-top: 8px; }
    .link-btn { 
        display: inline-flex; align-items: center; justify-content: center;
        text-decoration: none; background: #f0f2f6; color: #31333F;
        border-radius: 5px; height: 32px; padding: 0px 10px; font-size: 13px; font-weight: 500; border: 1px solid #d1d5db;
    }
    </style>
    """, unsafe_allow_html=True)

if 'scrap_list' not in st.session_state: st.session_state.scrap_list = []
if 'search_results' not in st.session_state: st.session_state.search_results = []

st.title("🚇 뉴스 스크랩 (Mobile)")

# 1. 스크랩 목록 (최상단)
st.subheader("📋 스크랩 목록")
if st.session_state.scrap_list:
    final_text = "".join(st.session_state.scrap_list)
    st.text_area("복사하기", value=final_text, height=150)
    if st.button("🗑️ 비우기"):
        st.session_state.scrap_list = []
        st.rerun()
else:
    st.caption("기사를 추가하면 여기에 나타납니다.")

st.divider()

# 2. 검색 설정
with st.expander("🔍 검색 조건", expanded=True):
    keyword = st.text_input("키워드", value="서울교통공사")
    col1, col2 = st.columns(2)
    with col1: start_date = st.date_input("시작", datetime.date.today() - datetime.timedelta(days=1))
    with col2: end_date = st.date_input("종료", datetime.date.today())
    
    # [추가] 필터 선택 (기본값: 네이버 기사)
    filter_choice = st.radio("검색 범위", ["네이버 기사", "언론사 자체기사", "모두 보기"], index=0, horizontal=True)

if st.button("🚀 뉴스 검색 실행", type="primary"):
    scraper = NewsScraper()
    with st.spinner('검색 중...'):
        results = scraper.fetch_news(start_date, end_date, keyword, 0)
        st.session_state.search_results = results

# 3. 검색 결과 (필터 적용)
if st.session_state.search_results:
    # 필터링 로직
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
            
            # 버튼 1줄 레이아웃 (columns 사용)
            btn_col1, btn_col2 = st.columns([1, 1])
            with btn_col1:
                # 원문링크 버튼을 작게 만들기 위해 HTML 버튼 사용
                st.markdown(f'<a href="{res["link"]}" target="_blank" class="link-btn">🔗 원문보기</a>', unsafe_allow_html=True)
            with btn_col2:
                if st.button("➕ 추가", key=f"add_{i}"):
                    item = f"ㅇ {res['title']}_{res['press']}\n{res['link']}\n\n"
                    if item not in st.session_state.scrap_list:
                        st.session_state.scrap_list.append(item)
                        st.toast("추가됨!")
                        st.rerun()
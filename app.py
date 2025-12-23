import streamlit as st
import cloudscraper
from bs4 import BeautifulSoup
import datetime
import time
import streamlit.components.v1 as components

# --- [1. 스마트 날짜 계산 함수] ---
def get_target_date():
    today = datetime.date.today()
    if today.weekday() == 4: target = today + datetime.timedelta(days=3)
    elif today.weekday() == 5: target = today + datetime.timedelta(days=2)
    else: target = today + datetime.timedelta(days=1)

    holidays = [
        datetime.date(2025,1,1), datetime.date(2025,1,28), datetime.date(2025,1,29), datetime.date(2025,1,30),
        datetime.date(2025,3,1), datetime.date(2025,3,3), datetime.date(2025,5,5), datetime.date(2025,5,6),
        datetime.date(2025,6,6), datetime.date(2025,8,15), datetime.date(2025,10,3), datetime.date(2025,10,5),
        datetime.date(2025,10,6), datetime.date(2025,10,7), datetime.date(2025,10,8), datetime.date(2025,10,9), datetime.date(2025,12,25),
    ]
    while target in holidays or target.weekday() >= 5:
        target += datetime.timedelta(days=1)
    return target

# --- [2. 뉴스 스크래퍼] ---
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
        all_results, seen_links = [], set()
        query = f'"{keyword}"'
        max_pages = (max_articles // 10) + 1
        
        for page in range(max_pages):
            if len(all_results) >= max_articles: break
            start_val = (page * 10) + 1
            url = f"https://search.naver.com/search.naver?where=news&query={query}&sm=tab_pge&sort=1&photo=0&pd=3&ds={ds}&de={de}&nso={nso}&start={start_val}"
            try:
                res = self.scraper.get(url, headers=self.headers, timeout=10)
                soup = BeautifulSoup(res.content, 'html.parser')
                items = soup.select('a[data-heatmap-target=".tit"]')
                for t_tag in items:
                    if len(all_results) >= max_articles: break
                    title = t_tag.get('title') if t_tag.get('title') else t_tag.get_text(strip=True)
                    link = t_tag.get('href')
                    if link in seen_links: continue
                    seen_links.add(link)
                    
                    press_name = "알 수 없음"
                    card = t_tag
                    for _ in range(5):
                        if card.parent:
                            card = card.parent
                            p_el = card.select_one(".sds-comps-profile-info-title-text, .press_name, .info.press")
                            if p_el: 
                                press_name = p_el.get_text(strip=True)
                                break
                    all_results.append({'title': title, 'link': link, 'press': press_name})
                time.sleep(0.1)
            except: break
        return all_results

# --- [3. UI 설정 및 밀착 레이아웃 CSS] ---
st.set_page_config(page_title="또타 스크립터", layout="wide")

st.markdown("""
    <style>
    /* 수평 간격 제거 및 가로 배치 강제 */
    [data-testid="stHorizontalBlock"] { gap: 0rem !important; }
    div[data-testid="column"] {
        padding: 0px 1px !important;
        flex-direction: row !important;
        align-items: center !important;
        min-width: 0px !important;
    }

    /* 버튼 스타일 (기본 및 색상) */
    .stButton > button, .stLinkButton > a {
        width: 100% !important; height: 38px !important;
        font-size: 9px !important; font-weight: 800 !important;
        padding: 2px !important; border-radius: 4px !important;
    }
    div[data-testid="column"]:nth-of-type(3) button { background-color: #D1E9FF !important; color: #004085 !important; border: 1px solid #B8DAFF !important; }
    div[data-testid="column"]:nth-of-type(4) button { background-color: #E2F0D9 !important; color: #385723 !important; border: 1px solid #C5E0B4 !important; }

    /* 뉴스 카드 및 배경색 */
    .news-card { padding: 10px; border-radius: 8px; border-left: 5px solid #007bff; box-shadow: 0 1px 2px rgba(0,0,0,0.1); width: 100%; }
    .bg-white { background: white !important; }
    .bg-scraped { background: #F0F2F6 !important; border-left: 5px solid #999 !important; opacity: 0.8; }
    .news-title { font-size: 15px !important; font-weight: 700; color: #111; line-height: 1.3; }
    .news-meta { font-size: 13px !important; color: #666; margin-top: 2px; }

    /* 개별 삭제 버튼 전용 스타일 */
    .del-btn button { background-color: #ffebee !important; color: #c62828 !important; border: none !important; height: 25px !important; }
    </style>
    """, unsafe_allow_html=True)

# 세션 관리
for key in ['corp_list', 'rel_list', 'search_results']:
    if key not in st.session_state: st.session_state[key] = []

st.title("🚇 또타 스크립터")

# 1. 스크랩 결과 영역
t_date = get_target_date()
date_header = f"<{t_date.month}월 {t_date.day}일 조간 스크랩>"
final_output = f"{date_header}\n\n[공사 관련 보도]\n" + "".join(st.session_state.corp_list) + "\n[유관기관 관련 보도]\n" + "".join(st.session_state.rel_list)

# 결과창 자동 높이 계산
dynamic_height = max(180, (final_output.count('\n') + 1) * 25)
st.text_area("📋 스크랩 결과 (전체 텍스트)", value=final_output, height=dynamic_height)

# 복사 및 전체 초기화 버튼
c_a, c_b = st.columns(2)
with c_a:
    if st.button("📋 복사", use_container_width=True):
        st.toast("복사 완료!")
        components.html(f"<script>navigator.clipboard.writeText(`{final_output}`);</script>", height=0)
with c_b:
    if st.button("🗑️ 전체 초기화", use_container_width=True):
        st.session_state.corp_list, st.session_state.rel_list = [], []
        st.rerun()

# [추가 기능] 스크랩 항목 개별 관리 (삭제)
with st.expander("🛠️ 스크랩 항목 개별 관리", expanded=False):
    st.write("**🏢 공사 보도 목록**")
    for idx, item in enumerate(st.session_state.corp_list):
        col_txt, col_del = st.columns([0.85, 0.15])
        col_txt.caption(item.split('\n')[0]) # 제목만 표시
        if col_del.button("삭제", key=f"del_c_{idx}"):
            st.session_state.corp_list.pop(idx)
            st.rerun()
    
    st.write("**🚆 유관기관 보도 목록**")
    for idx, item in enumerate(st.session_state.rel_list):
        col_txt, col_del = st.columns([0.85, 0.15])
        col_txt.caption(item.split('\n')[0])
        if col_del.button("삭제", key=f"del_r_{idx}"):
            st.session_state.rel_list.pop(idx)
            st.rerun()

st.divider()

# 2. 검색 및 날짜 설정
with st.expander("🔍 뉴스 검색 설정", expanded=True):
    keyword = st.text_input("검색어", value="서울교통공사")
    col_d1, col_d2 = st.columns(2)
    with col_d1: start_d = st.date_input("시작일", datetime.date.today() - datetime.timedelta(days=1))
    with col_d2: end_d = st.date_input("종료일", datetime.date.today())
    max_a = st.slider("최대 기사 수", 10, 100, 30)
    if st.button("🚀 뉴스 검색 시작", type="primary", use_container_width=True):
        st.session_state.search_results = NewsScraper().fetch_news(start_d, end_d, keyword, max_a)
        st.rerun()

# 3. 뉴스 리스트 (밀착 레이아웃 + 상태 시각화)
if st.session_state.search_results:
    for i, res in enumerate(st.session_state.search_results):
        item_check = f"ㅇ {res['title']}_{res['press']}\n{res['link']}\n\n"
        is_scraped = (item_check in st.session_state.corp_list) or (item_check in st.session_state.rel_list)
        bg_class = "bg-scraped" if is_scraped else "bg-white"

        with st.container():
            col1, col2, col3, col4 = st.columns([0.73, 0.09, 0.09, 0.09])
            with col1:
                st.markdown(f'''
                <div class="news-card {bg_class}">
                    <div class="news-title">{res["title"]}</div>
                    <div class="news-meta">[{res["press"]}] {"(스크랩됨)" if is_scraped else ""}</div>
                </div>
                ''', unsafe_allow_html=True)
            with col2:
                st.link_button("원문", res['link'])
            with col3:
                if st.button("공사+", key=f"c_{i}"):
                    if item_check not in st.session_state.corp_list:
                        st.session_state.corp_list.append(item_check)
                        st.toast("🏢 공사 추가 완료!"); time.sleep(0.3); st.rerun()
                    else: st.toast("⚠️ 이미 추가됨")
            with col4:
                if st.button("유관+", key=f"r_{i}"):
                    if item_check not in st.session_state.rel_list:
                        st.session_state.rel_list.append(item_check)
                        st.toast("🚆 유관 추가 완료!"); time.sleep(0.3); st.rerun()
                    else: st.toast("⚠️ 이미 추가됨")
        st.write("")
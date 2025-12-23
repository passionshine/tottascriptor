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

# --- [3. UI 및 모바일 밀착 레이아웃 CSS] ---
st.set_page_config(page_title="또타 스크립터", layout="wide")

st.markdown("""
    <style>
    /* 컬럼 간격 완전 제거 및 가로 배치 강제 */
    [data-testid="stHorizontalBlock"] { gap: 0px !important; }
    [data-testid="column"] { 
        flex-direction: row !important; 
        align-items: center !important; 
        padding: 0 1px !important; 
    }

    /* 버튼 스타일: 폭 좁게 최적화 */
    .stButton > button, .stLinkButton > a {
        width: 100% !important; height: 38px !important;
        font-size: 11px !important; font-weight: 800 !important;
        padding: 0px !important; border-radius: 4px !important;
    }

    /* 버튼 색상 */
    div[data-testid="column"]:nth-of-type(3) button { background-color: #D1E9FF !important; color: #004085 !important; }
    div[data-testid="column"]:nth-of-type(4) button { background-color: #E2F0D9 !important; color: #385723 !important; }

    /* 뉴스 카드: 너비 대폭 확장 */
    .news-card {
        background: white; padding: 10px; border-radius: 8px;
        border-left: 5px solid #007bff; box-shadow: 0 1px 2px rgba(0,0,0,0.1);
        width: 100%; margin-right: 5px;
    }
    .news-title { 
        font-size: 13px !important; font-weight: 700; color: #111; line-height: 1.3;
        display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
    }
    .news-meta { font-size: 9px !important; color: #666; margin-top: 2px; }
    </style>
    """, unsafe_allow_html=True)

for key in ['corp_list', 'rel_list', 'search_results']:
    if key not in st.session_state: st.session_state[key] = []

st.title("🚇 또타 스크립터")

# 스크랩 결과 영역
t_date = get_target_date()
date_header = f"<{t_date.month}월 {t_date.day}일 조간 스크랩>"
final_output = f"{date_header}\n\n[공사 관련 보도]\n" + "".join(st.session_state.corp_list) + "\n[유관기관 관련 보도]\n" + "".join(st.session_state.rel_list)
st.text_area("결과", value=final_output, height=150)

c_a, c_b = st.columns(2)
with c_a:
    if st.button("📋 복사", use_container_width=True):
        st.toast("복사 완료!")
        components.html(f"<script>navigator.clipboard.writeText(`{final_output}`);</script>", height=0)
with c_b:
    if st.button("🗑️ 초기화", use_container_width=True):
        st.session_state.corp_list, st.session_state.rel_list = [], []
        st.rerun()

st.divider()

# 검색 설정
with st.expander("🔍 검색 설정", expanded=True):
    keyword = st.text_input("검색어", value="서울교통공사")
    max_a = st.slider("기사 수", 10, 100, 30)
    if st.button("🚀 검색 시작", type="primary", use_container_width=True):
        st.session_state.search_results = NewsScraper().fetch_news(datetime.date.today()-datetime.timedelta(days=1), datetime.date.today(), keyword, max_a)
        st.rerun()

# 3. 뉴스 리스트 출력 (토스트 로직 개선)
if st.session_state.search_results:
    for i, res in enumerate(st.session_state.search_results):
        with st.container():
            # 비율 조정: 카드 76%, 버튼들 각 8%씩 밀착
            col1, col2, col3, col4 = st.columns([0.76, 0.08, 0.08, 0.08])
            with col1:
                st.markdown(f'<div class="news-card"><div class="news-title">{res["title"]}</div><div class="news-meta">[{res["press"]}]</div></div>', unsafe_allow_html=True)
            with col2:
                st.link_button("원문", res['link'])
            with col3:
                if st.button("공사+", key=f"c_{i}"):
                    item = f"ㅇ {res['title']}_{res['press']}\n{res['link']}\n\n"
                    if item not in st.session_state.corp_list:
                        st.session_state.corp_list.append(item)
                        st.toast("🏢 공사 추가 완료!")
                        time.sleep(0.4)
                        st.rerun()
                    else:
                        st.toast("⚠️ 이미 추가된 기사입니다.")
            with col4:
                if st.button("유관+", key=f"r_{i}"):
                    item = f"ㅇ {res['title']}_{res['press']}\n{res['link']}\n\n"
                    if item not in st.session_state.rel_list:
                        st.session_state.rel_list.append(item)
                        st.toast("🚆 유관 추가 완료!")
                        time.sleep(0.4)
                        st.rerun()
                    else:
                        st.toast("⚠️ 이미 추가된 기사입니다.")
        st.write("")
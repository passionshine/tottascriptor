import streamlit as st
import cloudscraper
from bs4 import BeautifulSoup
import datetime
import time

# --- [뉴스 스크래퍼 클래스] ---
class NewsScraper:
    def __init__(self):
        self.scraper = cloudscraper.create_scraper()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.naver.com/'
        }

    def fetch_news(self, start_datetime, end_datetime, keyword):
        ds, de = start_datetime.strftime("%Y.%m.%d"), end_datetime.strftime("%Y.%m.%d")
        nso = f"so:dd,p:from{start_datetime.strftime('%Y%m%d')}to{end_datetime.strftime('%Y%m%d')}"
        all_results, seen_links = [], set()
        
        query = f'"{keyword}"'
        for page in range(1, 4):
            start_index = (page - 1) * 10 + 1
            url = f"https://search.naver.com/search.naver?where=news&query={query}&sm=tab_pge&sort=1&photo=0&pd=3&ds={ds}&de={de}&nso={nso}&start={start_index}"
            try:
                response = self.scraper.get(url, headers=self.headers, timeout=10)
                soup = BeautifulSoup(response.content, 'html.parser')
                items = soup.select('a[data-heatmap-target=".tit"]')
                if not items: break

                for t_tag in items:
                    title, link = t_tag.get_text(strip=True), t_tag.get('href')
                    if link in seen_links: continue
                    
                    card = t_tag.find_parent('div', class_=lambda c: c and ('api_subject_bx' in c or 'sds-comps' in c))
                    press_name, date_text, is_naver = "알 수 없음", "정보 없음", "n.news.naver.com" in link
                    
                    if card:
                        naver_btn = card.select_one('a[href*="n.news.naver.com"]')
                        if naver_btn: link, is_naver = naver_btn.get('href'), True
                        press_el = card.select_one(".sds-comps-profile-info-title-text, .press_name, .info.press")
                        if press_el: press_name = press_el.get_text(strip=True)
                        subtext_area = card.select_one(".sds-comps-profile-info-subtexts, .news_info")
                        if subtext_area:
                            for txt in subtext_area.stripped_strings:
                                if ('전' in txt and len(txt) < 15) or ('.' in txt and len(txt) < 15 and txt[0].isdigit()):
                                    date_text = txt; break

                    seen_links.add(link)
                    all_results.append({'title': title, 'link': link, 'press': press_name, 'time': date_text, 'is_naver': is_naver})
                time.sleep(0.3)
            except: break
        return all_results

# --- [Streamlit UI 설정] ---
st.set_page_config(page_title="서울교통공사 스크랩", layout="wide")

# CSS: 카드 디자인 및 버튼 정렬
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .news-card {
        background: white; padding: 15px; border-radius: 12px;
        border-left: 6px solid #007bff; margin-bottom: 10px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    .news-title { font-size: 15px; font-weight: 700; color: #1a1a1a; margin-bottom: 5px; }
    .news-meta { font-size: 12px; color: #666; margin-bottom: 10px; }
    
    /* 버튼 스타일 */
    .stButton > button, .stLinkButton > a {
        width: 100% !important; height: 36px !important;
        font-size: 12px !important; font-weight: 600 !important;
        border-radius: 6px !important; display: inline-flex !important;
        align-items: center !important; justify-content: center !important;
        text-decoration: none !important;
    }
    </style>
    """, unsafe_allow_html=True)

# 날짜 계산 (헤더용)
today = datetime.date.today()
weekdays = ["월", "화", "수", "목", "금", "토", "일"]
date_header = f"<{today.month}월 {today.day}일({weekdays[today.weekday()]}) 조간 스크랩>"

# 세션 상태 초기화
if 'corp_list' not in st.session_state: st.session_state.corp_list = []
if 'rel_list' not in st.session_state: st.session_state.rel_list = []
if 'search_results' not in st.session_state: st.session_state.search_results = []

st.title("🚇 조간 뉴스 스크랩")

# --- [1] 상단: 스크랩 목록 영역 (분류 적용) ---
st.subheader("📋 스크랩 결과")
# 최종 텍스트 조립
final_output = f"{date_header}\n\n[공사 관련 보도]\n"
final_output += "".join(st.session_state.corp_list) if st.session_state.corp_list else "(기사를 추가해주세요)\n"
final_output += "\n[철도 등 기타 유관기관 관련 보도]\n"
final_output += "".join(st.session_state.rel_list) if st.session_state.rel_list else "(기사를 추가해주세요)\n"

# 가변 높이 설정
dynamic_h = min(max(200, (len(st.session_state.corp_list) + len(st.session_state.rel_list)) * 50 + 150), 500)
st.text_area("카톡/메일 복사용", value=final_output, height=dynamic_h)

if st.button("🗑️ 목록 비우기"):
    st.session_state.corp_list = []
    st.session_state.rel_list = []
    st.rerun()

st.divider()

# --- [2] 검색 설정 ---
with st.expander("🔍 검색 필터", expanded=True):
    keyword = st.text_input("키워드", value="서울교통공사")
    c1, c2 = st.columns(2)
    with c1: start_d = st.date_input("시작", today - datetime.timedelta(days=1))
    with c2: end_d = st.date_input("종료", today)
    filter_opt = st.radio("범위", ["네이버 기사", "언론사 자체기사", "모두 보기"], index=0, horizontal=True)

if st.button("🚀 검색 시작", type="primary"):
    sc = NewsScraper()
    with st.spinner('뉴스를 찾는 중...'):
        st.session_state.search_results = sc.fetch_news(start_d, end_d, keyword)

# --- [3] 검색 결과 (3버튼 분리형) ---
if st.session_state.search_results:
    res_list = st.session_state.search_results
    if filter_opt == "네이버 기사": res_list = [r for r in res_list if r['is_naver']]
    elif filter_opt == "언론사 자체기사": res_list = [r for r in res_list if not r['is_naver']]

    st.subheader(f"✅ 검색 결과: {len(res_list)}건")
    
    for i, res in enumerate(res_list):
        with st.container():
            # 카드 디자인
            st.markdown(f"""
            <div class="news-card">
                <div class="news-title">{res['title']}</div>
                <div class="news-meta">[{res['press']}] {res['time']} {'(네이버)' if res['is_naver'] else ''}</div>
            </div>
            """, unsafe_allow_html=True)
            
            # 3개 버튼 가로 배치
            b1, b2, b3 = st.columns(3)
            with b1:
                st.link_button("🔗 원문", res['link'])
            with b2:
                if st.button("🏢 공사 추가", key=f"corp_add_{i}"):
                    item = f"ㅇ {res['title']}_{res['press']}\n{res['link']}\n"
                    if item not in st.session_state.corp_list:
                        st.session_state.corp_list.append(item)
                        st.toast("공사 섹션에 추가됨!")
                        st.rerun()
            with b3:
                if st.button("🚆 유관 추가", key=f"rel_add_{i}"):
                    item = f"ㅇ {res['title']}_{res['press']}\n{res['link']}\n"
                    if item not in st.session_state.rel_list:
                        st.session_state.rel_list.append(item)
                        st.toast("유관기관 섹션에 추가됨!")
                        st.rerun()
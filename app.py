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
        self.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36...', 'Referer': 'https://www.naver.com/'}

    def fetch_news(self, start_d, end_d, keyword):
        ds, de = start_d.strftime("%Y.%m.%d"), end_d.strftime("%Y.%m.%d")
        nso = f"so:dd,p:from{start_d.strftime('%Y%m%d')}to{end_d.strftime('%Y%m%d')}"
        all_results, seen_links = [], set()
        query = f'"{keyword}"'
        url = f"https://search.naver.com/search.naver?where=news&query={query}&sm=tab_pge&sort=1&photo=0&pd=3&ds={ds}&de={de}&nso={nso}"
        try:
            res = self.scraper.get(url, headers=self.headers, timeout=10)
            soup = BeautifulSoup(res.content, 'html.parser')
            items = soup.select('a[data-heatmap-target=".tit"]')
            for t_tag in items:
                title, link = t_tag.get_text(strip=True), t_tag.get('href')
                if link in seen_links: continue
                card = t_tag.find_parent('div', class_=lambda c: c and ('api_subject_bx' in c or 'sds-comps' in c))
                press_name, date_text, is_naver = "알 수 없음", "정보 없음", "n.news.naver.com" in link
                if card:
                    naver_btn = card.select_one('a[href*="n.news.naver.com"]')
                    if naver_btn: link, is_naver = naver_btn.get('href'), True
                    p_el = card.select_one(".sds-comps-profile-info-title-text, .press_name, .info.press")
                    if p_el: press_name = p_el.get_text(strip=True)
                    t_el = card.select_one(".sds-comps-profile-info-subtexts, .news_info")
                    if t_el:
                        for txt in t_el.stripped_strings:
                            if ('전' in txt and len(txt) < 15) or ('.' in txt and len(txt) < 15 and txt[0].isdigit()):
                                date_text = txt; break
                seen_links.add(link)
                all_results.append({'title': title, 'link': link, 'press': press_name, 'time': date_text, 'is_naver': is_naver})
        except: pass
        return all_results

# --- [3. UI 설정] ---
st.set_page_config(page_title="서울교통공사 스크랩", layout="wide")

st.markdown("""
    <style>
    /* 폰트 사이즈 대폭 확대 */
    .news-title { 
        font-size: 20px !important; 
        font-weight: 800; 
        color: #1a1a1a; 
        line-height: 1.5;
        vertical-align: middle;
    }
    .news-meta { 
        font-size: 16px !important; 
        color: #555; 
        margin-top: 5px;
        margin-bottom: 15px;
        font-weight: 500;
    }
    
    /* 인라인 버튼 스타일 (밑줄 제거) */
    .inline-btn-group {
        display: inline-flex;
        gap: 5px;
        margin-left: 10px;
        vertical-align: middle;
    }
    
    /* 개별 버튼 스타일 */
    .stButton > button, .stLinkButton > a {
        border: 1px solid #d1d5db !important;
        background-color: #ffffff !important;
        color: #31333F !important;
        text-decoration: none !important; /* 밑줄 제거 */
        box-shadow: none !important;
        height: 30px !important;
        padding: 0 8px !important;
        font-size: 12px !important;
        border-radius: 4px !important;
    }
    
    .news-card {
        background: white; 
        padding: 15px; 
        border-radius: 12px;
        border-left: 8px solid #007bff; 
        margin-bottom: 20px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    }
    </style>
    """, unsafe_allow_html=True)

if 'corp_list' not in st.session_state: st.session_state.corp_list = []
if 'rel_list' not in st.session_state: st.session_state.rel_list = []
if 'search_results' not in st.session_state: st.session_state.search_results = []

target_date = get_target_date()
date_header = f"<{target_date.month}월 {target_date.day}일({['월','화','수','목','금','토','일'][target_date.weekday()]}) 조간 스크랩>"

st.title("🚇 조간 뉴스 스크랩")

# 상단 결과 영역
final_output = f"{date_header}\n\n[공사 관련 보도]\n"
final_output += "".join(st.session_state.corp_list) if st.session_state.corp_list else "(내용 없음)\n"
final_output += "\n[철도 등 기타 유관기관 관련 보도]\n"
final_output += "".join(st.session_state.rel_list) if st.session_state.rel_list else "(내용 없음)\n"

st.text_area("📋 스크랩 양식", value=final_output, height=250)
if st.button("📋 클립보드로 전체 복사"):
    st.toast("📋 복사되었습니다!")
    components.html(f"<script>navigator.clipboard.writeText(`{final_output}`);</script>", height=0)

st.divider()

# 검색 설정
with st.expander("🔍 검색 필터", expanded=True):
    keyword = st.text_input("키워드", value="서울교통공사")
    c1, c2 = st.columns(2)
    with c1: start_d = st.date_input("시작", datetime.date.today()-datetime.timedelta(days=1))
    with c2: end_d = st.date_input("종료", datetime.date.today())
    filter_choice = st.radio("검색 범위", ["네이버 기사", "언론사 자체기사", "모두 보기"], index=0, horizontal=True)

if st.button("🚀 뉴스 검색 시작", type="primary"):
    with st.spinner('검색 중...'):
        st.session_state.search_results = NewsScraper().fetch_news(start_d, end_d, keyword)

# 결과 리스트 출력
if st.session_state.search_results:
    res_list = st.session_state.search_results
    if filter_choice == "네이버 기사": res_list = [r for r in res_list if r['is_naver']]
    elif filter_choice == "언론사 자체기사": res_list = [r for r in res_list if not r['is_naver']]

    st.subheader(f"✅ 결과: {len(res_list)}건")
    for i, res in enumerate(res_list):
        with st.container():
            # [제목 구역] 제목과 버튼들을 한 줄(flex)로 배치하기 위해 컬럼 활용
            st.markdown(f'<div class="news-card">', unsafe_allow_html=True)
            
            # 제목 출력
            st.markdown(f'<span class="news-title">{res["title"]}</span>', unsafe_allow_html=True)
            
            # 버튼 3개를 제목 옆에 인라인으로 배치 (st.columns 활용)
            b1, b2, b3 = st.columns([1, 1, 1])
            with b1:
                st.link_button("🔗 원문", res['link'])
            with b2:
                if st.button("🏢 공사 추가", key=f"c_{i}"):
                    item = f"ㅇ {res['title']}_{res['press']}\n{res['link']}\n\n"
                    if item not in st.session_state.corp_list:
                        st.session_state.corp_list.append(item); st.toast("✅ 추가됨!"); st.rerun()
            with b3:
                if st.button("🚆 기타 추가", key=f"r_{i}"):
                    item = f"ㅇ {res['title']}_{res['press']}\n{res['link']}\n\n"
                    if item not in st.session_state.rel_list:
                        st.session_state.rel_list.append(item); st.toast("✅ 추가됨!"); st.rerun()
            
            # 메타데이터 출력
            st.markdown(f'<div class="news-meta">[{res["press"]}] {res["time"]}</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
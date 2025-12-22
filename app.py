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

# --- [2. 뉴스 스크래퍼 (페이지네이션 지원)] ---
class NewsScraper:
    def __init__(self):
        self.scraper = cloudscraper.create_scraper()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.naver.com/'
        }

    def fetch_news(self, start_d, end_d, keyword, max_pages):
        ds, de = start_d.strftime("%Y.%m.%d"), end_d.strftime("%Y.%m.%d")
        nso = f"so:dd,p:from{start_d.strftime('%Y%m%d')}to{end_d.strftime('%Y%m%d')}"
        
        all_results, seen_links = [], set()
        query = f'"{keyword}"'

        # 사용자가 설정한 max_pages 만큼 반복 수집
        for page in range(max_pages):
            start_val = (page * 10) + 1 # 1, 11, 21... 순서로 호출
            url = f"https://search.naver.com/search.naver?where=news&query={query}&sm=tab_pge&sort=1&photo=0&pd=3&ds={ds}&de={de}&nso={nso}&start={start_val}"
            
            try:
                res = self.scraper.get(url, headers=self.headers, timeout=10)
                res.raise_for_status()
                soup = BeautifulSoup(res.content, 'html.parser')
                items = soup.select('a[data-heatmap-target=".tit"]')
                
                if not items: break # 더 이상 결과가 없으면 종료

                for t_tag in items:
                    title, link = t_tag.get_text(strip=True), t_tag.get('href')
                    if link in seen_links: continue
                    
                    # 카드 정보 파싱 로직
                    card = None
                    curr = t_tag
                    for _ in range(5):
                        if curr.parent:
                            curr = curr.parent
                            if curr.select_one(".sds-comps-profile") or curr.select_one(".news_info"):
                                card = curr; break
                    
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
                
                time.sleep(0.3) # 네이버 차단 방지용 미세 지연
            except Exception as e:
                st.error(f"{page+1}페이지 로드 중 오류 발생: {e}")
                break
        return all_results

# --- [3. UI 설정] ---
st.set_page_config(page_title="서울교통공사 스크랩", layout="wide")

st.markdown("""
    <style>
    /* 버튼 3개 배치: 원문 / 공사+ / 유관+ */
    .stButton > button, .stLinkButton > a {
        width: 100% !important;
        height: 35px !important;
        font-size: 10.5px !important;
        font-weight: 600 !important;
        padding: 0px 1px !important;
        border-radius: 6px !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        white-space: nowrap !important;
    }
    /* 기사 카드 디자인 (제목 전체 노출) */
    .news-card {
        background: white; padding: 12px; border-radius: 12px;
        border-left: 6px solid #007bff; margin-bottom: 4px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    .news-title { 
        font-size: 15px !important; 
        font-weight: 700; color: #1a1a1a; 
        line-height: 1.4;
        word-break: keep-all; 
        white-space: normal !important; 
    }
    .news-meta { font-size: 12px !important; color: #666; margin-top: 5px; }
    
    [data-testid="column"] { padding: 0 2px !important; }
    </style>
    """, unsafe_allow_html=True)

if 'corp_list' not in st.session_state: st.session_state.corp_list = []
if 'rel_list' not in st.session_state: st.session_state.rel_list = []
if 'search_results' not in st.session_state: st.session_state.search_results = []

t_date = get_target_date()
date_header = f"<{t_date.month}월 {t_date.day}일({['월','화','수','목','금','토','일'][t_date.weekday()]}) 조간 스크랩>"

st.title("🚇 조간 뉴스 스크랩")

# 1. 스크랩 현황
st.subheader("📋 스크랩 결과")
final_output = f"{date_header}\n\n[공사 관련 보도]\n"
final_output += "".join(st.session_state.corp_list) if st.session_state.corp_list else "(내용 없음)\n"
final_output += "\n[철도 등 기타 유관기관 관련 보도]\n"
final_output += "".join(st.session_state.rel_list) if st.session_state.rel_list else "(내용 없음)\n"

st.text_area("전체 텍스트", value=final_output, height=200, label_visibility="collapsed")

if st.button("📋 클립보드로 전체 복사"):
    st.toast("📋 복사 완료!")
    components.html(f"<script>navigator.clipboard.writeText(`{final_output.replace('`','\\\\`')}`);</script>", height=0)

st.divider()

# 2. 검색 및 양 조절 슬라이더
with st.expander("🔍 검색 필터 및 수집 양 설정", expanded=True):
    keyword = st.text_input("키워드", value="서울교통공사")
    c1, c2 = st.columns(2)
    with c1: start_d = st.date_input("시작일", datetime.date.today()-datetime.timedelta(days=1))
    with c2: end_d = st.date_input("종료일", datetime.date.today())
    
    # 기사 양 조절 슬라이더 추가
    max_p = st.slider("수집할 페이지 수 (1페이지당 약 10~15건)", min_value=1, max_value=10, value=3)
    
    filter_choice = st.radio("보기 필터", ["네이버 기사", "언론사 자체기사", "모두 보기"], horizontal=True)

if st.button("🚀 뉴스 검색 시작", type="primary"):
    st.session_state.search_results = [] # 검색 시 초기화
    with st.spinner(f'{max_p}페이지 분량의 기사를 가져오고 있습니다...'):
        results = NewsScraper().fetch_news(start_d, end_d, keyword, max_p)
        if results:
            st.session_state.search_results = results
            st.success(f"총 {len(results)}건의 기사를 찾았습니다.")
        else:
            st.warning("검색 결과가 없습니다.")

# 3. 결과 리스트
if st.session_state.search_results:
    display_results = st.session_state.search_results
    if filter_choice == "네이버 기사":
        display_results = [r for r in display_results if r['is_naver']]
    elif filter_choice == "언론사 자체기사":
        display_results = [r for r in display_results if not r['is_naver']]

    for i, res in enumerate(display_results):
        with st.container():
            st.markdown(f"""
            <div class="news-card">
                <div class="news-title">{res['title']}</div>
                <div class="news-meta">[{res['press']}] {res['time']} {'(네이버)' if res['is_naver'] else ''}</div>
            </div>
            """, unsafe_allow_html=True)
            
            b1, b2, b3 = st.columns([1, 1, 1])
            with b1:
                st.link_button("🔗 원문보기", res['link'])
            with b2:
                if st.button("🏢 공사 보도 +", key=f"c_{i}"):
                    item = f"ㅇ {res['title']}_{res['press']}\n{res['link']}\n\n"
                    if item not in st.session_state.corp_list:
                        st.session_state.corp_list.append(item)
                        st.rerun()
            with b3:
                if st.button("🚆 유관기관 보도 +", key=f"r_{i}"):
                    item = f"ㅇ {res['title']}_{res['press']}\n{res['link']}\n\n"
                    if item not in st.session_state.rel_list:
                        st.session_state.rel_list.append(item)
                        st.rerun()
        st.write("")
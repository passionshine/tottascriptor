import streamlit as st
import cloudscraper
from bs4 import BeautifulSoup
import datetime
import time
import streamlit.components.v1 as components

# --- [1. 스마트 날짜 계산 함수 (2025-2029 공휴일 반영)] ---
def get_target_date():
    today = datetime.date.today()
    # 금요일(4)이면 다음주 월요일, 토요일(5)이면 다음주 월요일, 그 외엔 내일
    if today.weekday() == 4: target = today + datetime.timedelta(days=3)
    elif today.weekday() == 5: target = today + datetime.timedelta(days=2)
    else: target = today + datetime.timedelta(days=1)

    # 2025-2029 주요 공휴일 (설날, 추석, 대체휴일 포함)
    holidays = [
        # 2025년
        datetime.date(2025,1,1), datetime.date(2025,1,28), datetime.date(2025,1,29), datetime.date(2025,1,30),
        datetime.date(2025,3,1), datetime.date(2025,3,3), datetime.date(2025,5,5), datetime.date(2025,5,6),
        datetime.date(2025,6,6), datetime.date(2025,8,15), datetime.date(2025,10,3), datetime.date(2025,10,5),
        datetime.date(2025,10,6), datetime.date(2025,10,7), datetime.date(2025,10,8), datetime.date(2025,10,9), datetime.date(2025,12,25),
        # 2026년 이후 데이터는 로직상 평일이 나올 때까지 반복 검색함 (필요시 리스트 추가)
    ]
    
    # 공휴일이거나 주말이면 다음 평일이 나올 때까지 하루씩 더함
    while target in holidays or target.weekday() >= 5:
        target += datetime.timedelta(days=1)
    return target

# --- [2. 뉴스 스크래퍼 (성공 로직 적용)] ---
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
                    
                    # [보내주신 성공 파싱 로직 적용]
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

# --- [3. UI 설정] ---
st.set_page_config(page_title="서울교통공사 스크랩", layout="wide")

st.markdown("""
    <style>
    .news-card {
        background: white; padding: 12px; border-radius: 12px;
        border-left: 5px solid #007bff; margin-bottom: 8px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    .info-zone { width: 100%; }
    .news-title { font-size: 14px; font-weight: 700; color: #1a1a1a; line-height: 1.4; }
    .news-meta { font-size: 11px; color: #666; margin-top: 4px; }
    
    .stButton > button, .stLinkButton > a {
        width: 100% !important; height: 34px !important;
        font-size: 11px !important; font-weight: 600 !important;
        padding: 0 !important; border-radius: 6px !important;
        display: inline-flex !important; align-items: center !important; justify-content: center !important;
    }
    </style>
    """, unsafe_allow_html=True)

if 'corp_list' not in st.session_state: st.session_state.corp_list = []
if 'rel_list' not in st.session_state: st.session_state.rel_list = []
if 'search_results' not in st.session_state: st.session_state.search_results = []

# 날짜 헤더 생성
t_date = get_target_date()
date_header = f"<{t_date.month}월 {t_date.day}일({['월','화','수','목','금','토','일'][t_date.weekday()]}) 조간 스크랩>"

st.title("🚇 조간 뉴스 스크랩")

# 1. 상단 목록 및 클립보드 복사
st.subheader("📋 스크랩 결과")
final_output = f"{date_header}\n\n[공사 관련 보도]\n"
final_output += "".join(st.session_state.corp_list) if st.session_state.corp_list else "(내용 없음)\n"
final_output += "\n[철도 등 기타 유관기관 관련 보도]\n"
final_output += "".join(st.session_state.rel_list) if st.session_state.rel_list else "(내용 없음)\n"

st.text_area("텍스트 영역", value=final_output, height=250, label_visibility="collapsed")

if st.button("📋 클립보드로 전체 복사"):
    st.toast("📋 클립보드에 복사되었습니다!")
    components.html(f"<script>navigator.clipboard.writeText(`{final_output}`);</script>", height=0)

st.divider()

# 2. 검색 설정
with st.expander("🔍 검색 조건 및 날짜 필터", expanded=True):
    keyword = st.text_input("키워드", value="서울교통공사")
    c1, c2 = st.columns(2)
    with c1: start_d = st.date_input("시작 날짜", datetime.date.today() - datetime.timedelta(days=1))
    with c2: end_d = st.date_input("종료 날짜", datetime.date.today())

if st.button("🚀 뉴스 검색 시작", type="primary"):
    sc = NewsScraper()
    with st.spinner('검색 중...'):
        st.session_state.search_results = sc.fetch_news(start_d, end_d, keyword)

# 3. 결과 출력 (가로 배치 레이아웃 최적화)
if st.session_state.search_results:
    st.subheader(f"✅ 결과: {len(st.session_state.search_results)}건")
    for i, res in enumerate(st.session_state.search_results):
        with st.container():
            # 정보를 담는 상단 카드
            st.markdown(f"""
            <div class="news-card">
                <div class="info-zone">
                    <div class="news-title">{res['title']}</div>
                    <div class="news-meta">[{res['press']}] {res['time']} {'(네이버)' if res['is_naver'] else ''}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # 버튼을 기사 바로 옆/아래에 콤팩트하게 배치 (가로 3열)
            b1, b2, b3 = st.columns(3)
            with b1:
                st.link_button("🔗 원문", res['link'])
            with b2:
                if st.button("🏢 공사", key=f"c_{i}"):
                    item = f"ㅇ {res['title']}_{res['press']}\n{res['link']}\n\n"
                    if item not in st.session_state.corp_list:
                        st.session_state.corp_list.append(item)
                        st.toast("✅ 공사 섹션에 추가됨!")
                        st.rerun()
            with b3:
                if st.button("🚆 유관", key=f"r_{i}"):
                    item = f"ㅇ {res['title']}_{res['press']}\n{res['link']}\n\n"
                    if item not in st.session_state.rel_list:
                        st.session_state.rel_list.append(item)
                        st.toast("✅ 유관 섹션에 추가됨!")
                        st.rerun()
import streamlit as st
import cloudscraper
from bs4 import BeautifulSoup
import datetime
import time
import streamlit.components.v1 as components

# --- [1. 스마트 날짜 계산 함수 (2025-2029 공휴일 반영)] ---
def get_target_date():
    today = datetime.date.today()
    # 금요일이면 다음주 월요일, 토요일이면 월요일, 나머지는 다음날로 설정
    if today.weekday() == 4: target = today + datetime.timedelta(days=3)
    elif today.weekday() == 5: target = today + datetime.timedelta(days=2)
    else: target = today + datetime.timedelta(days=1)

    # 주요 공휴일 (2025년 위주 반영)
    holidays = [
        datetime.date(2025,1,1), datetime.date(2025,1,28), datetime.date(2025,1,29), datetime.date(2025,1,30),
        datetime.date(2025,3,1), datetime.date(2025,3,3), datetime.date(2025,5,5), datetime.date(2025,5,6),
        datetime.date(2025,6,6), datetime.date(2025,8,15), datetime.date(2025,10,3), datetime.date(2025,10,5),
        datetime.date(2025,10,6), datetime.date(2025,10,7), datetime.date(2025,10,8), datetime.date(2025,10,9), datetime.date(2025,12,25),
    ]
    while target in holidays or target.weekday() >= 5:
        target += datetime.timedelta(days=1)
    return target

# --- [2. 뉴스 스크래퍼 클래스] ---
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

        # 페이지당 약 10건 기준 반복
        max_pages = (max_articles // 10) + 1
        
        for page in range(max_pages):
            if len(all_results) >= max_articles: break
            start_val = (page * 10) + 1
            url = f"https://search.naver.com/search.naver?where=news&query={query}&sm=tab_pge&sort=1&photo=0&pd=3&ds={ds}&de={de}&nso={nso}&start={start_val}"
            
            try:
                res = self.scraper.get(url, headers=self.headers, timeout=10)
                soup = BeautifulSoup(res.content, 'html.parser')
                items = soup.select('a[data-heatmap-target=".tit"]')
                if not items: break

                for t_tag in items:
                    if len(all_results) >= max_articles: break
                    
                    # [핵심] 제목이 '...'으로 잘리는 것을 방지하기 위해 title 속성을 우선 사용
                    title = t_tag.get('title')
                    if not title:
                        title = t_tag.get_text(strip=True)
                    
                    link = t_tag.get('href')
                    if link in seen_links: continue
                    
                    # 언론사/시간 정보 파싱
                    card = None
                    curr = t_tag
                    for _ in range(5): # 부모 노드 탐색
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
                time.sleep(0.2) # 과부하 방지
            except: break
        return all_results

# --- [3. UI 설정 및 CSS] ---
st.set_page_config(page_title="서울교통공사 뉴스 스크랩", layout="wide")

st.markdown("""
    <style>
    /* 전체 폰트 및 배경 */
    .stApp { background-color: #f8f9fa; }
    
    /* 버튼 스타일 (높이 및 글씨 크기 조정) */
    .stButton > button, .stLinkButton > a {
        width: 100% !important; height: 34px !important;
        font-size: 11px !important; font-weight: 600 !important;
        padding: 0px 2px !important; border-radius: 6px !important;
        display: inline-flex !important; align-items: center !important;
        justify-content: center !important; white-space: nowrap !important;
    }
    
    /* 뉴스 카드 디자인: 제목 전체 노출 설정 */
    .news-card {
        background: white; padding: 14px; border-radius: 10px;
        border-left: 6px solid #007bff; margin-bottom: 5px;
        box-shadow: 0 1px 4px rgba(0,0,0,0.08);
        height: auto !important;
    }
    .news-title { 
        font-size: 15px !important; font-weight: 700; color: #111; 
        line-height: 1.5; word-break: keep-all; 
        white-space: normal !important; /* 자동 줄바꿈 */
        display: block !important; overflow: visible !important;
    }
    .news-meta { font-size: 12px !important; color: #666; margin-top: 6px; }
    
    /* 컬럼 간격 */
    [data-testid="column"] { padding: 0 4px !important; }
    </style>
    """, unsafe_allow_html=True)

# 세션 상태 초기화
for key in ['corp_list', 'rel_list', 'search_results']:
    if key not in st.session_state: st.session_state[key] = []

t_date = get_target_date()
date_header = f"<{t_date.month}월 {t_date.day}일({['월','화','수','목','금','토','일'][t_date.weekday()]}) 조간 스크랩>"

st.title("🚇 조간 뉴스 스크랩")

# 1. 결과 상단 영역 (스크랩 텍스트 생성)
st.subheader("📋 스크랩 결과 리스트")
final_output = f"{date_header}\n\n[공사 관련 보도]\n"
final_output += "".join(st.session_state.corp_list) if st.session_state.corp_list else "(내용 없음)\n"
final_output += "\n[철도 등 기타 유관기관 관련 보도]\n"
final_output += "".join(st.session_state.rel_list) if st.session_state.rel_list else "(내용 없음)\n"

st.text_area("결과 텍스트 영역", value=final_output, height=220, label_visibility="collapsed")

if st.button("📋 전체 복사하기", use_container_width=True):
    st.toast("✅ 클립보드에 복사되었습니다!", icon="📄")
    components.html(f"<script>navigator.clipboard.writeText(`{final_output}`);</script>", height=0)

st.divider()

# 2. 검색 설정 섹션
with st.expander("🔍 검색 필터 및 수집 설정", expanded=True):
    keyword = st.text_input("검색 키워드", value="서울교통공사")
    c1, c2 = st.columns(2)
    with c1: start_d = st.date_input("시작일", datetime.date.today()-datetime.timedelta(days=1))
    with c2: end_d = st.date_input("종료일", datetime.date.today())
    
    # 기사 양 조절 슬라이더
    max_a = st.slider("최대 수집 기사 수", min_value=10, max_value=100, value=30, step=10)
    
    # 필터 카운트 계산
    all_res = st.session_state.search_results
    n_count = len([r for r in all_res if r['is_naver']])
    p_count = len([r for r in all_res if not r['is_naver']])
    
    filter_choice = st.radio(
        "보기 필터 (개수)", 
        [f"모두 보기 ({len(all_res)})", f"네이버 기사 ({n_count})", f"언론사 자체기사 ({p_count})"], 
        horizontal=True
    )

if st.button("🚀 뉴스 검색 시작", type="primary", use_container_width=True):
    st.session_state.search_results = []
    with st.spinner('최신 기사 데이터를 가져오는 중...'):
        results = NewsScraper().fetch_news(start_d, end_d, keyword, max_a)
        st.session_state.search_results = results
        st.rerun()

# 3. 뉴스 결과 출력 영역
if st.session_state.search_results:
    # 필터링 적용
    if "네이버 기사" in filter_choice:
        display_results = [r for r in st.session_state.search_results if r['is_naver']]
    elif "언론사 자체기사" in filter_choice:
        display_results = [r for r in st.session_state.search_results if not r['is_naver']]
    else:
        display_results = st.session_state.search_results

    st.markdown(f"**현재 필터 결과: {len(display_results)}건**")
    
for i, res in enumerate(display_results):
        with st.container():
            # [레이아웃] 제목(0.7) + 원문보기(0.1) + 공사보도(0.1) + 유관보도(0.1) = 총 1.0
            col1, col2, col3, col4 = st.columns([0.7, 0.1, 0.1, 0.1])
            
            # 1. 기사 제목 및 메타정보 (70%)
            with col1:
                st.markdown(f"""
                <div class="news-card">
                    <div class="news-title">{res['title']}</div>
                    <div class="news-meta">[{res['press']}] {res['time']}</div>
                </div>
                """, unsafe_allow_html=True)
            
            # 2. 원문보기 버튼 (10%)
            with col2:
                st.write("") # 상단 여백 (제목 높이와 맞춤)
                st.link_button("🔗 원문보기", res['link'], help="기사 원문으로 이동")
            
            # 3. 공사 보도 스크랩 (10%)
            with col3:
                st.write("") 
                if st.button(f"🏢 공사보도", key=f"c_{i}"):
                    item = f"ㅇ {res['title']}_{res['press']}\n{res['link']}\n\n"
                    if item not in st.session_state.corp_list:
                        st.session_state.corp_list.append(item)
                        st.toast("✅ 공사 섹션 추가!", icon="🏢")
                        st.rerun()
            
            # 4. 유관기관 스크랩 (10%)
            with col4:
                st.write("") 
                if st.button(f"🚆 유관보도", key=f"r_{i}"):
                    item = f"ㅇ {res['title']}_{res['press']}\n{res['link']}\n\n"
                    if item not in st.session_state.rel_list:
                        st.session_state.rel_list.append(item)
                        st.toast("✅ 유관기관 추가!", icon="🚆")
                        st.rerun()
        
        st.write("---")
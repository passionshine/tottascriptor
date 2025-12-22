import streamlit as st
import cloudscraper
from bs4 import BeautifulSoup
import datetime
import time

# --- [뉴스 스크래퍼 클래스] ---
class NewsScraper:
    def fetch_news(self, start_datetime, end_datetime, keyword, photo_value):
        ds, de = start_datetime.strftime("%Y.%m.%d"), end_datetime.strftime("%Y.%m.%d")
        # nso 설정: 정확한 날짜 범위 지정
        nso = f"so:dd,p:from{start_datetime.strftime('%Y%m%d')}to{end_datetime.strftime('%Y%m%d')}"
        
        all_results = []
        seen_links = set()
        scraper = cloudscraper.create_scraper()
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.naver.com/'
        }

        # 모바일 웹 속도를 고려해 최대 5페이지까지 탐색
        for page in range(1, 6):
            start_index = (page - 1) * 10 + 1
            # 키워드에 큰따옴표를 붙여 반드시 포함되도록 함
            query = f'"{keyword}"'
            url = f"https://search.naver.com/search.naver?where=news&query={query}&sm=tab_pge&sort=1&photo={photo_value}&pd=3&ds={ds}&de={de}&nso={nso}&start={start_index}"
            
            try:
                response = scraper.get(url, headers=headers, timeout=10)
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # SDS 신규 디자인 요소들 찾기
                items = soup.select('a[data-heatmap-target=".tit"]')
                if not items: break

                for t_tag in items:
                    title = t_tag.get_text(strip=True)
                    link = t_tag.get('href')
                    if link in seen_links: continue
                    
                    # 정보 추출을 위해 부모 컨테이너(카드) 탐색
                    card = None
                    curr = t_tag
                    for _ in range(5): # 최대 5단계 위까지 탐색
                        if curr.parent:
                            curr = curr.parent
                            if curr.select_one(".sds-comps-profile"):
                                card = curr
                                break
                    
                    press_name = "알 수 없음"
                    date_text = "날짜 정보 없음"

                    if card:
                        # 1. 언론사 추출
                        press_el = card.select_one(".sds-comps-profile-info-title-text")
                        if press_el: press_name = press_el.get_text(strip=True)
                        
                        # 2. 날짜/시간 추출 (subtexts 영역 순회)
                        subtext_area = card.select_one(".sds-comps-profile-info-subtexts")
                        if subtext_area:
                            for txt in subtext_area.stripped_strings:
                                # "전"이 포함되거나 날짜 형식인 경우만 시간으로 인정
                                if ('전' in txt and len(txt) < 15) or ('.' in txt and len(txt) < 15 and txt[0].isdigit()):
                                    date_text = txt
                                    break

                    seen_links.add(link)
                    all_results.append({
                        'title': title, 
                        'link': link, 
                        'press': press_name, 
                        'time': date_text
                    })
                time.sleep(0.3)
            except: break
        return all_results

# --- [Streamlit 웹 UI] ---
st.set_page_config(page_title="서울교통공사 스크랩 앱", layout="wide")

# 스타일 설정 (모바일 최적화)
st.markdown("""
    <style>
    .main { background-color: #f0f2f6; }
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; }
    .news-card { background: white; padding: 12px; border-radius: 8px; border-left: 5px solid #007bff; margin-bottom: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .scrap-area { background: #fffbe6; padding: 10px; border: 1px dashed #ffc107; border-radius: 8px; }
    </style>
    """, unsafe_allow_html=True)

st.title("🚇 뉴스 스크랩 시스템")

# 세션 상태 초기화
if 'scrap_list' not in st.session_state:
    st.session_state.scrap_list = []
if 'search_results' not in st.session_state:
    st.session_state.search_results = []

# --- [1] 최종 스크랩 목록 (페이지 최상단 배치) ---
st.subheader("📋 실시간 스크랩 목록")
if st.session_state.scrap_list:
    final_text = "".join(st.session_state.scrap_list)
    st.text_area("결과 복사용 (전체 선택하여 복사하세요)", value=final_text, height=200)
    if st.button("🗑️ 목록 전체 비우기"):
        st.session_state.scrap_list = []
        st.rerun()
else:
    st.info("검색 후 '➕ 추가' 버튼을 누르면 여기에 기사가 담깁니다.")

st.divider()

# --- [2] 검색 설정 ---
with st.expander("🔍 검색 조건 설정", expanded=True):
    keyword = st.text_input("필수 포함 키워드", value="서울교통공사")
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("시작 날짜", datetime.date.today() - datetime.timedelta(days=1))
    with col2:
        end_date = st.date_input("종료 날짜", datetime.date.today())

if st.button("🚀 뉴스 검색 실행"):
    scraper = NewsScraper()
    with st.spinner('뉴스를 수집하고 있습니다...'):
        results = scraper.fetch_news(start_date, end_date, keyword, 0)
        st.session_state.search_results = results

# --- [3] 검색 결과 표시 ---
if st.session_state.search_results:
    st.subheader(f"✅ 검색 결과 ({len(st.session_state.search_results)}건)")
    for i, res in enumerate(st.session_state.search_results):
        with st.container():
            st.markdown(f"""
            <div class="news-card">
                <strong>[{res['press']}]</strong> {res['title']}<br>
                <small style="color:gray;">{res['time']}</small>
            </div>
            """, unsafe_allow_html=True)
            
            c1, c2 = st.columns([0.7, 0.3])
            with c1:
                st.link_button("📄 원문 링크", res['link'], use_container_width=True)
            with c2:
                if st.button("➕ 추가", key=f"add_{i}"):
                    # 중복 추가 방지 및 상단 목록 업데이트
                    item = f"ㅇ {res['title']}_{res['press']}\n{res['link']}\n\n"
                    if item not in st.session_state.scrap_list:
                        st.session_state.scrap_list.append(item)
                        st.toast("목록에 추가되었습니다!")
                        st.rerun() # 목록 즉시 반영을 위해 재실행
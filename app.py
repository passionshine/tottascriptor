import streamlit as st
import cloudscraper
from bs4 import BeautifulSoup
import datetime
import time
import re  # 정규표현식을 위해 추가
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

# --- [2. 뉴스 스크래퍼 (기능 강화됨)] ---
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
                    
                    # 1. 기본 정보 추출
                    title_text = t_tag.get('title') if t_tag.get('title') else t_tag.get_text(strip=True)
                    original_link = t_tag.get('href')
                    
                    # 2. 중복 제거 (제목 기준)
                    if title_text in seen_links: continue
                    seen_links.add(title_text)
                    
                    # 3. 부모 컨테이너(news_area) 찾기
                    news_area = t_tag.find_parent('div', class_='news_area')
                    
                    press_name = "알 수 없음"
                    is_naver = False
                    is_paper = False # 지면 기사 여부
                    final_link = original_link 

                    if news_area:
                        # 4. 언론사 이름 찾기
                        p_el = news_area.select_one(".info.press")
                        if p_el:
                            press_name = p_el.get_text(strip=True)
                        
                        # 5. [핵심] 네이버 뉴스 링크 & 지면 정보 파싱
                        # .info 클래스를 가진 요소들을 순회하며 확인합니다.
                        info_links = news_area.select(".info")
                        for info in info_links:
                            txt = info.get_text(strip=True)
                            
                            # (1) 네이버 뉴스 링크 확인
                            if "네이버뉴스" in txt and info.name == 'a':
                                is_naver = True
                                final_link = info['href']
                            
                            # (2) 지면 정보 확인 (예: A37면, 1면)
                            # 정규식: 영문(선택) + 숫자 + '면' 패턴
                            if re.search(r'[A-Za-z]*\d+면', txt):
                                is_paper = True

                    # 6. 제목에 지면 정보 추가
                    if is_paper:
                        title_text = f"{title_text} (지면)"

                    all_results.append({
                        'title': title_text, 
                        'link': final_link, 
                        'press': press_name,
                        'is_naver': is_naver
                    })
                time.sleep(0.1)
            except Exception as e:
                print(f"Error: {e}")
                break
        return all_results

# --- [3. UI 설정] ---
st.set_page_config(page_title="Totta Scriptor", layout="wide")

st.markdown("""
    <style>
    /* UI 스타일 생략 (기존과 동일) */
    [data-testid="stHorizontalBlock"] { gap: 4px !important; align-items: center !important; }
    div[data-testid="column"], div[data-testid="stColumn"] { padding: 0px !important; min-width: 0px !important; display: flex !important; justify-content: center !important; }
    .stButton { width: 100% !important; margin: 0 !important; }
    .stButton > button { width: 100% !important; height: 38px !important; padding: 0px 5px !important; font-size: 12px !important; font-weight: bold !important; border-radius: 6px !important; border: 1px solid #ddd !important; }
    .stLinkButton > a { width: 100% !important; height: 38px !important; display: flex; align-items: center; justify-content: center; font-size: 11px !important; }
    
    /* 버튼 색상 */
    div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(3) button,
    div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(3) button { background-color: #e3f2fd !important; color: #1565c0 !important; border: 1px solid #90caf9 !important; }
    div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(3) button:hover,
    div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(3) button:hover { background-color: #bbdefb !important; }

    div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(4) button,
    div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(4) button { background-color: #e8f5e9 !important; color: #2e7d32 !important; border: 1px solid #a5d6a7 !important; }
    div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(4) button:hover,
    div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(4) button:hover { background-color: #c8e6c9 !important; }

    /* 뉴스 카드 */
    .news-card { padding: 8px 12px; border-radius: 6px; border-left: 4px solid #007bff; box-shadow: 0 1px 1px rgba(0,0,0,0.05); display: flex; flex-direction: column; justify-content: center; height: 100%; }
    .bg-white { background: white !important; }
    .bg-scraped { background: #eee !important; border-left: 4px solid #888 !important; opacity: 0.7; }
    .news-title { font-size: 17px !important; font-weight: 600; color: #333; line-height: 1.2; margin-bottom: 2px; }
    .news-meta { font-size: 14px !important; color: #666; }
    .section-header { font-size: 18px; font-weight: 700; color: #333; margin-top: 25px; margin-bottom: 15px; border-bottom: 2px solid #007bff; padding-bottom: 5px; display: inline-block; }
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

dynamic_height = max(180, (final_output.count('\n') + 1) * 25)
st.text_area("📋 스크랩 결과 (전체 텍스트)", value=final_output, height=dynamic_height)

c_a, c_b = st.columns(2)
with c_a:
    if st.button("📋 텍스트 복사", use_container_width=True):
        st.toast("복사 완료!")
        components.html(f"<script>navigator.clipboard.writeText(`{final_output}`);</script>", height=0)
with c_b:
    if st.button("🗑️ 전체 초기화", use_container_width=True):
        st.session_state.corp_list, st.session_state.rel_list = [], []
        st.rerun()

# 관리 영역
with st.expander("🛠️ 스크랩 항목 개별 관리", expanded=False):
    st.write("**🏢 공사 보도 목록**")
    for idx, item in enumerate(st.session_state.corp_list):
        col_txt, col_del = st.columns([0.85, 0.15])
        with col_txt: st.caption(item.split('\n')[0])
        with col_del: 
            if st.button("삭제", key=f"del_c_{idx}"):
                st.session_state.corp_list.pop(idx); st.rerun()
    
    st.write("**🚆 유관기관 보도 목록**")
    for idx, item in enumerate(st.session_state.rel_list):
        col_txt, col_del = st.columns([0.85, 0.15])
        with col_txt: st.caption(item.split('\n')[0])
        with col_del:
            if st.button("삭제", key=f"del_r_{idx}"):
                st.session_state.rel_list.pop(idx); st.rerun()

st.divider()

# 2. 검색 설정
with st.expander("🔍 뉴스 검색 설정", expanded=True):
    keyword = st.text_input("검색어", value="서울교통공사")
    col_d1, col_d2 = st.columns(2)
    with col_d1: start_d = st.date_input("시작일", datetime.date.today() - datetime.timedelta(days=1))
    with col_d2: end_d = st.date_input("종료일", datetime.date.today())
    max_a = st.slider("최대 기사 수", 10, 100, 30)
    if st.button("🚀 뉴스 검색 시작", type="primary", use_container_width=True):
        with st.spinner('뉴스를 검색하고 URL 및 지면 정보를 분석 중입니다...'):
            st.session_state.search_results = NewsScraper().fetch_news(start_d, end_d, keyword, max_a)
        st.rerun()

# 3. 뉴스 리스트 출력 함수
def display_news_section(title, articles, section_key):
    st.markdown(f'<div class="section-header">{title} ({len(articles)}건)</div>', unsafe_allow_html=True)
    
    if not articles:
        st.caption("검색된 기사가 없습니다.")
        return

    for i, res in enumerate(articles):
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
            
            with col2: st.link_button("원문보기", res['link'])
            with col3:
                if st.button("공사보도", key=f"c_{section_key}_{i}"):
                    if item_check not in st.session_state.corp_list:
                        st.session_state.corp_list.append(item_check)
                        st.toast("🏢 추가 완료!"); time.sleep(0.1); st.rerun()
                    else: st.toast("⚠️ 이미 추가됨")
            with col4:
                if st.button("유관기관", key=f"r_{section_key}_{i}"):
                    if item_check not in st.session_state.rel_list:
                        st.session_state.rel_list.append(item_check)
                        st.toast("🚆 추가 완료!"); time.sleep(0.1); st.rerun()
                    else: st.toast("⚠️ 이미 추가됨")
        
        st.markdown("<hr style='margin: 3px 0; border: none; border-top: 1px solid #f0f0f0;'>", unsafe_allow_html=True)

# 4. 결과 출력
if st.session_state.search_results:
    naver_news = [item for item in st.session_state.search_results if item.get('is_naver', False)]
    other_news = [item for item in st.session_state.search_results if not item.get('is_naver', False)]
    
    display_news_section("🟢 네이버 뉴스", naver_news, "naver")
    st.write("") 
    display_news_section("🌐 언론사 자체 기사", other_news, "press")
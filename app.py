import streamlit as st
import cloudscraper
from bs4 import BeautifulSoup
import datetime
import time
import re
import json
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

# --- [2. 뉴스 스크래퍼 (JSON 파싱 방식 적용)] ---
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
        all_results = []
        seen_titles = set() # 중복 제거용
        
        query = f'"{keyword}"'
        max_pages = (max_articles // 10) + 1
        
        for page in range(max_pages):
            if len(all_results) >= max_articles: break
            
            start_val = (page * 10) + 1
            url = f"https://search.naver.com/search.naver?where=news&query={query}&sm=tab_pge&sort=1&photo=0&pd=3&ds={ds}&de={de}&nso={nso}&start={start_val}"
            
            try:
                res = self.scraper.get(url, headers=self.headers, timeout=10)
                soup = BeautifulSoup(res.content, 'html.parser')
                
                # [핵심 로직] entry.bootstrap 안의 JSON 데이터 추출
                scripts = soup.find_all('script')
                json_data = None
                
                for script in scripts:
                    if 'entry.bootstrap' in script.text:
                        # 정규식으로 entry.bootstrap(..., { JSON }); 패턴에서 JSON 부분만 추출
                        # (?<=...): 긍정형 후방 탐색, document.getElementById(...) 뒤에 오는 {,} 패턴 찾기
                        match = re.search(r'entry\.bootstrap\(document\.getElementById\(".*?"\), ({.*})\);', script.text)
                        if match:
                            try:
                                json_str = match.group(1)
                                json_data = json.loads(json_str)
                                break
                            except:
                                continue

                if not json_data:
                    # JSON 추출 실패 시 다음 페이지로 (혹은 HTML 파싱 폴백 가능하나 여기선 패스)
                    continue

                # JSON 구조 탐색: body -> props -> children 리스트
                try:
                    items_list = json_data.get('body', {}).get('props', {}).get('children', [])
                except:
                    items_list = []

                for item in items_list:
                    if len(all_results) >= max_articles: break
                    
                    # 템플릿 ID가 newsItem인 것만 처리 (광고 등 제외)
                    if item.get('templateId') != 'newsItem':
                        continue
                        
                    props = item.get('props', {})
                    
                    # 1. 제목 및 원본 링크
                    raw_title = props.get('title', '')
                    # HTML 태그 제거 (mark 태그 등)
                    clean_title = re.sub('<[^<]+?>', '', raw_title)
                    original_link = props.get('titleHref', '')
                    
                    # 중복 제거
                    if clean_title in seen_titles: continue
                    seen_titles.add(clean_title)

                    # 2. 언론사 정보
                    source_info = props.get('sourceProfile', {})
                    press_name = source_info.get('title', '알 수 없음')

                    # 3. 추가 정보 (지면, 네이버뉴스 링크 등)
                    sub_texts = props.get('subTexts', [])
                    
                    is_naver = False
                    final_link = original_link
                    paper_info = ""

                    for sub in sub_texts:
                        # (1) 네이버 뉴스 링크 확인
                        # JSON 구조상 "text": "네이버뉴스" 이고 "textHref"가 존재함
                        if sub.get('text') == '네이버뉴스' and sub.get('textHref'):
                            is_naver = True
                            final_link = sub.get('textHref')
                        
                        # (2) 지면 정보 확인 (예: "A10면", "1면")
                        txt = sub.get('text', '')
                        if txt and re.search(r'^\s*[A-Za-z]*\d+면', txt):
                            paper_info = f" ({txt})"

                    # 제목에 지면 정보 붙이기
                    full_title = f"{clean_title}{paper_info}"

                    all_results.append({
                        'title': full_title,
                        'link': final_link,
                        'press': press_name,
                        'is_naver': is_naver
                    })

                time.sleep(0.1)
                
            except Exception as e:
                print(f"Error processing page {page}: {e}")
                continue
                
        return all_results

# --- [3. UI 설정] ---
st.set_page_config(page_title="Totta Scriptor", layout="wide")

st.markdown("""
    <style>
    /* 1. 수평 블록 간격 제어 */
    [data-testid="stHorizontalBlock"] {
        gap: 4px !important;
        align-items: center !important; 
    }

    /* 2. 컬럼 패딩 최적화 */
    div[data-testid="column"], div[data-testid="stColumn"] {
        padding: 0px !important;
        min-width: 0px !important;
        display: flex !important;
        justify-content: center !important; 
    }

    /* 3. 버튼 기본 스타일 */
    .stButton { width: 100% !important; margin: 0 !important; }
    .stButton > button {
        width: 100% !important;
        height: 38px !important;
        padding: 0px 5px !important;
        font-size: 12px !important;
        font-weight: bold !important;
        border-radius: 6px !important;
        border: 1px solid #ddd !important;
    }
    .stLinkButton > a {
        width: 100% !important;
        height: 38px !important;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 11px !important;
    }

    /* 4. 버튼 색상 강제 지정 */
    div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(3) button,
    div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(3) button {
        background-color: #e3f2fd !important;
        color: #1565c0 !important;
        border: 1px solid #90caf9 !important;
    }
    div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(3) button:hover,
    div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(3) button:hover {
        background-color: #bbdefb !important;
    }

    div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(4) button,
    div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(4) button {
        background-color: #e8f5e9 !important;
        color: #2e7d32 !important;
        border: 1px solid #a5d6a7 !important;
    }
    div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(4) button:hover,
    div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(4) button:hover {
        background-color: #c8e6c9 !important;
    }

    /* 뉴스 카드 스타일 */
    .news-card {
        padding: 8px 12px;
        border-radius: 6px;
        border-left: 4px solid #007bff;
        box-shadow: 0 1px 1px rgba(0,0,0,0.05);
        display: flex;
        flex-direction: column;
        justify-content: center;
        height: 100%;
    }
    .bg-white { background: white !important; }
    .bg-scraped { background: #eee !important; border-left: 4px solid #888 !important; opacity: 0.7; }
    .news-title { font-size: 17px !important; font-weight: 600; color: #333; line-height: 1.2; margin-bottom: 2px; }
    .news-meta { font-size: 14px !important; color: #666; }
    
    /* 섹션 헤더 스타일 */
    .section-header {
        font-size: 18px;
        font-weight: 700;
        color: #333;
        margin-top: 25px;
        margin-bottom: 15px;
        border-bottom: 2px solid #007bff;
        padding-bottom: 5px;
        display: inline-block;
    }
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

# 결과창
dynamic_height = max(180, (final_output.count('\n') + 1) * 25)
st.text_area("📋 스크랩 결과 (전체 텍스트)", value=final_output, height=dynamic_height)

# 버튼 영역
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
                st.session_state.corp_list.pop(idx)
                st.rerun()
    
    st.write("**🚆 유관기관 보도 목록**")
    for idx, item in enumerate(st.session_state.rel_list):
        col_txt, col_del = st.columns([0.85, 0.15])
        with col_txt: st.caption(item.split('\n')[0])
        with col_del:
            if st.button("삭제", key=f"del_r_{idx}"):
                st.session_state.rel_list.pop(idx)
                st.rerun()

st.divider()

# 2. 검색 설정
with st.expander("🔍 뉴스 검색 설정", expanded=True):
    keyword = st.text_input("검색어", value="서울교통공사")
    col_d1, col_d2 = st.columns(2)
    with col_d1: start_d = st.date_input("시작일", datetime.date.today() - datetime.timedelta(days=1))
    with col_d2: end_d = st.date_input("종료일", datetime.date.today())
    max_a = st.slider("최대 기사 수", 10, 100, 30)
    if st.button("🚀 뉴스 검색 시작", type="primary", use_container_width=True):
        with st.spinner('뉴스를 검색하고 JSON 데이터를 분석 중입니다...'):
            st.session_state.search_results = NewsScraper().fetch_news(start_d, end_d, keyword, max_a)
        st.rerun()

# 3. 뉴스 리스트 출력 함수 (공통 사용)
def display_news_section(title, articles, section_key):
    st.markdown(f'<div class="section-header">{title} ({len(articles)}건)</div>', unsafe_allow_html=True)
    
    if not articles:
        st.caption("검색된 기사가 없습니다.")
        return

    for i, res in enumerate(articles):
        # 스크랩 텍스트 생성: 제목_언론사 (줄바꿈) URL
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
                st.link_button("원문보기", res['link'])
            with col3:
                # key에 section_key를 추가하여 ID 충돌 방지
                if st.button("공사보도", key=f"c_{section_key}_{i}"):
                    if item_check not in st.session_state.corp_list:
                        st.session_state.corp_list.append(item_check)
                        st.toast("🏢 공사관련 보도 추가 완료!"); time.sleep(0.1); st.rerun()
                    else: st.toast("⚠️ 이미 추가됨")
            with col4:
                if st.button("유관기관", key=f"r_{section_key}_{i}"):
                    if item_check not in st.session_state.rel_list:
                        st.session_state.rel_list.append(item_check)
                        st.toast("🚆 유관기관 보도 추가 완료!"); time.sleep(0.1); st.rerun()
                    else: st.toast("⚠️ 이미 추가됨")
        
        st.markdown("<hr style='margin: 3px 0; border: none; border-top: 1px solid #f0f0f0;'>", unsafe_allow_html=True)

# 4. 결과 출력 로직
if st.session_state.search_results:
    naver_news = [item for item in st.session_state.search_results if item.get('is_naver', False)]
    other_news = [item for item in st.session_state.search_results if not item.get('is_naver', False)]
    
    display_news_section("🟢 네이버 뉴스", naver_news, "naver")
    st.write("") 
    display_news_section("🌐 언론사 자체 기사", other_news, "press")
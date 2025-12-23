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

# --- [2. 뉴스 스크래퍼 (JSON 파싱 최적화)] ---
class NewsScraper:
    def __init__(self):
        # 봇 탐지 우회를 위한 브라우저 세팅
        self.scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True
            }
        )
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.naver.com/',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
        }

    def fetch_news(self, start_d, end_d, keyword, max_articles):
        ds, de = start_d.strftime("%Y.%m.%d"), end_d.strftime("%Y.%m.%d")
        nso = f"so:dd,p:from{start_d.strftime('%Y%m%d')}to{end_d.strftime('%Y%m%d')}"
        all_results = []
        seen_titles = set()
        
        query = f'"{keyword}"'
        max_pages = (max_articles // 10) + 1
        
        # 진행상황 표시
        progress_bar = st.progress(0)
        status_text = st.empty()

        for page in range(max_pages):
            if len(all_results) >= max_articles: break
            
            status_text.text(f"🔍 {page+1}페이지 검색 중...")
            progress_bar.progress((page + 1) / max_pages)
            
            start_val = (page * 10) + 1
            url = f"https://search.naver.com/search.naver?where=news&query={query}&sm=tab_pge&sort=1&photo=0&pd=3&ds={ds}&de={de}&nso={nso}&start={start_val}"
            
            try:
                res = self.scraper.get(url, headers=self.headers, timeout=10)
                soup = BeautifulSoup(res.content, 'html.parser')
                
                # [핵심] script 태그 내의 entry.bootstrap JSON 찾기
                scripts = soup.find_all('script')
                json_data = None
                
                for script in scripts:
                    if not script.string: continue
                    
                    # entry.bootstrap 문자열이 있는 스크립트 탐색
                    if 'entry.bootstrap' in script.string:
                        # 정규식 설명:
                        # 1. entry.bootstrap( ... ,  <-- 시작 부분 찾기
                        # 2. ({ ... })               <-- 중괄호로 묶인 JSON 부분 캡처 (re.DOTALL로 줄바꿈 포함)
                        # 3. );                      <-- 끝 부분 찾기
                        pattern = r'entry\.bootstrap\(document\.getElementById\(".*?"\),\s*({.*})\);'
                        match = re.search(pattern, script.string, re.DOTALL)
                        
                        if match:
                            try:
                                json_str = match.group(1)
                                json_data = json.loads(json_str)
                                break
                            except Exception as e:
                                print(f"JSON Parsing Error: {e}")
                                continue

                if not json_data:
                    # JSON이 없으면 다음 페이지로 (봇 차단되었거나 뉴스가 없음)
                    time.sleep(0.5)
                    continue

                # JSON 내부 구조: body > props > children 리스트에 기사 정보가 있음
                items_list = json_data.get('body', {}).get('props', {}).get('children', [])

                for item in items_list:
                    if len(all_results) >= max_articles: break
                    
                    # 템플릿 ID 확인 (newsItem이 기사임)
                    if item.get('templateId') != 'newsItem':
                        continue
                        
                    props = item.get('props', {})
                    
                    # 1. 제목 추출 (HTML 태그 제거)
                    raw_title = props.get('title', '')
                    clean_title = re.sub('<[^<]+?>', '', raw_title) # <mark> 등 제거
                    
                    # 원본 링크
                    original_link = props.get('titleHref', '')
                    
                    # 중복 제거
                    if clean_title in seen_titles: continue
                    seen_titles.add(clean_title)

                    # 2. 언론사 추출
                    source_info = props.get('sourceProfile', {})
                    press_name = source_info.get('title', '알 수 없음')

                    # 3. [중요] subTexts 분석 (지면정보 & 네이버뉴스 링크)
                    sub_texts = props.get('subTexts', [])
                    
                    is_naver = False
                    final_link = original_link
                    paper_info = ""

                    for sub in sub_texts:
                        text_val = sub.get('text', '')
                        
                        # (A) 네이버 뉴스 링크 파싱
                        # 예: {"text":"네이버뉴스", "textHref":"https://n.news.naver.com/..."}
                        if text_val == '네이버뉴스' and sub.get('textHref'):
                            is_naver = True
                            final_link = sub.get('textHref')
                        
                        # (B) 지면 정보 파싱 (예: "A37면", "1면")
                        # 정규식: 영문(옵션) + 숫자 + '면'으로 끝나는 단어
                        if re.search(r'[A-Za-z]*\d+면', text_val):
                            paper_info = f" ({text_val})"

                    # 제목에 지면 정보 추가
                    full_title = f"{clean_title}{paper_info}"

                    all_results.append({
                        'title': full_title,
                        'link': final_link,
                        'press': press_name,
                        'is_naver': is_naver
                    })

                time.sleep(0.3 + (0.2 * (page % 2))) # 랜덤 딜레이 살짝 추가
                
            except Exception as e:
                st.error(f"Error on page {page}: {e}")
                continue
        
        progress_bar.empty()
        status_text.empty()
        return all_results

# --- [3. UI 설정] ---
st.set_page_config(page_title="Totta Scriptor", layout="wide")

st.markdown("""
    <style>
    /* 기본 UI 스타일 */
    [data-testid="stHorizontalBlock"] { gap: 4px !important; align-items: center !important; }
    div[data-testid="column"], div[data-testid="stColumn"] { padding: 0px !important; min-width: 0px !important; display: flex !important; justify-content: center !important; }
    .stButton { width: 100% !important; margin: 0 !important; }
    .stButton > button { width: 100% !important; height: 38px !important; font-size: 12px !important; font-weight: bold !important; border-radius: 6px !important; }
    .stLinkButton > a { width: 100% !important; height: 38px !important; display: flex; align-items: center; justify-content: center; font-size: 11px !important; }

    /* 버튼 색상 */
    div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(3) button,
    div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(3) button { background-color: #e3f2fd !important; color: #1565c0 !important; border: 1px solid #90caf9 !important; }
    div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(3) button:hover { background-color: #bbdefb !important; }
    div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(4) button,
    div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(4) button { background-color: #e8f5e9 !important; color: #2e7d32 !important; border: 1px solid #a5d6a7 !important; }
    div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(4) button:hover { background-color: #c8e6c9 !important; }

    /* 뉴스 카드 스타일 */
    .news-card { padding: 8px 12px; border-radius: 6px; border-left: 4px solid #007bff; box-shadow: 0 1px 1px rgba(0,0,0,0.05); display: flex; flex-direction: column; justify-content: center; height: 100%; }
    .bg-white { background: white !important; }
    .bg-scraped { background: #eee !important; border-left: 4px solid #888 !important; opacity: 0.7; }
    .news-title { font-size: 17px !important; font-weight: 600; color: #333; line-height: 1.2; margin-bottom: 2px; }
    .news-meta { font-size: 14px !important; color: #666; }
    .section-header { font-size: 18px; font-weight: 700; color: #333; margin-top: 25px; margin-bottom: 15px; border-bottom: 2px solid #007bff; padding-bottom: 5px; display: inline-block; }
    </style>
    """, unsafe_allow_html=True)

# 세션 초기화
for key in ['corp_list', 'rel_list', 'search_results']:
    if key not in st.session_state: st.session_state[key] = []

st.title("🚇 또타 스크립터")

# 1. 결과 영역
t_date = get_target_date()
date_header = f"<{t_date.month}월 {t_date.day}일 조간 스크랩>"
final_output = f"{date_header}\n\n[공사 관련 보도]\n" + "".join(st.session_state.corp_list) + "\n[유관기관 관련 보도]\n" + "".join(st.session_state.rel_list)

dynamic_height = max(180, (final_output.count('\n') + 1) * 25)
st.text_area("📋 스크랩 결과", value=final_output, height=dynamic_height)

# 상단 버튼
c1, c2 = st.columns(2)
with c1:
    if st.button("📋 텍스트 복사", use_container_width=True):
        st.toast("복사 완료!")
        components.html(f"<script>navigator.clipboard.writeText(`{final_output}`);</script>", height=0)
with c2:
    if st.button("🗑️ 초기화", use_container_width=True):
        st.session_state.corp_list, st.session_state.rel_list = [], []
        st.rerun()

# 개별 관리
with st.expander("🛠️ 스크랩 항목 관리", expanded=False):
    st.write("**🏢 공사 보도**")
    for idx, item in enumerate(st.session_state.corp_list):
        ct, cd = st.columns([0.85, 0.15])
        with ct: st.caption(item.split('\n')[0])
        with cd: 
            if st.button("삭제", key=f"d_c_{idx}"): st.session_state.corp_list.pop(idx); st.rerun()
    st.write("**🚆 유관기관 보도**")
    for idx, item in enumerate(st.session_state.rel_list):
        ct, cd = st.columns([0.85, 0.15])
        with ct: st.caption(item.split('\n')[0])
        with cd:
            if st.button("삭제", key=f"d_r_{idx}"): st.session_state.rel_list.pop(idx); st.rerun()

st.divider()

# 2. 검색 설정
with st.expander("🔍 뉴스 검색 설정", expanded=True):
    keyword = st.text_input("검색어", value="서울교통공사")
    d1, d2 = st.columns(2)
    with d1: start_d = st.date_input("시작일", datetime.date.today() - datetime.timedelta(days=1))
    with d2: end_d = st.date_input("종료일", datetime.date.today())
    max_a = st.slider("최대 기사 수", 10, 100, 30)
    
    if st.button("🚀 뉴스 검색 시작", type="primary", use_container_width=True):
        with st.spinner('뉴스를 검색하고 데이터를 분석 중입니다...'):
            st.session_state.search_results = NewsScraper().fetch_news(start_d, end_d, keyword, max_a)
        st.rerun()

# 3. 뉴스 리스트 출력
def display_list(title, items, key_prefix):
    st.markdown(f'<div class="section-header">{title} ({len(items)}건)</div>', unsafe_allow_html=True)
    if not items:
        st.caption("기사가 없습니다.")
        return

    for i, res in enumerate(items):
        item_txt = f"ㅇ {res['title']}_{res['press']}\n{res['link']}\n\n"
        is_scraped = (item_txt in st.session_state.corp_list) or (item_txt in st.session_state.rel_list)
        bg = "bg-scraped" if is_scraped else "bg-white"

        with st.container():
            c1, c2, c3, c4 = st.columns([0.73, 0.09, 0.09, 0.09])
            with c1:
                st.markdown(f'''<div class="news-card {bg}">
                    <div class="news-title">{res["title"]}</div>
                    <div class="news-meta">[{res["press"]}] {"(스크랩됨)" if is_scraped else ""}</div>
                </div>''', unsafe_allow_html=True)
            with c2: st.link_button("원문", res['link'])
            with c3:
                if st.button("공사", key=f"c_{key_prefix}_{i}"):
                    if item_txt not in st.session_state.corp_list:
                        st.session_state.corp_list.append(item_txt)
                        st.toast("🏢 추가됨"); time.sleep(0.1); st.rerun()
            with c4:
                if st.button("유관", key=f"r_{key_prefix}_{i}"):
                    if item_txt not in st.session_state.rel_list:
                        st.session_state.rel_list.append(item_txt)
                        st.toast("🚆 추가됨"); time.sleep(0.1); st.rerun()
        st.markdown("<hr style='margin: 3px 0; border: none; border-top: 1px solid #f0f0f0;'>", unsafe_allow_html=True)

if st.session_state.search_results:
    naver_news = [x for x in st.session_state.search_results if x['is_naver']]
    other_news = [x for x in st.session_state.search_results if not x['is_naver']]
    
    display_list("🟢 네이버 뉴스", naver_news, "n")
    st.write("")
    display_list("🌐 언론사 자체 기사", other_news, "o")
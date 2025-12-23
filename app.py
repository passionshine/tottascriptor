import streamlit as st
import cloudscraper
from bs4 import BeautifulSoup
import datetime
import time
import re
import streamlit.components.v1 as components

# --- [1. 스마트 날짜 계산 함수 (2026년 공휴일 반영)] ---
def get_target_date():
    today = datetime.date.today()
    if today.weekday() == 4: target = today + datetime.timedelta(days=3)
    elif today.weekday() == 5: target = today + datetime.timedelta(days=2)
    else: target = today + datetime.timedelta(days=1)

    # 2026년 주요 공휴일 (대체공휴일 포함)
    holidays = [
        datetime.date(2026,1,1),  # 신정
        datetime.date(2026,2,16), datetime.date(2026,2,17), datetime.date(2026,2,18), # 설날
        datetime.date(2026,3,1), datetime.date(2026,3,2), # 삼일절 및 대체
        datetime.date(2026,5,5),  # 어린이날
        datetime.date(2026,5,24), datetime.date(2026,5,25), # 부처님오신날 및 대체
        datetime.date(2026,6,6),  # 현충일
        datetime.date(2026,8,15), # 광복절
        datetime.date(2026,9,24), datetime.date(2026,9,25), datetime.date(2026,9,26), # 추석
        datetime.date(2026,10,3), # 개천절
        datetime.date(2026,10,9), # 한글날
        datetime.date(2026,12,25) # 성탄절
    ]
    
    # 목표일이 공휴일이거나 주말이면 다음 평일로 이동
    while target in holidays or target.weekday() >= 5:
        target += datetime.timedelta(days=1)
    return target

# --- [2. 뉴스 스크래퍼 (수정됨)] ---
class NewsScraper:
    def __init__(self):
        self.scraper = cloudscraper.create_scraper()
        # 헤더를 모바일이 아닌 PC 버전으로 명시하여 구조 통일
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://search.naver.com/'
        }

    def fetch_news(self, start_d, end_d, keyword, max_articles):
        ds, de = start_d.strftime("%Y.%m.%d"), end_d.strftime("%Y.%m.%d")
        ds_param = start_d.strftime("%Y%m%d")
        de_param = end_d.strftime("%Y%m%d")
        
        # 정확한 날짜 필터링을 위한 파라미터 (so:dd = 최신순, p:from~to = 기간)
        nso = f"so:dd,p:from{ds_param}to{de_param},a:all"
        
        all_results = []
        seen_links = set()
        
        query = f'"{keyword}"'
        max_pages = (max_articles // 10) + 2  # 여유있게 페이지 계산
        
        status_text = st.empty()
        progress_bar = st.progress(0)
        log_container = st.container()

        status_text.text("뉴스 수집 시작...")

        for page in range(1, max_pages + 1):
            if len(all_results) >= max_articles: break
            
            current_progress = min(len(all_results) / max_articles, 1.0)
            progress_bar.progress(current_progress)
            status_text.text(f"⏳ {page}페이지 분석 중... (현재 {len(all_results)}건)")
            
            start_index = (page - 1) * 10 + 1
            url = f"https://search.naver.com/search.naver?where=news&query={query}&sm=tab_pge&sort=1&photo=0&pd=3&ds={ds}&de={de}&nso={nso}&start={start_index}"
            
            try:
                response = self.scraper.get(url, headers=self.headers, timeout=10)
                if response.status_code != 200:
                    with log_container: st.error(f"❌ 접속 실패: {response.status_code}")
                    continue

                soup = BeautifulSoup(response.content, 'html.parser')
                
                # 뉴스 카드 리스트 가져오기 (news_wrap 클래스 사용)
                items = soup.select('.news_wrap')
                
                if not items:
                    with log_container: st.warning(f"⚠️ {page}페이지: 더 이상 기사가 없습니다.")
                    break

                for card in items:
                    if len(all_results) >= max_articles: break

                    # 1. 제목 및 링크 추출
                    title_tag = card.select_one('a.news_tit')
                    if not title_tag: continue
                    
                    title = title_tag.get_text(strip=True)
                    original_link = title_tag.get('href')
                    
                    # 2. 언론사 및 날짜 추출 (정확도 개선)
                    press_name = "알 수 없음"
                    article_date = ""
                    is_paper = False
                    paper_info = ""

                    # info_group 안에서 순회하며 정보 찾기
                    info_group = card.select_one('.info_group')
                    if info_group:
                        # 언론사 찾기 (press 클래스)
                        press_el = info_group.select_one('.press')
                        if press_el: press_name = press_el.get_text(strip=True)
                        
                        # 날짜 및 지면 정보 찾기 (info 클래스 중 press가 아닌 것)
                        infos = info_group.select('.info')
                        for info in infos:
                            text = info.get_text(strip=True)
                            if "면" in text and "전" not in text: # 지면 정보 (예: A10면)
                                is_paper = True
                                paper_info = " (지면)"
                            elif re.search(r'\d{4}\.\d{2}\.\d{2}|\d+[분시일주초]\s?전|방금\s?전', text):
                                # 이미 날짜를 찾았는데 또 나오면(수정일 등) 무시하거나 덮어쓰기
                                if not article_date: 
                                    article_date = text

                    # 날짜가 여전히 비어있다면 백업 로직 (전체 텍스트에서 검색하지 않음)
                    if not article_date:
                        date_match = re.search(r'(\d{4}\.\d{2}\.\d{2})', card.get_text())
                        if date_match: article_date = date_match.group(1)

                    # 3. 네이버 뉴스 링크 확인
                    final_link = original_link
                    is_naver = "n.news.naver.com" in original_link
                    
                    naver_btn = card.select_one('a.info[href*="n.news.naver.com"]')
                    if naver_btn:
                        final_link = naver_btn.get('href')
                        is_naver = True

                    # 4. 중복 제거
                    if final_link in seen_links: continue
                    seen_links.add(final_link)
                    
                    full_title = f"{title}{paper_info}"
                    
                    all_results.append({
                        'title': full_title,
                        'link': final_link,
                        'press': press_name,
                        'is_naver': is_naver,
                        'is_paper': is_paper,
                        'date': article_date
                    })
                    
                time.sleep(0.3)
                
            except Exception as e:
                with log_container: st.error(f"Error on page {page}: {e}")
                continue
        
        progress_bar.progress(1.0)
        status_text.success(f"✅ 수집 완료! 총 {len(all_results)}건")
        time.sleep(0.5)
        progress_bar.empty()
        status_text.empty()
        
        return all_results

# --- [3. UI 설정] ---
st.set_page_config(page_title="Totta Scraper", layout="wide")

st.markdown("""
    <style>
    div[data-testid="column"] { 
        display: flex !important; 
        flex-direction: column !important; 
        justify-content: center !important; 
    }
    .news-card { 
        padding: 12px 16px; 
        border-radius: 8px; 
        border-left: 5px solid #007bff; 
        box-shadow: 0 2px 4px rgba(0,0,0,0.08); 
        background: white;
        height: 100%;
        display: flex;
        flex-direction: column;
        justify-content: center;
        margin-right: 15px !important;
        margin-bottom: 5px !important; 
    }
    .bg-scraped { background: #f8f9fa !important; border-left: 5px solid #adb5bd !important; opacity: 0.7; }
    .news-title { font-size: 16px !important; font-weight: 700; color: #222; margin-bottom: 5px; line-height: 1.3; }
    .news-meta { font-size: 13px !important; color: #666; font-weight: 500; }
    
    .stButton > button, .stLinkButton > a { 
        width: 100% !important; 
        height: 36px !important; 
        border-radius: 6px !important; 
        font-size: 13px !important; 
        font-weight: 600 !important; 
        padding: 0px 5px !important; 
        border: 1px solid #e0e0e0 !important; 
        background-color: white !important; 
        color: #555 !important; 
        box-shadow: 0 1px 2px rgba(0,0,0,0.05) !important; 
    }
    .stButton > button:hover, .stLinkButton > a:hover {
        border-color: #007bff !important; 
        color: #007bff !important; 
        background-color: #f0f7ff !important; 
    }
    .section-header { font-size: 18px; font-weight: 700; color: #333; margin-top: 30px; margin-bottom: 15px; border-bottom: 2px solid #007bff; display: inline-block; }
    
    div[data-testid="stHorizontalBlock"] .stButton:nth-of-type(2) button { color: #0056b3 !important; }
    div[data-testid="stHorizontalBlock"] .stButton:nth-of-type(3) button { color: #198754 !important; }
    </style>
    """, unsafe_allow_html=True)

# 세션 초기화
for key in ['corp_list', 'rel_list', 'search_results']:
    if key not in st.session_state: st.session_state[key] = []

st.title("🚇 또타 스크립터 (Final Ver)")

# 1. 스크랩 목록
t_date = get_target_date()
date_header = f"<{t_date.month}월 {t_date.day}일 조간 스크랩>"

if st.session_state.corp_list or st.session_state.rel_list:
    final_output = f"{date_header}\n\n[공사 관련 보도]\n" + "".join(st.session_state.corp_list) + "\n[유관기관 관련 보도]\n" + "".join(st.session_state.rel_list)
else:
    final_output = ""

text_height = max(180, (final_output.count('\n') + 1) * 25)
st.text_area("📋 스크랩 결과", value=final_output, height=text_height)

if final_output:
    js_code = f"""
    <html>
        <head>
            <style>
                .copy-btn {{
                    display: inline-flex; align-items: center; justify-content: center;
                    width: 100%; height: 38px; background-color: #f0f2f6;
                    color: #31333F; border: 1px solid #d1d5db; border-radius: 6px;
                    cursor: pointer; font-family: sans-serif; font-weight: 600; font-size: 14px;
                }}
                .copy-btn:hover {{ border-color: #007bff; color: #007bff; background-color: #e7f3ff; }}
            </style>
        </head>
        <body>
            <textarea id="hidden-text" style="position:absolute; top:-9999px; left:-9999px;">{final_output}</textarea>
            <button class="copy-btn" onclick="copyToClipboard()">📋 텍스트 복사하기 (클릭)</button>
            <script>
                function copyToClipboard() {{
                    var textArea = document.getElementById("hidden-text");
                    textArea.select();
                    textArea.setSelectionRange(0, 99999);
                    try {{
                        var successful = document.execCommand('copy');
                        if (successful) alert('✅ 복사되었습니다!');
                        else alert('❌ 복사 실패.');
                    }} catch (err) {{ alert('❌ 브라우저 차단됨.'); }}
                }}
            </script>
        </body>
    </html>
    """
    components.html(js_code, height=50)

if st.button("🗑️ 전체 초기화", use_container_width=True):
    st.session_state.corp_list, st.session_state.rel_list = [], []
    st.rerun()

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
        st.session_state.search_results = NewsScraper().fetch_news(start_d, end_d, keyword, max_a)

# 3. 뉴스 리스트 출력
def display_list(title, items, key_prefix):
    st.markdown(f'<div class="section-header">{title} ({len(items)}건)</div>', unsafe_allow_html=True)
    if not items:
        st.caption("기사가 없습니다.")
        return

    for i, res in enumerate(items):
        date_val = res.get('date', '')
        date_str = f"[{date_val}] " if date_val else ""
        item_txt = f"ㅇ {date_str}{res['title']}_{res['press']}\n{res['link']}\n\n"
        
        is_scraped = (item_txt in st.session_state.corp_list) or (item_txt in st.session_state.rel_list)
        bg = "bg-scraped" if is_scraped else "bg-white"

        main_cols = st.columns([0.75, 0.25], gap="small")
        with main_cols[0]:
            st.markdown(f'''<div class="news-card {bg}">
                <div class="news-title">{res["title"]}</div>
                <div class="news-meta">
                    <span style="color: #007bff; font-weight: bold;">{date_val}</span>
                    [{res["press"]}] {"(스크랩됨)" if is_scraped else ""}
                </div>
            </div>''', unsafe_allow_html=True)

        with main_cols[1]:
            btn_cols = st.columns(3, gap="small") 
            with btn_cols[0]:
                st.link_button("원문", res['link'], use_container_width=True)
            with btn_cols[1]:
                if st.button("공사", key=f"c_{key_prefix}_{i}", use_container_width=True):
                    if item_txt not in st.session_state.corp_list:
                        st.session_state.corp_list.append(item_txt)
                        st.toast("🏢 추가됨!", icon="✅"); time.sleep(1.0); st.rerun()
            with btn_cols[2]:
                if st.button("유관", key=f"r_{key_prefix}_{i}", use_container_width=True):
                    if item_txt not in st.session_state.rel_list:
                        st.session_state.rel_list.append(item_txt)
                        st.toast("🚆 추가됨!", icon="✅"); time.sleep(1.0); st.rerun()
        
        st.markdown("<div style='margin-bottom: 6px;'></div>", unsafe_allow_html=True)

# 결과 분류 로직
if st.session_state.search_results:
    paper_news = [x for x in st.session_state.search_results if x.get('is_paper')]
    naver_news = [x for x in st.session_state.search_results if x.get('is_naver') and not x.get('is_paper')]
    other_news = [x for x in st.session_state.search_results if not x.get('is_naver') and not x.get('is_paper')]
    
    if paper_news:
        display_list("📰 지면 보도", paper_news, "p")
        st.write("") 
        
    display_list("🟢 네이버 뉴스", naver_news, "n")
    st.write("")
    display_list("🌐 언론사 자체 기사", other_news, "o")

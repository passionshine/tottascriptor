import streamlit as st
import cloudscraper
from bs4 import BeautifulSoup
import datetime
import time
import re
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

# --- [2. 뉴스 스크래퍼 (통합 버전)] ---
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
        seen_links = set()
        
        query = f'"{keyword}"'
        max_pages = (max_articles // 10) + 1
        
        # 진행상황 UI
        status_text = st.empty()
        progress_bar = st.progress(0)
        log_container = st.container()

        status_text.text("뉴스 수집 시작...")

        for page in range(1, max_pages + 1):
            if len(all_results) >= max_articles: break
            
            # 진행률 업데이트
            current_progress = min(page / max_pages, 1.0)
            progress_bar.progress(current_progress)
            status_text.text(f"⏳ {page}/{max_pages}페이지 분석 중... (현재 {len(all_results)}건)")
            
            start_index = (page - 1) * 10 + 1
            url = f"https://search.naver.com/search.naver?where=news&query={query}&sm=tab_pge&sort=1&photo=0&pd=3&ds={ds}&de={de}&nso={nso}&start={start_index}"
            
            try:
                response = self.scraper.get(url, headers=self.headers, timeout=10)
                if response.status_code != 200:
                    with log_container: st.error(f"❌ 접속 실패: {response.status_code}")
                    continue

                soup = BeautifulSoup(response.content, 'html.parser')
                
                # 1차 시도
                items = soup.select('a[data-heatmap-target=".tit"]')
                # 2차 시도
                if not items: items = soup.select('a.news_tit')
                
                if not items:
                    with log_container: st.warning(f"⚠️ {page}페이지: 기사를 찾을 수 없습니다.")
                    break

                for t_tag in items:
                    if len(all_results) >= max_articles: break

                    title = t_tag.get_text(strip=True)
                    original_link = t_tag.get('href')
                    
                    # 부모 카드 찾기 (DOM 탐색)
                    card = None
                    curr = t_tag
                    for _ in range(5):
                        if curr.parent:
                            curr = curr.parent
                            if curr.select_one(".sds-comps-profile") or curr.select_one(".news_info") or 'bx' in curr.get('class', []):
                                card = curr
                                break
                    
                    final_link = original_link
                    is_naver = "n.news.naver.com" in original_link
                    press_name = "알 수 없음"
                    paper_info = ""
                    article_date = ""

                    if card:
                        # 1. 네이버 뉴스 링크
                        naver_btn = card.select_one('a[href*="n.news.naver.com"]')
                        if naver_btn:
                            final_link = naver_btn.get('href')
                            is_naver = True
                        
                        # 2. 언론사 이름
                        press_el = card.select_one(".sds-comps-profile-info-title-text, .press_name, .info.press")
                        if press_el:
                            press_name = press_el.get_text(strip=True)
                        
                        # 3. 날짜 및 지면 정보 파싱
                        # span 태그들 모두 확인
                        info_spans = card.select(".info, .subtexts span")
                        for span in info_spans:
                            txt = span.get_text(strip=True)
                            
                            # 날짜 패턴 (1시간 전, 2024.01.01 등)
                            if re.search(r'(\d+[분시일주]\s?전|방금\s?전|\d{4}\.\d{2}\.\d{2}\.?)', txt):
                                article_date = txt
                            
                            # 지면 정보 패턴 (A1면 등)
                            elif re.search(r'[A-Za-z]*\d+면', txt):
                                paper_info = f" ({txt})"

                    full_title = f"{title}{paper_info}"

                    if final_link in seen_links: continue
                    seen_links.add(final_link)
                    
                    all_results.append({
                        'title': full_title,
                        'link': final_link,
                        'press': press_name,
                        'is_naver': is_naver,
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
    [data-testid="stHorizontalBlock"] { gap: 4px !important; align-items: center !important; }
    div[data-testid="column"], div[data-testid="stColumn"] { padding: 0px !important; display: flex !important; justify-content: center !important; }
    .stButton > button { width: 100% !important; height: 38px !important; border-radius: 6px !important; }
    .stLinkButton > a { width: 100% !important; height: 38px !important; display: flex; align-items: center; justify-content: center; font-size: 11px !important; }
    
    .news-card { padding: 8px 12px; border-radius: 6px; border-left: 4px solid #007bff; box-shadow: 0 1px 1px rgba(0,0,0,0.05); display: flex; flex-direction: column; justify-content: center; height: 100%; }
    .bg-scraped { background: #eee !important; border-left: 4px solid #888 !important; opacity: 0.7; }
    .bg-white { background: white !important; }
    .news-title { font-size: 16px !important; font-weight: 600; color: #333; line-height: 1.2; margin-bottom: 2px; }
    .news-meta { font-size: 13px !important; color: #666; }
    .section-header { font-size: 18px; font-weight: 700; color: #333; margin-top: 20px; margin-bottom: 10px; border-bottom: 2px solid #007bff; display: inline-block; }
    
    div[data-testid="stHorizontalBlock"] > div:nth-child(3) button { background-color: #e3f2fd !important; color: #1565c0 !important; border: 1px solid #90caf9 !important; }
    div[data-testid="stHorizontalBlock"] > div:nth-child(4) button { background-color: #e8f5e9 !important; color: #2e7d32 !important; border: 1px solid #a5d6a7 !important; }
    </style>
    """, unsafe_allow_html=True)

# 세션 초기화
for key in ['corp_list', 'rel_list', 'search_results']:
    if key not in st.session_state: st.session_state[key] = []

st.title("🚇 또타 스크립터 (Final Ver)")

# 1. 결과 영역
t_date = get_target_date()
date_header = f"<{t_date.month}월 {t_date.day}일 조간 스크랩>"
final_output = f"{date_header}\n\n[공사 관련 보도]\n" + "".join(st.session_state.corp_list) + "\n[유관기관 관련 보도]\n" + "".join(st.session_state.rel_list)

st.text_area("📋 스크랩 결과", value=final_output, height=max(180, (final_output.count('\n') + 1) * 25))

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
        st.session_state.search_results = NewsScraper().fetch_news(start_d, end_d, keyword, max_a)

# 3. 뉴스 리스트 출력
def display_list(title, items, key_prefix):
    st.markdown(f'<div class="section-header">{title} ({len(items)}건)</div>', unsafe_allow_html=True)
    if not items:
        st.caption("기사가 없습니다.")
        return

    for i, res in enumerate(items):
        # [수정] .get으로 안전하게 가져오기
        date_val = res.get('date', '')
        date_str = f"[{date_val}] " if date_val else ""
        item_txt = f"ㅇ {date_str}{res['title']}_{res['press']}\n{res['link']}\n\n"
        
        is_scraped = (item_txt in st.session_state.corp_list) or (item_txt in st.session_state.rel_list)
        bg = "bg-scraped" if is_scraped else "bg-white"

        with st.container():
            c1, c2, c3, c4 = st.columns([0.73, 0.09, 0.09, 0.09])
            with c1:
                st.markdown(f'''<div class="news-card {bg}">
                    <div class="news-title">{res["title"]}</div>
                    <div class="news-meta">
                        <span style="color: #007bff; font-weight: bold;">{date_val}</span>
                        [{res["press"]}] {"(스크랩됨)" if is_scraped else ""}
                    </div>
                </div>''', unsafe_allow_html=True)
            with c2: st.link_button("원문", res['link'])
            
            with c3:
                if st.button("공사", key=f"c_{key_prefix}_{i}"):
                    if item_txt not in st.session_state.corp_list:
                        st.session_state.corp_list.append(item_txt)
                        st.toast("🏢 공사 관련 기사에 스크랩되었습니다!"); time.sleep(1.5); st.rerun()
            with c4:
                if st.button("유관", key=f"r_{key_prefix}_{i}"):
                    if item_txt not in st.session_state.rel_list:
                        st.session_state.rel_list.append(item_txt)
                        st.toast("🚆 유관기관 기타 기사에 스크랩 되었습니다!"); time.sleep(1.5); st.rerun()
        
        st.markdown("<hr style='margin: 3px 0; border: none; border-top: 1px solid #f0f0f0;'>", unsafe_allow_html=True)

if st.session_state.search_results:
    naver_news = [x for x in st.session_state.search_results if x['is_naver']]
    other_news = [x for x in st.session_state.search_results if not x['is_naver']]
    
    display_list("🟢 네이버 뉴스", naver_news, "n")
    st.write("")
    display_list("🌐 언론사 자체 기사", other_news, "o")

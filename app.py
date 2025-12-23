import streamlit as st
import cloudscraper
from bs4 import BeautifulSoup
import datetime
import time
import re
import streamlit.components.v1 as components

# --- [1. 스마트 날짜 계산 함수 (사용자 제공 기준)] ---
def get_target_date():
    today = datetime.date.today()
    if today.weekday() == 4: target = today + datetime.timedelta(days=3)
    elif today.weekday() == 5: target = today + datetime.timedelta(days=2)
    else: target = today + datetime.timedelta(days=1)

    holidays = [
        datetime.date(2026,1,1), datetime.date(2026,2,16), datetime.date(2026,2,17), datetime.date(2026,2,18),
        datetime.date(2026,3,1), datetime.date(2026,3,2), datetime.date(2026,5,5),
        datetime.date(2026,5,24), datetime.date(2026,5,25), datetime.date(2026,6,6),
        datetime.date(2026,8,15), datetime.date(2026,9,24), datetime.date(2026,9,25),
        datetime.date(2026,9,26), datetime.date(2026,10,3), datetime.date(2026,10,9),
        datetime.date(2026,12,25)
    ]
    
    while target in holidays or target.weekday() >= 5:
        target += datetime.timedelta(days=1)
    return target

# --- [2. 뉴스 스크립터 (요약 기능 및 시간 파싱 강화)] ---
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
        
        status_text = st.empty()
        progress_bar = st.progress(0)
        status_text.text("뉴스 수집 시작...")

        for page in range(1, max_pages + 1):
            if len(all_results) >= max_articles: break
            progress_bar.progress(min(page / max_pages, 1.0))
            
            start_index = (page - 1) * 10 + 1
            url = f"https://search.naver.com/search.naver?where=news&query={query}&sm=tab_pge&sort=1&photo=0&pd=3&ds={ds}&de={de}&nso={nso}&qdt=1&start={start_index}"
            
            try:
                response = self.scraper.get(url, headers=self.headers, timeout=10)
                if response.status_code != 200: continue
                soup = BeautifulSoup(response.content, 'html.parser')
                items = soup.select('a[data-heatmap-target=".tit"]') or soup.select('a.news_tit')
                if not items: break

                for t_tag in items:
                    if len(all_results) >= max_articles: break
                    title = t_tag.get_text(strip=True)
                    original_link = t_tag.get('href')
                    
                    card = None
                    curr = t_tag
                    for _ in range(5):
                        if curr.parent:
                            curr = curr.parent
                            if curr.select_one(".sds-comps-profile") or curr.select_one(".news_info") or 'bx' in curr.get('class', []):
                                card = curr
                                break
                    
                    if card:
                        # 요약문(Snippet) 추출
                        dsc_el = card.select_one(".api_txt_lines.dsc_txt_it, .news_dsc")
                        summary = dsc_el.get_text(strip=True) if dsc_el else "요약 정보가 없습니다."
                        
                        naver_btn = card.select_one('a[href*="n.news.naver.com"]')
                        final_link = naver_btn.get('href') if naver_btn else original_link
                        is_naver = True if naver_btn else False
                        
                        press_el = card.select_one(".sds-comps-profile-info-title-text, .press_name, .info.press")
                        press_name = press_el.get_text(strip=True) if press_el else "알 수 없음"
                        
                        full_text = card.get_text(separator=" ", strip=True)
                        date_match = re.search(r'(\d+\s?(?:분|시간|일|주|초)\s?전|방금\s?전)', full_text)
                        abs_date_match = re.search(r'(\d{4}[\.\-]\d{2}[\.\-]\d{2})', full_text)
                        
                        article_date = ""
                        if date_match:
                            article_date = date_match.group(1)
                        elif abs_date_match:
                            article_date = abs_date_match.group(1).rstrip('.')
                        
                        is_paper = True if re.search(r'([A-Za-z]*\d+면)', full_text) else False
                        paper_info = " (지면)" if is_paper else ""

                        if final_link in seen_links: continue
                        seen_links.add(final_link)
                        
                        all_results.append({
                            'title': f"{title}{paper_info}",
                            'link': final_link,
                            'press': press_name,
                            'is_naver': is_naver,
                            'is_paper': is_paper,
                            'date': article_date,
                            'summary': summary
                        })
                time.sleep(0.3)
            except: continue
        
        progress_bar.empty()
        status_text.empty()
        return all_results

# --- [3. UI 설정 및 CSS] ---
st.set_page_config(page_title="Totta Scriptor for web", layout="wide")

st.markdown("""
    <style>
    /* 뉴스 카드 디자인 */
    .news-card { 
        padding: 12px 16px; border-radius: 8px; border-left: 5px solid #007bff; 
        box-shadow: 0 2px 4px rgba(0,0,0,0.08); background: white; margin-bottom: 5px;
    }
    .bg-scraped { background: #f8f9fa !important; border-left: 5px solid #adb5bd !important; opacity: 0.7; }
    .news-title { font-size: 15px !important; font-weight: 700; color: #222; margin-bottom: 3px; line-height: 1.4; }
    .news-summary { font-size: 12.5px !important; color: #555; margin-bottom: 8px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
    .news-meta { font-size: 12px !important; color: #666; }
    
    /* 버튼 그룹 간격 축소 및 스타일 */
    div[data-testid="column"] { padding: 0 !important; }
    div[data-testid="stHorizontalBlock"] { gap: 0.2rem !important; }
    .stButton > button { 
        width: 100% !important; height: 35px !important; font-size: 11px !important; 
        padding: 0 !important; letter-spacing: -0.5px;
    }
    .section-header { font-size: 17px; font-weight: 700; color: #333; margin: 25px 0 10px 0; border-bottom: 2px solid #007bff; display: inline-block; }
    </style>
    """, unsafe_allow_html=True)

# 세션 상태 초기화
for key in ['corp_list', 'rel_list', 'search_results']:
    if key not in st.session_state: st.session_state[key] = []

st.title("🚇 Totta Scriptor for web")

# 1. 결과 출력 영역
t_date = get_target_date()
date_header = f"<{t_date.month}월 {t_date.day}일 조간 스크랩>"

final_output = f"{date_header}\n\n[공사 관련 보도]\n" + "".join(st.session_state.corp_list) + "\n[유관기관 관련 보도]\n" + "".join(st.session_state.rel_list)
text_height = max(150, (final_output.count('\n') + 1) * 22)
st.text_area("📋 최종 스크랩 텍스트", value=final_output, height=text_height)

if final_output.strip() != date_header.strip():
    components.html(f"""
        <button onclick="copy()" style="width:100%; height:40px; background:#007bff; color:white; border:none; border-radius:5px; cursor:pointer; font-weight:bold;">📋 텍스트 복사하기</button>
        <textarea id="t" style="position:absolute;top:-9999px">{final_output}</textarea>
        <script>function copy(){{var t=document.getElementById("t");t.select();document.execCommand("copy");alert("✅ 복사되었습니다!");}}</script>
    """, height=50)

if st.button("🗑️ 전체 초기화"):
    st.session_state.corp_list, st.session_state.rel_list = [], []
    st.rerun()

st.divider()

# 2. 검색 설정
with st.expander("🔍 뉴스 검색 설정", expanded=True):
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1: kw = st.text_input("검색어", value="서울교통공사")
    with col2: sd = st.date_input("시작", datetime.date.today() - datetime.timedelta(days=1))
    with col3: ed = st.date_input("종료", datetime.date.today())
    mx = st.slider("최대 기사 수", 10, 100, 30)
    if st.button("🚀 뉴스 검색 시작", type="primary", use_container_width=True):
        st.session_state.search_results = NewsScraper().fetch_news(sd, ed, kw, mx)

# 3. 뉴스 리스트 출력 함수
def display_list(title, items, key_p):
    st.markdown(f'<div class="section-header">{title} ({len(items)}건)</div>', unsafe_allow_html=True)
    for i, res in enumerate(items):
        d_val = res.get('date', '')
        d_str = f"[{d_val}] " if d_val else ""
        item_txt = f"ㅇ {d_str}{res['title']}_{res['press']}\n{res['link']}\n\n"
        
        is_scraped = (item_txt in st.session_state.corp_list) or (item_txt in st.session_state.rel_list)
        bg = "bg-scraped" if is_scraped else ""

        col_m, col_b = st.columns([0.7, 0.3], gap="small")
        with col_m:
            st.markdown(f"""<div class="news-card {bg}">
                <div class="news-title">{res['title']}</div>
                <div class="news-summary">{res['summary']}</div>
                <div class="news-meta"><span style="color:#007bff;font-weight:bold;">{d_val}</span> | {res['press']}</div>
            </div>""", unsafe_allow_html=True)
        
        with col_b:
            # 버튼 3개를 1/3씩 배분 (gap 수정 완료)
            b1, b2, b3 = st.columns(3, gap="small")
            with b1: st.link_button("원문", res['link'])
            with b2:
                if st.button("공사", key=f"c_{key_p}_{i}"):
                    if item_txt not in st.session_state.corp_list:
                        st.session_state.corp_list.append(item_txt)
                        st.toast("🏢 공사 보도 추가"); time.sleep(0.5); st.rerun()
            with b3:
                if st.button("기타", key=f"r_{key_p}_{i}"):
                    if item_txt not in st.session_state.rel_list:
                        st.session_state.rel_list.append(item_txt)
                        st.toast("🚆 기타 보도 추가"); time.sleep(0.5); st.rerun()

# 분류 후 출력
if st.session_state.search_results:
    res = st.session_state.search_results
    p_news = [x for x in res if x['is_paper']]
    n_news = [x for x in res if x['is_naver'] and not x['is_paper']]
    o_news = [x for x in res if not x['is_naver'] and not x['is_paper']]
    
    if p_news: display_list("📰 지면 보도", p_news, "p")
    if n_news: display_list("🟢 네이버 뉴스", n_news, "n")
    if o_news: display_list("🌐 기타 뉴스", o_news, "o")

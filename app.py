import streamlit as st
import cloudscraper
from bs4 import BeautifulSoup
import datetime
import time
import google.generativeai as genai

# --- [AI 설정] ---
# Streamlit의 Secrets 기능을 통해 보안상 안전하게 키를 가져옵니다.
# (테스트용으로 직접 넣으시려면 "본인의_API_키"를 입력하세요)
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    AI_ENABLED = True
except:
    AI_ENABLED = False

# --- [뉴스 스크래퍼 클래스] ---
class NewsScraper:
    def summarize_text(self, title):
        if not AI_ENABLED:
            return "AI 키가 설정되지 않아 요약을 제공할 수 없습니다."
        try:
            # 제목을 기반으로 AI에게 한 줄 요약 요청
            prompt = f"다음 뉴스 제목을 분석해서 30자 이내의 아주 짧은 요약문 한 줄만 만들어줘: {title}"
            response = model.generate_content(prompt)
            return response.text.strip()
        except:
            return "요약 중 오류가 발생했습니다."

    def fetch_news(self, start_datetime, end_datetime, keyword, photo_value):
        ds, de = start_datetime.strftime("%Y.%m.%d"), end_datetime.strftime("%Y.%m.%d")
        nso = f"so:dd,p:from{start_datetime.strftime('%Y%m%d')}to{end_datetime.strftime('%Y%m%d')}"
        all_results, seen_links = [], set()
        scraper = cloudscraper.create_scraper()
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36', 'Referer': 'https://www.naver.com/'}

        query = f'"{keyword}"'
        for page in range(1, 4):
            start_index = (page - 1) * 10 + 1
            url = f"https://search.naver.com/search.naver?where=news&query={query}&sm=tab_pge&sort=1&photo={photo_value}&pd=3&ds={ds}&de={de}&nso={nso}&start={start_index}"
            try:
                response = scraper.get(url, headers=headers, timeout=10)
                soup = BeautifulSoup(response.content, 'html.parser')
                items = soup.select('a[data-heatmap-target=".tit"]')
                if not items: break

                for t_tag in items:
                    title = t_tag.get_text(strip=True)
                    link = t_tag.get('href')
                    if link in seen_links: continue
                    
                    card = None
                    curr = t_tag
                    for _ in range(5):
                        if curr.parent:
                            curr = curr.parent
                            if curr.select_one(".sds-comps-profile") or curr.select_one(".news_info"):
                                card = curr; break
                    
                    final_link, is_naver, press_name, date_text = link, "n.news.naver.com" in link, "알 수 없음", "정보 없음"
                    if card:
                        naver_btn = card.select_one('a[href*="n.news.naver.com"]')
                        if naver_btn: final_link = naver_btn.get('href'); is_naver = True
                        press_el = card.select_one(".sds-comps-profile-info-title-text, .press_name, .info.press")
                        if press_el: press_name = press_el.get_text(strip=True)
                        subtext_area = card.select_one(".sds-comps-profile-info-subtexts, .news_info")
                        if subtext_area:
                            for txt in subtext_area.stripped_strings:
                                if ('전' in txt and len(txt) < 15) or ('.' in txt and len(txt) < 15 and txt[0].isdigit()):
                                    date_text = txt; break

                    # AI 요약 생성
                    summary = self.summarize_text(title)

                    seen_links.add(final_link)
                    all_results.append({'title': title, 'link': final_link, 'press': press_name, 'time': date_text, 'is_naver': is_naver, 'summary': summary})
                time.sleep(0.3)
            except: break
        return all_results

# --- [Streamlit 웹 UI] ---
st.set_page_config(page_title="서울교통공사 AI 스크랩", layout="wide")

st.markdown("""
    <style>
    .stButton > button, .stLinkButton > a {
        display: inline-flex !important; align-items: center !important; justify-content: center !important;
        width: 100% !important; height: 40px !important; background-color: #ffffff !important;
        color: #31333F !important; border: 1px solid #d1d5db !important; border-radius: 8px !important;
        text-decoration: none !important; font-size: 14px !important; font-weight: 600 !important; margin: 0 !important;
    }
    .stButton > button:hover, .stLinkButton > a:hover { border-color: #007bff !important; color: #007bff !important; background-color: #f0f7ff !important; }
    .news-card { background: white; padding: 15px; border-radius: 12px; border-left: 6px solid #007bff; margin-bottom: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }
    .ai-summary { background-color: #f3f0ff; color: #553c9a; padding: 10px; border-radius: 8px; font-size: 13px; margin-top: 10px; border-left: 4px solid #9f7aea; }
    </style>
    """, unsafe_allow_html=True)

if 'scrap_list' not in st.session_state: st.session_state.scrap_list = []
if 'search_results' not in st.session_state: st.session_state.search_results = []

st.title("🚇 AI 이슈 스크래퍼")

# 1. 상단: 가변형 스크랩 목록
st.subheader("📋 실시간 스크랩 목록")
if st.session_state.scrap_list:
    final_text = "".join(st.session_state.scrap_list)
    dynamic_height = min(max(150, len(st.session_state.scrap_list) * 55), 450)
    st.text_area("전체 선택 후 복사하세요", value=final_text, height=dynamic_height)
    if st.button("🗑️ 목록 비우기"):
        st.session_state.scrap_list = []
        st.rerun()
else:
    st.info("➕ 추가 버튼을 누르면 AI 요약과 함께 여기에 저장됩니다.")

st.divider()

# 2. 중간: 검색 설정
with st.expander("🔍 검색 조건 설정", expanded=True):
    keyword = st.text_input("필수 포함 단어", value="서울교통공사")
    c1, c2 = st.columns(2)
    with c1: start_date = st.date_input("시작", datetime.date.today() - datetime.timedelta(days=1))
    with c2: end_date = st.date_input("종료", datetime.date.today())
    filter_choice = st.radio("검색 범위", ["네이버 기사", "언론사 자체기사", "모두 보기"], index=0, horizontal=True)

if st.button("🚀 AI 분석 및 검색 시작", type="primary"):
    scraper = NewsScraper()
    with st.spinner('AI가 기사를 하나씩 분석하고 있습니다...'):
        results = scraper.fetch_news(start_date, end_date, keyword, 0)
        st.session_state.search_results = results

# 3. 하단: 검색 결과
if st.session_state.search_results:
    if filter_choice == "네이버 기사": display_results = [r for r in st.session_state.search_results if r['is_naver']]
    elif filter_choice == "언론사 자체기사": display_results = [r for r in st.session_state.search_results if not r['is_naver']]
    else: display_results = st.session_state.search_results

    st.subheader(f"✅ 분석 결과: {len(display_results)}건")
    for i, res in enumerate(display_results):
        with st.container():
            st.markdown(f"""
            <div class="news-card">
                <strong>[{res['press']}]</strong> {res['title']}<br>
                <small style="color:gray;">{res['time']} {'(네이버뉴스)' if res['is_naver'] else ''}</small>
                <div class="ai-summary">✨ <b>AI 한줄요약:</b> {res['summary']}</div>
            </div>
            """, unsafe_allow_html=True)
            
            b1, b2 = st.columns(2)
            with b1: st.link_button("🔗 원문보기", res['link'])
            with b2:
                if st.button("➕ 목록 추가", key=f"add_{i}"):
                    # 요약본을 포함하여 스크랩 텍스트 구성
                    item = f"ㅇ {res['title']}_{res['press']}\n(요약: {res['summary']})\n{res['link']}\n\n"
                    if item not in st.session_state.scrap_list:
                        st.session_state.scrap_list.append(item)
                        st.toast("추가되었습니다!")
                        st.rerun()
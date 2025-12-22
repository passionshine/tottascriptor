import streamlit as st
import cloudscraper
from bs4 import BeautifulSoup
import datetime
import time
import google.generativeai as genai

# --- [1. AI 설정] ---
# Streamlit Cloud의 Settings > Secrets에 GOOGLE_API_KEY를 등록하세요.
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
    HAS_AI = True
except:
    HAS_AI = False

# --- [2. 뉴스 스크래퍼 클래스] ---
class NewsScraper:
    def __init__(self):
        self.scraper = cloudscraper.create_scraper()
        self.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36', 'Referer': 'https://www.naver.com/'}

    # 기사 본문 수집 함수 (네이버 뉴스 전용)
    def get_article_body(self, url):
        if "n.news.naver.com" not in url:
            return "" # 외부 사이트는 구조가 다양하여 일단 생략
        try:
            res = self.scraper.get(url, headers=self.headers, timeout=5)
            soup = BeautifulSoup(res.content, 'html.parser')
            # 네이버 뉴스 본문 선택자
            content = soup.select_one("#newsct_article") or soup.select_one("#articleBodyContents")
            return content.get_text(strip=True)[:2000] if content else ""
        except:
            return ""

    # AI 요약 실행 함수
    def summarize_with_ai(self, title, body, keyword):
        if not HAS_AI:
            return f"'{keyword}' 관련 주요 보도 내용입니다. (API 키 미설정)"
        
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            if not body:
                prompt = f"다음 뉴스 제목을 보고 핵심을 한 줄로 요약해줘: {title}"
            else:
                prompt = f"다음 뉴스 본문을 읽고 '{keyword}' 업무와 관련된 핵심 내용을 1줄로 요약해줘. \n본문: {body}"
            
            response = model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            return "요약을 생성하는 중 오류가 발생했습니다."

    def fetch_news(self, start_datetime, end_datetime, keyword):
        ds, de = start_datetime.strftime("%Y.%m.%d"), end_datetime.strftime("%Y.%m.%d")
        nso = f"so:dd,p:from{start_datetime.strftime('%Y%m%d')}to{end_datetime.strftime('%Y%m%d')}"
        all_results = []
        seen_links = set()
        
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
                    title = t_tag.get_text(strip=True)
                    link = t_tag.get('href')
                    if link in seen_links: continue
                    
                    # 언론사 및 시간 정보 파싱 (생략 - 이전 버전과 동일)
                    is_naver = "n.news.naver.com" in link
                    press_name = "언론사"
                    date_text = "시간"
                    
                    # 실제 파싱 로직 (카드 탐색)
                    card = t_tag.find_parent('div', class_=lambda c: c and ('api_subject_bx' in c or 'sds-comps' in c))
                    if card:
                        p_el = card.select_one(".sds-comps-profile-info-title-text, .press_name")
                        if p_el: press_name = p_el.get_text(strip=True)
                        t_el = card.select_one(".sds-comps-profile-info-subtexts")
                        if t_el: date_text = t_el.get_text(strip=True)

                    seen_links.add(link)
                    all_results.append({'title': title, 'link': link, 'press': press_name, 'time': date_text, 'is_naver': is_naver})
                time.sleep(0.3)
            except: break
        return all_results

# --- [3. Streamlit UI] ---
st.set_page_config(page_title="서울교통공사 스크랩", layout="wide")

st.markdown("""
    <style>
    .stButton > button, .stLinkButton > a {
        display: inline-flex !important; align-items: center !important; justify-content: center !important;
        width: 100% !important; height: 40px !important; background-color: #ffffff !important;
        color: #31333F !important; border: 1px solid #d1d5db !important; border-radius: 8px !important;
        font-size: 14px !important; font-weight: 600 !important;
    }
    .news-card {
        background: white; padding: 15px; border-radius: 12px; border-left: 6px solid #007bff;
        margin-bottom: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    }
    .ai-summary-box {
        background-color: #f3f0ff; color: #553c9a; padding: 10px; border-radius: 8px;
        font-size: 13px; margin-top: 10px; border-left: 4px solid #9f7aea;
    }
    </style>
    """, unsafe_allow_html=True)

if 'scrap_list' not in st.session_state: st.session_state.scrap_list = []
if 'search_results' not in st.session_state: st.session_state.search_results = []

st.title("🚇 뉴스 스크랩 (본문 기반 AI 요약)")

# [최상단] 가변형 스크랩 목록
st.subheader("📋 실시간 스크랩 목록")
if st.session_state.scrap_list:
    final_text = "".join(st.session_state.scrap_list)
    dynamic_height = min(max(150, len(st.session_state.scrap_list) * 55), 450)
    st.text_area("내용 복사", value=final_text, height=dynamic_height)
    if st.button("🗑️ 전체 비우기"):
        st.session_state.scrap_list = []
        st.rerun()
else:
    st.info("검색 후 '➕ 추가'를 누르면 AI가 본문을 요약하여 목록에 담습니다.")

st.divider()

# [중간] 검색 조건
with st.expander("🔍 검색 조건 설정", expanded=True):
    keyword_input = st.text_input("필수 단어", value="서울교통공사")
    c1, c2 = st.columns(2)
    with c1: start_d = st.date_input("시작", datetime.date.today() - datetime.timedelta(days=1))
    with c2: end_d = st.date_input("종료", datetime.date.today())
    filter_opt = st.radio("필터", ["네이버 기사", "언론사 자체기사", "모두 보기"], horizontal=True)

if st.button("🚀 뉴스 검색 시작", type="primary"):
    sc = NewsScraper()
    with st.spinner('검색 중...'):
        st.session_state.search_results = sc.fetch_news(start_d, end_d, keyword_input)

# [하단] 결과 출력
if st.session_state.search_results:
    res_list = st.session_state.search_results
    if filter_opt == "네이버 기사": res_list = [r for r in res_list if r['is_naver']]
    elif filter_opt == "언론사 자체기사": res_list = [r for r in res_list if not r['is_naver']]

    st.subheader(f"✅ 결과: {len(res_list)}건")
    for i, res in enumerate(res_list):
        with st.container():
            st.markdown(f"""
            <div class="news-card">
                <strong>[{res['press']}]</strong> {res['title']}<br>
                <small style="color:gray;">{res['time']} {'(인링크)' if res['is_naver'] else ''}</small>
            </div>
            """, unsafe_allow_html=True)
            
            b1, b2 = st.columns(2)
            with b1: st.link_button("🔗 원문보기", res['link'])
            with b2:
                if st.button("➕ 추가 & 요약", key=f"add_{i}"):
                    sc = NewsScraper()
                    with st.spinner('✨ AI가 본문을 분석하고 있습니다...'):
                        # 1. 본문 긁어오기
                        body_content = sc.get_article_body(res['link'])
                        # 2. AI 요약 실행
                        ai_summary = sc.summarize_with_ai(res['title'], body_content, keyword_input)
                        # 3. 목록에 추가
                        item = f"ㅇ {res['title']}_{res['press']}\n(✨ AI요약: {ai_summary})\n{res['link']}\n\n"
                        if item not in st.session_state.scrap_list:
                            st.session_state.scrap_list.append(item)
                            st.toast("요약과 함께 추가되었습니다!")
                            st.rerun()
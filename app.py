import streamlit as st
import cloudscraper
from bs4 import BeautifulSoup
import datetime
import time
import google.generativeai as genai

# --- [1. AI 설정] ---
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
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.naver.com/'
        }

    # 기사 본문 수집 (AI 요약용)
    def get_article_body(self, url):
        if "n.news.naver.com" not in url: return ""
        try:
            res = self.scraper.get(url, headers=self.headers, timeout=5)
            soup = BeautifulSoup(res.content, 'html.parser')
            content = soup.select_one("#newsct_article") or soup.select_one("#articleBodyContents")
            return content.get_text(strip=True)[:2000] if content else ""
        except: return ""

    # AI 요약 실행
    def summarize_ai(self, title, body, keyword):
        if not HAS_AI: return "API 키 설정 후 사용 가능합니다."
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            prompt = f"다음 뉴스 본문을 읽고 '{keyword}' 업무 관점에서 핵심을 1줄로 요약해줘.\n본문: {body if body else title}"
            return model.generate_content(prompt).text.strip()
        except: return "요약 생성 중 오류가 발생했습니다."

    def fetch_news(self, start_datetime, end_datetime, keyword):
        ds, de = start_datetime.strftime("%Y.%m.%d"), end_datetime.strftime("%Y.%m.%d")
        nso = f"so:dd,p:from{start_datetime.strftime('%Y%m%d')}to{end_datetime.strftime('%Y%m%d')}"
        all_results, seen_links = [], set()
        
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
                    title, link = t_tag.get_text(strip=True), t_tag.get('href')
                    if link in seen_links: continue
                    
                    # [파싱 핵심] 카드 컨테이너 찾기 (SDS 디자인 대응)
                    card = t_tag.find_parent('div', class_=lambda c: c and ('api_subject_bx' in c or 'sds-comps' in c))
                    press_name, date_text, is_naver = "알 수 없음", "정보 없음", "n.news.naver.com" in link
                    
                    if card:
                        # 1. 네이버 인링크 우선 탐색
                        naver_btn = card.select_one('a[href*="n.news.naver.com"]')
                        if naver_btn: link, is_naver = naver_btn.get('href'), True
                        
                        # 2. 언론사 추출 (정밀 클래스 타겟팅)
                        press_el = card.select_one(".sds-comps-profile-info-title-text, .press_name, .info.press")
                        if press_el: press_name = press_el.get_text(strip=True)
                        
                        # 3. 시간 추출 (subtexts 영역 순회)
                        subtext_area = card.select_one(".sds-comps-profile-info-subtexts, .news_info")
                        if subtext_area:
                            for txt in subtext_area.stripped_strings:
                                if ('전' in txt and len(txt) < 15) or ('.' in txt and len(txt) < 15 and txt[0].isdigit()):
                                    date_text = txt; break

                    seen_links.add(link)
                    all_results.append({'title': title, 'link': link, 'press': press_name, 'time': date_text, 'is_naver': is_naver})
                time.sleep(0.3)
            except: break
        return all_results

# --- [3. Streamlit UI] ---
st.set_page_config(page_title="서울교통공사 스크랩", layout="wide")

# CSS: 버튼 3개 동일 스타일 및 1줄 배치
st.markdown("""
    <style>
    .stButton > button, .stLinkButton > a {
        display: inline-flex !important; align-items: center !important; justify-content: center !important;
        width: 100% !important; height: 38px !important; background-color: #ffffff !important;
        color: #31333F !important; border: 1px solid #d1d5db !important; border-radius: 8px !important;
        font-size: 13px !important; font-weight: 600 !important; margin: 0 !important;
        text-decoration: none !important;
    }
    .stButton > button:hover, .stLinkButton > a:hover {
        border-color: #007bff !important; color: #007bff !important; background-color: #f0f7ff !important;
    }
    .news-card {
        background: white; padding: 14px; border-radius: 12px; border-left: 6px solid #007bff;
        margin-bottom: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    }
    .ai-box { background-color: #f3f0ff; color: #553c9a; padding: 10px; border-radius: 8px; font-size: 13px; margin-top: 8px; border-left: 4px solid #9f7aea; }
    </style>
    """, unsafe_allow_html=True)

if 'scrap_list' not in st.session_state: st.session_state.scrap_list = []
if 'search_results' not in st.session_state: st.session_state.search_results = []
if 'summaries' not in st.session_state: st.session_state.summaries = {}

st.title("🚇 뉴스 스크랩 (Mobile)")

# 1. 상단 스크랩 목록 (가변형 높이)
st.subheader("📋 실시간 스크랩 목록")
if st.session_state.scrap_list:
    final_text = "".join(st.session_state.scrap_list)
    dynamic_h = min(max(150, len(st.session_state.scrap_list) * 55), 450)
    st.text_area("내용 복사용", value=final_text, height=dynamic_h)
    if st.button("🗑️ 전체 비우기"): st.session_state.scrap_list = []; st.rerun()
else: st.info("기사를 추가하면 여기에 담깁니다.")

st.divider()

# 2. 검색 조건
with st.expander("🔍 검색 조건 설정", expanded=True):
    keyword = st.text_input("필수 키워드", value="서울교통공사")
    c1, c2 = st.columns(2)
    with c1: start_d = st.date_input("시작", datetime.date.today() - datetime.timedelta(days=1))
    with c2: end_d = st.date_input("종료", datetime.date.today())
    filter_opt = st.radio("필터", ["네이버 기사", "언론사 자체기사", "모두 보기"], index=0, horizontal=True)

if st.button("🚀 뉴스 검색", type="primary"):
    sc = NewsScraper()
    with st.spinner('뉴스를 읽어오는 중...'):
        st.session_state.search_results = sc.fetch_news(start_d, end_d, keyword)

# 3. 결과 출력
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
                <small style="color:gray;">{res['time']} {'(네이버)' if res['is_naver'] else ''}</small>
            </div>
            """, unsafe_allow_html=True)
            
            # AI 요약 박스 (요약 결과가 있을 때만 표시)
            if res['link'] in st.session_state.summaries:
                st.markdown(f'<div class="ai-box">✨ <b>AI 요약:</b> {st.session_state.summaries[res["link"]]}</div>', unsafe_allow_html=True)

            # [3개 버튼 한 줄 배치]
            b1, b2, b3 = st.columns(3)
            with b1:
                if st.button("✨ 요약", key=f"sum_{i}"):
                    sc = NewsScraper()
                    with st.spinner('분석 중...'):
                        body = sc.get_article_body(res['link'])
                        st.session_state.summaries[res['link']] = sc.summarize_ai(res['title'], body, keyword)
                        st.rerun()
            with b2:
                st.link_button("🔗 원문", res['link'])
            with b3:
                if st.button("➕ 추가", key=f"add_{i}"):
                    summary = st.session_state.summaries.get(res['link'], "요약되지 않음")
                    item = f"ㅇ {res['title']}_{res['press']}\n(✨ AI요약: {summary})\n{res['link']}\n\n"
                    if item not in st.session_state.scrap_list:
                        st.session_state.scrap_list.append(item)
                        st.toast("목록에 추가되었습니다!")
                        st.rerun()
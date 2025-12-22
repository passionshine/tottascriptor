import streamlit as st
import cloudscraper
from bs4 import BeautifulSoup
import datetime
import time
import streamlit.components.v1 as components

# --- [1. 스마트 날짜 계산 함수 (2025-2029 공휴일 반영)] ---
def get_target_date():
    today = datetime.date.today()
    
    # 기본적으로 오늘이 금(4)/토(5)면 다음주 월요일, 아니면 내일
    if today.weekday() == 4: target = today + datetime.timedelta(days=3)
    elif today.weekday() == 5: target = today + datetime.timedelta(days=2)
    else: target = today + datetime.timedelta(days=1)

    # 2025년~2029년 대한민국 주요 공휴일 및 대체공휴일 리스트
    holidays = [
        # 2025년
        datetime.date(2025,1,1), datetime.date(2025,1,28), datetime.date(2025,1,29), datetime.date(2025,1,30),
        datetime.date(2025,3,1), datetime.date(2025,3,3), datetime.date(2025,5,5), datetime.date(2025,5,6),
        datetime.date(2025,6,6), datetime.date(2025,8,15), datetime.date(2025,10,3), datetime.date(2025,10,5),
        datetime.date(2025,10,6), datetime.date(2025,10,7), datetime.date(2025,10,8), datetime.date(2025,10,9), datetime.date(2025,12,25),
        # 2026년
        datetime.date(2026,1,1), datetime.date(2026,2,16), datetime.date(2026,2,17), datetime.date(2026,2,18),
        datetime.date(2026,3,1), datetime.date(2026,3,2), datetime.date(2026,5,5), datetime.date(2026,5,24),
        datetime.date(2026,5,25), datetime.date(2026,6,6), datetime.date(2026,8,15), datetime.date(2026,10,3),
        datetime.date(2026,9,24), datetime.date(2026,9,25), datetime.date(2026,9,26), datetime.date(2026,10,9), datetime.date(2026,12,25),
        # 2027년
        datetime.date(2027,1,1), datetime.date(2027,2,6), datetime.date(2027,2,7), datetime.date(2027,2,8),
        datetime.date(2027,2,9), datetime.date(2027,3,1), datetime.date(2027,5,5), datetime.date(2027,5,13),
        datetime.date(2027,6,6), datetime.date(2027,6,7), datetime.date(2027,8,15), datetime.date(2027,8,16),
        datetime.date(2027,10,3), datetime.date(2027,10,4), datetime.date(2027,9,14), datetime.date(2027,9,15),
        datetime.date(2027,9,16), datetime.date(2027,10,9), datetime.date(2027,12,25),
        # 2028년
        datetime.date(2028,1,1), datetime.date(2028,1,26), datetime.date(2028,1,27), datetime.date(2028,1,28),
        datetime.date(2028,3,1), datetime.date(2028,5,2), datetime.date(2028,5,5), datetime.date(2028,6,6),
        datetime.date(2028,8,15), datetime.date(2028,10,3), datetime.date(2028,10,2), datetime.date(2028,10,3),
        datetime.date(2028,10,4), datetime.date(2028,10,9), datetime.date(2028,12,25),
        # 2029년
        datetime.date(2029,1,1), datetime.date(2029,2,12), datetime.date(2029,2,13), datetime.date(2029,2,14),
        datetime.date(2029,3,1), datetime.date(2029,5,5), datetime.date(2029,5,7), datetime.date(2029,5,20),
        datetime.date(2029,5,21), datetime.date(2029,6,6), datetime.date(2029,8,15), datetime.date(2029,10,3),
        datetime.date(2029,9,21), datetime.date(2029,9,22), datetime.date(2029,9,23), datetime.date(2029,9,24),
        datetime.date(2029,10,9), datetime.date(2029,12,25)
    ]

    while target in holidays or target.weekday() >= 5:
        target += datetime.timedelta(days=1)
    return target

# --- [2. 뉴스 스크래퍼] ---
class NewsScraper:
    def __init__(self):
        self.scraper = cloudscraper.create_scraper()
        self.headers = {'User-Agent': 'Mozilla/5.0...', 'Referer': 'https://www.naver.com/'}

    def fetch_news(self, start_d, end_d, keyword):
        ds, de = start_d.strftime("%Y.%m.%d"), end_d.strftime("%Y.%m.%d")
        nso = f"so:dd,p:from{start_d.strftime('%Y%m%d')}to{end_d.strftime('%Y%m%d')}"
        all_results, seen_links = [], set()
        
        url = f"https://search.naver.com/search.naver?where=news&query=\"{keyword}\"&sort=1&pd=3&ds={ds}&de={de}&nso={nso}"
        try:
            res = self.scraper.get(url, headers=self.headers, timeout=10)
            soup = BeautifulSoup(res.content, 'html.parser')
            items = soup.select('a[data-heatmap-target=".tit"]')
            for t_tag in items:
                title, link = t_tag.get_text(strip=True), t_tag.get('href')
                if link in seen_links: continue
                
                card = t_tag.find_parent('div', class_=lambda c: c and ('api_subject_bx' in c or 'sds-comps' in c))
                press, date, is_naver = "알 수 없음", "정보 없음", "n.news.naver.com" in link
                if card:
                    n_btn = card.select_one('a[href*="n.news.naver.com"]')
                    if n_btn: link, is_naver = n_btn.get('href'), True
                    p_el = card.select_one(".sds-comps-profile-info-title-text, .press_name, .info.press")
                    if p_el: press = p_el.get_text(strip=True)
                    t_el = card.select_one(".sds-comps-profile-info-subtexts, .news_info")
                    if t_el:
                        for txt in t_el.stripped_strings:
                            if ('전' in txt and len(txt) < 15) or ('.' in txt and len(txt) < 15 and txt[0].isdigit()):
                                date = txt; break
                seen_links.add(link)
                all_results.append({'title': title, 'link': link, 'press': press, 'time': date, 'is_naver': is_naver})
        except: pass
        return all_results

# --- [3. UI 설정] ---
st.set_page_config(page_title="서울교통공사 스크랩", layout="wide")
st.markdown("<style>.stButton>button { width:100%; font-weight:bold; height:40px; } .news-card { background:white; padding:12px; border-radius:10px; border-left:5px solid #007bff; margin-bottom:8px; }</style>", unsafe_allow_html=True)

if 'corp_list' not in st.session_state: st.session_state.corp_list = []
if 'rel_list' not in st.session_state: st.session_state.rel_list = []
if 'search_results' not in st.session_state: st.session_state.search_results = []

target_date = get_target_date()
date_header = f"<{target_date.month}월 {target_date.day}일({['월','화','수','목','금','토','일'][target_date.weekday()]}) 조간 스크랩>"

st.title("🚇 조간 뉴스 스크랩")

# 상단 목록
final_output = f"{date_header}\n\n[공사 관련 보도]\n"
final_output += "".join(st.session_state.corp_list) if st.session_state.corp_list else "(내용 없음)\n"
final_output += "\n[철도 등 기타 유관기관 관련 보도]\n"
final_output += "".join(st.session_state.rel_list) if st.session_state.rel_list else "(내용 없음)\n"

st.text_area("📋 전체 내용 복사", value=final_output, height=300)

# [카카오톡 전송 기능 추가]
# 이 기능은 모바일에서 카카오톡으로 텍스트를 전달하는 링크를 생성합니다.
kakao_link = f"https://sharer.kakao.com/talk/friends/picker/link?app_key=YOUR_JS_KEY&display_vars=%7B%22title%22%3A%22{date_header}%22%2C%22description%22%3A%22{final_output[:100]}...%22%7D"
# 간단하게 '복사 후 카톡 열기' 형태로 제안드립니다.
if st.button("💬 카카오톡으로 보내기 (전체 복사 후 클릭)"):
    st.info("내용을 복사한 뒤 아래 버튼을 눌러 카카오톡을 실행하세요.")
    components.html(f"""
        <script>
        window.open('kakaolink://send?text=' + encodeURIComponent(`{final_output}`));
        </script>
    """, height=0)

st.divider()

# 검색 및 결과
with st.expander("🔍 검색 설정", expanded=True):
    keyword = st.text_input("키워드", value="서울교통공사")
    filter_opt = st.radio("필터", ["네이버 기사", "모두 보기"], horizontal=True)

if st.button("🚀 검색 시작", type="primary"):
    with st.spinner('검색 중...'):
        st.session_state.search_results = NewsScraper().fetch_news(datetime.date.today()-datetime.timedelta(days=1), datetime.date.today(), keyword)

if st.session_state.search_results:
    res_list = st.session_state.search_results
    if filter_opt == "네이버 기사": res_list = [r for r in res_list if r['is_naver']]
    
    for i, res in enumerate(res_list):
        st.markdown(f"<div class='news-card'><b>[{res['press']}]</b> {res['title']}<br><small>{res['time']}</small></div>", unsafe_allow_html=True)
        b1, b2, b3 = st.columns(3)
        with b1: st.link_button("🔗 원문", res['link'])
        with b2:
            if st.button("🏢 공사 추가", key=f"c_{i}"):
                # 기사 사이 엔터 한 칸 추가 (\n\n)
                item = f"ㅇ {res['title']}_{res['press']}\n{res['link']}\n\n"
                if item not in st.session_state.corp_list:
                    st.session_state.corp_list.append(item); st.rerun()
        with b3:
            if st.button("🚆 유관 추가", key=f"r_{i}"):
                item = f"ㅇ {res['title']}_{res['press']}\n{res['link']}\n\n"
                if item not in st.session_state.rel_list:
                    st.session_state.rel_list.append(item); st.rerun()
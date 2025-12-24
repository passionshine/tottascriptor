import streamlit as st
import cloudscraper
from bs4 import BeautifulSoup
import datetime
import time
import re
import streamlit.components.v1 as components
import json
import os
import smtplib
from email.mime.text import MIMEText

# ==============================================================================
# [0] 사용량 카운트 관리
# ==============================================================================
USAGE_FILE = "usage_log.json"

def get_usage_count():
    if not os.path.exists(USAGE_FILE):
        return 0
    try:
        with open(USAGE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("count", 0)
    except:
        return 0

def increment_usage_count():
    current_count = get_usage_count()
    new_count = current_count + 1
    with open(USAGE_FILE, "w", encoding="utf-8") as f:
        json.dump({"count": new_count}, f)
    return new_count

# ==============================================================================
# [1] 스마트 날짜 계산
# ==============================================================================
def get_target_date():
    today = datetime.date.today()
    if today.weekday() == 4: target = today + datetime.timedelta(days=3)
    elif today.weekday() == 5: target = today + datetime.timedelta(days=2)
    else: target = today + datetime.timedelta(days=1)

    holidays = [
        datetime.date(2026,1,1), datetime.date(2026,2,16), datetime.date(2026,2,17), datetime.date(2026,2,18),
        datetime.date(2026,3,1), datetime.date(2026,3,2), datetime.date(2026,5,5),
        datetime.date(2026,5,24), datetime.date(2026,5,25), datetime.date(2026,6,6),
        datetime.date(2026,8,15), datetime.date(2026,9,24), datetime.date(2026,9,25), datetime.date(2026,9,26),
        datetime.date(2026,10,3), datetime.date(2026,10,9), datetime.date(2026,12,25)
    ]
    
    while target in holidays or target.weekday() >= 5:
        target += datetime.timedelta(days=1)
    return target

# ==============================================================================
# [2] 이메일 발송 함수 (Gmail)
# ==============================================================================
def send_email_gmail(sender_email, sender_pw, receiver_email, subject, content):
    try:
        msg = MIMEText(content, _charset="utf-8")
        msg['Subject'] = subject
        msg['From'] = sender_email
        msg['To'] = receiver_email

        smtp = smtplib.SMTP("smtp.gmail.com", 587)
        smtp.ehlo()
        smtp.starttls()
        
        smtp.login(sender_email, sender_pw)
        smtp.sendmail(sender_email, receiver_email, msg.as_string())
        smtp.quit()
        return True, "✅ 메일 전송 성공!"
    except Exception as e:
        return False, f"❌ 전송 실패: {e}"

# ==============================================================================
# [3] 뉴스 스크래퍼
# ==============================================================================
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
            status_text.text(f"⏳ {page}/{max_pages}페이지 분석 중... (현재 {len(all_results)}건)")
            
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
                    
                    final_link = original_link
                    is_naver = "n.news.naver.com" in original_link
                    press_name = "알 수 없음"
                    paper_info = ""
                    article_date = ""
                    is_paper = False

                    if card:
                        naver_btn = card.select_one('a[href*="n.news.naver.com"]')
                        if naver_btn:
                            final_link = naver_btn.get('href')
                            is_naver = True
                        
                        press_el = card.select_one(".sds-comps-profile-info-title-text, .press_name, .info.press")
                        if press_el: press_name = press_el.get_text(strip=True)
                        full_text = card.get_text(separator=" ", strip=True)
                        
                        date_match = re.search(r'(\d+\s?(?:분|시간|일|주|초)\s?전|방금\s?전)', full_text)
                        abs_date_match = re.search(r'(\d{4}[\.\-]\d{2}[\.\-]\d{2})', full_text)

                        if date_match: article_date = date_match.group(1)
                        elif abs_date_match: article_date = abs_date_match.group(1).rstrip('.')
                        if re.search(r'([A-Za-z]*\d+면)', full_text):
                            paper_info = " (지면)"
                            is_paper = True

                    if final_link in seen_links: continue
                    seen_links.add(final_link)
                    
                    all_results.append({
                        'title': f"{title}{paper_info}",
                        'link': final_link,
                        'press': press_name,
                        'is_naver': is_naver,
                        'is_paper': is_paper,
                        'date': article_date
                    })
                time.sleep(0.3)
            except: continue
        
        progress_bar.empty()
        status_text.empty()
        return all_results

# ==============================================================================
# [4] UI 설정 및 CSS 스타일링
# ==============================================================================
st.set_page_config(page_title="Totta Scriptor for web", layout="wide")

st.markdown("""
    <style>
    /* 1. 뉴스 카드 스타일 */
    .news-card { 
        padding: 12px 16px; border-radius: 8px; border-left: 5px solid #007bff; 
        box-shadow: 0 2px 4px rgba(0,0,0,0.08); 
        background: #f0f8ff; 
        margin-bottom: 15px;
    }
    .bg-scraped { background: #e9ecef !important; border-left: 5px solid #adb5bd !important; opacity: 0.8; }
    .news-title { font-size: 15px !important; font-weight: 700; color: #222; margin-bottom: 5px; line-height: 1.4; }
    .news-meta { font-size: 12px !important; color: #666; }
    
    /* 2. 모든 버튼 기본 초기화 */
    .stButton > button, .stLinkButton > a, .stButton > button p, .stLinkButton > a p { 
        width: 100% !important; height: 38px !important; 
        font-size: 13px !important; font-weight: 600 !important; 
        padding: 0 !important; display: flex; align-items: center; justify-content: center; 
        border-radius: 4px !important; transition: all 0.2s ease !important;
        font-family: "Source Sans Pro", sans-serif !important;
    }

    /* 3. [상단 툴바] 버튼 스타일 통일 */
    div[data-testid="stVerticalBlockBorderWrapper"] .stButton > button {
        background-color: white !important;
        color: #31333F !important;
        border: 1px solid #e0e0e0 !important;
        box-shadow: none !important;
    }
    div[data-testid="stVerticalBlockBorderWrapper"] .stButton > button:hover {
        border-color: #007bff !important;
        color: #007bff !important;
    }
    div[data-testid="stVerticalBlockBorderWrapper"] { 
        padding: 5px !important; margin-bottom: -10px !important; 
    }

    /* 4. [뉴스 리스트] 버튼 3종 세트 */
    /* 1번: 원문보기 (Link) */
    div:not([data-testid="stVerticalBlockBorderWrapper"]) [data-testid="column"]:nth-of-type(1) a {
        border: none !important; background-color: transparent !important; color: #666 !important;
        text-decoration: none !important;
    }
    div:not([data-testid="stVerticalBlockBorderWrapper"]) [data-testid="column"]:nth-of-type(1) a:hover {
        text-decoration: underline !important; color: #007bff !important;
    }
    /* 2번: 공사 기사 (Main) */
    div:not([data-testid="stVerticalBlockBorderWrapper"]) [data-testid="column"]:nth-of-type(2) button {
        border: 1px solid #e0e0e0 !important; background-color: white !important; color: #007bff !important;
    }
    div:not([data-testid="stVerticalBlockBorderWrapper"]) [data-testid="column"]:nth-of-type(2) button:hover {
        border-color: #007bff !important; background-color: #f0f8ff !important; color: #007bff !important;
    }
    /* 3번: 기타 기사 (Sub) */
    div:not([data-testid="stVerticalBlockBorderWrapper"]) [data-testid="column"]:nth-of-type(3) button {
        border: none !important; background-color: transparent !important; color: #888 !important;
    }
    div:not([data-testid="stVerticalBlockBorderWrapper"]) [data-testid="column"]:nth-of-type(3) button:hover {
        color: #333 !important; background-color: #f1f3f5 !important;
    }

    /* 간격 조정 */
    div[data-testid="stVerticalBlock"] > div:has(div[data-testid="stVerticalBlockBorderWrapper"]) + div {
        margin-top: -25px !important; 
    }
    .section-header { font-size: 17px; font-weight: 700; color: #333; margin: 25px 0 10px 0; border-bottom: 2px solid #007bff; display: inline-block; }
    </style>
    """, unsafe_allow_html=True)

# 세션 데이터 초기화
for key in ['corp_list', 'rel_list', 'search_results']:
    if key not in st.session_state: st.session_state[key] = []

# ==============================================================================
# [5] 메인 UI 구성
# ==============================================================================
c1, c2 = st.columns([0.8, 0.2])
with c1: st.title("🚇 Totta Scriptor for web")
with c2:
    current_usage = get_usage_count()
    st.markdown(f"<div style='text-align:right; font-size:14px; color:#888; margin-top:20px;'>🔢 누적 실행: <b>{current_usage}</b>회</div>", unsafe_allow_html=True)

# 날짜 헤더
t_date = get_target_date()
weekdays = ["월", "화", "수", "목", "금", "토", "일"]
w_str = weekdays[t_date.weekday()]
date_header = f"<{t_date.month}월 {t_date.day}일({w_str}) 조간 스크랩>"

final_output = f"{date_header}\n\n[공사 관련 보도]\n" + "".join(st.session_state.corp_list) + "\n[유관기관 관련 등 기타 보도]\n" + "".join(st.session_state.rel_list)

# --------------------------------------------------------------------------
# [POPUP] 이메일 전송 다이얼로그
# --------------------------------------------------------------------------
@st.dialog("📧 결과 메일 보내기")
def email_dialog(content):
    st.caption("아래 정보를 입력하여 뉴스 스크랩 결과를 메일로 전송합니다.")
    
    # Secrets 가져오기
    try:
        default_id = st.secrets["gmail"]["id"]
        default_pw = st.secrets["gmail"]["pw"]
        has_secrets = True
    except:
        default_id = ""
        default_pw = ""
        has_secrets = False

    # 1. 보내는 사람 정보
    if has_secrets:
        # [수정] 성공 메시지 삭제
        sender_id = default_id
        sender_pw = default_pw
    else:
        st.markdown("**보내는 사람**")
        sender_id = st.text_input("보내는 구글 메일", placeholder="example@gmail.com", label_visibility="collapsed")
        sender_pw = st.text_input("구글 앱 비밀번호", type="password", label_visibility="collapsed")

    # 2. 받는 사람 정보 (아이디 + 도메인 선택)
    st.markdown("**받는 사람**", help="아이디 입력 후 도메인을 선택하세요.")
    
    r_c1, r_c2, r_c3 = st.columns([3, 0.4, 3.6])
    
    with r_c1:
        receiver_user = st.text_input("받는사람ID", placeholder="userid", label_visibility="collapsed")
    with r_c2:
        st.markdown("<div style='text-align:center; padding-top:10px; font-weight:bold;'>@</div>", unsafe_allow_html=True)
    with r_c3:
        domains = ["seoulmetro.co.kr", "naver.com", "gmail.com", "daum.net", "google.com", "직접입력"]
        selected_domain = st.selectbox("도메인선택", domains, label_visibility="collapsed")

    if selected_domain == "직접입력":
        custom_domain = st.text_input("도메인 직접 입력", placeholder="company.com")
        if receiver_user and custom_domain:
            receiver_id = f"{receiver_user}@{custom_domain}"
        else:
            receiver_id = ""
    else:
        if receiver_user:
            receiver_id = f"{receiver_user}@{selected_domain}"
        else:
            receiver_id = ""

    # 3. 메일 제목
    st.markdown("**메일 제목**")
    mail_title = st.text_input("메일 제목", value=f"[{t_date.month}/{t_date.day}] 뉴스 스크랩 보고", label_visibility="collapsed")
    
    st.markdown("") 

    if st.button("🚀 전송하기", use_container_width=True, type="primary"):
        if not sender_id or not sender_pw or not receiver_id:
            st.error("이메일 정보를 모두 입력해주세요.")
        elif not content.strip():
            st.warning("보낼 내용이 없습니다.")
        else:
            with st.spinner("전송 중..."):
                success, msg = send_email_gmail(sender_id, sender_pw, receiver_id, mail_title, content)
                if success:
                    st.success(msg)
                    time.sleep(1.5)
                    st.rerun()
                else:
                    st.error(msg)

# --------------------------------------------------------------------------
# [TOOLBAR] 복사 / 메일 / 초기화 버튼
# --------------------------------------------------------------------------
with st.container(border=True):
    cb1, cb2, cb3 = st.columns(3)
    
    # 1. 복사 버튼
    with cb1:
        if final_output.strip() != date_header.strip():
            js_code = f"""
            <style>
                body {{ margin: 0; padding: 0; overflow: hidden; }}
                .custom-btn {{
                    width: 100%; height: 38px; background-color: white; color: #31333F;
                    border: 1px solid #e0e0e0; border-radius: 4px; cursor: pointer;
                    font-size: 13px; font-weight: 600; font-family: "Source Sans Pro", sans-serif;
                    display: flex; align-items: center; justify-content: center;
                    box-sizing: border-box; transition: all 0.2s ease;
                }}
                .custom-btn:hover {{ border-color: #007bff; color: #007bff; outline: none; }}
                .custom-btn:active {{ background-color: #f0f7ff; }}
            </style>
            <textarea id="copy_target" style="position:absolute;top:-9999px;">{final_output}</textarea>
            <button class="custom-btn" onclick="copyToClipboard()">📋 텍스트 복사</button>
            <script>
                function copyToClipboard() {{
                    var t = document.getElementById("copy_target");
                    t.select(); document.execCommand("copy"); alert("✅ 복사되었습니다!");
                }}
            </script>
            """
            components.html(js_code, height=38)
        else:
            st.button("📋 텍스트 복사", disabled=True, use_container_width=True)

    # 2. 메일 보내기 버튼
    with cb2:
        if st.button("📧 메일 보내기", use_container_width=True):
            email_dialog(final_output)

    # 3. 초기화 버튼
    with cb3:
        if st.button("🗑️ 전체 초기화", use_container_width=True):
            st.session_state.corp_list, st.session_state.rel_list = [], []
            st.rerun()

text_height = max(150, (final_output.count('\n') + 1) * 22)
st.text_area("스크랩 결과", value=final_output, height=text_height, label_visibility="collapsed")

st.divider()

# ==============================================================================
# [6] 검색 설정
# ==============================================================================
with st.expander("🔍 뉴스 검색 설정", expanded=True):
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1: kw = st.text_input("검색어", value="서울교통공사")
    with col2: sd = st.date_input("시작", datetime.date.today() - datetime.timedelta(days=1))
    with col3: ed = st.date_input("종료", datetime.date.today())
    mx = st.slider("최대 기사 수", 10, 100, 30)
    
    if st.button("🚀 뉴스 검색 시작", type="primary", use_container_width=True):
        increment_usage_count()
        st.session_state.search_results = NewsScraper().fetch_news(sd, ed, kw, mx)
        st.rerun()

# ==============================================================================
# [7] 리스트 출력 함수
# ==============================================================================
def display_list(title, items, key_p):
    st.markdown(f'<div class="section-header">{title} ({len(items)}건)</div>', unsafe_allow_html=True)
    
    for i, res in enumerate(items):
        d_val = res.get('date', '')
        item_txt = f"ㅇ {res['title']}_{res['press']}\n{res['link']}\n\n"
        
        is_scraped = (item_txt in st.session_state.corp_list) or (item_txt in st.session_state.rel_list)
        bg = "bg-scraped" if is_scraped else ""

        col_m, col_b = st.columns([0.65, 0.35])
        
        with col_m:
            st.markdown(f"""<div class="news-card {bg}">
                <div class="news-title">{res['title']}</div>
                <div class="news-meta"><span style="color:#007bff;font-weight:bold;">{d_val}</span> | {res['press']}</div>
            </div>""", unsafe_allow_html=True)
        
        with col_b:
            b1, b2, b3 = st.columns(3, gap="small")
            
            with b1: # 1번: 원문
                st.link_button("원문보기", res['link'], use_container_width=True)
            with b2: # 2번: 공사
                if st.button("공사보도", key=f"c_{key_p}_{i}", use_container_width=True):
                    if item_txt not in st.session_state.corp_list:
                        st.session_state.corp_list.append(item_txt)
                        st.toast("🏢 공사 관련 스크랩 완료!", icon="✅"); time.sleep(0.5); st.rerun()
                    else:
                        st.toast("⚠️ 이미 추가된 기사입니다", icon="❗")
            with b3: # 3번: 기타
                if st.button("기타보도", key=f"r_{key_p}_{i}", use_container_width=True):
                    if item_txt not in st.session_state.rel_list:
                        st.session_state.rel_list.append(item_txt)
                        st.toast("🚆 유관기관 기타 스크랩 완료!", icon="✅"); time.sleep(0.5); st.rerun()
                    else:
                        st.toast("⚠️ 이미 추가된 기사입니다.", icon="❗")

if st.session_state.search_results:
    res = st.session_state.search_results
    p_news = [x for x in res if x['is_paper']]
    n_news = [x for x in res if x['is_naver'] and not x['is_paper']]
    o_news = [x for x in res if not x['is_naver'] and not x['is_paper']]
    
    if p_news: display_list("📰 지면 보도", p_news, "p")
    if n_news: display_list("🟢 네이버 뉴스", n_news, "n")
    if o_news: display_list("🌐 언론사 자체 뉴스", o_news, "o")

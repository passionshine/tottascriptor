import streamlit as st
import cloudscraper
from bs4 import BeautifulSoup
import datetime
import time
import re
import streamlit.components.v1 as components
import smtplib
from email.mime.text import MIMEText
import os
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# ==============================================================================
# [0] 페이지 기본 설정
# ==============================================================================
st.set_page_config(page_title="Totta Scriptor", layout="wide", page_icon="🚇")

# ==============================================================================
# [1] 로그인(잠금) 시스템
# ==============================================================================
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

def check_password():
    try:
        correct_password = st.secrets["system"]["password"]
    except:
        correct_password = "0000"

    if st.session_state["password_input"] == correct_password:
        st.session_state["logged_in"] = True
    else:
        st.toast("🚫 비밀번호가 일치하지 않습니다.", icon="🚨")

if not st.session_state["logged_in"]:
    st.markdown("""
        <style>
        .login-container { margin-top: 10vh; }
        </style>
        <div class='login-container'></div>
        """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1.5, 2, 1.5])
    
    with col2:
        with st.container(border=True):
            lc1, lc2, lc3 = st.columns([0.5, 3, 0.5])
            with lc2:
                if os.path.exists("logo.png"):
                    st.image("logo.png", use_container_width=True)
                else:
                    st.markdown("<h1 style='text-align: center; color: #2c3e50;'>🚇 Totta Scriptor</h1>", unsafe_allow_html=True)
            
            st.markdown("""
                <div style='text-align: center; margin-bottom: 30px; margin-top: 10px;'>
                    <p style='color: #7f8c8d; font-size: 15px;'>안전한 뉴스 스크랩을 위한 공간입니다.<br>접속을 위해 비밀번호를 입력해주세요.</p>
                </div>
                """, unsafe_allow_html=True)

            st.text_input("비밀번호", type="password", key="password_input", on_change=check_password, placeholder="비밀번호 입력")
            
            st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
            
            if st.button("로그인", use_container_width=True, type="primary"):
                check_password()
                
            st.markdown("""
                <div style='text-align: center; margin-top: 30px; color: #bdc3c7; font-size: 12px;'>
                    © 2025 Totta Scriptor. All rights reserved.
                </div>
                """, unsafe_allow_html=True)
    st.stop()

# ==============================================================================
# [2] 스마트 날짜 계산
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
# [3] 구글 시트 로그 기록 함수 (NEW)
# ==============================================================================
def log_to_gsheets(keyword, count):
    """구글 시트에 검색 기록을 저장합니다."""
    try:
        # 1. 시트 연결 (secrets.toml 정보 사용)
        conn = st.connection("gsheets", type=GSheetsConnection)
        
        # 2. 기존 데이터 읽기 (오류 방지를 위해 5초 캐시)
        try:
            existing_data = conn.read(worksheet="Sheet1", usecols=list(range(5)), ttl=5)
            # 만약 데이터가 비어있으면 초기화
            if existing_data.empty:
                 existing_data = pd.DataFrame(columns=["날짜", "시간", "검색어", "결과수", "상태"])
        except:
             existing_data = pd.DataFrame(columns=["날짜", "시간", "검색어", "결과수", "상태"])

        # 3. 새 데이터 생성
        now = datetime.datetime.now()
        new_row = pd.DataFrame([{
            "날짜": now.strftime("%Y-%m-%d"),
            "시간": now.strftime("%H:%M:%S"),
            "검색어": keyword,
            "결과수": count,
            "상태": "성공"
        }])
        
        # 4. 데이터 합치기
        updated_df = pd.concat([existing_data, new_row], ignore_index=True)
        
        # 5. 시트 업데이트
        conn.update(worksheet="Sheet1", data=updated_df)
        
    except Exception as e:
        # 로그 실패해도 앱은 멈추지 않게 처리
        print(f"로그 기록 실패: {e}")

# ==============================================================================
# [4] 이메일 발송 함수
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
# [5] 뉴스 스크래퍼
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
# [6] UI 설정 및 CSS 스타일링
# ==============================================================================
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
    div:not([data-testid="stVerticalBlockBorderWrapper"]) [data-testid="column"]:nth-of-type(1) a {
        border: none !important; background-color: transparent !important; color: #666 !important;
        text-decoration: none !important;
    }
    div:not([data-testid="stVerticalBlockBorderWrapper"]) [data-testid="column"]:nth-of-type(1) a:hover {
        text-decoration: underline !important; color: #007bff !important;
    }
    div:not([data-testid="stVerticalBlockBorderWrapper"]) [data-testid="column"]:nth-of-type(2) button {
        border: 1px solid #e0e0e0 !important; background-color: white !important; color: #007bff !important;
    }
    div:not([data-testid="stVerticalBlockBorderWrapper"]) [data-testid="column"]:nth-of-type(2) button:hover {
        border-color: #007bff !important; background-color: #f0f8ff !important; color: #007bff !important;
    }
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
# [7] 메인 UI 구성
# ==============================================================================
c1, c2 = st.columns([0.8, 0.2])

with c1: 
    st.title("🚇 Totta Scriptor for web")

# 우측 상단: 로그아웃 버튼
with c2:
    st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True) 
    if st.button("🔒 로그아웃", key="logout_btn", use_container_width=True):
        st.session_state["logged_in"] = False
        st.rerun()

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
    with r_

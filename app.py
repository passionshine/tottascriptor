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
        .stTextInput input[type="password"] {
            font-size: 13px !important;
            height: 32px !important;
            min-height: 32px !important;
            padding: 0 10px !important;
        }
        .stTextInput > div > div {
            height: 32px !important;
            min-height: 32px !important;
        }
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

            st.text_input("비밀번호", type="password", key="password_input", on_change=check_password, placeholder="비밀번호 입력", label_visibility="collapsed")
            
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
# [3] 구글 시트 로그 기록 함수들
# ==============================================================================
def log_to_gsheets(keyword, count):
    """(기본) 검색 기록을 저장합니다."""
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        try:
            existing_data = conn.read(worksheet="Sheet1", ttl=0)
            if existing_data is None or existing_data.empty:
                existing_data = pd.DataFrame(columns=["날짜", "시간", "검색어", "결과수", "상태"])
        except:
             existing_data = pd.DataFrame(columns=["날짜", "시간", "검색어", "결과수", "상태"])

        now = datetime.datetime.now()
        new_row = pd.DataFrame([{
            "날짜": now.strftime("%Y-%m-%d"),
            "시간": now.strftime("%H:%M:%S"),
            "검색어": keyword,
            "결과수": count,
            "상태": "성공"
        }])
        
        updated_df = pd.concat([existing_data, new_row], ignore_index=True)
        conn.update(worksheet="Sheet1", data=updated_df)
    except Exception as e:
        st.error(f"⚠️ 구글 시트 저장 실패: {e}")

def log_email_to_gsheets(receiver, subject):
    """(이메일) 발송 기록을 저장합니다."""
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        try:
            existing_data = conn.read(worksheet="Sheet1", ttl=0)
            if existing_data is None or existing_data.empty:
                existing_data = pd.DataFrame(columns=["날짜", "시간", "검색어", "결과수", "상태"])
        except:
            existing_data = pd.DataFrame(columns=["날짜", "시간", "검색어", "결과수", "상태"])

        now = datetime.datetime.now()
        new_row = pd.DataFrame([{
            "날짜": now.strftime("%Y-%m-%d"),
            "시간": now.strftime("%H:%M:%S"),
            "검색어": f"📧 메일 발송 ({subject})",
            "결과수": 1,
            "상태": f"To: {receiver}"
        }])
        
        updated_df = pd.concat([existing_data, new_row], ignore_index=True)
        conn.update(worksheet="Sheet1", data=updated_df)
    except Exception as e:
        st.error(f"메일 로그 저장 실패: {e}")

def log_copy_to_gsheets():
    """(텍스트 복사) 기록을 저장합니다."""
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        try:
            existing_data = conn.read(worksheet="Sheet1", ttl=0)
            if existing_data is None or existing_data.empty:
                existing_data = pd.DataFrame(columns=["날짜", "시간", "검색어", "결과수", "상태"])
        except:
            existing_data = pd.DataFrame(columns=["날짜", "시간", "검색어", "결과수", "상태"])

        now = datetime.datetime.now()
        new_row = pd.DataFrame([{
            "날짜": now.strftime("%Y-%m-%d"),
            "시간": now.strftime("%H:%M:%S"),
            "검색어": "📋 텍스트 복사 실행",
            "결과수": 1,
            "상태": "클립보드 복사"
        }])
        
        updated_df = pd.concat([existing_data, new_row], ignore_index=True)
        conn.update(worksheet="Sheet1", data=updated_df)
    except Exception as e:
        print(f"복사 로그 저장 실패: {e}")

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
# [5] 뉴스 스크래퍼 (제목+언론사 중복 제거 기능 추가)
# ==============================================================================
class NewsScraper:
    def __init__(self):
        self.scraper = cloudscraper.create_scraper()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.naver.com/'
        }

    def parse_date(self, date_str):
        now = datetime.datetime.now()
        try:
            if "분 전" in date_str:
                minutes = int(re.search(r'(\d+)', date_str).group(1))
                return now - datetime.timedelta(minutes=minutes)
            elif "시간 전" in date_str:
                hours = int(re.search(r'(\d+)', date_str).group(1))
                return now - datetime.timedelta(hours=hours)
            elif "일 전" in date_str:
                days = int(re.search(r'(\d+)', date_str).group(1))
                return now - datetime.timedelta(days=days)
            elif "주 전" in date_str:
                weeks = int(re.search(r'(\d+)', date_str).group(1))
                return now - datetime.timedelta(weeks=weeks)
            else:
                return datetime.datetime.strptime(date_str.replace('.', '-'), "%Y-%m-%d")
        except:
            return now - datetime.timedelta(days=365)

    def fetch_news(self, start_d, end_d, keywords, max_articles, include_others=True):
        if isinstance(keywords, str):
            keywords = [keywords]

        priority_map = {
            "서울교통공사": 0,
            "서울지하철": 1,
            "도시철도": 2
        }

        ds, de = start_d.strftime("%Y.%m.%d"), end_d.strftime("%Y.%m.%d")
        nso = f"so:dd,p:from{start_d.strftime('%Y%m%d')}to{end_d.strftime('%Y%m%d')}"
        
        all_results = []
        seen_links = set()
        seen_title_press = set() # [NEW] 제목+언론사 중복 체크용
        
        status_text = st.empty()
        progress_bar = st.progress(0)
        status_text.text("뉴스 수집 시작...")

        total_keywords = len(keywords)
        
        for k_idx, keyword in enumerate(keywords):
            query = f'"{keyword}"'
            rank_score = priority_map.get(keyword, 99)
            
            limit_per_keyword = max_articles if total_keywords == 1 else int(max_articles * 0.6)
            base_url = "https://search.naver.com/search.naver?where=news&query={}&sm=tab_pge&sort=1&photo=0&pd=3&ds={}&de={}&nso={}&qdt=1&start={}"
            
            current_count = 0
            max_pages = (limit_per_keyword // 10) + 3 

            for page in range(1, max_pages + 1):
                if current_count >= limit_per_keyword: break
                
                overall_progress = (k_idx / total_keywords) + ((page / max_pages) / total_keywords)
                progress_bar.progress(min(overall_progress, 1.0))
                status_text.text(f"🔍 '{keyword}' 검색 중... ({current_count}건 수집)")
                
                start_index = (page - 1) * 10 + 1
                url = base_url.format(query, ds, de, nso, start_index)
                
                try:
                    response = self.scraper.get(url, headers=self.headers, timeout=10)
                    if response.status_code != 200: continue

                    soup = BeautifulSoup(response.content, 'html.parser')
                    items = soup.select('a[data-heatmap-target=".tit"]') or soup.select('a.news_tit')
                    if not items: break

                    for t_tag in items:
                        if current_count >= limit_per_keyword: break
                        
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

                        if not include_others and not is_naver and not is_paper:
                            continue

                        # [NEW] 제목+언론사 중복 체크 (띄어쓰기 없이 비교)
                        unique_key = (title.replace(" ", ""), press_name.replace(" ", ""))
                        
                        if final_link in seen_links or unique_key in seen_title_press: 
                            continue
                            
                        seen_links.add(final_link)
                        seen_title_press.add(unique_key)
                        
                        all_results.append({
                            'title': f"{title}{paper_info}",
                            'link': final_link,
                            'press': press_name,
                            'is_naver': is_naver,
                            'is_paper': is_paper,
                            'date': article_date,
                            'source_keyword': keyword,
                            'datetime': self.parse_date(article_date),
                            'rank': rank_score
                        })
                        current_count += 1
                    time.sleep(0.3)
                except: continue

        progress_bar.empty()
        status_text.empty()
        
        all_results.sort(key=lambda x: x['datetime'], reverse=True)
        all_results.sort(key=lambda x: x['rank'])
        
        return all_results[:max_articles]

# ==============================================================================
# [6] UI 설정 및 CSS 스타일링
# ==============================================================================
st.markdown("""
    <style>
    .news-card { 
        padding: 12px 16px; border-radius: 8px; border-left: 5px solid #007bff; 
        box-shadow: 0 2px 4px rgba(0,0,0,0.08); 
        background: #f0f8ff; 
        margin-bottom: 15px;
    }
    .bg-scraped { background: #e9ecef !important; border-left: 5px solid #adb5bd !important; opacity: 0.8; }
    .news-title { font-size: 15px !important; font-weight: 700; color: #222; margin-bottom: 5px; line-height: 1.4; }
    .news-meta { font-size: 12px !important; color: #666; }
    
    .keyword-badge {
        background-color: #e3f2fd; color: #1565c0; 
        padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: 600;
        margin-right: 6px; border: 1px solid #bbdefb;
    }
    
    .stButton > button, .stLinkButton > a, .stButton > button p, .stLinkButton > a p { 
        width: 100% !important; height: 38px !important; 
        font-size: 13px !important; font-weight: 600 !important; 
        padding: 0 !important; display: flex; align-items: center; justify-content: center; 
        border-radius: 4px !important; transition: all 0.2s ease !important;
        font-family: "Source Sans Pro", sans-serif !important;
    }

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

with c2:
    st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True) 
    if st.button("🔒 로그아웃", key="logout_btn", use_container_width=True):
        st.session_state["logged_in"] = False
        st.rerun()

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
    
    try:
        default_id = st.secrets["gmail"]["id"]
        default_pw = st.secrets["gmail"]["pw"]
        has_secrets = True
    except:
        default_id = ""
        default_pw = ""
        has_secrets = False

    if has_secrets:
        sender_id = default_id
        sender_pw = default_pw
    else:
        st.markdown("**보내는 사람**")
        sender_id = st.text_input("보내는 구글 메일", placeholder="example@gmail.com", label_visibility="collapsed")
        sender_pw = st.text_input("구글 앱 비밀번호", type="password", label_visibility="collapsed")

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

    st.markdown("**메일 제목**")
    mail_title = st.text_input("메일 제목", value=f"[{t_date.month}/{t_date.day}] 뉴스 스크랩 보고", label_visibility="collapsed")
    
    st.markdown("") 

    if st.button("🚀 전송하기", key="btn_send_email", use_container_width=True, type="primary"):
        if not sender_id or not sender_pw or not receiver_id:
            st.error("이메일 정보를 모두 입력해주세요.")
        elif not content.strip():
            st.warning("보낼 내용이 없습니다.")
        else:
            with st.spinner("전송 중..."):
                success, msg = send_email_gmail(sender_id, sender_pw, receiver_id, mail_title, content)
                
                if success:
                    log_email_to_gsheets(receiver_id, mail_title)
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
    
    with cb1:
        if st.button("📋 텍스트 복사", key="btn_copy_text", use_container_width=True):
            if final_output.strip() != date_header.strip():
                log_copy_to_gsheets()
                js_code = f"""
                <textarea id="copy_target" style="position:absolute;top:-9999px;">{final_output}</textarea>
                <script>
                    var t = document.getElementById("copy_target");
                    t.select();
                    document.execCommand("copy");
                </script>
                """
                components.html(js_code, height=0)
                st.toast("✅ 텍스트가 복사되었습니다!", icon="📋")
            else:
                st.toast("⚠️ 복사할 내용이 없습니다.", icon="❗")

    with cb2:
        if st.button("📧 메일 보내기", use_container_width=True):
            email_dialog(final_output)

    with cb3:
        if st.button("🗑️ 전체 초기화", use_container_width=True):
            st.session_state.corp_list, st.session_state.rel_list = [], []
            st.rerun()

text_height = max(150, (final_output.count('\n') + 1) * 22)
st.text_area("스크랩 결과", value=final_output, height=text_height, label_visibility="collapsed")

st.divider()

# ==============================================================================
# [8] 검색 설정
# ==============================================================================
with st.expander("🔍 뉴스 검색 설정", expanded=True):
    mode = st.radio("검색 모드 선택", ["🤖 자동 (서울교통공사 + 서울지하철 + 도시철도)", "⌨️ 수동 입력"], horizontal=True)
    st.markdown("<div style='margin-bottom:10px;'></div>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns([2, 1, 1])
    
    if "수동" in mode:
        with col1: 
            user_kw = st.text_input("검색어 입력", value="서울교통공사")
            search_keywords = [user_kw]
            log_keyword = user_kw
    else:
        with col1: 
            st.info("💡 3가지 키워드로 동시에 검색하고 우선순위별로 정렬합니다.")
            search_keywords = ["서울교통공사", "서울지하철", "도시철도"]
            log_keyword = "🤖 자동(복합키워드)"

    with col2: sd = st.date_input("시작", datetime.date.today() - datetime.timedelta(days=1))
    with col3: ed = st.date_input("종료", datetime.date.today())
    
    c_opt1, c_opt2 = st.columns([1, 1])
    with c_opt1:
        mx = st.slider("최대 기사 수 (전체 합계)", 10, 100, 30)
    with c_opt2:
        st.markdown("<div style='margin-top: 25px;'></div>", unsafe_allow_html=True)
        include_others = st.checkbox("🌐 언론사 자체 기사(Outlink) 포함", value=False, help="체크하면 네이버 뉴스 링크가 없는 언론사 자체 페이지도 수집합니다.")

    if st.button("🚀 뉴스 검색 시작", type="primary", use_container_width=True):
        results = NewsScraper().fetch_news(sd, ed, search_keywords, mx, include_others)
        
        if not results:
            st.error("검색 결과가 없습니다. 날짜 범위나 키워드를 확인해주세요.")
        else:
            st.session_state.search_results = results
            log_to_gsheets(log_keyword, len(results))
            st.rerun()

# ==============================================================================
# [9] 리스트 출력 함수
# ==============================================================================
def display_list(title, items, key_p):
    st.markdown(f'<div class="section-header">{title} ({len(items)}건)</div>', unsafe_allow_html=True)
    
    for i, res in enumerate(items):
        d_val = res.get('date', '')
        src_kw = res.get('source_keyword', '')
        
        item_txt = f"ㅇ {res['title']}_{res['press']}\n{res['link']}\n\n"
        
        is_scraped = (item_txt in st.session_state.corp_list) or (item_txt in st.session_state.rel_list)
        bg = "bg-scraped" if is_scraped else ""

        col_m, col_b = st.columns([0.65, 0.35])
        
        with col_m:
            badge_html = f"<span class='keyword-badge'>🔍 {src_kw}</span>" if src_kw else ""
            
            st.markdown(f"""<div class="news-card {bg}">
                <div class="news-title">{badge_html}{res['title']}</div>
                <div class="news-meta"><span style="color:#007bff;font-weight:bold;">{d_val}</span> | {res['press']}</div>
            </div>""", unsafe_allow_html=True)
        
        with col_b:
            b1, b2, b3 = st.columns(3, gap="small")
            
            with b1: 
                st.link_button("원문보기", res['link'], use_container_width=True)
            with b2: 
                if st.button("공사보도", key=f"c_{key_p}_{i}", use_container_width=True):
                    if item_txt not in st.session_state.corp_list:
                        st.session_state.corp_list.append(item_txt)
                        st.toast("🏢 공사 관련 스크랩 완료!", icon="✅"); time.sleep(0.5); st.rerun()
                    else:
                        st.toast("⚠️ 이미 추가된 기사입니다", icon="❗")
            with b3: 
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

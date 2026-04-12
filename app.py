"""Diet Tracker — Streamlit 앱 엔트리포인트.

Google OAuth 인증 + st.navigation 기반 멀티페이지 라우팅.
"""

import streamlit as st

from services.auth_service import is_logged_in, render_sidebar_account

st.set_page_config(
    page_title="식단 트래커",
    page_icon="🥗",
    layout="wide",
    initial_sidebar_state="collapsed",
)

render_sidebar_account()

PAGES = {
    "기록": [
        st.Page("pages/record.py", title="식단 및 운동 기록", icon=":material/restaurant:"),
    ],
    "분석": [
        st.Page("pages/calendar_view.py", title="캘린더", icon=":material/calendar_month:"),
        st.Page("pages/trends.py", title="트렌드", icon=":material/insights:"),
    ],
    "설정": [
        st.Page("pages/profile.py", title="프로필", icon=":material/person:"),
        st.Page("pages/favorites.py", title="즐겨찾기", icon=":material/star:"),
    ],
}

pg = st.navigation(PAGES, position="sidebar")

# ─── 상단 네비게이션 바 (아이콘만, HTML로 가로 고정) ─────────
if is_logged_in():
    st.markdown("""
    <style>
    .nav-bar { display:flex; justify-content:center; gap:4px; padding:4px 0; }
    .nav-bar a {
        text-decoration:none; font-size:24px; padding:6px 14px;
        border-radius:10px; background:rgba(30,41,59,0.6);
        transition: background 0.15s;
    }
    .nav-bar a:hover { background:rgba(59,130,246,0.3); }
    </style>
    <div class="nav-bar">
        <a href="/식단_및_운동_기록" target="_self" title="식단 및 운동 기록">🍽️</a>
        <a href="/캘린더" target="_self" title="캘린더">📅</a>
        <a href="/트렌드" target="_self" title="트렌드">📊</a>
        <a href="/프로필" target="_self" title="프로필">👤</a>
        <a href="/즐겨찾기" target="_self" title="즐겨찾기">⭐</a>
    </div>
    """, unsafe_allow_html=True)

pg.run()

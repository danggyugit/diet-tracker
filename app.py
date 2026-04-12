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

# ─── 상단 네비게이션 바 ──────────────────────────────────────
if is_logged_in():
    nav_cols = st.columns(5, gap="small")
    nav_cols[0].page_link("pages/record.py", label="기록", icon="🍽️", use_container_width=True)
    nav_cols[1].page_link("pages/calendar_view.py", label="캘린더", icon="📅", use_container_width=True)
    nav_cols[2].page_link("pages/trends.py", label="트렌드", icon="📊", use_container_width=True)
    nav_cols[3].page_link("pages/profile.py", label="프로필", icon="👤", use_container_width=True)
    nav_cols[4].page_link("pages/favorites.py", label="즐겨찾기", icon="⭐", use_container_width=True)
    st.divider()

pg.run()

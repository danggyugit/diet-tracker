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

# ─── 상단 네비게이션 바 (아이콘만) ────────────────────────────
if is_logged_in():
    # page_link 버튼 크기를 최소화하는 CSS
    st.markdown("""<style>
    div[data-testid="stPageLink"] a {
        padding: 0.3rem 0.5rem !important;
        min-height: 0 !important;
    }
    div[data-testid="stPageLink"] a span {
        font-size: 0 !important;
    }
    div[data-testid="stPageLink"] a span[data-testid="stIconEmoji"] {
        font-size: 22px !important;
        margin: 0 !important;
    }
    </style>""", unsafe_allow_html=True)
    nc = st.columns(5, gap="small")
    nc[0].page_link("pages/record.py", icon="🍽️", label="기록", use_container_width=True)
    nc[1].page_link("pages/calendar_view.py", icon="📅", label="캘린더", use_container_width=True)
    nc[2].page_link("pages/trends.py", icon="📊", label="트렌드", use_container_width=True)
    nc[3].page_link("pages/profile.py", icon="👤", label="프로필", use_container_width=True)
    nc[4].page_link("pages/favorites.py", icon="⭐", label="즐겨찾기", use_container_width=True)

pg.run()

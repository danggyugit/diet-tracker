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

# 상단 여백 조정 (사이드바 토글 버튼과 pills 겹침 방지)
st.markdown("""<style>
.block-container { padding-top:4rem !important; }
</style>""", unsafe_allow_html=True)

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
    NAV_LABELS = ["기록", "캘린더", "트렌드", "프로필", "즐겨찾기"]
    NAV_ICONS = [
        ":material/restaurant:",
        ":material/calendar_month:",
        ":material/insights:",
        ":material/person:",
        ":material/star:",
    ]
    NAV_PAGES = [
        "pages/record.py", "pages/calendar_view.py",
        "pages/trends.py", "pages/profile.py", "pages/favorites.py",
    ]
    selected = st.pills(
        "nav", NAV_LABELS,
        icons=NAV_ICONS,
        selection_mode="single", default=None,
        label_visibility="collapsed",
    )
    if selected:
        idx = NAV_LABELS.index(selected)
        st.switch_page(NAV_PAGES[idx])

pg.run()

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
    NAV_MAP = {
        "🍽️": "pages/record.py",
        "📅": "pages/calendar_view.py",
        "📊": "pages/trends.py",
        "👤": "pages/profile.py",
        "⭐": "pages/favorites.py",
    }
    NAV_LABELS = ["기록", "캘린더", "트렌드", "프로필", "즐겨찾기"]

    selected = st.pills(
        "nav", list(NAV_MAP.keys()),
        selection_mode="single", default=None,
        label_visibility="collapsed",
    )
    # 아이콘 아래 라벨
    st.markdown(
        "<div style='display:flex;justify-content:space-around;margin-top:-10px;margin-bottom:8px;'>"
        + "".join(f"<span style='font-size:10px;color:#64748B;'>{l}</span>" for l in NAV_LABELS)
        + "</div>",
        unsafe_allow_html=True,
    )
    if selected:
        st.switch_page(NAV_MAP[selected])

pg.run()

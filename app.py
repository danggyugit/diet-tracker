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

# ─── 상단 네비게이션 바 (HTML grid + query_params) ────────────
if is_logged_in():
    NAV_ITEMS = [
        ("🍽️", "record", "pages/record.py"),
        ("📅", "calendar", "pages/calendar_view.py"),
        ("📊", "trends", "pages/trends.py"),
        ("👤", "profile", "pages/profile.py"),
        ("⭐", "favorites", "pages/favorites.py"),
    ]
    NAV_LOOKUP = {key: path for _, key, path in NAV_ITEMS}

    qp = st.query_params
    if "nav" in qp:
        target = NAV_LOOKUP.get(qp["nav"])
        del st.query_params["nav"]
        if target:
            st.switch_page(target)

    btn_style = (
        "background:rgba(30,41,59,0.5);border:1px solid rgba(148,163,184,0.2);"
        "color:#F8FAFC;padding:10px 0;border-radius:10px;text-align:center;"
        "text-decoration:none;font-size:20px;"
    )
    nav_html = "<div style='display:grid;grid-template-columns:repeat(5,1fr);gap:6px;margin-bottom:10px;'>"
    for icon, key, _ in NAV_ITEMS:
        nav_html += f"<a href='?nav={key}' target='_self' style='{btn_style}'>{icon}</a>"
    nav_html += "</div>"
    st.markdown(nav_html, unsafe_allow_html=True)

pg.run()

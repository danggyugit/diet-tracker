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
    NAV_MAP = {
        "🍽️": "pages/record.py",
        "📅": "pages/calendar_view.py",
        "📊": "pages/trends.py",
        "👤": "pages/profile.py",
        "⭐": "pages/favorites.py",
    }

    # pills 스타일: 전체 너비 균등 분배
    st.markdown("""<style>
    /* pills 컨테이너를 전체 너비로 */
    div[data-testid="stPills"] > div {
        width:100% !important;
        display:flex !important;
        gap:6px !important;
    }
    /* 각 pill 버튼을 균등 크기로 */
    div[data-testid="stPills"] button {
        flex:1 !important;
        font-size:24px !important;
        padding:10px 0 !important;
        border-radius:12px !important;
        border:1px solid rgba(148,163,184,0.15) !important;
        background:rgba(30,41,59,0.5) !important;
        justify-content:center !important;
        transition: all 0.2s !important;
    }
    div[data-testid="stPills"] button:hover {
        background:rgba(59,130,246,0.2) !important;
        border-color:rgba(59,130,246,0.4) !important;
    }
    /* 선택된 pill */
    div[data-testid="stPills"] button[aria-checked="true"] {
        background:rgba(59,130,246,0.25) !important;
        border-color:#3B82F6 !important;
        box-shadow:0 0 10px rgba(59,130,246,0.25) !important;
    }
    </style>""", unsafe_allow_html=True)

    selected = st.pills(
        "nav", list(NAV_MAP.keys()),
        selection_mode="single", default=None,
        label_visibility="collapsed",
    )
    if selected:
        st.switch_page(NAV_MAP[selected])

pg.run()

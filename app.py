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

# ─── 상단 네비게이션 바 (아이콘만, 가로 고정) ─────────────────
if is_logged_in():
    # st.columns는 모바일에서 세로로 쌓이므로, page_link를 먼저 렌더링하고
    # CSS로 가로 배치 + 텍스트 숨김 처리
    st.markdown("""<style>
    /* 네비 컨테이너를 flex 가로 배치로 강제 */
    div.nav-container [data-testid="stHorizontalBlock"] {
        flex-wrap: nowrap !important;
        gap: 0.25rem !important;
    }
    /* 각 컬럼이 줄바꿈되지 않도록 */
    div.nav-container [data-testid="stHorizontalBlock"] > div {
        min-width: 0 !important;
        flex: 1 !important;
    }
    /* page_link 스타일 */
    div.nav-container [data-testid="stPageLink"] a {
        padding: 0.4rem 0 !important;
        min-height: 0 !important;
        justify-content: center !important;
    }
    /* 텍스트 숨기기 */
    div.nav-container [data-testid="stPageLink"] a p {
        font-size: 0 !important;
        line-height: 0 !important;
        height: 0 !important;
        overflow: hidden !important;
    }
    /* 아이콘 크기 */
    div.nav-container [data-testid="stPageLink"] a img,
    div.nav-container [data-testid="stPageLink"] a span[data-testid="stIconEmoji"] {
        font-size: 24px !important;
        margin: 0 !important;
    }
    </style>""", unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="nav-container">', unsafe_allow_html=True)
        nc = st.columns(5, gap="small")
        nc[0].page_link("pages/record.py", icon="🍽️", label="기록", use_container_width=True)
        nc[1].page_link("pages/calendar_view.py", icon="📅", label="캘린더", use_container_width=True)
        nc[2].page_link("pages/trends.py", icon="📊", label="트렌드", use_container_width=True)
        nc[3].page_link("pages/profile.py", icon="👤", label="프로필", use_container_width=True)
        nc[4].page_link("pages/favorites.py", icon="⭐", label="즐겨찾기", use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

pg.run()

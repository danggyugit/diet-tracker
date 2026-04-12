"""Google OAuth 인증 서비스 (Streamlit st.login 래퍼)."""

import streamlit as st


def is_logged_in() -> bool:
    try:
        return bool(st.user.is_logged_in)
    except Exception:
        return False


def get_user_email() -> str | None:
    return getattr(st.user, "email", None) if is_logged_in() else None


def get_user_name() -> str:
    return getattr(st.user, "name", "") if is_logged_in() else ""


def get_user_picture() -> str:
    return getattr(st.user, "picture", "") if is_logged_in() else ""


def require_auth() -> str:
    """페이지 가드: 미로그인 시 로그인 버튼 + st.stop(). 로그인 시 email 반환."""
    if not is_logged_in():
        st.title("🥗 식단 트래커")
        st.markdown("Google 계정으로 로그인하면 식단을 기록하고 분석할 수 있습니다.")
        if st.button("Google로 로그인", type="primary"):
            st.login("google")
        st.stop()

    email = get_user_email()
    if not email:
        st.error("사용자 정보를 가져올 수 없습니다. 로그아웃 후 다시 로그인해 주세요.")
        if st.button("로그아웃"):
            st.logout()
        st.stop()
    return email


def render_sidebar_account() -> None:
    """사이드바에 프로필 카드 + 로그아웃 버튼 표시."""
    if not is_logged_in():
        return

    name = get_user_name() or "사용자"
    email = get_user_email() or ""
    picture = get_user_picture()

    col_profile, col_logout = st.sidebar.columns([4, 1], vertical_alignment="center")
    with col_profile:
        avatar_html = (
            f'<img src="{picture}" style="width:32px;height:32px;border-radius:50%;'
            f'object-fit:cover;vertical-align:middle;" onerror="this.style.display=\'none\'"/>'
            if picture else ""
        )
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:8px;padding:6px;'
            f'background:rgba(30,41,59,0.5);border-radius:8px;">'
            f'{avatar_html}'
            f'<div style="overflow:hidden;min-width:0;">'
            f'<div style="font-weight:600;color:#F8FAFC;font-size:13px;'
            f'overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{name}</div>'
            f'<div style="font-size:10px;color:#94A3B8;'
            f'overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{email}</div>'
            f'</div></div>',
            unsafe_allow_html=True,
        )
    with col_logout:
        if st.button("⇥", key="logout_btn", help="로그아웃"):
            st.logout()

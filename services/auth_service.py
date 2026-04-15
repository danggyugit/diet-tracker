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


def _render_landing_page() -> None:
    """로그인 전 랜딩 페이지 (앱 소개, 기능, 개발자 정보)."""
    # ─── 헤더 ────────────────────────────────────────────────
    st.markdown(
        """
        <div style='text-align:center;padding:40px 20px 20px;'>
            <div style='font-size:64px;'>🥗</div>
            <h1 style='margin:10px 0;font-size:42px;font-weight:700;'>AI 식단 트래커</h1>
            <p style='font-size:18px;color:#94A3B8;margin:0 0 8px;'>
                사진 한 장으로 칼로리 · 영양소 자동 계산
            </p>
            <p style='font-size:14px;color:#64748B;margin:0;'>
                체중 감량 목표에 맞춘 개인화된 식단 관리
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ─── 로그인 CTA ──────────────────────────────────────────
    cta1, cta2, cta3 = st.columns([1, 2, 1])
    with cta2:
        if st.button("🔐 Google 계정으로 시작하기", type="primary", use_container_width=True):
            st.login("google")
        st.caption("무료 · Google 계정만 있으면 바로 사용 가능")

    st.markdown("---")

    # ─── 주요 기능 ──────────────────────────────────────────
    st.markdown("### ✨ 주요 기능")

    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        st.markdown(
            """
            <div style='background:rgba(30,41,59,0.5);border-radius:12px;padding:20px;height:170px;'>
                <div style='font-size:36px;'>📷</div>
                <div style='font-weight:600;font-size:16px;margin-top:8px;'>AI 사진 분석</div>
                <div style='font-size:13px;color:#94A3B8;margin-top:6px;line-height:1.5;'>
                    음식 사진을 올리면 Gemini AI가<br>칼로리·영양소를 자동 계산
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with fc2:
        st.markdown(
            """
            <div style='background:rgba(30,41,59,0.5);border-radius:12px;padding:20px;height:170px;'>
                <div style='font-size:36px;'>📊</div>
                <div style='font-weight:600;font-size:16px;margin-top:8px;'>개인 맞춤 목표</div>
                <div style='font-size:13px;color:#94A3B8;margin-top:6px;line-height:1.5;'>
                    체중·활동량·감량 강도 기반<br>과학적 영양소 목표 자동 계산
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with fc3:
        st.markdown(
            """
            <div style='background:rgba(30,41,59,0.5);border-radius:12px;padding:20px;height:170px;'>
                <div style='font-size:36px;'>📅</div>
                <div style='font-weight:600;font-size:16px;margin-top:8px;'>캘린더 · 트렌드</div>
                <div style='font-size:13px;color:#94A3B8;margin-top:6px;line-height:1.5;'>
                    일자별 기록 · 체중 변화 추이<br>목표 달성 예측 시각화
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    fc4, fc5, fc6 = st.columns(3)
    with fc4:
        st.markdown(
            """
            <div style='background:rgba(30,41,59,0.5);border-radius:12px;padding:20px;height:170px;'>
                <div style='font-size:36px;'>🏃</div>
                <div style='font-weight:600;font-size:16px;margin-top:8px;'>운동 기록</div>
                <div style='font-size:13px;color:#94A3B8;margin-top:6px;line-height:1.5;'>
                    20종 운동 선택 · 시간 입력<br>소모 칼로리 자동 차감
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with fc5:
        st.markdown(
            """
            <div style='background:rgba(30,41,59,0.5);border-radius:12px;padding:20px;height:170px;'>
                <div style='font-size:36px;'>⚖️</div>
                <div style='font-weight:600;font-size:16px;margin-top:8px;'>체중 추적</div>
                <div style='font-size:13px;color:#94A3B8;margin-top:6px;line-height:1.5;'>
                    일일 체중 기록<br>7일 이동평균 + 예측선
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with fc6:
        st.markdown(
            """
            <div style='background:rgba(30,41,59,0.5);border-radius:12px;padding:20px;height:170px;'>
                <div style='font-size:36px;'>⭐</div>
                <div style='font-weight:600;font-size:16px;margin-top:8px;'>즐겨찾기</div>
                <div style='font-size:13px;color:#94A3B8;margin-top:6px;line-height:1.5;'>
                    자주 먹는 음식 원터치 추가<br>어제 식단 1클릭 복사
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # ─── 사용 방법 ─────────────────────────────────────────
    st.markdown("### 🚀 사용 방법")

    st.markdown(
        """
        <div style='background:rgba(30,41,59,0.3);border-radius:12px;padding:20px;'>
            <div style='display:flex;gap:16px;margin-bottom:14px;align-items:flex-start;'>
                <div style='font-size:24px;font-weight:700;color:#3B82F6;min-width:30px;'>1</div>
                <div>
                    <div style='font-weight:600;'>프로필 설정</div>
                    <div style='font-size:13px;color:#94A3B8;'>성별·나이·키·체중·활동량 입력 → 개인 맞춤 목표 자동 계산</div>
                </div>
            </div>
            <div style='display:flex;gap:16px;margin-bottom:14px;align-items:flex-start;'>
                <div style='font-size:24px;font-weight:700;color:#3B82F6;min-width:30px;'>2</div>
                <div>
                    <div style='font-weight:600;'>매일 식단 기록</div>
                    <div style='font-size:13px;color:#94A3B8;'>음식 사진 업로드 OR 이름 입력 → AI가 영양소 자동 분석</div>
                </div>
            </div>
            <div style='display:flex;gap:16px;margin-bottom:14px;align-items:flex-start;'>
                <div style='font-size:24px;font-weight:700;color:#3B82F6;min-width:30px;'>3</div>
                <div>
                    <div style='font-weight:600;'>체중·운동 기록</div>
                    <div style='font-size:13px;color:#94A3B8;'>일일 체중, 운동 시간 입력 → 순 칼로리 실시간 계산</div>
                </div>
            </div>
            <div style='display:flex;gap:16px;align-items:flex-start;'>
                <div style='font-size:24px;font-weight:700;color:#3B82F6;min-width:30px;'>4</div>
                <div>
                    <div style='font-weight:600;'>트렌드 확인</div>
                    <div style='font-size:13px;color:#94A3B8;'>주간 리포트 + 목표 도달 예측선으로 진행 상황 파악</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # ─── 특징 강조 ─────────────────────────────────────────
    st.markdown("### 💡 왜 이 앱인가요?")

    hc1, hc2 = st.columns(2)
    with hc1:
        st.markdown(
            """
            **🔬 과학적 계산**
            - Mifflin-St Jeor BMR 공식
            - 체중 × 1.3~1.8g 단백질 (ISSN 기준)
            - 감량 강도 선택 (-500/-700/-1000kcal)
            """
        )
        st.markdown(
            """
            **🇰🇷 한국형 최적화**
            - 한국 음식 인식 정확도 우수
            - 한국인 표준 1인분 기준 영양 추정
            - 한국 시간대 자동 적용
            """
        )
    with hc2:
        st.markdown(
            """
            **🔒 데이터 투명성**
            - 모든 기록은 본인 Google Sheets에 저장
            - 언제든 직접 확인·수정·내보내기 가능
            - 개인정보는 Google OAuth로 안전 관리
            """
        )
        st.markdown(
            """
            **📱 어디서나 사용**
            - 모바일/PC 어디서나 접속
            - 설치 불필요, 웹 브라우저로 바로 사용
            - 홈 화면에 추가 시 앱처럼 사용
            """
        )

    st.markdown("---")

    # ─── 재로그인 CTA ────────────────────────────────────────
    fcta1, fcta2, fcta3 = st.columns([1, 2, 1])
    with fcta2:
        if st.button("🚀 지금 시작하기", type="primary", use_container_width=True, key="cta_bottom"):
            st.login("google")

    # ─── 푸터 ──────────────────────────────────────────────
    st.markdown(
        """
        <div style='text-align:center;padding:40px 20px 20px;margin-top:30px;
                    border-top:1px solid rgba(148,163,184,0.15);color:#64748B;font-size:12px;'>
            <div style='margin-bottom:8px;'>
                <strong style='color:#94A3B8;'>AI 식단 트래커</strong>
            </div>
            <div style='line-height:1.8;'>
                개인 식단·운동 관리 서비스 · Powered by Google Gemini AI<br>
                본 서비스는 사용자의 식단 데이터를 Google Sheets에 안전하게 저장하며,<br>
                제공되는 영양 정보는 참고용이며 의학적 조언을 대체하지 않습니다.<br>
                <span style='color:#475569;'>© 2026 Diet Tracker · 문의: support@diet-tracker.app</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def require_auth() -> str:
    """페이지 가드: 미로그인 시 랜딩 페이지 + st.stop(). 로그인 시 email 반환."""
    if not is_logged_in():
        _render_landing_page()
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

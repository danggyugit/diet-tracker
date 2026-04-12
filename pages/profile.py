"""👤 프로필 페이지 — 신체정보 + 목표 설정 + BMR/TDEE/적자 표시."""

import datetime

import streamlit as st

from config import ACTIVITY_MULTIPLIERS, today_kst
from services.auth_service import require_auth
from services.sheets_service import get_profile, save_profile, get_latest_weight
from services.calorie_service import calc_bmr, calc_tdee, calc_daily_deficit

email = require_auth()
st.title("👤 프로필")

# ─── 기존 프로필 로드 ───────────────────────────────────────
profile = get_profile(email) or {}
latest_weight = get_latest_weight(email)

# ─── 신체 정보 ───────────────────────────────────────────────
st.subheader("신체 정보")
st.caption("성별·키·나이는 한 번만 입력하면 됩니다. 체중은 매일 식단 기록 페이지에서 기록할 수 있습니다.")

with st.form("profile_form"):
    col1, col2 = st.columns(2)
    with col1:
        gender = st.radio(
            "성별",
            ["남성", "여성"],
            index=0 if profile.get("gender", "남성") == "남성" else 1,
            horizontal=True,
        )
        age = st.number_input(
            "나이",
            min_value=10, max_value=100,
            value=int(profile.get("age", 30)),
        )
        height = st.number_input(
            "키 (cm)",
            min_value=100.0, max_value=250.0,
            value=float(profile.get("height", 170)),
            step=0.5, format="%.1f",
        )
    with col2:
        default_weight = latest_weight or float(profile.get("weight", 70))
        weight = st.number_input(
            "현재 체중 (kg)",
            min_value=30.0, max_value=200.0,
            value=default_weight,
            step=0.1, format="%.1f",
            help="최근 기록된 체중이 자동 반영됩니다",
        )
        activity_level = st.selectbox(
            "활동 수준",
            list(ACTIVITY_MULTIPLIERS.keys()),
            index=list(ACTIVITY_MULTIPLIERS.keys()).index(
                profile.get("activity_level", "보통활동")
            ) if profile.get("activity_level") in ACTIVITY_MULTIPLIERS else 2,
        )

    # ─── 목표 설정 ──────────────────────────────────────────
    st.divider()
    st.subheader("목표 설정")

    goal_col1, goal_col2, goal_col3 = st.columns(3)
    with goal_col1:
        target_weight = st.number_input(
            "목표 체중 (kg)",
            min_value=30.0, max_value=200.0,
            value=float(profile.get("target_weight", 0)) or default_weight,
            step=0.5, format="%.1f",
        )
    with goal_col2:
        saved_date = profile.get("target_date", "")
        default_date = (
            datetime.date.fromisoformat(saved_date)
            if saved_date
            else today_kst() + datetime.timedelta(days=90)
        )
        target_date = st.date_input(
            "목표 날짜",
            value=default_date,
            min_value=today_kst(),
        )
    with goal_col3:
        target_calories = st.number_input(
            "목표 칼로리 (0=자동)",
            min_value=0, max_value=5000,
            value=int(profile.get("target_calories", 0)),
            step=50,
            help="0이면 TDEE - 적자 기반 자동 계산",
        )

    submitted = st.form_submit_button("저장", type="primary", use_container_width=True)

# ─── BMR / TDEE 표시 ────────────────────────────────────────
bmr = calc_bmr(weight, height, age, gender)
tdee = calc_tdee(bmr, activity_level)

st.divider()
st.subheader("계산 결과")

col_bmr, col_tdee = st.columns(2)
col_bmr.metric("기초대사량 (BMR)", f"{bmr:,.0f} kcal")
col_tdee.metric("일일 소모량 (TDEE)", f"{tdee:,.0f} kcal")

# ─── 목표 분석 ──────────────────────────────────────────────
if target_weight and target_weight != weight:
    deficit_info = calc_daily_deficit(weight, target_weight, target_date.isoformat())

    st.divider()
    st.subheader("다이어트 계획 분석")

    d1, d2, d3, d4 = st.columns(4)
    direction = "감량" if deficit_info["total_kg"] > 0 else "증량"
    d1.metric(f"총 {direction}", f"{abs(deficit_info['total_kg']):.1f} kg")
    d2.metric("남은 기간", f"{deficit_info['remaining_days']}일")
    d3.metric("주당 변화", f"{abs(deficit_info['weekly_kg']):.2f} kg/주")

    if target_calories > 0:
        daily_budget = target_calories
    else:
        daily_budget = max(round(tdee - deficit_info["deficit_per_day"]), 1200)
    d4.metric("일일 칼로리 예산", f"{daily_budget:,} kcal")

    if not deficit_info["is_safe"]:
        st.warning(
            f"주당 {abs(deficit_info['weekly_kg']):.1f}kg 변화는 권장 범위(1kg/주)를 초과합니다. "
            f"목표 날짜를 늘리거나 목표 체중을 조정해 주세요."
        )
    else:
        st.success(
            f"하루 {abs(deficit_info['deficit_per_day']):,}kcal {'적자' if deficit_info['total_kg'] > 0 else '잉여'}로 "
            f"목표 달성 가능합니다."
        )

st.caption(
    f"Mifflin-St Jeor · {gender} · {age}세 · {height}cm · {weight}kg "
    f"· 활동계수 {ACTIVITY_MULTIPLIERS.get(activity_level, 1.55):.3f}"
)

# ─── 저장 처리 ───────────────────────────────────────────
if submitted:
    save_profile(email, {
        "gender": gender,
        "age": age,
        "height": height,
        "weight": weight,
        "activity_level": activity_level,
        "target_calories": target_calories,
        "target_weight": target_weight,
        "target_date": target_date.isoformat(),
    })
    st.success("프로필이 저장되었습니다!")
    st.rerun()

"""👤 프로필 페이지 — 신체정보 + 감량 강도 + BMR/TDEE/영양소 목표."""

import datetime

import streamlit as st

from config import ACTIVITY_MULTIPLIERS, PROTEIN_MULTIPLIERS, today_kst
from services.auth_service import require_auth
from services.sheets_service import get_profile, save_profile, get_latest_weight
from services.calorie_service import calc_bmr, calc_tdee

email = require_auth()
st.title("👤 프로필")

# ─── 기존 프로필 로드 ───────────────────────────────────────
profile = get_profile(email) or {}
latest_weight = get_latest_weight(email)

# ─── 감량 강도 옵션 ──────────────────────────────────────────
DEFICIT_OPTIONS = {
    "🟢 가벼운 감량 (-500kcal) — 주 0.45kg": 500,
    "🟡 보통 감량 (-700kcal) — 주 0.64kg": 700,
    "🔴 강한 감량 (-1000kcal) — 주 0.9kg": 1000,
    "⚪ 체중 유지 (0kcal)": 0,
}
DEFICIT_KEYS = list(DEFICIT_OPTIONS.keys())

# ─── 입력 폼 ─────────────────────────────────────────────
st.subheader("신체 정보")

with st.form("profile_form"):
    col1, col2 = st.columns(2)
    with col1:
        gender = st.radio(
            "성별", ["남성", "여성"],
            index=0 if profile.get("gender", "남성") == "남성" else 1,
            horizontal=True,
        )
        age = st.number_input(
            "나이", min_value=10, max_value=100,
            value=int(profile.get("age", 30)),
        )
        height = st.number_input(
            "키 (cm)", min_value=100.0, max_value=250.0,
            value=float(profile.get("height", 170)),
            step=0.5, format="%.1f",
        )
    with col2:
        default_weight = latest_weight or float(profile.get("weight", 70))
        weight = st.number_input(
            "현재 체중 (kg)", min_value=30.0, max_value=200.0,
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

    # ─── 감량 강도 설정 ──────────────────────────────────────
    st.divider()
    st.subheader("감량 강도")

    saved_deficit = int(profile.get("deficit_level", 700))
    default_idx = 1  # 보통 감량
    for i, (_, v) in enumerate(DEFICIT_OPTIONS.items()):
        if v == saved_deficit:
            default_idx = i
            break

    deficit_choice = st.radio(
        "하루 감량 강도 선택",
        DEFICIT_KEYS,
        index=default_idx,
        label_visibility="collapsed",
    )
    deficit_level = DEFICIT_OPTIONS[deficit_choice]

    # ─── 목표 체중/날짜 (참고용) ─────────────────────────────
    st.divider()
    st.subheader("목표 (참고)")
    st.caption("감량 속도 예측용입니다. 일일 목표 칼로리는 위 감량 강도로 결정됩니다.")

    gc1, gc2 = st.columns(2)
    with gc1:
        target_weight = st.number_input(
            "목표 체중 (kg)", min_value=30.0, max_value=200.0,
            value=float(profile.get("target_weight", 0)) or default_weight - 10,
            step=0.5, format="%.1f",
        )
    with gc2:
        saved_date = profile.get("target_date", "")
        default_date = (
            datetime.date.fromisoformat(saved_date)
            if saved_date
            else today_kst() + datetime.timedelta(days=180)
        )
        target_date = st.date_input("목표 날짜", value=default_date, min_value=today_kst())

    submitted = st.form_submit_button("저장", type="primary", use_container_width=True)

# ═══════════════════════════════════════════════════════════════
# 계산 결과
# ═══════════════════════════════════════════════════════════════

bmr = calc_bmr(weight, height, age, gender)
tdee = calc_tdee(bmr, activity_level)
daily_target = round(tdee - deficit_level)

# 체중 + 활동 수준 기반 영양소 목표
protein_mult = PROTEIN_MULTIPLIERS.get(activity_level, 1.3)
protein_g = round(weight * protein_mult)
fat_g = round(daily_target * 0.30 / 9)
protein_cal = protein_g * 4
fat_cal = fat_g * 9
carbs_g = round((daily_target - protein_cal - fat_cal) / 4)

st.divider()
st.subheader("계산 결과")

c1, c2, c3 = st.columns(3)
c1.metric("기초대사량 (BMR)", f"{bmr:,.0f} kcal")
c2.metric("일일 소모 (TDEE)", f"{tdee:,.0f} kcal")
c3.metric("일일 섭취 목표", f"{daily_target:,} kcal")

st.divider()
st.subheader("영양소 목표 (체중 기반)")

n1, n2, n3 = st.columns(3)
n1.metric("🍚 탄수화물", f"{carbs_g}g", delta=f"{round(carbs_g*4/daily_target*100)}%")
n2.metric("🥩 단백질", f"{protein_g}g", delta=f"체중×{protein_mult}g")
n3.metric("🧈 지방", f"{fat_g}g", delta=f"30%")

st.caption(
    f"단백질: {weight:.0f}kg × {protein_mult}g = {protein_g}g ({protein_cal}kcal) · "
    f"지방: {daily_target:,} × 30% ÷ 9 = {fat_g}g ({fat_cal}kcal) · "
    f"탄수화물: 나머지 = {carbs_g}g ({carbs_g*4}kcal)"
)

# ─── 목표 도달 예측 ──────────────────────────────────────────
if deficit_level > 0 and target_weight < weight:
    weekly_loss = deficit_level * 7 / 7700
    kg_to_lose = weight - target_weight
    weeks_needed = kg_to_lose / weekly_loss if weekly_loss > 0 else 0
    predicted_date = today_kst() + datetime.timedelta(weeks=weeks_needed)

    st.divider()
    st.subheader("목표 도달 예측")
    p1, p2, p3 = st.columns(3)
    p1.metric("총 감량", f"{kg_to_lose:.1f} kg")
    p2.metric("주당 감량", f"{weekly_loss:.2f} kg")
    p3.metric("예상 도달일", f"{predicted_date.isoformat()}")

    if predicted_date <= datetime.date.fromisoformat(target_date.isoformat()):
        st.success(f"목표 날짜({target_date}) 이내에 달성 가능합니다!")
    else:
        diff_days = (predicted_date - datetime.date.fromisoformat(target_date.isoformat())).days
        st.info(f"목표 날짜보다 약 {diff_days}일 늦을 수 있습니다. 감량 강도를 올리거나 목표를 조정해 보세요.")

st.caption(
    f"Mifflin-St Jeor · {gender} · {age}세 · {height}cm · {weight}kg "
    f"· 활동계수 {ACTIVITY_MULTIPLIERS.get(activity_level, 1.55):.3f}"
)

# ─── 저장 ────────────────────────────────────────────────
if submitted:
    save_profile(email, {
        "gender": gender,
        "age": age,
        "height": height,
        "weight": weight,
        "activity_level": activity_level,
        "target_calories": 0,
        "target_weight": target_weight,
        "target_date": target_date.isoformat(),
        "deficit_level": deficit_level,
    })
    st.success("프로필이 저장되었습니다!")
    st.rerun()

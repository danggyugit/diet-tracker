"""📸 식단 기록 페이지.

모바일 단일 컬럼. 하나의 폼에 모든 입력을 묶고 버튼 하나로 처리.
날짜 → 게이지 → [폼: 체중·식사유형·사진·수동음식] → 저장된기록
"""

import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import MEAL_TYPES, MAX_FILE_SIZE, PLOT_CFG
from services.auth_service import require_auth
from services.gemini_service import analyze_food_image, estimate_multiple_foods
from services.calorie_service import calc_bmr, calc_tdee, calc_exercise_plan, calc_daily_deficit
from services.sheets_service import (
    get_profile, get_meals_for_date, save_meals, delete_meal_row, update_meal_row,
    get_latest_weight, save_weight, get_daily_totals, save_memo, get_memo,
)

email = require_auth()

# ─── 세션 상태 ───────────────────────────────────────────────
if "editing_key" not in st.session_state:
    st.session_state.editing_key = None

# ─── 프로필 + TDEE (캐싱됨) ──────────────────────────────────
profile = get_profile(email) or {}
latest_weight = get_latest_weight(email) or float(profile.get("weight", 70))

bmr = calc_bmr(
    latest_weight,
    float(profile.get("height", 170)),
    int(profile.get("age", 30)),
    profile.get("gender", "남성"),
)
tdee = calc_tdee(bmr, profile.get("activity_level", "보통활동"))

target_cal = int(profile.get("target_calories", 0))
target_wt = float(profile.get("target_weight", 0))
target_dt = profile.get("target_date", "")

if target_cal > 0:
    daily_budget = target_cal
elif target_wt > 0 and target_dt:
    deficit = calc_daily_deficit(latest_weight, target_wt, target_dt)
    daily_budget = max(round(tdee - deficit["deficit_per_day"]), 1200)
else:
    daily_budget = round(tdee)

# ═══════════════════════════════════════════════════════════════
# 1. 날짜
# ═══════════════════════════════════════════════════════════════

selected_date = st.date_input("날짜", value=datetime.date.today())
date_str = selected_date.isoformat()

# ═══════════════════════════════════════════════════════════════
# 2. 오늘 섭취 / 예산 게이지
# ═══════════════════════════════════════════════════════════════

today_totals = get_daily_totals(email, date_str, date_str)
eaten_cal = float(today_totals["total_cal"].sum()) if not today_totals.empty else 0
remaining_cal = daily_budget - eaten_cal

if remaining_cal > daily_budget * 0.3:
    bar_color, status = "#22C55E", f"아직 {remaining_cal:,.0f} kcal 더 드실 수 있어요"
elif remaining_cal > 0:
    bar_color, status = "#FBBF24", f"남은 예산 {remaining_cal:,.0f} kcal"
else:
    bar_color, status = "#EF4444", f"{abs(remaining_cal):,.0f} kcal 초과했어요"

fig_budget = go.Figure(go.Indicator(
    mode="gauge+number",
    value=eaten_cal,
    gauge=dict(
        axis=dict(range=[0, daily_budget * 1.3], tickfont=dict(size=10)),
        bar=dict(color=bar_color),
        steps=[
            dict(range=[0, daily_budget], color="rgba(34,197,94,0.15)"),
            dict(range=[daily_budget, daily_budget * 1.3], color="rgba(239,68,68,0.15)"),
        ],
        threshold=dict(line=dict(color="#F8FAFC", width=2), value=daily_budget),
    ),
    title=dict(text="오늘 섭취 / 예산", font=dict(size=14)),
    number=dict(suffix=f" / {daily_budget:,} kcal", font=dict(size=18)),
))
fig_budget.update_layout(**PLOT_CFG, height=180, margin=dict(l=15, r=15, t=45, b=0))
st.plotly_chart(fig_budget, use_container_width=True)
st.caption(status)

# ═══════════════════════════════════════════════════════════════
# 3. 통합 입력 폼 (체중 + 식사유형 + 사진 + 수동음식)
# ═══════════════════════════════════════════════════════════════

with st.form("record_form"):
    today_weight = st.number_input(
        "⚖️ 오늘 체중 (kg)", min_value=30.0, max_value=200.0,
        value=latest_weight, step=0.1, format="%.1f",
    )
    meal_type = st.radio("🍽️ 식사 유형", MEAL_TYPES, horizontal=True)

    st.markdown("---")
    st.markdown("**📷 음식 사진**")
    uploaded = st.file_uploader(
        "사진 업로드", type=["jpg", "jpeg", "png"],
        help="JPG, PNG / 최대 10MB", label_visibility="collapsed",
    )

    st.markdown("---")
    st.markdown("**✏️ 수동 음식 추가** (사진에 안 나온 음식이 있으면 입력)")
    manual_text = st.text_area(
        "음식 목록 (한 줄에 하나씩)",
        placeholder="연어스테이크 1인분\n함박스테이크 반인분\n와인 1병\n루꼴라양배추샐러드\n버섯파스타 반인분",
        height=120, key="m_text",
    )
    st.caption("한 줄에 음식 하나씩 입력. 양을 적으면 반영되고, 안 적으면 1인분 기준 추정.")

    st.markdown("---")
    st.markdown("**📝 오늘의 컨디션 & 메모**")
    from config import CONDITION_OPTIONS
    memo_condition = st.selectbox("컨디션", CONDITION_OPTIONS, key="m_cond")
    memo_text = st.text_input("메모", placeholder="오늘 식단에 대한 메모", key="m_memo")

    submitted = st.form_submit_button(
        "🔍 AI 분석 및 저장", type="primary", use_container_width=True,
    )

# ═══════════════════════════════════════════════════════════════
# 폼 제출 처리
# ═══════════════════════════════════════════════════════════════

if submitted:
    all_foods = []

    # 1) 사진 분석
    if uploaded:
        if uploaded.size > MAX_FILE_SIZE:
            st.error("10MB 이하만 가능")
        else:
            st.image(uploaded, width=200)
            ext = uploaded.name.rsplit(".", 1)[-1].lower()
            media_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"}
            with st.spinner("AI가 사진을 분석 중..."):
                try:
                    result = analyze_food_image(uploaded.getvalue(), media_map.get(ext, "image/jpeg"))
                except Exception as e:
                    st.error(f"사진 분석 오류: {e}")
                    result = None
            if result and not result.get("error") and result.get("foods"):
                for f in result["foods"]:
                    f["source"] = "ai"
                all_foods.extend(result["foods"])
                st.success(f"사진에서 {len(result['foods'])}개 음식 인식")
            elif result:
                st.warning(result.get("error", "음식을 인식하지 못했습니다."))

    # 2) 수동 음식 (여러 줄)
    food_lines = [line.strip() for line in manual_text.strip().split("\n") if line.strip()] if manual_text.strip() else []
    if food_lines:
        with st.spinner(f"{len(food_lines)}개 음식 영양 정보 추정 중..."):
            try:
                estimated = estimate_multiple_foods(food_lines)
                for f in estimated:
                    f["source"] = "manual"
                all_foods.extend(estimated)
                for f in estimated:
                    st.success(
                        f"✏️ {f.get('name', '')} — "
                        f"{f.get('calories', 0)}kcal × {f.get('quantity', 1)}인분"
                    )
            except Exception as e:
                st.error(f"수동 음식 추정 실패: {e}")

    # 3) 저장
    if all_foods:
        save_meals(email, date_str, meal_type, all_foods)

    # 체중은 항상 저장
    save_weight(email, date_str, today_weight)

    # 메모/컨디션 저장 (입력이 있을 때)
    if memo_text.strip() or memo_condition:
        save_memo(email, date_str, memo_condition, memo_text.strip())

    if all_foods:
        total = sum(f.get("calories", 0) * f.get("quantity", 1) for f in all_foods)
        st.success(f"💾 {meal_type} {len(all_foods)}개 음식 ({total:,.0f}kcal) + 체중 {today_weight}kg 저장!")
    else:
        st.success(f"💾 체중 {today_weight}kg 저장!")

    st.rerun()

# ═══════════════════════════════════════════════════════════════
# 4. 저장된 기록 (삭제 가능)
# ═══════════════════════════════════════════════════════════════

st.divider()
saved = get_meals_for_date(email, date_str)

if saved.empty:
    st.caption(f"{date_str} 저장된 기록이 없습니다.")
else:
    st.markdown(f"#### 📋 {date_str} 저장된 기록")

    for c in ["calories", "carbs", "protein", "fat", "quantity", "total_cal"]:
        if c in saved.columns:
            saved[c] = pd.to_numeric(saved[c], errors="coerce").fillna(0)

    saved_total = saved["total_cal"].sum()
    st.caption(f"총 {saved_total:,.0f} kcal")

    for mt in MEAL_TYPES:
        meal_df = saved[saved["meal_type"] == mt]
        if meal_df.empty:
            continue

        st.markdown(f"**{mt}** ({meal_df['total_cal'].sum():,.0f} kcal)")

        for idx, row in meal_df.iterrows():
            row_key = f"{mt}_{idx}"
            is_editing = st.session_state.editing_key == row_key

            if is_editing:
                # 수정 모드
                with st.form(f"edit_form_{row_key}"):
                    st.markdown(f"**{row['food_name']}** 수정")
                    ec1, ec2 = st.columns(2)
                    edit_cal = ec1.number_input(
                        "칼로리", value=int(row["calories"]),
                        min_value=0, key=f"ecal_{row_key}",
                    )
                    edit_qty = ec2.number_input(
                        "인분", value=float(row["quantity"]),
                        min_value=0.5, max_value=10.0, step=0.5,
                        key=f"eqty_{row_key}",
                    )
                    bc1, bc2 = st.columns(2)
                    if bc1.form_submit_button("저장", use_container_width=True):
                        update_meal_row(
                            email, date_str,
                            row["food_name"],
                            str(row.get("created_at", "")),
                            edit_cal, edit_qty,
                        )
                        st.session_state.editing_key = None
                        st.rerun()
                    if bc2.form_submit_button("취소", use_container_width=True):
                        st.session_state.editing_key = None
                        st.rerun()
            else:
                # 표시 모드 — popover로 수정/삭제 (모바일 대응)
                r1, r2 = st.columns([6, 1])
                with r1:
                    st.markdown(
                        f"**{row['food_name']}** {row.get('amount', '')}  \n"
                        f"<span style='font-size:13px;color:#94A3B8;'>"
                        f"{int(row['calories'])}kcal × {row['quantity']}인분 = {int(row['total_cal'])}kcal"
                        f"</span>",
                        unsafe_allow_html=True,
                    )
                with r2:
                    with st.popover("⋯"):
                        if st.button("✏️ 수정", key=f"sedit_{row_key}", use_container_width=True):
                            st.session_state.editing_key = row_key
                            st.rerun()
                        if st.button("🗑️ 삭제", key=f"sdel_{row_key}", use_container_width=True):
                            delete_meal_row(
                                email, date_str,
                                row["food_name"],
                                str(row.get("created_at", "")),
                            )
                            st.rerun()

# ─── 메모/컨디션 표시 ────────────────────────────────────────
saved_memo = get_memo(email, date_str)
if saved_memo:
    st.markdown(
        f"**📝 컨디션**: {saved_memo.get('condition', '')}  \n"
        f"**메모**: {saved_memo.get('memo', '') or '없음'}",
    )

# ─── 운동 추천 ───────────────────────────────────────────────
if not saved.empty:
    st.markdown("**🔥 운동 추천**")
    for ex in calc_exercise_plan(saved_total, latest_weight):
        st.caption(f"{ex['icon']} {ex['name']}: **{ex['rec_time']}분** ({ex['kcal_per_min']}kcal/분)")

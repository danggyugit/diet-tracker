"""📸 식단 기록 페이지.

모바일 단일 컬럼 레이아웃:
날짜 → 게이지(순칼로리) → 체중 → 식사유형 → 사진(2단계) → 수동추가 → 즐겨찾기
→ 운동기록 → 물섭취 → 컨디션/메모 → [저장] → 저장된기록
"""

import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import (
    MEAL_TYPES, MAX_FILE_SIZE, PLOT_CFG, CONDITION_OPTIONS,
    EXERCISE_OPTIONS, WATER_TARGET_ML,
)
from services.auth_service import require_auth
from services.gemini_service import analyze_food_image, estimate_multiple_foods
from services.barcode_service import lookup_barcode, decode_barcode_from_image, PYZBAR_AVAILABLE
from services.calorie_service import calc_bmr, calc_tdee, calc_exercise_plan, calc_daily_deficit
from services.sheets_service import (
    get_profile, get_meals_for_date, save_meals, delete_meal_row, update_meal_row,
    get_latest_weight, save_weight, get_daily_totals,
    save_memo, get_memo,
    save_exercise, get_daily_burned, get_exercise_log,
    save_water, get_water_log,
    get_favorites, add_favorite, auto_add_favorites_from_meals,
)

email = require_auth()

# ─── 세션 상태 ───────────────────────────────────────────────
if "pending_foods" not in st.session_state:
    st.session_state.pending_foods = []
if "editing_key" not in st.session_state:
    st.session_state.editing_key = None

# ─── 프로필 + TDEE ───────────────────────────────────────────
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
SAFETY_FLOOR = 1200

if target_cal > 0:
    daily_budget = target_cal
elif target_wt > 0 and target_dt:
    deficit = calc_daily_deficit(latest_weight, target_wt, target_dt)
    daily_budget = round(tdee - deficit["deficit_per_day"])
else:
    daily_budget = round(tdee)

is_below_safety = daily_budget < SAFETY_FLOOR

# ═══════════════════════════════════════════════════════════════
# 1. 날짜
# ═══════════════════════════════════════════════════════════════

selected_date = st.date_input("날짜", value=datetime.date.today())
date_str = selected_date.isoformat()

# ═══════════════════════════════════════════════════════════════
# 2. 순 칼로리 게이지 (섭취 - 운동 소모)
# ═══════════════════════════════════════════════════════════════

today_totals = get_daily_totals(email, date_str, date_str)
eaten_cal = float(today_totals["total_cal"].sum()) if not today_totals.empty else 0
burned_cal = get_daily_burned(email, date_str)
net_cal = eaten_cal - burned_cal
remaining_cal = daily_budget - net_cal

if remaining_cal > daily_budget * 0.3:
    bar_color, status = "#22C55E", f"남은 {remaining_cal:,.0f} kcal"
elif remaining_cal > 0:
    bar_color, status = "#FBBF24", f"남은 {remaining_cal:,.0f} kcal"
else:
    bar_color, status = "#EF4444", f"{abs(remaining_cal):,.0f} kcal 초과"

gauge_max = max(daily_budget * 1.3, net_cal * 1.1, 100)
fig_budget = go.Figure(go.Indicator(
    mode="gauge+number",
    value=net_cal,
    gauge=dict(
        axis=dict(range=[0, gauge_max], tickfont=dict(size=10)),
        bar=dict(color=bar_color),
        steps=[
            dict(range=[0, daily_budget], color="rgba(34,197,94,0.15)"),
            dict(range=[daily_budget, gauge_max], color="rgba(239,68,68,0.15)"),
        ],
        threshold=dict(line=dict(color="#F8FAFC", width=2), value=daily_budget),
    ),
    title=dict(text="순 칼로리 (섭취 - 운동)", font=dict(size=14)),
    number=dict(suffix=f" / {daily_budget:,} kcal", font=dict(size=18)),
))
fig_budget.update_layout(**PLOT_CFG, height=180, margin=dict(l=15, r=15, t=45, b=0))
st.plotly_chart(fig_budget, use_container_width=True)

if burned_cal > 0:
    st.caption(f"{status} | 섭취 {eaten_cal:,.0f} - 운동 {burned_cal:,.0f} = 순 {net_cal:,.0f} kcal")
else:
    st.caption(status)

if is_below_safety:
    st.warning(f"⚠️ 목표 예산({daily_budget:,}kcal)이 안전 하한선({SAFETY_FLOOR:,}kcal) 미만입니다.")

# ═══════════════════════════════════════════════════════════════
# 3. 통합 입력 폼
# ═══════════════════════════════════════════════════════════════

existing_memo = get_memo(email, date_str)
existing_condition = existing_memo.get("condition", "") if existing_memo else ""
existing_memo_text = existing_memo.get("memo", "") if existing_memo else ""

with st.form("record_form"):
    # 체중
    today_weight = st.number_input(
        "⚖️ 오늘 체중 (kg)", min_value=30.0, max_value=200.0,
        value=latest_weight, step=0.1, format="%.1f",
    )

    # 식사 유형
    meal_type = st.radio("🍽️ 식사 유형", MEAL_TYPES, horizontal=True)

    # 사진
    st.markdown("---")
    st.markdown("**📷 음식 사진**")
    uploaded = st.file_uploader(
        "사진 업로드", type=["jpg", "jpeg", "png"],
        help="JPG, PNG / 최대 10MB", label_visibility="collapsed",
    )

    # 바코드 스캔
    st.markdown("---")
    st.markdown("**📦 바코드 (포장 식품)**")
    barcode_input = st.text_input("바코드 번호 입력", placeholder="880123456789", key="barcode")
    if PYZBAR_AVAILABLE:
        barcode_cam = st.camera_input("또는 바코드 촬영", key="barcode_cam")
    else:
        barcode_cam = None

    # 수동 음식
    st.markdown("---")
    st.markdown("**✏️ 수동 음식 추가** (한 줄에 하나씩)")
    manual_text = st.text_area(
        "음식 목록",
        placeholder="연어스테이크 1인분\n함박스테이크 반인분\n와인 1병",
        height=100, key="m_text", label_visibility="collapsed",
    )

    # 운동 기록
    st.markdown("---")
    st.markdown("**🏃 운동 기록**")
    ex_names = [f"{e['icon']} {e['name']}" for e in EXERCISE_OPTIONS]
    selected_ex = st.selectbox("운동 선택", ex_names, key="ex_sel")
    ex_idx = ex_names.index(selected_ex)
    ex_duration = st.number_input("운동 시간 (분)", min_value=0, max_value=300, value=0, step=5, key="ex_dur")
    if EXERCISE_OPTIONS[ex_idx]["met"] == 0 and ex_duration > 0:
        ex_custom_met = st.number_input("MET 값 (직접 입력)", min_value=1.0, max_value=20.0, value=5.0, step=0.5)
    else:
        ex_custom_met = None

    # 물 섭취
    st.markdown("---")
    today_water = get_water_log(email, date_str)
    st.markdown(f"**💧 물 섭취** (오늘: {today_water}ml / {WATER_TARGET_ML}ml)")
    water_ml = st.number_input("추가 섭취량 (ml)", min_value=0, max_value=2000, value=0, step=100, key="water")

    # 컨디션/메모
    st.markdown("---")
    st.markdown("**📝 컨디션 & 메모**")
    cond_index = CONDITION_OPTIONS.index(existing_condition) if existing_condition in CONDITION_OPTIONS else 0
    memo_condition = st.selectbox("컨디션", CONDITION_OPTIONS, index=cond_index, key="m_cond")
    memo_text = st.text_input("메모", value=existing_memo_text, placeholder="오늘 식단에 대한 메모", key="m_memo")

    submitted = st.form_submit_button(
        "🔍 AI 분석", type="primary", use_container_width=True,
    )

# ═══════════════════════════════════════════════════════════════
# 폼 제출 → 2단계: 결과 확인
# ═══════════════════════════════════════════════════════════════

if submitted:
    pending = []

    # 사진 분석
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
                pending.extend(result["foods"])
            elif result:
                st.warning(result.get("error", "음식을 인식하지 못했습니다."))

    # 바코드 조회
    bc_number = barcode_input.strip()
    if not bc_number and barcode_cam:
        bc_number = decode_barcode_from_image(barcode_cam.getvalue()) or ""
        if bc_number:
            st.info(f"바코드 인식: {bc_number}")
    if bc_number:
        with st.spinner(f"바코드 {bc_number} 조회 중..."):
            bc_result = lookup_barcode(bc_number)
        if bc_result:
            bc_result["source"] = "barcode"
            pending.append(bc_result)
            st.success(f"📦 {bc_result['name']} ({bc_result['calories']}kcal/100g)")
            if bc_result.get("note"):
                st.caption(bc_result["note"])
        else:
            st.warning(f"바코드 {bc_number}에 해당하는 제품을 찾지 못했습니다.")

    # 수동 음식
    food_lines = [l.strip() for l in manual_text.strip().split("\n") if l.strip()] if manual_text.strip() else []
    if food_lines:
        with st.spinner(f"{len(food_lines)}개 음식 추정 중..."):
            try:
                estimated = estimate_multiple_foods(food_lines)
                for f in estimated:
                    f["source"] = "manual"
                pending.extend(estimated)
            except Exception as e:
                st.error(f"추정 실패: {e}")

    # 체중 저장 (항상)
    save_weight(email, date_str, today_weight)

    # 운동 저장
    if ex_duration > 0:
        ex_info = EXERCISE_OPTIONS[ex_idx]
        met = ex_custom_met if ex_info["met"] == 0 else ex_info["met"]
        save_exercise(email, date_str, ex_info["name"], ex_duration, met, today_weight)
        cal_burned = round(met * today_weight * ex_duration / 60)
        st.success(f"🏃 {ex_info['name']} {ex_duration}분 ({cal_burned}kcal 소모) 기록!")

    # 물 저장
    if water_ml > 0:
        save_water(email, date_str, water_ml)
        st.success(f"💧 물 {water_ml}ml 기록!")

    # 메모 저장
    if memo_text.strip() or memo_condition:
        save_memo(email, date_str, memo_condition, memo_text.strip())

    # 음식이 있으면 세션에 저장 (2단계 확인용)
    if pending:
        st.session_state.pending_foods = pending
        st.rerun()
    elif not pending and not uploaded and not food_lines:
        st.success(f"💾 체중 {today_weight}kg 기록 완료!")
        st.rerun()
    else:
        st.rerun()

# ═══════════════════════════════════════════════════════════════
# 2단계: 분석 결과 확인 → 수정 → 저장
# ═══════════════════════════════════════════════════════════════

if st.session_state.pending_foods:
    st.divider()
    st.markdown("#### 🔍 분석 결과 (수정 후 저장하세요)")

    foods = st.session_state.pending_foods
    total_pending = 0

    with st.form("confirm_form"):
        edited_foods = []
        for i, food in enumerate(foods):
            badge = "🤖" if food.get("source") == "ai" else "✏️"
            st.markdown(f"**{badge} {food.get('name', '')}** {food.get('amount', '')}")
            c1, c2, c3, c4, c5 = st.columns(5)
            e_cal = c1.number_input("kcal", value=int(food.get("calories", 0)), min_value=0, key=f"pc_{i}")
            e_carbs = c2.number_input("탄(g)", value=int(food.get("carbs", 0)), min_value=0, key=f"pcb_{i}")
            e_prot = c3.number_input("단(g)", value=int(food.get("protein", 0)), min_value=0, key=f"pp_{i}")
            e_fat = c4.number_input("지(g)", value=int(food.get("fat", 0)), min_value=0, key=f"pf_{i}")
            e_qty = c5.number_input("인분", value=float(food.get("quantity", 1.0)), min_value=0.5, max_value=10.0, step=0.5, key=f"pq_{i}")
            edited_foods.append({
                "name": food.get("name", ""),
                "amount": food.get("amount", ""),
                "calories": e_cal, "carbs": e_carbs,
                "protein": e_prot, "fat": e_fat,
                "quantity": e_qty, "source": food.get("source", "ai"),
            })
            total_pending += e_cal * e_qty

        st.markdown(f"**총 {total_pending:,.0f} kcal**")

        col_save, col_cancel = st.columns(2)
        save_btn = col_save.form_submit_button("💾 저장", type="primary", use_container_width=True)
        cancel_btn = col_cancel.form_submit_button("취소", use_container_width=True)

    if save_btn:
        save_meals(email, date_str, meal_type, edited_foods)
        # 즐겨찾기에 자동 추가
        for f in edited_foods:
            add_favorite(email, f)
        st.session_state.pending_foods = []
        st.success(f"💾 {meal_type} {len(edited_foods)}개 음식 저장!")
        st.rerun()
    if cancel_btn:
        st.session_state.pending_foods = []
        st.rerun()

# ═══════════════════════════════════════════════════════════════
# 즐겨찾기 빠른 추가
# ═══════════════════════════════════════════════════════════════

favorites = get_favorites(email)
if favorites:
    st.divider()
    st.markdown("#### ⭐ 자주 먹는 음식")
    for i, fav in enumerate(favorites[:10]):
        fc1, fc2 = st.columns([4, 1])
        fc1.caption(
            f"**{fav['food_name']}** {fav.get('amount', '')} · "
            f"{fav.get('calories', 0)}kcal"
        )
        if fc2.button("추가", key=f"fav_{i}"):
            save_meals(email, date_str, meal_type, [{
                "name": fav["food_name"], "amount": fav.get("amount", ""),
                "calories": int(fav.get("calories", 0)),
                "carbs": int(fav.get("carbs", 0)),
                "protein": int(fav.get("protein", 0)),
                "fat": int(fav.get("fat", 0)),
                "quantity": 1.0, "source": "favorite",
            }])
            add_favorite(email, {"name": fav["food_name"], "amount": fav.get("amount", ""),
                                 "calories": fav.get("calories", 0), "carbs": fav.get("carbs", 0),
                                 "protein": fav.get("protein", 0), "fat": fav.get("fat", 0)})
            st.success(f"⭐ {fav['food_name']} 추가!")
            st.rerun()

# ═══════════════════════════════════════════════════════════════
# 저장된 기록
# ═══════════════════════════════════════════════════════════════

st.divider()
saved = get_meals_for_date(email, date_str)

if saved.empty:
    st.caption(f"{date_str} 저장된 식단 기록이 없습니다.")
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
                with st.form(f"edit_form_{row_key}"):
                    st.markdown(f"**{row['food_name']}** 수정")
                    ec1, ec2 = st.columns(2)
                    edit_cal = ec1.number_input("칼로리", value=int(row["calories"]), min_value=0, key=f"ecal_{row_key}")
                    edit_qty = ec2.number_input("인분", value=float(row["quantity"]), min_value=0.5, max_value=10.0, step=0.5, key=f"eqty_{row_key}")
                    bc1, bc2 = st.columns(2)
                    if bc1.form_submit_button("저장", use_container_width=True):
                        update_meal_row(email, date_str, row["food_name"], str(row.get("created_at", "")), edit_cal, edit_qty)
                        st.session_state.editing_key = None
                        st.rerun()
                    if bc2.form_submit_button("취소", use_container_width=True):
                        st.session_state.editing_key = None
                        st.rerun()
            else:
                st.markdown(
                    f"**{row['food_name']}** {row.get('amount', '')} · "
                    f"<span style='color:#94A3B8;'>"
                    f"{int(row['calories'])}kcal x {row['quantity']}인분 = {int(row['total_cal'])}kcal"
                    f"</span>",
                    unsafe_allow_html=True,
                )
                bc1, bc2, bc3 = st.columns([1, 1, 4])
                if bc1.button("수정", key=f"sedit_{row_key}", use_container_width=True):
                    st.session_state.editing_key = row_key
                    st.rerun()
                if bc2.button("삭제", key=f"sdel_{row_key}", use_container_width=True):
                    delete_meal_row(email, date_str, row["food_name"], str(row.get("created_at", "")))
                    st.rerun()

# ─── 운동 기록 표시 ──────────────────────────────────────────
ex_log = get_exercise_log(email, date_str, date_str)
if not ex_log.empty:
    st.markdown(f"**🏃 운동 기록** ({burned_cal:,.0f} kcal 소모)")
    for _, ex in ex_log.iterrows():
        st.caption(f"  · {ex['exercise_name']} {int(ex['duration_min'])}분 — {int(ex['calories_burned'])}kcal")

# ─── 물 섭취 표시 ────────────────────────────────────────────
total_water = get_water_log(email, date_str)
if total_water > 0:
    pct = min(total_water / WATER_TARGET_ML * 100, 100)
    st.markdown(f"**💧 물 섭취** {total_water}ml / {WATER_TARGET_ML}ml ({pct:.0f}%)")

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

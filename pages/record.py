"""📸 식단 기록 페이지.

모바일 단일 컬럼 레이아웃:
날짜 → 게이지(순칼로리) → [폼: 체중·식사유형·사진·수동추가·즐겨찾기·운동·물·메모]
→ 2단계 확인 → 저장된기록
"""

import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import (
    MEAL_TYPES, MAX_FILE_SIZE, PLOT_CFG, CONDITION_OPTIONS,
    EXERCISE_OPTIONS, WATER_TARGET_ML, PROTEIN_MULTIPLIERS,
)
from services.auth_service import require_auth
from services.gemini_service import analyze_food_image, estimate_multiple_foods
from services.calorie_service import calc_bmr, calc_tdee, calc_exercise_plan
from services.sheets_service import (
    get_profile, get_meals_for_date, save_meals, delete_meal_row, update_meal_row,
    get_latest_weight, save_weight, get_daily_totals,
    save_memo, get_memo,
    save_exercise, get_daily_burned, get_exercise_log,
    delete_exercise_row, update_exercise_row,
    save_water, get_water_log, reset_water,
    get_favorites, add_favorite,
)

email = require_auth()

# ─── 세션 상태 ───────────────────────────────────────────────
if "pending_foods" not in st.session_state:
    st.session_state.pending_foods = []
if "editing_key" not in st.session_state:
    st.session_state.editing_key = None
if "editing_ex_key" not in st.session_state:
    st.session_state.editing_ex_key = None

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

# 감량 강도 기반 일일 목표
try:
    deficit_level = int(profile.get("deficit_level") or 700)
except (ValueError, TypeError):
    deficit_level = 700
daily_budget = round(tdee - deficit_level)
SAFETY_FLOOR = 1200
is_below_safety = daily_budget < SAFETY_FLOOR

# 체중 + 활동 수준 기반 영양소 목표
activity = profile.get("activity_level", "보통활동")
protein_mult = PROTEIN_MULTIPLIERS.get(activity, 1.3)
target_protein = round(latest_weight * protein_mult)
target_fat = round(daily_budget * 0.30 / 9)
target_carbs = round((daily_budget - target_protein * 4 - target_fat * 9) / 4)
if target_carbs < 0:
    target_carbs = 50

# ═══════════════════════════════════════════════════════════════
# 1. 날짜
# ═══════════════════════════════════════════════════════════════

from config import today_kst
selected_date = st.date_input("날짜", value=today_kst())
date_str = selected_date.isoformat()

# ═══════════════════════════════════════════════════════════════
# 2. 순 칼로리 게이지 (박스 영역)
# ═══════════════════════════════════════════════════════════════

today_totals = get_daily_totals(email, date_str, date_str)
eaten_cal = float(today_totals["total_cal"].sum()) if not today_totals.empty else 0
burned_cal = get_daily_burned(email, date_str)
net_cal = eaten_cal - burned_cal
remaining_cal = daily_budget - net_cal

if remaining_cal > daily_budget * 0.3:
    bar_color, status = "#4ADE80", f"남은 {remaining_cal:,.0f} kcal"
elif remaining_cal > 0:
    bar_color, status = "#FDE047", f"남은 {remaining_cal:,.0f} kcal"
else:
    bar_color, status = "#FB7185", f"{abs(remaining_cal):,.0f} kcal 초과"

gauge_max = max(daily_budget * 1.3, net_cal * 1.1, 100)
fig_budget = go.Figure(go.Indicator(
    mode="gauge+number",
    value=net_cal,
    gauge=dict(
        axis=dict(range=[0, gauge_max], tickfont=dict(size=10)),
        bar=dict(color=bar_color, thickness=0.3),
        steps=[
            dict(range=[0, daily_budget * 0.3], color="rgba(74,222,128,0.6)"),
            dict(range=[daily_budget * 0.3, daily_budget * 0.6], color="rgba(74,222,128,0.4)"),
            dict(range=[daily_budget * 0.6, daily_budget * 0.85], color="rgba(253,224,71,0.45)"),
            dict(range=[daily_budget * 0.85, daily_budget], color="rgba(251,176,59,0.5)"),
            dict(range=[daily_budget, daily_budget * 1.1], color="rgba(252,129,129,0.5)"),
            dict(range=[daily_budget * 1.1, gauge_max], color="rgba(252,129,129,0.7)"),
        ],
        threshold=dict(line=dict(color="#F8FAFC", width=2), value=daily_budget),
    ),
    title=dict(text="순 칼로리 (섭취 - 운동)", font=dict(size=14)),
    number=dict(suffix=f" / {daily_budget:,} kcal", font=dict(size=18), valueformat=","),
))
fig_budget.update_layout(**PLOT_CFG, height=180, margin=dict(l=15, r=15, t=45, b=0))
st.plotly_chart(fig_budget, use_container_width=True)

if burned_cal > 0:
    st.caption(f"{status} | 섭취 {eaten_cal:,.0f} - 운동 {burned_cal:,.0f} = 순 {net_cal:,.0f} kcal")
else:
    st.caption(status)

if is_below_safety:
    st.caption(f"⚠️ 일일 목표({daily_budget:,})가 안전 권장량({SAFETY_FLOOR:,}) 미만")

# ─── 오늘 영양소 (목표 대비 섭취량 바) ────────────────────────
t_carbs = float(today_totals["total_carbs"].sum()) if not today_totals.empty and "total_carbs" in today_totals.columns else 0
t_protein = float(today_totals["total_protein"].sum()) if not today_totals.empty and "total_protein" in today_totals.columns else 0
t_fat = float(today_totals["total_fat"].sum()) if not today_totals.empty and "total_fat" in today_totals.columns else 0


def _macro_bar(icon, name, current, goal, color):
    pct = current / goal * 100 if goal > 0 else 0
    bar_width = min(pct, 100)
    over = current - goal if current > goal else 0
    over_width = min(over / goal * 100, 50) if goal > 0 else 0
    status_color = color if pct <= 100 else "#FB7185"
    status_text = f"{current:.0f} / {goal}g" if pct <= 100 else f"{current:.0f} / {goal}g (+{over:.0f}g 초과)"
    return (
        f"<div style='margin:6px 0;'>"
        f"<div style='display:flex;align-items:center;gap:6px;margin-bottom:3px;'>"
        f"<span style='font-size:16px;'>{icon}</span>"
        f"<span style='font-size:12px;font-weight:600;color:#F8FAFC;'>{name}</span>"
        f"<span style='font-size:11px;color:{status_color};margin-left:auto;'>{status_text}</span>"
        f"</div>"
        f"<div style='background:rgba(30,41,59,0.8);border-radius:6px;height:14px;position:relative;overflow:hidden;'>"
        f"<div style='width:{bar_width}%;height:100%;background:{color};border-radius:6px;'></div>"
        f"{'<div style=\"position:absolute;top:0;left:' + str(bar_width) + '%;width:' + str(over_width) + '%;height:100%;background:#FB7185;border-radius:0 6px 6px 0;\"></div>' if over > 0 else ''}"
        f"</div></div>"
    )


# 영양소별 도넛 차트 3개
def _mini_donut(current, goal, color, bg_color):
    pct = min(current / goal * 100, 100) if goal > 0 else 0
    over = max(current - goal, 0)
    fig = go.Figure()
    if over > 0:
        # 초과: 빨간색 전체 + 중앙 텍스트
        fig.add_trace(go.Pie(
            values=[goal, over],
            marker=dict(colors=[color, "#FB7185"]),
            hole=0.7, textinfo="none", hoverinfo="skip",
            direction="clockwise", sort=False,
        ))
    else:
        # 미달: 색상 + 남은 부분 회색
        fig.add_trace(go.Pie(
            values=[current, goal - current],
            marker=dict(colors=[color, "rgba(30,41,59,0.6)"]),
            hole=0.7, textinfo="none", hoverinfo="skip",
            direction="clockwise", sort=False,
        ))
    fig.update_layout(
        **PLOT_CFG, height=110, showlegend=False,
        margin=dict(l=0, r=0, t=0, b=0),
        annotations=[dict(
            text=f"<b>{current:.0f}g</b>",
            x=0.5, y=0.5, font=dict(size=14, color=color if over == 0 else "#FB7185"),
            showarrow=False,
        )],
    )
    return fig

if t_carbs + t_protein + t_fat > 0:
    macros = [
        ("🍚 탄수화물", t_carbs, target_carbs, "#4ADE80"),
        ("🥩 단백질", t_protein, target_protein, "#60A5FA"),
        ("🧈 지방", t_fat, target_fat, "#FBBF24"),
    ]
    # Plotly subplots로 도넛 3개를 하나의 차트에 (모바일 가로 유지)
    from plotly.subplots import make_subplots
    fig_macros = make_subplots(
        rows=1, cols=3,
        specs=[[{"type": "pie"}, {"type": "pie"}, {"type": "pie"}]],
        horizontal_spacing=0.02,
    )
    annotations = []
    for i, (name, cur, goal, color) in enumerate(macros):
        over = max(cur - goal, 0)
        if over > 0:
            values = [goal, over]
            colors = [color, "#FB7185"]
        else:
            values = [cur, goal - cur]
            colors = [color, "rgba(30,41,59,0.6)"]
        fig_macros.add_trace(go.Pie(
            values=values,
            marker=dict(colors=colors),
            hole=0.7, textinfo="none", hoverinfo="skip",
            direction="clockwise", sort=False,
        ), row=1, col=i+1)
        # 중앙 텍스트
        x_pos = [0.13, 0.5, 0.87][i]
        annotations.append(dict(
            text=f"<b>{cur:.0f}g</b>",
            x=x_pos, y=0.5,
            font=dict(size=13, color=color if over == 0 else "#FB7185"),
            showarrow=False,
        ))

    fig_macros.update_layout(
        **PLOT_CFG, height=120, showlegend=False,
        margin=dict(l=0, r=0, t=0, b=0),
        annotations=annotations,
    )
    st.plotly_chart(fig_macros, use_container_width=True)

    # 라벨 (HTML로 가로 3칸)
    label_html = "<div style='display:flex;text-align:center;gap:4px;'>"
    for name, cur, goal, color in macros:
        over = cur - goal
        over_html = f"<div style='color:#FB7185;font-size:11px;'>+{over:.0f}g 초과</div>" if over > 0 else ""
        label_html += (
            f"<div style='flex:1;'>"
            f"<div style='font-size:12px;color:#F8FAFC;'>{name}</div>"
            f"<div style='font-size:11px;color:#94A3B8;'>{cur:.0f} / {goal}g</div>"
            f"{over_html}</div>"
        )
    label_html += "</div>"
    st.markdown(label_html, unsafe_allow_html=True)
    st.caption(f"목표 — 탄 {target_carbs}g · 단 {target_protein}g (체중×{protein_mult}) · 지 {target_fat}g (30%)")
else:
    st.caption("오늘 식사 기록이 없습니다.")

# ═══════════════════════════════════════════════════════════════
# 3. 통합 입력 폼
# ═══════════════════════════════════════════════════════════════

existing_memo = get_memo(email, date_str)
existing_condition = existing_memo.get("condition", "") if existing_memo else ""
existing_memo_text = existing_memo.get("memo", "") if existing_memo else ""

# 즐겨찾기 목록 (폼 안 multiselect용)
favorites = get_favorites(email)
fav_names = [f"{f['food_name']} ({f.get('calories', 0)}kcal)" for f in favorites] if favorites else []

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

    # 수동 음식
    st.markdown("---")
    st.markdown("**✏️ 수동 음식 추가** (한 줄에 하나씩)")
    manual_text = st.text_area(
        "음식 목록",
        placeholder="연어스테이크 1인분\n함박스테이크 반인분\n와인 1병",
        height=100, key="m_text", label_visibility="collapsed",
    )

    # 즐겨찾기 선택
    st.markdown("---")
    st.markdown("**⭐ 즐겨찾기에서 선택**")
    if fav_names:
        selected_favs = st.multiselect(
            "음식 선택 (복수 가능)",
            fav_names,
            key="fav_select", label_visibility="collapsed",
        )
    else:
        st.caption("즐겨찾기가 비어있습니다. 설정 > 즐겨찾기에서 등록하세요.")
        selected_favs = []

    # 물 섭취
    st.markdown("---")
    today_water = get_water_log(email, date_str)
    st.markdown(f"**💧 물 섭취** (오늘: {today_water}ml / {WATER_TARGET_ML}ml)")
    water_ml = st.number_input("추가 섭취량 (ml)", min_value=0, max_value=2000, value=0, step=100, key="water")

    # 컨디션/메모
    st.markdown("---")
    st.markdown("**📝 컨디션 & 메모**")
    cond_index = CONDITION_OPTIONS.index(existing_condition) if existing_condition in CONDITION_OPTIONS else 0
    memo_condition = st.selectbox("컨디션", CONDITION_OPTIONS, index=cond_index, key=f"m_cond_{date_str}")
    memo_text = st.text_input("메모", value=existing_memo_text, placeholder="오늘 식단에 대한 메모", key=f"m_memo_{date_str}")

    submitted = st.form_submit_button(
        "🔍 AI 분석 및 저장", type="primary", use_container_width=True,
    )

# ═══════════════════════════════════════════════════════════════
# 폼 제출 처리
# ═══════════════════════════════════════════════════════════════

if submitted:
    pending = []
    has_error = False

    # 사진 분석
    if uploaded:
        if uploaded.size > MAX_FILE_SIZE:
            st.error("10MB 이하만 가능")
            has_error = True
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
                    has_error = True
            if result and not result.get("error") and result.get("foods"):
                for f in result["foods"]:
                    f["source"] = "ai"
                pending.extend(result["foods"])
            elif result:
                st.warning(result.get("error", "음식을 인식하지 못했습니다."))

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
                has_error = True

    # 즐겨찾기 선택 음식
    if selected_favs:
        for sel_name in selected_favs:
            for fav in favorites:
                display = f"{fav['food_name']} ({fav.get('calories', 0)}kcal)"
                if display == sel_name:
                    pending.append({
                        "name": fav["food_name"], "amount": fav.get("amount", ""),
                        "calories": int(fav.get("calories", 0)),
                        "carbs": int(fav.get("carbs", 0)),
                        "protein": int(fav.get("protein", 0)),
                        "fat": int(fav.get("fat", 0)),
                        "quantity": 1.0, "source": "favorite",
                    })
                    break

    # 체중 저장 (항상)
    save_weight(email, date_str, today_weight)

    # 물 저장
    if water_ml > 0:
        save_water(email, date_str, water_ml)
        st.success(f"💧 물 {water_ml}ml 기록!")

    # 메모 저장
    if memo_text.strip() or memo_condition:
        save_memo(email, date_str, memo_condition, memo_text.strip())

    # 음식 바로 저장
    if pending:
        save_meals(email, date_str, meal_type, pending)
        total = sum(f.get("calories", 0) * f.get("quantity", 1) for f in pending)
        st.success(f"💾 {meal_type} {len(pending)}개 음식 ({total:,.0f}kcal) + 체중 {today_weight}kg 저장!")
    elif not has_error:
        st.success(f"💾 체중 {today_weight}kg 기록 완료!")

    # 에러 없을 때만 rerun (에러 메시지 유지)
    if not has_error:
        st.rerun()

# ═══════════════════════════════════════════════════════════════
# 운동 기록 (폼 밖 — multiselect 즉시 반응)
# ═══════════════════════════════════════════════════════════════

st.divider()
st.markdown("**🏃 운동 기록** (여러 개 선택 가능)")
ex_display = [f"{e['icon']} {e['name']}" for e in EXERCISE_OPTIONS]
selected_exercises = st.multiselect(
    "운동 선택", ex_display,
    key="ex_multi", label_visibility="collapsed",
)

if selected_exercises:
    ex_durations = {}
    for sel_ex in selected_exercises:
        idx = ex_display.index(sel_ex)
        dur = st.number_input(
            f"{sel_ex} 시간 (분)",
            min_value=5, max_value=300, value=30, step=5,
            key=f"exdur_{idx}",
        )
        ex_durations[idx] = dur

    if st.button("🏃 운동 저장", use_container_width=True):
        for idx, dur in ex_durations.items():
            ex_info = EXERCISE_OPTIONS[idx]
            met = ex_info["met"] if ex_info["met"] > 0 else 5.0
            save_exercise(email, date_str, ex_info["name"], dur, met, latest_weight)
            cal_burned = round(met * latest_weight * dur / 60)
            st.success(f"{ex_info['icon']} {ex_info['name']} {dur}분 ({cal_burned}kcal) 저장!")
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

# ─── 운동 기록 표시 (수정/삭제) ─────────────────────────────
ex_log = get_exercise_log(email, date_str, date_str)
if not ex_log.empty:
    st.markdown(f"**🏃 운동 기록** ({burned_cal:,.0f} kcal 소모)")
    for ex_idx, ex in ex_log.iterrows():
        ex_key = f"ex_{ex_idx}"
        is_ex_editing = st.session_state.editing_ex_key == ex_key

        if is_ex_editing:
            with st.form(f"edit_ex_{ex_key}"):
                st.markdown(f"**{ex['exercise_name']}** 수정")
                new_dur = st.number_input(
                    "시간 (분)", value=int(ex["duration_min"]),
                    min_value=5, max_value=300, step=5, key=f"exed_{ex_key}",
                )
                ebc1, ebc2 = st.columns(2)
                if ebc1.form_submit_button("저장", use_container_width=True):
                    update_exercise_row(
                        email, date_str, ex["exercise_name"],
                        str(ex.get("created_at", "")), new_dur, latest_weight,
                    )
                    st.session_state.editing_ex_key = None
                    st.rerun()
                if ebc2.form_submit_button("취소", use_container_width=True):
                    st.session_state.editing_ex_key = None
                    st.rerun()
        else:
            st.markdown(
                f"**{ex['exercise_name']}** {int(ex['duration_min'])}분 · "
                f"<span style='color:#94A3B8;'>{int(ex['calories_burned'])}kcal</span>",
                unsafe_allow_html=True,
            )
            ebc1, ebc2, ebc3 = st.columns([1, 1, 4])
            if ebc1.button("수정", key=f"exedit_{ex_key}", use_container_width=True):
                st.session_state.editing_ex_key = ex_key
                st.rerun()
            if ebc2.button("삭제", key=f"exdel_{ex_key}", use_container_width=True):
                delete_exercise_row(
                    email, date_str, ex["exercise_name"],
                    str(ex.get("created_at", "")),
                )
                st.rerun()

# ─── 물 섭취 표시 ────────────────────────────────────────────
total_water = get_water_log(email, date_str)
if total_water > 0:
    pct = min(total_water / WATER_TARGET_ML * 100, 100)
    wc1, wc2 = st.columns([4, 1])
    wc1.markdown(f"**💧 물 섭취** {total_water}ml / {WATER_TARGET_ML}ml ({pct:.0f}%)")
    if wc2.button("초기화", key="water_reset"):
        reset_water(email, date_str)
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

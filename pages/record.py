"""📸 식단 및 운동 기록 페이지 (탭 기반 리팩토링).

레이아웃:
- 상단: 날짜 + 체중 + 게이지(비교) + 영양소(큰 도넛 + 세로 바) + 주간 통계
- 탭: [🍽️ 식사] [🏃 운동] [💧 물] [📝 메모]
- 하단: 저장된 기록 (카드형, 시간순, 컬러 바, 삭제 취소)
"""

import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import (
    MEAL_TYPES, MAX_FILE_SIZE, PLOT_CFG, CONDITION_OPTIONS,
    EXERCISE_OPTIONS, WATER_TARGET_ML, today_kst,
)
from services.auth_service import require_auth
from services.gemini_service import analyze_food_image, estimate_multiple_foods
from services.calorie_service import (
    calc_bmr, calc_tdee, calc_exercise_plan,
    calc_protein_g, calc_fat_g, calc_carbs_g,
    evaluate_calorie_status,
)
from services.sheets_service import (
    get_profile, get_meals_for_date, save_meals, delete_meal_row, update_meal_row,
    delete_meals_by_type,
    get_latest_weight, save_weight, get_daily_totals,
    save_memo, get_memo,
    save_exercise, get_daily_burned, get_exercise_log,
    delete_exercise_row, update_exercise_row,
    save_water, get_water_log, reset_water,
    get_favorites, get_recent_foods, get_yesterday_meals, get_streak,
    lookup_food_nutrition,
)

email = require_auth()
st.title("🍽️ 식단 기록")

# ─── 세션 상태 ───────────────────────────────────────────────
for key, default in [
    ("editing_key", None), ("editing_ex_key", None),
    ("form_version", 0), ("ex_form_version", 0),
    ("last_deleted_meal", None), ("last_deleted_ex", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ═══════════════════════════════════════════════════════════════
# 프로필 + 계산
# ═══════════════════════════════════════════════════════════════

profile = get_profile(email) or {}

# ─── 첫 사용자 온보딩 ──────────────────────────────────────
if not profile:
    st.markdown("## 👋 환영합니다!")
    st.markdown(
        "식단 기록을 시작하기 전에 **프로필을 먼저 설정**해 주세요.  \n"
        "키·체중·활동 수준을 입력하면 개인 맞춤 칼로리 목표가 자동으로 계산됩니다."
    )
    st.info(
        "⏱️ 1분이면 설정 완료!\n\n"
        "**왜 프로필 설정이 먼저 필요한가요?**\n"
        "- 체중/활동량 기반으로 하루 섭취 목표 칼로리 계산\n"
        "- 단백질/탄수화물/지방 목표 영양소 자동 산출\n"
        "- 감량 속도 예측 및 목표 도달일 계산"
    )
    if st.button("👤 프로필 설정하러 가기", type="primary", use_container_width=True):
        st.switch_page("pages/profile.py")
    st.stop()

latest_weight = get_latest_weight(email) or float(profile.get("weight", 70))
bmr = calc_bmr(latest_weight, float(profile.get("height", 170)),
               int(profile.get("age", 30)), profile.get("gender", "남성"))
tdee = calc_tdee(bmr, profile.get("activity_level", "보통활동"))

try:
    deficit_level = int(profile.get("deficit_level") or 700)
except (ValueError, TypeError):
    deficit_level = 700
base_budget = round(tdee - deficit_level)

# 운동 칼로리 보정 — off / avg7 / daily (그날 운동 burn 기반)
_comp_raw = (profile.get("exercise_compensation") or "off").lower()
if _comp_raw == "on":  # 하위 호환
    _comp_raw = "avg7"
if _comp_raw not in ("off", "avg7", "daily"):
    _comp_raw = "off"
exercise_comp_mode = _comp_raw

target_protein, protein_mult = calc_protein_g(latest_weight, deficit_level)
# daily_budget·target_fat·target_carbs는 date_str 결정 후 재계산

# ═══════════════════════════════════════════════════════════════
# 상단: 날짜 + 체중
# ═══════════════════════════════════════════════════════════════

if "rec_date" not in st.session_state:
    st.session_state.rec_date = today_kst()
if "date_ver" not in st.session_state:
    st.session_state.date_ver = 0

# 날짜 빠른 이동 (query_params + 일반 session_state)
qp = st.query_params
if "date_nav" in qp:
    nav = qp["date_nav"]
    cur = st.session_state.rec_date
    if nav == "prev":
        st.session_state.rec_date = cur - datetime.timedelta(days=1)
    elif nav == "today":
        st.session_state.rec_date = today_kst()
    elif nav == "next":
        st.session_state.rec_date = cur + datetime.timedelta(days=1)
    st.session_state.date_ver += 1
    del st.query_params["date_nav"]
    st.rerun()

selected_date = st.date_input(
    "날짜", value=st.session_state.rec_date,
    key=f"dp_{st.session_state.date_ver}",
)
if selected_date != st.session_state.rec_date:
    st.session_state.rec_date = selected_date
date_str = st.session_state.rec_date.isoformat()

# date_str 결정 후 운동 보정 + 영양소 목표 계산
if exercise_comp_mode == "avg7":
    _end_d = today_kst()
    _start_d = _end_d - datetime.timedelta(days=7)
    _ex7 = get_exercise_log(email, _start_d.isoformat(), _end_d.isoformat())
    exercise_boost = int(_ex7["calories_burned"].sum() / 7) if not _ex7.empty else 0
elif exercise_comp_mode == "daily":
    exercise_boost = int(get_daily_burned(email, date_str))
else:
    exercise_boost = 0
daily_budget = base_budget + exercise_boost
target_fat, _fat_source = calc_fat_g(daily_budget, latest_weight)
target_carbs = calc_carbs_g(daily_budget, target_protein, target_fat)

st.markdown(
    "<div style='display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px;margin:4px 0 8px;'>"
    "<a href='?date_nav=prev' target='_self' style='background:rgba(30,41,59,0.5);"
    "border:1px solid rgba(148,163,184,0.2);color:#F8FAFC;padding:8px 0;"
    "border-radius:8px;text-align:center;text-decoration:none;font-size:13px;"
    "font-weight:500;'>◀ 어제</a>"
    "<a href='?date_nav=today' target='_self' style='background:rgba(30,41,59,0.5);"
    "border:1px solid rgba(148,163,184,0.2);color:#F8FAFC;padding:8px 0;"
    "border-radius:8px;text-align:center;text-decoration:none;font-size:13px;"
    "font-weight:500;'>오늘</a>"
    "<a href='?date_nav=next' target='_self' style='background:rgba(30,41,59,0.5);"
    "border:1px solid rgba(148,163,184,0.2);color:#F8FAFC;padding:8px 0;"
    "border-radius:8px;text-align:center;text-decoration:none;font-size:13px;"
    "font-weight:500;'>내일 ▶</a>"
    "</div>",
    unsafe_allow_html=True,
)

with st.expander("⚖️ 체중 기록", expanded=False):
    wc1, wc2 = st.columns([3, 1])
    with wc1:
        today_weight = st.number_input(
            "체중 (kg)", min_value=30.0, max_value=200.0,
            value=latest_weight, step=0.1, format="%.1f",
            key=f"weight_top_{date_str}", label_visibility="collapsed",
        )
    with wc2:
        if st.button("저장", use_container_width=True, key="btn_save_weight"):
            save_weight(email, date_str, today_weight)
            st.toast(f"✅ 체중 {today_weight}kg 저장!", icon="⚖️")
            st.rerun()

# ═══════════════════════════════════════════════════════════════
# 게이지 + 비교
# ═══════════════════════════════════════════════════════════════

today_totals = get_daily_totals(email, date_str, date_str)
eaten_cal = float(today_totals["total_cal"].sum()) if not today_totals.empty else 0
burned_cal = get_daily_burned(email, date_str)
net_cal = eaten_cal - burned_cal
# 보정 ON: 섭취 vs effective target (운동은 이미 target에 포함)
# 보정 OFF: 순칼로리 vs base target (운동은 추가 적자)
if exercise_comp_mode != "off":
    remaining_cal = daily_budget - eaten_cal
else:
    remaining_cal = daily_budget - net_cal

# 어제 비교
yesterday = (selected_date - datetime.timedelta(days=1)).isoformat()
y_totals = get_daily_totals(email, yesterday, yesterday)
y_cal = float(y_totals["total_cal"].sum()) if not y_totals.empty else 0

# 주평균 비교
week_start = (selected_date - datetime.timedelta(days=7)).isoformat()
w_totals = get_daily_totals(email, week_start, date_str)
w_avg = float(w_totals["total_cal"].mean()) if not w_totals.empty else 0

# 4단계 평가 — 보정 ON: 섭취 vs effective, OFF: 순 vs base
_eval_value = eaten_cal if exercise_comp_mode != "off" else net_cal
_eval_label, _eval_color, _eval_level = evaluate_calorie_status(_eval_value, daily_budget)

if _eval_level == "too_low":
    bar_color = "#60A5FA"
    fill_color = "#60A5FA"
    hero_text = f"<b style='font-size:28px;'>{remaining_cal:,.0f}</b> kcal 남음 <span style='font-size:13px;'>🔵 너무 적음</span>"
elif remaining_cal > daily_budget * 0.3:
    bar_color = "#22C55E"
    fill_color = "#22C55E"
    hero_text = f"남은 <b style='font-size:28px;'>{remaining_cal:,.0f}</b> kcal"
elif remaining_cal > 0:
    bar_color = "#FBBF24"
    fill_color = "#FBBF24"
    hero_text = f"남은 <b style='font-size:28px;'>{remaining_cal:,.0f}</b> kcal"
else:
    bar_color = "#EF4444"
    fill_color = "#FBBF24"
    hero_text = f"<b style='font-size:28px;'>{abs(remaining_cal):,.0f}</b> kcal 초과"

# 바 위치·is_over 모두 _eval_value 기준으로 통일
is_over = _eval_value > daily_budget
_cal_max = _eval_value * 1.02 if is_over else daily_budget * 1.08
_cal_max = max(_cal_max, 1)
cal_goal_pos = daily_budget / _cal_max * 100
cal_fill_pos = min(_eval_value, daily_budget) / _cal_max * 100
cal_over_pos = max(_eval_value - daily_budget, 0) / _cal_max * 100

# 하단 비교 텍스트
comp_parts = []
if exercise_comp_mode != "off" and burned_cal > 0:
    comp_parts.append(f"섭취 {eaten_cal:,.0f} · 운동 보정 +{int(exercise_boost):,}")
elif burned_cal > 0:
    comp_parts.append(f"섭취 {eaten_cal:,.0f} − 운동 {burned_cal:,.0f}")
if y_cal > 0:
    diff = eaten_cal - y_cal
    arrow, clr = ("↑", "#FB7185") if diff > 0 else ("↓", "#4ADE80")
    comp_parts.append(f"어제 <span style='color:{clr};'>{arrow}{abs(diff):,.0f}</span>")
if w_avg > 0:
    diff = eaten_cal - w_avg
    arrow, clr = ("↑", "#FB7185") if diff > 0 else ("↓", "#4ADE80")
    comp_parts.append(f"주평균 <span style='color:{clr};'>{arrow}{abs(diff):,.0f}</span>")
comp_html = " · ".join(comp_parts)

# 바 하단 라벨: 보정 ON이면 섭취 기준 표시, OFF면 순 기준
if exercise_comp_mode != "off":
    left_label = f"섭취 {eaten_cal:,.0f} kcal"
else:
    left_label = f"순 {net_cal:,.0f} kcal"

st.markdown(
    f"<div style='background:rgba(30,41,59,0.5);"
    f"border:1px solid {'#EF4444' if is_over else ('#60A5FA' if _eval_level == 'too_low' else 'rgba(148,163,184,0.15)')};"
    f"border-radius:12px;padding:14px;margin:4px 0;'>"
    f"<div style='text-align:center;color:{bar_color};margin-bottom:8px;'>{hero_text}</div>"
    f"<div style='background:rgba(15,23,42,0.6);border-radius:6px;height:14px;position:relative;overflow:hidden;'>"
    f"<div style='width:{cal_fill_pos:.1f}%;height:100%;background:{fill_color};border-radius:6px 0 0 6px;'></div>"
    f"{'<div style=\"position:absolute;top:0;left:' + f'{cal_goal_pos:.1f}' + '%;width:' + f'{cal_over_pos:.1f}' + '%;height:100%;background:#EF4444;\"></div>' if is_over else ''}"
    f"<div style='position:absolute;left:{cal_goal_pos:.1f}%;top:0;width:2px;height:100%;background:#F8FAFC;z-index:1;'></div>"
    f"</div>"
    f"<div style='display:flex;justify-content:space-between;font-size:11px;color:#94A3B8;margin-top:6px;'>"
    f"<span>{left_label}</span>"
    f"<span>{'⚠️ ' if is_over else ''}목표 {daily_budget:,} kcal</span></div>"
    f"{'<div style=\"text-align:center;font-size:11px;color:#94A3B8;margin-top:4px;\">' + comp_html + '</div>' if comp_html else ''}"
    f"</div>",
    unsafe_allow_html=True,
)

if daily_budget < 1200:
    st.caption(f"⚠️ 일일 목표({daily_budget:,})가 안전 권장량(1,200) 미만")
if _eval_level == "too_low" and net_cal > 0:
    st.caption(f"🔵 순칼로리 {net_cal:,.0f} kcal — 에너지 부족 위험. 더 드셔도 됩니다.")

# ═══════════════════════════════════════════════════════════════
# 영양소 (큰 도넛 + 세로 바)
# ═══════════════════════════════════════════════════════════════

t_carbs = float(today_totals["total_carbs"].sum()) if not today_totals.empty and "total_carbs" in today_totals.columns else 0
t_protein = float(today_totals["total_protein"].sum()) if not today_totals.empty and "total_protein" in today_totals.columns else 0
t_fat = float(today_totals["total_fat"].sum()) if not today_totals.empty and "total_fat" in today_totals.columns else 0

def _bar_html(icon, name, cur, goal, color):
    bmax = cur * 1.02 if cur > goal else goal * 1.08
    bmax = max(bmax, 1)
    gpos = goal / bmax * 100
    fpos = min(cur, goal) / bmax * 100
    opos = max(cur - goal, 0) / bmax * 100
    over_val = max(cur - goal, 0)
    ov = cur > goal
    status = f"{cur:.0f}/{goal}g" if not ov else f"{cur:.0f}/{goal}g <span style='color:#FB7185;'>(+{over_val:.0f})</span>"
    return (
        f"<div style='margin:6px 0;'>"
        f"<div style='display:flex;gap:6px;font-size:13px;margin-bottom:3px;'>"
        f"<span>{icon} {name}</span>"
        f"<span style='margin-left:auto;color:#94A3B8;'>{status}</span>"
        f"</div>"
        f"<div style='background:rgba(30,41,59,0.8);border-radius:6px;height:14px;position:relative;overflow:hidden;'>"
        f"<div style='width:{fpos:.1f}%;height:100%;background:{color};'></div>"
        f"{'<div style=\"position:absolute;top:0;left:' + f'{gpos:.1f}' + '%;width:' + f'{opos:.1f}' + '%;height:100%;background:#EF4444;\"></div>' if ov else ''}"
        f"<div style='position:absolute;left:{gpos:.1f}%;top:0;width:2px;height:100%;background:#F8FAFC;z-index:1;'></div>"
        f"</div></div>"
    )

if t_carbs + t_protein + t_fat > 0:
    dc_l, dc_c, dc_r = st.columns([1, 2, 1])
    with dc_c:
        fig = go.Figure(go.Pie(
            labels=["탄수화물", "단백질", "지방"],
            values=[t_carbs, t_protein, t_fat],
            marker=dict(colors=["#4ADE80", "#60A5FA", "#FBBF24"]),
            textinfo="percent", textposition="inside",
            textfont=dict(size=12, color="#0F172A"),
            hole=0.58, sort=False,
            hovertemplate="%{label}: %{value:.0f}g<extra></extra>",
        ))
        fig.update_layout(**PLOT_CFG, height=180, showlegend=False,
            margin=dict(l=5, r=5, t=5, b=5),
            annotations=[dict(
                text=f"<b>{eaten_cal:,.0f}</b><br><span style='font-size:10px;color:#94A3B8;'>kcal</span>",
                x=0.5, y=0.5, font=dict(size=16), showarrow=False,
            )],
        )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown(
        _bar_html("🍚", "탄수화물", t_carbs, target_carbs, "#4ADE80")
        + _bar_html("🥩", "단백질", t_protein, target_protein, "#60A5FA")
        + _bar_html("🧈", "지방", t_fat, target_fat, "#FBBF24"),
        unsafe_allow_html=True,
    )
else:
    st.caption("오늘 식사 기록이 없습니다.")

# 주간 통계 + 연속 기록 (통합 카드)
streak = get_streak(email)
week_stats = ""
if not w_totals.empty:
    days_recorded = len(w_totals)
    over_days = int((w_totals["total_cal"] > daily_budget).sum())
    week_stats = (
        f"<div style='font-size:12px;color:#94A3B8;'>"
        f"📊 이번 주 {days_recorded}일 기록 · 평균 {w_avg:,.0f}kcal · 초과 {over_days}일</div>"
    )

streak_html = ""
if streak >= 3:
    if streak >= 30:
        badge, msg = "🏆", f"{streak}일 연속! 대단해요!"
    elif streak >= 14:
        badge, msg = "🌟", f"{streak}일 연속 기록 중!"
    elif streak >= 7:
        badge, msg = "🔥", f"{streak}일 연속 기록 중!"
    else:
        badge, msg = "✨", f"{streak}일 연속 기록 중!"
    streak_html = f"<div style='font-size:13px;'>{badge} <span style='color:#FBBF24;font-weight:600;'>{msg}</span></div>"

if week_stats or streak_html:
    st.markdown(
        f"<div style='background:rgba(30,41,59,0.3);border:1px solid rgba(148,163,184,0.1);"
        f"border-radius:10px;padding:10px 12px;margin:6px 0;'>"
        f"{streak_html}{week_stats}</div>",
        unsafe_allow_html=True,
    )

# ═══════════════════════════════════════════════════════════════
# 식사유형 자동 추천 (시간대 기반)
# ═══════════════════════════════════════════════════════════════

def _auto_meal_type() -> str:
    now = datetime.datetime.now().hour
    if 5 <= now < 11:
        return "아침"
    elif 11 <= now < 14:
        return "점심"
    elif 17 <= now < 21:
        return "저녁"
    else:
        return "간식"

default_meal = _auto_meal_type()

# ═══════════════════════════════════════════════════════════════
# 탭 구성
# ═══════════════════════════════════════════════════════════════

st.divider()
tab_meal, tab_exercise, tab_water, tab_memo = st.tabs([
    "🍽️ 식사", "🏃 운동", "💧 물", "📝 메모"
])

# ─── 탭 1: 식사 ─────────────────────────────────────────────
with tab_meal:
    meal_type = st.radio(
        "식사 유형", MEAL_TYPES,
        index=MEAL_TYPES.index(default_meal),
        horizontal=True, key=f"meal_type_{st.session_state.form_version}",
    )

    # 어제 식단 복사 버튼
    yest_meals = get_yesterday_meals(email, date_str)
    yest_meal_df = yest_meals[yest_meals["meal_type"] == meal_type] if not yest_meals.empty else pd.DataFrame()
    if not yest_meal_df.empty:
        total_y = yest_meal_df["total_cal"].astype(float).sum() if "total_cal" in yest_meal_df.columns else 0
        if st.button(f"📋 어제 {meal_type} 복사 ({len(yest_meal_df)}개, {total_y:,.0f}kcal)",
                     use_container_width=True, key="btn_copy_yesterday"):
            foods_to_copy = []
            for _, row in yest_meal_df.iterrows():
                foods_to_copy.append({
                    "name": row.get("food_name", ""),
                    "amount": row.get("amount", ""),
                    "calories": int(row.get("calories", 0)),
                    "carbs": int(row.get("carbs", 0)),
                    "protein": int(row.get("protein", 0)),
                    "fat": int(row.get("fat", 0)),
                    "quantity": float(row.get("quantity", 1.0)),
                    "source": "copy",
                })
            save_meals(email, date_str, meal_type, foods_to_copy)
            st.toast(f"✅ 어제 {meal_type} {len(foods_to_copy)}개 복사!", icon="📋")
            st.rerun()

    # 최근 먹은 음식 원터치
    recent = get_recent_foods(email, days=3, limit=8)
    if not recent.empty:
        with st.expander(f"🕐 최근 먹은 음식 ({len(recent)}개)", expanded=False):
            for i, rf in recent.iterrows():
                rc1, rc2 = st.columns([4, 1])
                rc1.caption(f"**{rf['food_name']}** · {int(rf['calories'])}kcal")
                if rc2.button("추가", key=f"recent_{i}", use_container_width=True):
                    save_meals(email, date_str, meal_type, [{
                        "name": rf["food_name"], "amount": rf.get("amount", ""),
                        "calories": int(rf["calories"]), "carbs": int(rf["carbs"]),
                        "protein": int(rf["protein"]), "fat": int(rf["fat"]),
                        "quantity": 1.0, "source": "recent",
                    }])
                    st.toast(f"✅ {rf['food_name']} 추가!", icon="🕐")
                    st.rerun()

    # 입력 폼
    favorites = get_favorites(email)
    fav_names = [f"{f['food_name']} ({f.get('calories', 0)}kcal)" for f in favorites] if favorites else []

    with st.form(f"meal_form_{st.session_state.form_version}"):
        st.markdown("**📷 음식 사진** (여러 장 가능)")
        uploaded_files = st.file_uploader(
            "사진 업로드", type=["jpg", "jpeg", "png"],
            help="JPG, PNG / 최대 10MB", label_visibility="collapsed",
            accept_multiple_files=True,
        )

        st.markdown("---")
        st.markdown("**✏️ 수동 음식 추가** (한 줄에 하나씩)")
        manual_text = st.text_area(
            "음식 목록",
            placeholder="연어스테이크 1인분\n함박스테이크 반인분\n와인 1병",
            height=100, label_visibility="collapsed",
        )

        st.markdown("---")
        st.markdown("**⭐ 즐겨찾기에서 선택**")
        if fav_names:
            selected_favs = st.multiselect(
                "음식 선택", fav_names, label_visibility="collapsed",
            )
        else:
            st.caption("즐겨찾기가 비어있습니다. 설정 > 즐겨찾기에서 등록하세요.")
            selected_favs = []

        meal_submitted = st.form_submit_button(
            "🔍 AI 분석 및 저장", type="primary", use_container_width=True,
        )

    # 폼 제출 처리
    if meal_submitted:
        pending = []
        has_error = False

        for uploaded in uploaded_files or []:
            if uploaded.size > MAX_FILE_SIZE:
                st.error(f"{uploaded.name}: 10MB 초과")
                has_error = True
                continue
            st.image(uploaded, width=180)
            ext = uploaded.name.rsplit(".", 1)[-1].lower()
            media_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"}
            with st.spinner(f"🔍 {uploaded.name} AI 분석 중... (5~15초 소요)"):
                try:
                    result = analyze_food_image(uploaded.getvalue(), media_map.get(ext, "image/jpeg"))
                    if result and not result.get("error") and result.get("foods"):
                        for f in result["foods"]:
                            f["source"] = "ai"
                        pending.extend(result["foods"])
                except Exception as e:
                    st.error(f"분석 오류: {e}")
                    has_error = True

        food_lines = [l.strip() for l in manual_text.strip().split("\n") if l.strip()] if manual_text.strip() else []
        if food_lines:
            # 1단계: 로컬 기록 조회 (즐겨찾기 + 최근 30일) — Gemini 호출 없음
            local_hits = []
            needs_ai = []
            for line in food_lines:
                # "반인분", "2인분" 등 수량 표현 제거하고 음식명만 추출
                bare_name = line.split(" ")[0] if " " in line else line
                found = lookup_food_nutrition(email, bare_name)
                if found:
                    local_hits.append(found)
                else:
                    needs_ai.append(line)

            if local_hits:
                pending.extend(local_hits)
                st.info(f"✅ {len(local_hits)}개 음식을 기존 기록에서 가져왔습니다 (AI 호출 생략)")

            # 2단계: 로컬에 없는 음식만 Gemini 호출
            if needs_ai:
                with st.spinner(f"🔍 {len(needs_ai)}개 음식 AI 추정 중..."):
                    try:
                        estimated = estimate_multiple_foods(needs_ai)
                        for f in estimated:
                            f["source"] = "manual"
                        pending.extend(estimated)
                    except Exception as e:
                        st.error(f"추정 실패: {e}")
                        has_error = True

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

        if pending:
            save_meals(email, date_str, meal_type, pending)
            total = sum(f.get("calories", 0) * f.get("quantity", 1) for f in pending)
            st.toast(f"✅ {meal_type} {len(pending)}개 ({total:,.0f}kcal) 저장!", icon="🍽️")

            # 목표 달성 축하 토스트
            new_eaten = eaten_cal + total
            new_protein = t_protein + sum(f.get("protein", 0) * f.get("quantity", 1) for f in pending)
            if eaten_cal < daily_budget <= new_eaten:
                st.toast("🎉 오늘 칼로리 목표 달성!", icon="🎯")
            if t_protein < target_protein <= new_protein:
                st.toast(f"🥩 단백질 목표 달성! ({new_protein:.0f}g)", icon="💪")

        if not has_error:
            st.session_state.form_version += 1
            st.rerun()

# ─── 탭 2: 운동 ─────────────────────────────────────────────
with tab_exercise:
    ev = st.session_state.ex_form_version
    ex_display = [f"{e['icon']} {e['name']}" for e in EXERCISE_OPTIONS]
    selected_exercises = st.multiselect(
        "운동 선택 (여러 개 가능)", ex_display, key=f"ex_multi_{ev}",
    )

    if selected_exercises:
        ex_durations = {}
        for sel_ex in selected_exercises:
            idx = ex_display.index(sel_ex)
            dur = st.number_input(
                f"{sel_ex} 시간 (분)",
                min_value=5, max_value=300, value=30, step=5,
                key=f"exdur_{idx}_{ev}",
            )
            ex_durations[idx] = dur

        if st.button("🏃 운동 저장", use_container_width=True, type="primary"):
            total_burned = 0
            for idx, dur in ex_durations.items():
                ex_info = EXERCISE_OPTIONS[idx]
                met = ex_info["met"] if ex_info["met"] > 0 else 5.0
                save_exercise(email, date_str, ex_info["name"], dur, met, latest_weight)
                total_burned += round(met * latest_weight * dur / 60)
            st.toast(f"✅ {len(ex_durations)}개 운동 ({total_burned}kcal 소모) 저장!", icon="🏃")
            st.session_state.ex_form_version += 1
            st.rerun()

# ─── 탭 3: 물 ────────────────────────────────────────────────
with tab_water:
    total_water = get_water_log(email, date_str)
    pct = min(total_water / WATER_TARGET_ML * 100, 100)
    st.markdown(f"**오늘 섭취: {total_water}ml / {WATER_TARGET_ML}ml ({pct:.0f}%)**")

    wfv = st.session_state.form_version
    water_ml = st.number_input(
        "추가 섭취량 (ml)", min_value=0, max_value=2000, value=0, step=100,
        key=f"water_amt_{wfv}",
    )
    wbc1, wbc2 = st.columns(2)
    if wbc1.button("💧 물 저장", use_container_width=True, type="primary", key="btn_save_water"):
        if water_ml > 0:
            save_water(email, date_str, water_ml)
            st.toast(f"✅ 물 {water_ml}ml 추가!", icon="💧")
            st.session_state.form_version += 1
            st.rerun()
    if wbc2.button("초기화", use_container_width=True, key="btn_reset_water"):
        reset_water(email, date_str)
        st.toast("물 기록 초기화", icon="🔄")
        st.rerun()

    # 빠른 추가 버튼
    st.caption("빠른 추가:")
    qc1, qc2, qc3, qc4 = st.columns(4)
    for col, ml in [(qc1, 200), (qc2, 330), (qc3, 500), (qc4, 1000)]:
        if col.button(f"{ml}ml", use_container_width=True, key=f"qwater_{ml}"):
            save_water(email, date_str, ml)
            st.toast(f"✅ 물 {ml}ml 추가!", icon="💧")
            st.rerun()

# ─── 탭 4: 메모 ─────────────────────────────────────────────
with tab_memo:
    existing_memo = get_memo(email, date_str)
    existing_cond = existing_memo.get("condition", "") if existing_memo else ""
    existing_text = existing_memo.get("memo", "") if existing_memo else ""

    cond_idx = CONDITION_OPTIONS.index(existing_cond) if existing_cond in CONDITION_OPTIONS else 0
    memo_condition = st.selectbox("컨디션", CONDITION_OPTIONS, index=cond_idx, key=f"mcond_{date_str}")
    memo_text = st.text_area("메모", value=existing_text, placeholder="오늘 식단에 대한 메모",
                              height=100, key=f"mmemo_{date_str}")

    if st.button("📝 메모 저장", use_container_width=True, type="primary"):
        save_memo(email, date_str, memo_condition, memo_text.strip())
        st.toast("✅ 메모 저장!", icon="📝")
        st.rerun()

# ═══════════════════════════════════════════════════════════════
# 저장된 기록 (시간순 + 카드형 + 컬러바 + 삭제취소)
# ═══════════════════════════════════════════════════════════════

st.divider()
saved = get_meals_for_date(email, date_str)

# 마지막 삭제 취소 버튼
if st.session_state.last_deleted_meal:
    deleted = st.session_state.last_deleted_meal
    uc1, uc2 = st.columns([4, 1])
    uc1.caption(f"🗑️ '{deleted['food_name']}' 삭제됨")
    if uc2.button("↩ 되돌리기", key="btn_undo_meal", use_container_width=True):
        save_meals(email, date_str, deleted["meal_type"], [deleted])
        st.session_state.last_deleted_meal = None
        st.toast("✅ 복구됨", icon="↩")
        st.rerun()

if saved.empty:
    st.markdown(
        f"<div style='text-align:center;padding:30px 20px;background:rgba(30,41,59,0.3);border-radius:12px;'>"
        f"<div style='font-size:48px;'>🍽️</div>"
        f"<div style='margin-top:8px;color:#94A3B8;'>{date_str} 식단 기록이 없습니다</div>"
        f"<div style='font-size:12px;color:#64748B;margin-top:4px;'>위의 '식사' 탭에서 음식을 추가해 보세요</div>"
        f"</div>",
        unsafe_allow_html=True,
    )
else:
    st.markdown(f"#### 📋 {date_str} 저장된 기록")

    for c in ["calories", "carbs", "protein", "fat", "quantity", "total_cal"]:
        if c in saved.columns:
            saved[c] = pd.to_numeric(saved[c], errors="coerce").fillna(0)

    saved_total = saved["total_cal"].sum()
    st.caption(f"총 {saved_total:,.0f} kcal")

    # 식사유형별 색상
    MEAL_COLORS = {
        "아침": "#F59E0B", "점심": "#22C55E",
        "저녁": "#3B82F6", "간식": "#A855F7",
    }

    for mt in MEAL_TYPES:
        meal_df = saved[saved["meal_type"] == mt].copy()
        if meal_df.empty:
            continue

        # 시간순 정렬 (created_at 기준)
        if "created_at" in meal_df.columns:
            meal_df = meal_df.sort_values("created_at")

        mt_carbs = (meal_df["carbs"] * meal_df["quantity"]).sum()
        mt_protein = (meal_df["protein"] * meal_df["quantity"]).sum()
        mt_fat = (meal_df["fat"] * meal_df["quantity"]).sum()
        color = MEAL_COLORS.get(mt, "#64748B")

        st.markdown(
            f"<div style='border-left:4px solid {color};padding-left:10px;margin-top:12px;'>"
            f"<span style='font-weight:600;color:{color};'>{mt}</span> "
            f"<span style='color:#94A3B8;'>({meal_df['total_cal'].sum():,.0f} kcal · "
            f"🍚 {mt_carbs:.0f}g · 🥩 {mt_protein:.0f}g · 🧈 {mt_fat:.0f}g)</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

        # 식사 유형 일괄 삭제 (확인용 토글)
        confirm_key = f"confirm_del_{mt}"
        if confirm_key not in st.session_state:
            st.session_state[confirm_key] = False

        mbc1, mbc2 = st.columns([5, 1])
        if not st.session_state[confirm_key]:
            if mbc2.button(f"전체 삭제", key=f"mass_del_{mt}", use_container_width=True):
                st.session_state[confirm_key] = True
                st.rerun()
        else:
            mbc1.caption(f"⚠️ {mt} 전체 {len(meal_df)}개를 삭제할까요?")
            cdc1, cdc2 = st.columns(2)
            if cdc1.button("확인", key=f"confirm_yes_{mt}", use_container_width=True, type="primary"):
                count = delete_meals_by_type(email, date_str, mt)
                st.session_state[confirm_key] = False
                st.toast(f"🗑️ {mt} {count}개 삭제!", icon="🗑️")
                st.rerun()
            if cdc2.button("취소", key=f"confirm_no_{mt}", use_container_width=True):
                st.session_state[confirm_key] = False
                st.rerun()

        for idx, row in meal_df.iterrows():
            row_key = f"{mt}_{idx}"
            is_editing = st.session_state.editing_key == row_key

            if is_editing:
                # 빠른 인분 버튼은 form 밖에서 (즉시 session_state 반영)
                qty_key = f"edit_qty_{row_key}"
                if qty_key not in st.session_state:
                    st.session_state[qty_key] = float(row["quantity"])

                st.markdown(f"**{row['food_name']}** 수정")
                st.caption("빠른 인분 선택 (아래 폼에 즉시 반영):")
                qc = st.columns(4)
                for i, q in enumerate([0.5, 1.0, 1.5, 2.0]):
                    if qc[i].button(f"{q}인분", key=f"qq_{row_key}_{q}", use_container_width=True):
                        st.session_state[qty_key] = q
                        st.rerun()

                with st.form(f"edit_form_{row_key}"):
                    ec1, ec2 = st.columns(2)
                    edit_cal = ec1.number_input("칼로리 (kcal)", value=int(row["calories"]), min_value=0)
                    edit_qty = ec2.number_input(
                        "인분", value=st.session_state[qty_key],
                        min_value=0.25, max_value=10.0, step=0.25,
                    )
                    ec3, ec4, ec5 = st.columns(3)
                    edit_carbs = ec3.number_input("탄(g)", value=int(row.get("carbs", 0)), min_value=0)
                    edit_protein = ec4.number_input("단(g)", value=int(row.get("protein", 0)), min_value=0)
                    edit_fat = ec5.number_input("지(g)", value=int(row.get("fat", 0)), min_value=0)
                    bc1, bc2 = st.columns(2)
                    if bc1.form_submit_button("저장", use_container_width=True, type="primary"):
                        update_meal_row(
                            email, date_str, row["food_name"], str(row.get("created_at", "")),
                            edit_cal, edit_qty, edit_carbs, edit_protein, edit_fat,
                        )
                        st.session_state.editing_key = None
                        st.session_state.pop(qty_key, None)
                        st.toast("✅ 수정됨", icon="✏️")
                        st.rerun()
                    if bc2.form_submit_button("취소", use_container_width=True):
                        st.session_state.editing_key = None
                        st.session_state.pop(qty_key, None)
                        st.rerun()
            else:
                # 시간 표시 (created_at에서 HH:MM 추출)
                time_str = ""
                if row.get("created_at"):
                    try:
                        time_str = str(row["created_at"])[11:16]
                    except Exception:
                        pass

                st.markdown(
                    f"<div style='background:rgba(30,41,59,0.4);border-radius:8px;padding:8px 12px;margin:6px 0;'>"
                    f"<div style='display:flex;align-items:center;gap:8px;'>"
                    f"<span style='font-weight:600;'>{row['food_name']}</span>"
                    f"<span style='font-size:12px;color:#94A3B8;'>{row.get('amount', '')}</span>"
                    f"<span style='font-size:11px;color:#64748B;margin-left:auto;'>{time_str}</span>"
                    f"</div>"
                    f"<div style='font-size:12px;color:#94A3B8;margin-top:2px;'>"
                    f"{int(row['calories'])}kcal × {row['quantity']}인분 = {int(row['total_cal'])}kcal · "
                    f"🍚 {int(row.get('carbs', 0))}g · 🥩 {int(row.get('protein', 0))}g · 🧈 {int(row.get('fat', 0))}g"
                    f"</div></div>",
                    unsafe_allow_html=True,
                )
                bc1, bc2, bc3 = st.columns([1, 1, 4])
                if bc1.button("수정", key=f"sedit_{row_key}", use_container_width=True):
                    st.session_state.editing_key = row_key
                    st.rerun()
                if bc2.button("삭제", key=f"sdel_{row_key}", use_container_width=True):
                    # 삭제 전 백업 (되돌리기용)
                    st.session_state.last_deleted_meal = {
                        "food_name": row["food_name"], "amount": row.get("amount", ""),
                        "calories": int(row["calories"]), "carbs": int(row.get("carbs", 0)),
                        "protein": int(row.get("protein", 0)), "fat": int(row.get("fat", 0)),
                        "quantity": float(row["quantity"]), "source": row.get("source", "ai"),
                        "meal_type": mt,
                    }
                    delete_meal_row(email, date_str, row["food_name"], str(row.get("created_at", "")))
                    st.rerun()

# ─── 운동 기록 (수정/삭제 + 삭제취소) ────────────────────────
ex_log = get_exercise_log(email, date_str, date_str)
if not ex_log.empty or st.session_state.last_deleted_ex:
    st.markdown(f"**🏃 운동 기록** ({burned_cal:,.0f} kcal 소모)")

    if st.session_state.last_deleted_ex:
        deleted_ex = st.session_state.last_deleted_ex
        euc1, euc2 = st.columns([4, 1])
        euc1.caption(f"🗑️ '{deleted_ex['exercise_name']}' 운동 삭제됨")
        if euc2.button("↩ 되돌리기", key="btn_undo_ex", use_container_width=True):
            save_exercise(email, date_str, deleted_ex["exercise_name"],
                         int(deleted_ex["duration_min"]), float(deleted_ex["met"]), latest_weight)
            st.session_state.last_deleted_ex = None
            st.toast("✅ 복구됨", icon="↩")
            st.rerun()

    for ex_idx, ex in ex_log.iterrows():
        ex_key = f"ex_{ex_idx}"
        is_ex_editing = st.session_state.editing_ex_key == ex_key

        if is_ex_editing:
            with st.form(f"edit_ex_{ex_key}"):
                st.markdown(f"**{ex['exercise_name']}** 수정")
                new_dur = st.number_input("시간 (분)", value=int(ex["duration_min"]),
                    min_value=5, max_value=300, step=5)
                ebc1, ebc2 = st.columns(2)
                if ebc1.form_submit_button("저장", use_container_width=True, type="primary"):
                    update_exercise_row(email, date_str, ex["exercise_name"],
                        str(ex.get("created_at", "")), new_dur, latest_weight)
                    st.session_state.editing_ex_key = None
                    st.toast("✅ 수정됨", icon="✏️")
                    st.rerun()
                if ebc2.form_submit_button("취소", use_container_width=True):
                    st.session_state.editing_ex_key = None
                    st.rerun()
        else:
            st.markdown(
                f"<div style='background:rgba(30,41,59,0.4);border-radius:8px;padding:8px 12px;margin:6px 0;'>"
                f"<span style='font-weight:600;'>{ex['exercise_name']}</span> "
                f"<span style='color:#94A3B8;'>{int(ex['duration_min'])}분 · {int(ex['calories_burned'])}kcal</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
            ebc1, ebc2, ebc3 = st.columns([1, 1, 4])
            if ebc1.button("수정", key=f"exedit_{ex_key}", use_container_width=True):
                st.session_state.editing_ex_key = ex_key
                st.rerun()
            if ebc2.button("삭제", key=f"exdel_{ex_key}", use_container_width=True):
                st.session_state.last_deleted_ex = {
                    "exercise_name": ex["exercise_name"],
                    "duration_min": ex["duration_min"],
                    "met": ex.get("met", 5.0),
                    "calories_burned": ex["calories_burned"],
                }
                delete_exercise_row(email, date_str, ex["exercise_name"], str(ex.get("created_at", "")))
                st.rerun()

# ─── 물 섭취 표시 ────────────────────────────────────────────
if total_water > 0:
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
    with st.expander("🔥 이 칼로리 소모하려면?", expanded=False):
        for ex in calc_exercise_plan(saved_total, latest_weight):
            st.caption(f"{ex['icon']} {ex['name']}: **{ex['rec_time']}분** ({ex['kcal_per_min']}kcal/분)")

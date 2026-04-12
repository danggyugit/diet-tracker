"""📅 캘린더 페이지 — 월별 칼로리 히트맵 + 일자 드릴다운."""

import calendar
import datetime

import plotly.graph_objects as go
import streamlit as st

from config import PLOT_CFG, MEAL_TYPES
from services.auth_service import require_auth
from services.sheets_service import (
    get_daily_totals, get_meals_for_date, get_profile, get_memo,
)
from services.calorie_service import calc_bmr, calc_tdee

email = require_auth()
st.title("📅 캘린더")

# ─── 프로필 → TDEE 기준값 ──────────────────────────────────
profile = get_profile(email) or {}
bmr = calc_bmr(
    float(profile.get("weight", 70)),
    float(profile.get("height", 170)),
    int(profile.get("age", 30)),
    profile.get("gender", "남성"),
)
tdee = calc_tdee(bmr, profile.get("activity_level", "보통활동"))
target = int(profile.get("target_calories", 0)) or round(tdee)

# ─── 월/년 네비게이터 ────────────────────────────────────────
if "cal_year" not in st.session_state:
    st.session_state.cal_year = datetime.date.today().year
if "cal_month" not in st.session_state:
    st.session_state.cal_month = datetime.date.today().month
if "cal_selected_date" not in st.session_state:
    st.session_state.cal_selected_date = None

col_prev, col_title, col_next = st.columns([1, 3, 1])
with col_prev:
    if st.button("◀ 이전"):
        if st.session_state.cal_month == 1:
            st.session_state.cal_month = 12
            st.session_state.cal_year -= 1
        else:
            st.session_state.cal_month -= 1
        st.session_state.cal_selected_date = None
        st.rerun()
with col_title:
    st.markdown(
        f"<h3 style='text-align:center;margin:0;'>"
        f"{st.session_state.cal_year}년 {st.session_state.cal_month}월</h3>",
        unsafe_allow_html=True,
    )
with col_next:
    if st.button("다음 ▶"):
        if st.session_state.cal_month == 12:
            st.session_state.cal_month = 1
            st.session_state.cal_year += 1
        else:
            st.session_state.cal_month += 1
        st.session_state.cal_selected_date = None
        st.rerun()

year = st.session_state.cal_year
month = st.session_state.cal_month

# ─── 해당 월 데이터 로드 ─────────────────────────────────────
first_day = datetime.date(year, month, 1)
last_day = datetime.date(year, month, calendar.monthrange(year, month)[1])
totals_df = get_daily_totals(email, first_day.isoformat(), last_day.isoformat())
daily_map = {}
if not totals_df.empty:
    for _, row in totals_df.iterrows():
        daily_map[row["date"]] = int(row["total_cal"])

# ─── 캘린더 그리드 ───────────────────────────────────────────
cal = calendar.Calendar(firstweekday=0)  # 월요일 시작
weeks = cal.monthdatescalendar(year, month)

# 요일 헤더
day_names = ["월", "화", "수", "목", "금", "토", "일"]
header_cols = st.columns(7)
for i, name in enumerate(day_names):
    header_cols[i].markdown(f"<div style='text-align:center;font-weight:bold;color:#94A3B8;'>{name}</div>", unsafe_allow_html=True)

# 주별 그리드
for week in weeks:
    week_cols = st.columns(7)
    for i, day in enumerate(week):
        with week_cols[i]:
            if day.month != month:
                st.markdown("<div style='height:65px;'></div>", unsafe_allow_html=True)
                continue

            date_key = day.isoformat()
            cal_val = daily_map.get(date_key, 0)

            # 색상: 초록(부족) → 노랑(적정) → 빨강(초과)
            if cal_val == 0:
                bg = "rgba(30,41,59,0.5)"
                text_color = "#64748B"
            elif cal_val < target * 0.8:
                bg = "rgba(22,101,52,0.5)"
                text_color = "#86EFAC"
            elif cal_val <= target * 1.1:
                bg = "rgba(34,197,94,0.4)"
                text_color = "#22C55E"
            elif cal_val <= target * 1.3:
                bg = "rgba(253,224,71,0.3)"
                text_color = "#FBBF24"
            else:
                bg = "rgba(239,68,68,0.3)"
                text_color = "#EF4444"

            is_today = day == datetime.date.today()
            border = "2px solid #3B82F6" if is_today else "1px solid rgba(148,163,184,0.15)"

            st.markdown(
                f"<div style='background:{bg};border:{border};border-radius:8px;"
                f"padding:4px 6px;height:65px;cursor:pointer;'>"
                f"<div style='font-size:12px;color:#94A3B8;'>{day.day}</div>"
                f"<div style='font-size:14px;font-weight:600;color:{text_color};'>"
                f"{cal_val:,}</div>"
                f"<div style='font-size:9px;color:#64748B;'>kcal</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
            if st.button("상세", key=f"cal_{date_key}", use_container_width=True):
                st.session_state.cal_selected_date = date_key
                st.rerun()

# ═══════════════════════════════════════════════════════════════
# 드릴다운: 선택된 날짜 상세
# ═══════════════════════════════════════════════════════════════

sel_date = st.session_state.cal_selected_date
if sel_date:
    st.divider()
    st.subheader(f"📋 {sel_date} 상세")

    day_meals = get_meals_for_date(email, sel_date)
    day_memo = get_memo(email, sel_date)

    # 컨디션 & 메모
    if day_memo:
        mc1, mc2 = st.columns([1, 3])
        mc1.markdown(f"**컨디션**: {day_memo.get('condition', '')}")
        if day_memo.get("memo"):
            mc2.markdown(f"**메모**: {day_memo['memo']}")

    if day_meals.empty:
        st.info("이 날의 식단 기록이 없습니다.")
    else:
        # 매크로 파이 차트
        for c in ["total_cal", "carbs", "protein", "fat", "quantity"]:
            day_meals[c] = day_meals[c].apply(lambda x: float(x) if x else 0)

        t_carbs = (day_meals["carbs"] * day_meals["quantity"]).sum()
        t_protein = (day_meals["protein"] * day_meals["quantity"]).sum()
        t_fat = (day_meals["fat"] * day_meals["quantity"]).sum()
        t_cal = day_meals["total_cal"].sum()

        col_pie, col_list = st.columns([1, 2])
        with col_pie:
            fig = go.Figure(go.Pie(
                labels=["탄수화물", "단백질", "지방"],
                values=[t_carbs, t_protein, t_fat],
                marker=dict(colors=["#FBBF24", "#EF4444", "#6B7280"]),
                textinfo="label+percent",
                hole=0.4,
            ))
            fig.update_layout(
                **PLOT_CFG, height=250, showlegend=False,
                margin=dict(l=10, r=10, t=10, b=10),
            )
            st.plotly_chart(fig, use_container_width=True)
            st.metric("총 칼로리", f"{t_cal:,.0f} kcal")

        with col_list:
            for mt in MEAL_TYPES:
                meal_df = day_meals[day_meals["meal_type"] == mt]
                if meal_df.empty:
                    continue
                st.markdown(f"**{mt}**")
                for _, row in meal_df.iterrows():
                    st.caption(
                        f"  · {row['food_name']} ({row.get('amount', '')}) "
                        f"— {row.get('total_cal', 0)} kcal"
                    )

    if not day_memo and day_meals.empty:
        st.info("이 날의 기록이 없습니다.")

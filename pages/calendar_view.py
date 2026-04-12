"""📅 캘린더 페이지 — 월별 칼로리 히트맵 + 일자 드릴다운.

HTML 테이블 기반 캘린더로 모바일에서도 7열 그리드 유지.
"""

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

col_prev, col_title, col_next = st.columns([1, 3, 1])
with col_prev:
    if st.button("◀ 이전"):
        if st.session_state.cal_month == 1:
            st.session_state.cal_month = 12
            st.session_state.cal_year -= 1
        else:
            st.session_state.cal_month -= 1
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

# ─── HTML 캘린더 테이블 ──────────────────────────────────────
cal = calendar.Calendar(firstweekday=0)
weeks = cal.monthdatescalendar(year, month)
today = datetime.date.today()

def _cell_color(cal_val: int) -> tuple[str, str]:
    if cal_val == 0:
        return "rgba(30,41,59,0.5)", "#64748B"
    elif cal_val < target * 0.8:
        return "rgba(22,101,52,0.5)", "#86EFAC"
    elif cal_val <= target * 1.1:
        return "rgba(34,197,94,0.4)", "#22C55E"
    elif cal_val <= target * 1.3:
        return "rgba(253,224,71,0.3)", "#FBBF24"
    else:
        return "rgba(239,68,68,0.3)", "#EF4444"

html = """
<style>
.cal-table { width:100%; border-collapse:separate; border-spacing:3px; table-layout:fixed; }
.cal-table th { text-align:center; color:#94A3B8; font-size:13px; font-weight:600; padding:4px 0; }
.cal-table td { border-radius:8px; padding:4px; vertical-align:top; height:58px; }
.cal-day { font-size:11px; color:#94A3B8; }
.cal-val { font-size:14px; font-weight:600; }
.cal-unit { font-size:9px; color:#64748B; }
</style>
<table class="cal-table">
<tr><th>월</th><th>화</th><th>수</th><th>목</th><th>금</th><th>토</th><th>일</th></tr>
"""

for week in weeks:
    html += "<tr>"
    for day in week:
        if day.month != month:
            html += "<td style='background:transparent;'></td>"
            continue

        date_key = day.isoformat()
        cal_val = daily_map.get(date_key, 0)
        bg, text_color = _cell_color(cal_val)
        border = "2px solid #3B82F6" if day == today else "1px solid rgba(148,163,184,0.15)"

        html += (
            f"<td style='background:{bg};border:{border};'>"
            f"<div class='cal-day'>{day.day}</div>"
            f"<div class='cal-val' style='color:{text_color};'>{cal_val:,}</div>"
            f"<div class='cal-unit'>kcal</div>"
            f"</td>"
        )
    html += "</tr>"

html += "</table>"
st.markdown(html, unsafe_allow_html=True)

# ─── 색상 범례 ───────────────────────────────────────────────
st.caption(
    f"🟢 목표 이하 · 🟡 목표 근접 · 🔴 목표 초과 (목표: {target:,} kcal)"
)

# ═══════════════════════════════════════════════════════════════
# 드릴다운: 날짜 선택
# ═══════════════════════════════════════════════════════════════

st.divider()

# 기록이 있는 날짜 목록
recorded_dates = sorted(daily_map.keys(), reverse=True)
if recorded_dates:
    sel_date = st.selectbox(
        "날짜 선택 (상세 보기)",
        recorded_dates,
        format_func=lambda d: f"{d} ({daily_map.get(d, 0):,} kcal)",
    )
else:
    sel_date = None
    st.caption("이번 달 기록이 없습니다.")

if sel_date:
    st.subheader(f"📋 {sel_date} 상세")

    day_meals = get_meals_for_date(email, sel_date)
    day_memo = get_memo(email, sel_date)

    # 컨디션 & 메모
    if day_memo:
        st.markdown(
            f"**📝 컨디션**: {day_memo.get('condition', '')}  \n"
            f"**메모**: {day_memo.get('memo', '') or '없음'}",
        )

    if day_meals.empty:
        st.info("이 날의 식단 기록이 없습니다.")
    else:
        for c in ["total_cal", "carbs", "protein", "fat", "quantity"]:
            day_meals[c] = day_meals[c].apply(lambda x: float(x) if x else 0)

        t_carbs = (day_meals["carbs"] * day_meals["quantity"]).sum()
        t_protein = (day_meals["protein"] * day_meals["quantity"]).sum()
        t_fat = (day_meals["fat"] * day_meals["quantity"]).sum()
        t_cal = day_meals["total_cal"].sum()

        # 총합 + 매크로
        st.metric("총 칼로리", f"{t_cal:,.0f} kcal")

        fig = go.Figure(go.Pie(
            labels=["탄수화물", "단백질", "지방"],
            values=[t_carbs, t_protein, t_fat],
            marker=dict(colors=["#FBBF24", "#EF4444", "#6B7280"]),
            textinfo="label+percent",
            hole=0.4,
        ))
        fig.update_layout(
            **PLOT_CFG, height=220, showlegend=False,
            margin=dict(l=10, r=10, t=10, b=10),
        )
        st.plotly_chart(fig, use_container_width=True)

        for mt in MEAL_TYPES:
            meal_df = day_meals[day_meals["meal_type"] == mt]
            if meal_df.empty:
                continue
            st.markdown(f"**{mt}** ({meal_df['total_cal'].sum():,.0f} kcal)")
            for _, row in meal_df.iterrows():
                st.caption(
                    f"  · {row['food_name']} ({row.get('amount', '')}) "
                    f"— {row.get('total_cal', 0)} kcal"
                )

    if not day_memo and day_meals.empty:
        st.info("이 날의 기록이 없습니다.")

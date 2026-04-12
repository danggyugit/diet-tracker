"""📅 캘린더 페이지 — 월별 칼로리 히트맵 + 날짜 클릭 드릴다운.

HTML 테이블 + JS onclick → query_params로 날짜 선택.
"""

import calendar
import datetime

import plotly.graph_objects as go
import streamlit as st

from config import PLOT_CFG, MEAL_TYPES
from services.auth_service import require_auth
from services.sheets_service import (
    get_daily_totals, get_meals_for_date, get_profile, get_memo,
    get_latest_weight, get_daily_burned,
)
from services.calorie_service import calc_bmr, calc_tdee, calc_daily_deficit

email = require_auth()
st.title("📅 캘린더")

# ─── 프로필 → 일일 예산 (식단 기록과 동일 로직) ──────────────
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
    target = target_cal
elif target_wt > 0 and target_dt:
    deficit = calc_daily_deficit(latest_weight, target_wt, target_dt)
    target = round(tdee - deficit["deficit_per_day"])
else:
    target = round(tdee)

# ─── 월/년 네비게이터 ────────────────────────────────────────
if "cal_year" not in st.session_state:
    st.session_state.cal_year = datetime.date.today().year
if "cal_month" not in st.session_state:
    st.session_state.cal_month = datetime.date.today().month

nc1, nc2, nc3 = st.columns([1, 2, 1], gap="small")
if nc1.button("◀", use_container_width=True):
    if st.session_state.cal_month == 1:
        st.session_state.cal_month = 12
        st.session_state.cal_year -= 1
    else:
        st.session_state.cal_month -= 1
    st.rerun()
nc2.markdown(
    f"<h3 style='text-align:center;margin:0;line-height:2.2;'>"
    f"{st.session_state.cal_year}년 {st.session_state.cal_month}월</h3>",
    unsafe_allow_html=True,
)
if nc3.button("▶", use_container_width=True):
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
daily_eaten = {}
daily_burned_map = {}
daily_net = {}
if not totals_df.empty:
    for _, row in totals_df.iterrows():
        d = row["date"]
        eaten = int(row["total_cal"])
        burned = int(get_daily_burned(email, d))
        daily_eaten[d] = eaten
        daily_burned_map[d] = burned
        daily_net[d] = eaten - burned

# ─── HTML 캘린더 테이블 ──────────────────────────────────────
cal_obj = calendar.Calendar(firstweekday=0)
weeks = cal_obj.monthdatescalendar(year, month)
today = datetime.date.today()


def _cell_color(cal_val: int) -> tuple[str, str]:
    if cal_val == 0:
        return "rgba(30,41,59,0.5)", "#64748B"
    elif cal_val <= target:
        # 목표 이하 → 초록
        return "rgba(34,197,94,0.4)", "#22C55E"
    elif cal_val <= target * 1.1:
        # 목표 살짝 초과 (10% 이내) → 노랑
        return "rgba(253,224,71,0.3)", "#FBBF24"
    else:
        # 목표 10% 이상 초과 → 빨강
        return "rgba(239,68,68,0.3)", "#EF4444"


html = """
<style>
.cal-table { width:100%; border-collapse:separate; border-spacing:3px; table-layout:fixed; }
.cal-table th { text-align:center; color:#94A3B8; font-size:13px; font-weight:600; padding:4px 0; }
.cal-table td { border-radius:8px; padding:3px; vertical-align:top; height:72px; }
.cal-day { font-size:11px; color:#94A3B8; }
.cal-val { font-size:13px; font-weight:600; }
.cal-detail { font-size:8px; color:#64748B; line-height:1.3; }
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
        eaten = daily_eaten.get(date_key, 0)
        burned = daily_burned_map.get(date_key, 0)
        net = daily_net.get(date_key, 0)
        bg, text_color = _cell_color(net)
        is_today = day == today
        border = "2px solid #3B82F6" if is_today else "1px solid rgba(148,163,184,0.15)"

        if eaten > 0 and burned > 0:
            detail = f"<div class='cal-detail'>식{eaten:,}-운{burned:,}</div>"
        elif eaten > 0:
            detail = f"<div class='cal-detail'>섭취</div>"
        else:
            detail = ""

        html += (
            f"<td style='background:{bg};border:{border};'>"
            f"<div class='cal-day'>{day.day}</div>"
            f"<div class='cal-val' style='color:{text_color};'>{net:,}</div>"
            f"{detail}"
            f"</td>"
        )
    html += "</tr>"

html += "</table>"
st.markdown(html, unsafe_allow_html=True)

st.caption(
    f"🟢 목표 이하 (0 - {target:,}) · "
    f"🟡 소폭 초과 ({target+1:,} - {round(target*1.1):,}) · "
    f"🔴 초과 ({round(target*1.1)+1:,} 이상) · "
    f"목표: {target:,} kcal"
)

# ═══════════════════════════════════════════════════════════════
# 드릴다운: 날짜 선택
# ═══════════════════════════════════════════════════════════════

st.divider()
sel_date = st.date_input(
    "📋 날짜 선택 (상세 보기)",
    value=today if today.month == month and today.year == year else first_day,
    min_value=first_day,
    max_value=last_day,
)
sel_date_str = sel_date.isoformat()

if sel_date_str:
    st.subheader(f"📋 {sel_date_str} 상세")

    day_meals = get_meals_for_date(email, sel_date_str)
    day_memo = get_memo(email, sel_date_str)

    # 컨디션 & 메모
    if day_memo:
        st.markdown(
            f"**📝 컨디션**: {day_memo.get('condition', '')}  \n"
            f"**메모**: {day_memo.get('memo', '') or '없음'}",
        )

    if day_meals.empty:
        if not day_memo:
            st.info("이 날의 기록이 없습니다.")
    else:
        for c in ["total_cal", "carbs", "protein", "fat", "quantity"]:
            day_meals[c] = day_meals[c].apply(lambda x: float(x) if x else 0)

        t_carbs = (day_meals["carbs"] * day_meals["quantity"]).sum()
        t_protein = (day_meals["protein"] * day_meals["quantity"]).sum()
        t_fat = (day_meals["fat"] * day_meals["quantity"]).sum()
        t_cal = day_meals["total_cal"].sum()

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

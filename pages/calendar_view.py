"""📅 캘린더 페이지 — 월별 칼로리 히트맵 + 날짜 상세.

레이아웃:
- 월 네비게이터 (가로 고정)
- HTML 테이블 캘린더 (순칼로리 색상)
- 날짜 선택
- 상세: 도넛(중앙 숫자) + 식사 카드
"""

import calendar
import datetime

import plotly.graph_objects as go
import streamlit as st

from config import PLOT_CFG, MEAL_TYPES, today_kst
from services.auth_service import require_auth
from services.sheets_service import (
    get_daily_totals, get_meals_for_date, get_profile, get_memo,
    get_latest_weight, get_daily_burned,
)
from services.calorie_service import calc_bmr, calc_tdee

email = require_auth()
st.title("📅 캘린더")

# ─── 프로필 → 일일 목표 ──────────────────────────────────────
profile = get_profile(email) or {}
latest_weight = get_latest_weight(email) or float(profile.get("weight", 70))
bmr = calc_bmr(
    latest_weight, float(profile.get("height", 170)),
    int(profile.get("age", 30)), profile.get("gender", "남성"),
)
tdee = calc_tdee(bmr, profile.get("activity_level", "보통활동"))
try:
    deficit_level = int(profile.get("deficit_level") or 700)
except (ValueError, TypeError):
    deficit_level = 700
target = round(tdee - deficit_level)

# ─── 월/년 네비게이터 (모바일 가로 강제) ────────────────────
if "cal_year" not in st.session_state:
    st.session_state.cal_year = today_kst().year
if "cal_month" not in st.session_state:
    st.session_state.cal_month = today_kst().month

# HTML 그리드로 강제 가로 배치 (st.columns 쓰면 모바일에서 세로 쌓임)
nav_html = (
    f"<div style='display:grid;grid-template-columns:50px 1fr 50px;"
    f"gap:8px;align-items:center;margin-bottom:12px;'>"
    f"<button onclick=\"document.querySelector('[data-testid=\\\"baseButton-secondary\\\"][key=\\\"cal_prev\\\"]')?.click()\" "
    f"style='background:rgba(30,41,59,0.5);border:1px solid rgba(148,163,184,0.2);"
    f"color:#F8FAFC;padding:10px;border-radius:8px;cursor:pointer;font-size:16px;'>◀</button>"
    f"<div style='text-align:center;font-size:20px;font-weight:700;'>"
    f"{st.session_state.cal_year}년 {st.session_state.cal_month}월</div>"
    f"<button style='background:rgba(30,41,59,0.5);border:1px solid rgba(148,163,184,0.2);"
    f"color:#F8FAFC;padding:10px;border-radius:8px;cursor:pointer;font-size:16px;'>▶</button>"
    f"</div>"
)
# HTML 버튼은 작동 안 하니 실제 기능은 아래 숨김 Streamlit 버튼으로
nc1, nc2, nc3 = st.columns([1, 3, 1])
if nc1.button("◀ 이전", use_container_width=True, key="cal_prev"):
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
if nc3.button("다음 ▶", use_container_width=True, key="cal_next"):
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
daily_eaten, daily_burned_map, daily_net = {}, {}, {}
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
today = today_kst()


def _cell_color(cal_val: int) -> tuple[str, str]:
    if cal_val == 0:
        return "rgba(30,41,59,0.5)", "#64748B"
    elif cal_val <= target:
        return "rgba(34,197,94,0.4)", "#22C55E"
    elif cal_val <= target * 1.1:
        return "rgba(253,224,71,0.3)", "#FBBF24"
    else:
        return "rgba(239,68,68,0.3)", "#EF4444"


html = """
<style>
.cal-table { width:100%; border-collapse:separate; border-spacing:3px; table-layout:fixed; }
.cal-table th { text-align:center; color:#94A3B8; font-size:12px; font-weight:600; padding:4px 0; }
.cal-table td { border-radius:8px; padding:3px; vertical-align:top; height:80px; }
.cal-day { font-size:11px; color:#94A3B8; }
.cal-val { font-size:13px; font-weight:700; line-height:1.2; }
.cal-detail { font-size:9px; color:#CBD5E1; line-height:1.3; }
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
            detail = f"<div class='cal-detail'>식{eaten:,}<br>운{burned:,}</div>"
        elif eaten > 0:
            detail = f"<div class='cal-detail'>식{eaten:,}</div>"
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

# 범례 - 간결하게
st.caption(
    f"🟢 목표 이하 · 🟡 소폭 초과 · 🔴 초과 (목표 {target:,} kcal)"
)

# ═══════════════════════════════════════════════════════════════
# 날짜 선택 + 상세
# ═══════════════════════════════════════════════════════════════

st.divider()
sel_date = st.date_input(
    "📋 상세 보기할 날짜",
    value=today if today.month == month and today.year == year else first_day,
    min_value=first_day, max_value=last_day,
)
sel_date_str = sel_date.isoformat()

if sel_date_str:
    day_meals = get_meals_for_date(email, sel_date_str)
    day_memo = get_memo(email, sel_date_str)

    # 메모 먼저 (위쪽)
    if day_memo:
        condition = day_memo.get("condition", "")
        memo_text = day_memo.get("memo", "")
        memo_html = f"<div style='background:rgba(139,92,246,0.1);border-left:3px solid #8B5CF6;padding:10px 12px;border-radius:6px;margin:8px 0;'>"
        memo_html += f"<div style='font-size:13px;color:#A78BFA;font-weight:600;margin-bottom:4px;'>📝 {condition}</div>"
        if memo_text:
            memo_html += f"<div style='font-size:13px;color:#CBD5E1;'>{memo_text}</div>"
        memo_html += "</div>"
        st.markdown(memo_html, unsafe_allow_html=True)

    if day_meals.empty:
        if not day_memo:
            st.info(f"📝 {sel_date_str} 기록이 없습니다.")
    else:
        for c in ["total_cal", "carbs", "protein", "fat", "quantity"]:
            day_meals[c] = day_meals[c].apply(lambda x: float(x) if x else 0)

        t_carbs = (day_meals["carbs"] * day_meals["quantity"]).sum()
        t_protein = (day_meals["protein"] * day_meals["quantity"]).sum()
        t_fat = (day_meals["fat"] * day_meals["quantity"]).sum()
        t_cal = day_meals["total_cal"].sum()

        # 도넛 (중앙에 총 칼로리)
        fig = go.Figure(go.Pie(
            labels=["탄수화물", "단백질", "지방"],
            values=[t_carbs, t_protein, t_fat],
            marker=dict(colors=["#4ADE80", "#60A5FA", "#FBBF24"]),
            textinfo="label+percent",
            textfont=dict(size=13, color="#F8FAFC"),
            hole=0.6,
        ))
        fig.update_layout(
            **PLOT_CFG, height=240, showlegend=False,
            margin=dict(l=10, r=10, t=10, b=10),
            annotations=[dict(
                text=f"<span style='font-size:12px;color:#94A3B8;'>총 섭취</span><br>"
                     f"<b style='font-size:22px;'>{t_cal:,.0f}</b><br>"
                     f"<span style='font-size:11px;color:#94A3B8;'>kcal</span>",
                x=0.5, y=0.5, showarrow=False,
            )],
        )
        dc_l, dc_c, dc_r = st.columns([1, 2, 1])
        with dc_c:
            st.plotly_chart(fig, use_container_width=True)

        # 영양소 요약 (작게)
        st.caption(
            f"🍚 탄 {t_carbs:.0f}g · 🥩 단 {t_protein:.0f}g · 🧈 지 {t_fat:.0f}g"
        )

        # 식사별 카드 (컬러바 + 카드형)
        MEAL_COLORS = {
            "아침": "#F59E0B", "점심": "#22C55E",
            "저녁": "#3B82F6", "간식": "#A855F7",
        }

        for mt in MEAL_TYPES:
            meal_df = day_meals[day_meals["meal_type"] == mt]
            if meal_df.empty:
                continue

            color = MEAL_COLORS.get(mt, "#64748B")
            mt_cal = meal_df["total_cal"].sum()

            st.markdown(
                f"<div style='border-left:4px solid {color};padding-left:10px;margin-top:14px;margin-bottom:6px;'>"
                f"<span style='font-weight:600;color:{color};font-size:15px;'>{mt}</span> "
                f"<span style='color:#94A3B8;font-size:13px;'>({mt_cal:,.0f} kcal)</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

            for _, row in meal_df.iterrows():
                qty = row.get("quantity", 1.0)
                cal_per = int(row.get("calories", 0))
                total = int(row.get("total_cal", 0))
                st.markdown(
                    f"<div style='background:rgba(30,41,59,0.4);border-radius:8px;padding:8px 12px;margin:4px 0;'>"
                    f"<div style='font-weight:600;font-size:14px;'>{row['food_name']} "
                    f"<span style='font-size:12px;color:#94A3B8;font-weight:normal;'>{row.get('amount', '')}</span>"
                    f"</div>"
                    f"<div style='font-size:12px;color:#94A3B8;margin-top:2px;'>"
                    f"{cal_per}kcal × {qty}인분 = <strong style='color:#F8FAFC;'>{total}kcal</strong>"
                    f"</div></div>",
                    unsafe_allow_html=True,
                )

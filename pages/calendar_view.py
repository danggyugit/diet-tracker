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
base_target = round(tdee - deficit_level)

# 운동 보정 모드 (off / avg7 / daily)
_comp_raw = (profile.get("exercise_compensation") or "off").lower()
if _comp_raw == "on":
    _comp_raw = "avg7"
if _comp_raw not in ("off", "avg7", "daily"):
    _comp_raw = "off"
cal_comp_mode = _comp_raw

# ─── 월/년 네비게이터 (모바일 가로 강제) ────────────────────
if "cal_year" not in st.session_state:
    st.session_state.cal_year = today_kst().year
if "cal_month" not in st.session_state:
    st.session_state.cal_month = today_kst().month

# query_params 기반 네비게이션 (HTML 그리드로 가로 고정)
qp = st.query_params
if "cal_nav" in qp:
    nav_action = qp["cal_nav"]
    if nav_action == "prev":
        if st.session_state.cal_month == 1:
            st.session_state.cal_month = 12
            st.session_state.cal_year -= 1
        else:
            st.session_state.cal_month -= 1
    elif nav_action == "next":
        if st.session_state.cal_month == 12:
            st.session_state.cal_month = 1
            st.session_state.cal_year += 1
        else:
            st.session_state.cal_month += 1
    elif nav_action == "current":
        st.session_state.cal_year = today_kst().year
        st.session_state.cal_month = today_kst().month
    del st.query_params["cal_nav"]
    st.rerun()

# ─── 연/월 드롭다운 선택 ─────────────────────────────────────
_this_year = today_kst().year
year_options = list(range(_this_year - 3, _this_year + 2))
month_options = list(range(1, 13))

if st.session_state.cal_year not in year_options:
    year_options = sorted(set(year_options + [st.session_state.cal_year]))

yc, mc = st.columns(2)
sel_year = yc.selectbox(
    "년도",
    year_options,
    index=year_options.index(st.session_state.cal_year),
    key="cal_year_sel",
    format_func=lambda y: f"{y}년",
    label_visibility="collapsed",
)
sel_month = mc.selectbox(
    "월",
    month_options,
    index=month_options.index(st.session_state.cal_month),
    key="cal_month_sel",
    format_func=lambda m: f"{m}월",
    label_visibility="collapsed",
)
if sel_year != st.session_state.cal_year or sel_month != st.session_state.cal_month:
    st.session_state.cal_year = sel_year
    st.session_state.cal_month = sel_month
    st.rerun()

nav_html = (
    f"<div style='display:grid;grid-template-columns:1fr 2fr 1fr;"
    f"gap:8px;align-items:center;margin:12px 0;'>"
    f"<a href='?cal_nav=prev' target='_self' "
    f"style='background:rgba(30,41,59,0.5);border:1px solid rgba(148,163,184,0.2);"
    f"color:#F8FAFC;padding:10px 0;border-radius:8px;text-align:center;"
    f"text-decoration:none;font-size:14px;font-weight:500;'>◀ 이전달</a>"
    f"<a href='?cal_nav=current' target='_self' "
    f"style='display:block;text-align:center;font-size:16px;font-weight:700;"
    f"color:#F8FAFC;text-decoration:none;padding:10px 0;border-radius:8px;"
    f"background:rgba(30,41,59,0.5);border:1px solid rgba(148,163,184,0.2);'>"
    f"{today_kst().year}년 {today_kst().month}월</a>"
    f"<a href='?cal_nav=next' target='_self' "
    f"style='background:rgba(30,41,59,0.5);border:1px solid rgba(148,163,184,0.2);"
    f"color:#F8FAFC;padding:10px 0;border-radius:8px;text-align:center;"
    f"text-decoration:none;font-size:14px;font-weight:500;'>다음달 ▶</a>"
    f"</div>"
)
st.markdown(nav_html, unsafe_allow_html=True)

year = st.session_state.cal_year
month = st.session_state.cal_month

if year != today_kst().year or month != today_kst().month:
    st.markdown(
        f"<div style='text-align:center;font-size:18px;font-weight:700;margin:4px 0 8px;'>"
        f"{year}년 {month}월</div>",
        unsafe_allow_html=True,
    )

# ─── 해당 월 데이터 로드 ─────────────────────────────────────
first_day = datetime.date(year, month, 1)
last_day = datetime.date(year, month, calendar.monthrange(year, month)[1])
totals_df = get_daily_totals(email, first_day.isoformat(), last_day.isoformat())
daily_eaten, daily_burned_map, daily_net, daily_target = {}, {}, {}, {}
if not totals_df.empty:
    all_burns = []
    for _, row in totals_df.iterrows():
        d = row["date"]
        eaten = int(row["total_cal"])
        burned = int(get_daily_burned(email, d))
        daily_eaten[d] = eaten
        daily_burned_map[d] = burned
        daily_net[d] = eaten - burned
        all_burns.append(burned)

    # 보정 모드별 일별 effective target
    avg7_burn = int(sum(all_burns) / len(all_burns)) if all_burns else 0
    for d in daily_eaten:
        if cal_comp_mode == "daily":
            daily_target[d] = base_target + daily_burned_map.get(d, 0)
        elif cal_comp_mode == "avg7":
            daily_target[d] = base_target + avg7_burn
        else:
            daily_target[d] = base_target

# ─── HTML 캘린더 테이블 ──────────────────────────────────────
cal_obj = calendar.Calendar(firstweekday=0)
weeks = cal_obj.monthdatescalendar(year, month)
today = today_kst()


def _cell_color(cal_val: int, day_target: int) -> tuple[str, str]:
    if cal_val == 0:
        return "rgba(30,41,59,0.5)", "#64748B"
    pct = cal_val / day_target * 100 if day_target > 0 else 0
    if cal_val < 1200 or pct < 60:
        return "rgba(96,165,250,0.3)", "#60A5FA"    # 🔵 너무 적음
    elif pct <= 95:
        return "rgba(34,197,94,0.4)", "#22C55E"     # ✅ 적정
    elif pct <= 105:
        return "rgba(253,224,71,0.3)", "#FBBF24"    # 🟡 근접
    else:
        return "rgba(239,68,68,0.3)", "#EF4444"     # 🔴 초과


sel_date_state = st.session_state.get("cal_sel_date")

html = """
<style>
.cal-table { width:100%; border-collapse:separate; border-spacing:3px; table-layout:fixed; }
.cal-table th { text-align:center; color:#94A3B8; font-size:12px; font-weight:600; padding:4px 0; }
.cal-table td { border-radius:8px; padding:3px; vertical-align:top; height:62px; }
.cal-day { font-size:11px; color:#94A3B8; }
.cal-val { font-size:13px; font-weight:700; line-height:1.2; }
.cal-detail { font-size:9px; color:#CBD5E1; line-height:1.2; }
.cal-empty { font-size:14px; color:#475569; text-align:center; margin-top:6px; }
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
        has_data = eaten > 0 or burned > 0
        dt = daily_target.get(date_key, base_target)
        # 보정 ON: 섭취 vs effective target, OFF: 순 vs base
        eval_val = eaten if cal_comp_mode != "off" else net
        bg, text_color = _cell_color(eval_val, dt) if has_data else ("rgba(30,41,59,0.25)", "#475569")
        is_today = day == today
        is_selected = sel_date_state == day
        if is_selected:
            border = "2px solid #F59E0B"
        elif is_today:
            border = "2px solid #3B82F6"
        else:
            border = "1px solid rgba(148,163,184,0.15)"

        if has_data:
            if eaten > 0 and burned > 0:
                detail = f"<div class='cal-detail'>식{eaten:,}·운{burned:,}</div>"
            elif eaten > 0:
                detail = f"<div class='cal-detail'>식{eaten:,}</div>"
            else:
                detail = f"<div class='cal-detail'>운{burned:,}</div>"
            body = (
                f"<div class='cal-val' style='color:{text_color};'>{net:,}</div>"
                f"{detail}"
            )
        else:
            body = "<div class='cal-empty'>·</div>"

        html += (
            f"<td style='background:{bg};border:{border};'>"
            f"<div class='cal-day'>{day.day}</div>"
            f"{body}"
            f"</td>"
        )
    html += "</tr>"
html += "</table>"
st.markdown(html, unsafe_allow_html=True)

# 범례 - 가로 강제 배치
st.markdown(
    f"<div style='display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:4px;"
    f"font-size:11px;color:#94A3B8;text-align:center;margin:8px 0 0;'>"
    f"<div>🔵 너무 적음</div><div>🟢 적정</div><div>🟡 근접</div><div>🔴 초과</div>"
    f"</div>"
    f"<div style='text-align:center;font-size:11px;color:#64748B;margin-top:2px;'>"
    f"기본 목표 {base_target:,} kcal"
    f"{' + 운동 보정' if cal_comp_mode != 'off' else ''}"
    f"</div>",
    unsafe_allow_html=True,
)

# ═══════════════════════════════════════════════════════════════
# 날짜 선택 + 상세
# ═══════════════════════════════════════════════════════════════

st.divider()
_default_sel = today if today.month == month and today.year == year else first_day
if "cal_sel_date" not in st.session_state or not (first_day <= st.session_state.cal_sel_date <= last_day):
    st.session_state.cal_sel_date = _default_sel
sel_date = st.date_input(
    "📋 상세 보기할 날짜",
    min_value=first_day, max_value=last_day,
    key="cal_sel_date",
)
sel_date_str = sel_date.isoformat()

if sel_date_str:
    day_meals = get_meals_for_date(email, sel_date_str)
    day_memo = get_memo(email, sel_date_str)

    if not day_meals.empty:
        for c in ["total_cal", "carbs", "protein", "fat", "quantity"]:
            day_meals[c] = day_meals[c].apply(lambda x: float(x) if x else 0)

        t_carbs = (day_meals["carbs"] * day_meals["quantity"]).sum()
        t_protein = (day_meals["protein"] * day_meals["quantity"]).sum()
        t_fat = (day_meals["fat"] * day_meals["quantity"]).sum()
        t_cal = day_meals["total_cal"].sum()

        # 도넛 (중앙에 총 칼로리) — 라벨 안쪽 배치 + 작은 폰트
        fig = go.Figure(go.Pie(
            labels=["탄수화물", "단백질", "지방"],
            values=[t_carbs, t_protein, t_fat],
            marker=dict(colors=["#4ADE80", "#60A5FA", "#FBBF24"]),
            textinfo="percent",
            textposition="inside",
            insidetextorientation="horizontal",
            textfont=dict(size=12, color="#0F172A"),
            hole=0.62,
            sort=False,
            hovertemplate="%{label}: %{value:.0f}g<extra></extra>",
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

        # 영양소 요약 (컬러 라벨 + 값)
        st.markdown(
            f"<div style='display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;text-align:center;margin:-10px 0 10px;'>"
            f"<div><span style='color:#4ADE80;'>● 탄수화물</span><br><b>{t_carbs:.0f}g</b></div>"
            f"<div><span style='color:#60A5FA;'>● 단백질</span><br><b>{t_protein:.0f}g</b></div>"
            f"<div><span style='color:#FBBF24;'>● 지방</span><br><b>{t_fat:.0f}g</b></div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    # 메모 (도넛 아래)
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

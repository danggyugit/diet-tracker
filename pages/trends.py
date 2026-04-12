"""📊 트렌드 & 인사이트 페이지.

9종 시각화 + 메모/컨디션 기록:
1. 일별 칼로리 라인 차트 (+ TDEE 기준선)
2. 매크로 분포 도넛 (오늘 vs 주간평균)
3. GitHub 스타일 연간 히트맵
4. 주간 요약 카드
5. 자주 먹은 음식 TOP 5
6. TDEE 달성률 게이지
7. 체중 변화 차트 (+ 7일 이동평균)
8. 주간 체중 변화 요약
9. 메모·컨디션 기록
"""

import datetime

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import PLOT_CFG
from services.auth_service import require_auth
from services.sheets_service import (
    get_daily_totals, get_all_meals_for_year, get_top_foods,
    get_meals, get_profile, get_weight_log,
)
from services.calorie_service import calc_bmr, calc_tdee

email = require_auth()
st.title("📊 트렌드 & 인사이트")

# ─── 프로필 → TDEE ──────────────────────────────────────────
profile = get_profile(email) or {}
bmr = calc_bmr(
    float(profile.get("weight", 70)),
    float(profile.get("height", 170)),
    int(profile.get("age", 30)),
    profile.get("gender", "남성"),
)
tdee = calc_tdee(bmr, profile.get("activity_level", "보통활동"))
target = int(profile.get("target_calories", 0)) or round(tdee)

# ─── 기간 선택 ───────────────────────────────────────────────
period = st.radio("기간", ["7일", "30일"], horizontal=True)
days = 7 if period == "7일" else 30

today = datetime.date.today()
start = (today - datetime.timedelta(days=days - 1)).isoformat()
end = today.isoformat()

totals = get_daily_totals(email, start, end)

# ═══════════════════════════════════════════════════════════════
# 1. 일별 칼로리 라인 차트
# ═══════════════════════════════════════════════════════════════

st.subheader("📈 일별 칼로리 추이")

if totals.empty:
    st.info("아직 기록이 없습니다. 식단을 기록하면 차트가 표시됩니다.")
else:
    fig_line = go.Figure()
    fig_line.add_trace(go.Scatter(
        x=totals["date"], y=totals["total_cal"],
        mode="lines+markers",
        name="섭취 칼로리",
        line=dict(color="#3B82F6", width=2),
        marker=dict(size=6),
    ))
    fig_line.add_hline(
        y=target, line_dash="dash", line_color="#EF4444",
        annotation_text=f"목표: {target:,} kcal",
    )
    fig_line.update_layout(
        **PLOT_CFG, height=350,
        xaxis_title="날짜", yaxis_title="칼로리 (kcal)",
        margin=dict(l=50, r=20, t=30, b=40),
        showlegend=False,
    )
    st.plotly_chart(fig_line, use_container_width=True)

# ═══════════════════════════════════════════════════════════════
# 2. 매크로 분포 도넛 (오늘 vs 기간 평균)
# ═══════════════════════════════════════════════════════════════

st.subheader("🥧 매크로 분포")

today_totals = get_daily_totals(email, end, end)
col_today, col_avg = st.columns(2)

def _draw_macro_pie(data: pd.DataFrame, title: str, container):
    with container:
        st.caption(title)
        if data.empty:
            st.info("데이터 없음")
            return
        carbs = data["total_carbs"].sum()
        protein = data["total_protein"].sum()
        fat = data["total_fat"].sum()
        if carbs + protein + fat == 0:
            st.info("데이터 없음")
            return
        fig = go.Figure(go.Pie(
            labels=["탄수화물", "단백질", "지방"],
            values=[carbs, protein, fat],
            marker=dict(colors=["#FBBF24", "#EF4444", "#6B7280"]),
            textinfo="label+percent",
            hole=0.4,
        ))
        fig.update_layout(
            **PLOT_CFG, height=280, showlegend=False,
            margin=dict(l=10, r=10, t=10, b=10),
        )
        st.plotly_chart(fig, use_container_width=True)

_draw_macro_pie(today_totals, "오늘", col_today)
_draw_macro_pie(totals, f"{period} 평균", col_avg)

# ═══════════════════════════════════════════════════════════════
# 3. GitHub 스타일 연간 히트맵
# ═══════════════════════════════════════════════════════════════

st.subheader("🔥 연간 칼로리 히트맵")

year = today.year
year_df = get_all_meals_for_year(email, year)

if year_df.empty:
    st.info(f"{year}년 기록이 없습니다.")
else:
    year_totals = get_daily_totals(email, f"{year}-01-01", f"{year}-12-31")
    daily_cal_map = dict(zip(year_totals["date"], year_totals["total_cal"]))

    # 7×53 매트릭스 구성 (행=요일, 열=주차)
    jan1 = datetime.date(year, 1, 1)
    dec31 = datetime.date(year, 12, 31)
    total_days = (dec31 - jan1).days + 1

    z_data = np.zeros((7, 53))
    hover_data = [[""] * 53 for _ in range(7)]

    for d in range(total_days):
        current = jan1 + datetime.timedelta(days=d)
        week_num = current.isocalendar()[1] - 1
        if week_num >= 53:
            week_num = 52
        dow = current.weekday()  # 0=Mon
        cal = daily_cal_map.get(current.isoformat(), 0)
        z_data[dow][week_num] = cal
        hover_data[dow][week_num] = f"{current.isoformat()}: {cal:,.0f} kcal"

    fig_heatmap = go.Figure(go.Heatmap(
        z=z_data,
        y=["월", "화", "수", "목", "금", "토", "일"],
        colorscale=[
            [0, "#1E293B"],
            [0.25, "#166534"],
            [0.5, "#22C55E"],
            [0.75, "#FDE047"],
            [1.0, "#EF4444"],
        ],
        hovertext=hover_data,
        hoverinfo="text",
        showscale=True,
        colorbar=dict(title="kcal"),
    ))
    fig_heatmap.update_layout(
        **PLOT_CFG, height=200,
        xaxis=dict(showticklabels=False, title="주차"),
        yaxis=dict(autorange="reversed"),
        margin=dict(l=40, r=20, t=10, b=10),
    )
    st.plotly_chart(fig_heatmap, use_container_width=True)

# ═══════════════════════════════════════════════════════════════
# 4. 주간 요약 카드
# ═══════════════════════════════════════════════════════════════

st.subheader("📊 기간 요약")

if totals.empty:
    st.info("데이터 없음")
else:
    avg_cal = totals["total_cal"].mean()
    over_days = int((totals["total_cal"] > target).sum())
    under_days = int((totals["total_cal"] <= target).sum())
    max_row = totals.loc[totals["total_cal"].idxmax()]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("평균 섭취", f"{avg_cal:,.0f} kcal")
    c2.metric("초과 일수", f"{over_days}일")
    c3.metric("목표 이하", f"{under_days}일")
    c4.metric("최고 섭취일", f"{int(max_row['total_cal']):,} kcal", delta=max_row["date"])

# ═══════════════════════════════════════════════════════════════
# 5. 자주 먹은 음식 TOP 5
# ═══════════════════════════════════════════════════════════════

st.subheader("🏆 자주 먹은 음식 TOP 5")

top_foods = get_top_foods(email, days)

if top_foods.empty:
    st.info("데이터 없음")
else:
    fig_bar = go.Figure(go.Bar(
        x=top_foods["count"],
        y=top_foods["food_name"],
        orientation="h",
        marker_color="#8B5CF6",
        text=top_foods.apply(lambda r: f"{r['count']}회 (평균 {r['avg_cal']}kcal)", axis=1),
        textposition="outside",
    ))
    fig_bar.update_layout(
        **PLOT_CFG, height=250,
        xaxis_title="횟수",
        yaxis=dict(autorange="reversed"),
        margin=dict(l=120, r=80, t=10, b=30),
    )
    st.plotly_chart(fig_bar, use_container_width=True)

# ═══════════════════════════════════════════════════════════════
# 6. TDEE 달성률 게이지
# ═══════════════════════════════════════════════════════════════

st.subheader("⚖️ TDEE 달성률")

col_gauge_today, col_gauge_avg = st.columns(2)

def _draw_gauge(value: float, title: str, container):
    with container:
        fig = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=value,
            delta=dict(reference=target, valueformat=".0f", suffix=" kcal"),
            gauge=dict(
                axis=dict(range=[0, target * 1.5]),
                bar=dict(color="#3B82F6"),
                steps=[
                    dict(range=[0, target * 0.8], color="rgba(22,101,52,0.3)"),
                    dict(range=[target * 0.8, target], color="rgba(34,197,94,0.3)"),
                    dict(range=[target, target * 1.2], color="rgba(253,224,71,0.2)"),
                    dict(range=[target * 1.2, target * 1.5], color="rgba(239,68,68,0.2)"),
                ],
                threshold=dict(line=dict(color="#EF4444", width=3), value=target),
            ),
            title=dict(text=title),
            number=dict(suffix=" kcal"),
        ))
        fig.update_layout(**PLOT_CFG, height=250, margin=dict(l=20, r=20, t=60, b=20))
        st.plotly_chart(fig, use_container_width=True)

today_cal = float(today_totals["total_cal"].sum()) if not today_totals.empty else 0
avg_cal = float(totals["total_cal"].mean()) if not totals.empty else 0

_draw_gauge(today_cal, "오늘", col_gauge_today)
_draw_gauge(avg_cal, f"{period} 일평균", col_gauge_avg)

# ═══════════════════════════════════════════════════════════════
# 7. 체중 변화 차트
# ═══════════════════════════════════════════════════════════════

st.subheader("📉 체중 변화 추이")

weight_log = get_weight_log(email, start, end)

if weight_log.empty:
    st.info("체중 기록이 없습니다. 식단 기록 페이지에서 매일 체중을 입력해 보세요.")
else:
    fig_weight = go.Figure()
    fig_weight.add_trace(go.Scatter(
        x=weight_log["date"], y=weight_log["weight"],
        mode="lines+markers",
        name="체중",
        line=dict(color="#8B5CF6", width=2),
        marker=dict(size=6),
    ))

    # 7일 이동평균 (데이터 3개 이상일 때)
    if len(weight_log) >= 3:
        window = min(7, len(weight_log))
        weight_log["ma7"] = weight_log["weight"].rolling(window=window, min_periods=1).mean()
        fig_weight.add_trace(go.Scatter(
            x=weight_log["date"], y=weight_log["ma7"],
            mode="lines",
            name="7일 이동평균",
            line=dict(color="#FBBF24", width=2, dash="dash"),
        ))

    # 목표 체중 라인
    target_wt = float(profile.get("target_weight", 0))
    if target_wt > 0:
        fig_weight.add_hline(
            y=target_wt, line_dash="dot", line_color="#22C55E",
            annotation_text=f"목표: {target_wt}kg",
        )

    fig_weight.update_layout(
        **PLOT_CFG, height=350,
        xaxis_title="날짜", yaxis_title="체중 (kg)",
        margin=dict(l=50, r=20, t=30, b=40),
    )
    st.plotly_chart(fig_weight, use_container_width=True)

# ═══════════════════════════════════════════════════════════════
# 8. 주간 체중 변화 요약
# ═══════════════════════════════════════════════════════════════

st.subheader("⚖️ 체중 변화 요약")

if weight_log.empty or len(weight_log) < 2:
    st.info("체중 기록이 2일 이상 필요합니다.")
else:
    first_wt = float(weight_log.iloc[0]["weight"])
    last_wt = float(weight_log.iloc[-1]["weight"])
    change = last_wt - first_wt
    record_days = len(weight_log)
    weekly_change = change / max((record_days / 7), 1)

    wc1, wc2, wc3, wc4 = st.columns(4)
    wc1.metric("시작 체중", f"{first_wt:.1f} kg")
    wc2.metric("현재 체중", f"{last_wt:.1f} kg")
    wc3.metric(
        f"{period} 변화",
        f"{change:+.1f} kg",
        delta=f"{change:+.1f} kg",
        delta_color="inverse",
    )
    wc4.metric("주당 변화", f"{weekly_change:+.2f} kg/주")

    if change < 0:
        st.success(f"{period} 동안 {abs(change):.1f}kg 감량 중입니다!")
    elif change > 0:
        st.warning(f"{period} 동안 {change:.1f}kg 증가했습니다. 식단을 점검해 보세요.")
    else:
        st.info("체중이 유지되고 있습니다.")

# 메모·컨디션 입력은 식단 기록 페이지로 이동됨

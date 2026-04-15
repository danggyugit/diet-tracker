"""📊 트렌드 & 인사이트 페이지.

3개 섹션 + 명확한 인사이트:
1. 한눈에 보기 — 핵심 지표 4개 (평가 포함)
2. 진행 상황 — 체중/칼로리 추이 + 예측
3. 패턴 발견 — 자주 먹는 음식, 요일별 습관
"""

import datetime

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import PLOT_CFG, PROTEIN_MULTIPLIERS, today_kst
from services.auth_service import require_auth
from services.sheets_service import (
    get_daily_totals, get_top_foods, get_meals,
    get_profile, get_weight_log, get_latest_weight, get_streak,
)
from services.calorie_service import calc_bmr, calc_tdee

email = require_auth()
st.title("📊 트렌드 & 인사이트")

# ─── 프로필 + 목표 계산 ──────────────────────────────────────
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

# ─── 기간 선택 ───────────────────────────────────────────────
period = st.radio("기간", ["7일", "30일", "90일"], horizontal=True)
days_map = {"7일": 7, "30일": 30, "90일": 90}
days = days_map[period]

today = today_kst()
start = (today - datetime.timedelta(days=days - 1)).isoformat()
end = today.isoformat()
totals = get_daily_totals(email, start, end)
weight_log = get_weight_log(email, start, end)

# ═══════════════════════════════════════════════════════════════
# 섹션 1: 한눈에 보기 (핵심 지표 + 평가)
# ═══════════════════════════════════════════════════════════════

st.markdown("## 🎯 한눈에 보기")

if totals.empty and weight_log.empty:
    st.info(
        "📝 아직 기록이 없습니다.\n\n"
        "식단 및 운동 기록 페이지에서 매일 체중과 식사를 기록하면, "
        "여기서 진행 상황과 패턴을 분석해 드립니다."
    )
    st.stop()

# 핵심 지표 4개 (모바일: 2x2, PC: 4x1)
mr1 = st.columns(2)
mr2 = st.columns(2)
c1, c2 = mr1[0], mr1[1]
c3, c4 = mr2[0], mr2[1]

# 1. 평균 섭취 vs 목표
if not totals.empty:
    avg_cal = totals["total_cal"].mean()
    achievement = (avg_cal / target * 100) if target > 0 else 0
    if 90 <= achievement <= 105:
        eval_text = "✅ 적정"
    elif achievement < 90:
        eval_text = "⬇️ 부족"
    else:
        eval_text = "⚠️ 초과"
    c1.metric(
        "평균 섭취",
        f"{avg_cal:,.0f} kcal",
        delta=f"{eval_text} (목표 {achievement:.0f}%)",
        delta_color="off",
    )
else:
    c1.metric("평균 섭취", "기록 없음")

# 2. 체중 변화
if not weight_log.empty and len(weight_log) >= 2:
    w_start = float(weight_log.iloc[0]["weight"])
    w_end = float(weight_log.iloc[-1]["weight"])
    w_change = w_end - w_start
    c2.metric(
        "체중 변화",
        f"{w_end:.1f} kg",
        delta=f"{w_change:+.1f} kg",
        delta_color="inverse",
    )
else:
    c2.metric("체중 변화", "2일+ 기록 필요")

# 3. 주당 감량 속도
if not weight_log.empty and len(weight_log) >= 2:
    w_start = float(weight_log.iloc[0]["weight"])
    w_end = float(weight_log.iloc[-1]["weight"])
    first_date = weight_log.iloc[0]["date"]
    last_date = weight_log.iloc[-1]["date"]
    elapsed = (datetime.date.fromisoformat(last_date) - datetime.date.fromisoformat(first_date)).days
    if elapsed > 0:
        weekly = (w_end - w_start) / elapsed * 7
        if -1.0 <= weekly <= 0:
            eval_text = "✅ 안전"
        elif weekly < -1.0:
            eval_text = "⚠️ 빠름"
        elif weekly > 0:
            eval_text = "⬆️ 증가"
        else:
            eval_text = "— 유지"
        c3.metric(
            "주당 감량",
            f"{weekly:+.2f} kg",
            delta=eval_text,
            delta_color="off",
        )
    else:
        c3.metric("주당 감량", "—")
else:
    c3.metric("주당 감량", "—")

# 4. 기록 지속률 (연속 기록)
streak = get_streak(email)
if streak >= 30:
    streak_eval = "🏆 우수"
elif streak >= 7:
    streak_eval = "🔥 좋음"
elif streak >= 3:
    streak_eval = "✨ 시작"
else:
    streak_eval = "⬇️ 저조"
c4.metric(
    "연속 기록",
    f"{streak}일",
    delta=streak_eval,
    delta_color="off",
)

# ─── 종합 평가 한 줄 ──────────────────────────────────────────
eval_lines = []
if not totals.empty:
    avg_cal = totals["total_cal"].mean()
    if avg_cal <= target:
        eval_lines.append("✅ 칼로리 유지")
    elif avg_cal <= target * 1.1:
        eval_lines.append("🟡 칼로리 근접")
    else:
        eval_lines.append("🔴 칼로리 초과")

if not weight_log.empty and len(weight_log) >= 2:
    w_change = float(weight_log.iloc[-1]["weight"]) - float(weight_log.iloc[0]["weight"])
    if w_change < 0:
        eval_lines.append(f"✅ {abs(w_change):.1f}kg 감량")
    elif w_change > 0:
        eval_lines.append(f"🔴 {w_change:.1f}kg 증가")
    else:
        eval_lines.append("🟡 체중 유지")

if eval_lines:
    st.info(" · ".join(eval_lines))

# ═══════════════════════════════════════════════════════════════
# 섹션 2: 진행 상황 (체중 + 칼로리 추이)
# ═══════════════════════════════════════════════════════════════

st.markdown("---")
st.markdown("## 📈 진행 상황")

# ─── 체중 변화 차트 (예측 포함) ──────────────────────────────
st.markdown("#### ⚖️ 체중 변화 추이")
st.caption(f"목표 체중 달성까지 얼마나 남았는지 한눈에 확인하세요.")

if weight_log.empty:
    st.info("📝 체중 기록이 없습니다. 식단 기록 페이지에서 매일 체중을 입력해 보세요.")
else:
    fig_weight = go.Figure()
    fig_weight.add_trace(go.Scatter(
        x=weight_log["date"], y=weight_log["weight"],
        mode="lines+markers", name="체중",
        line=dict(color="#8B5CF6", width=2), marker=dict(size=6),
    ))

    if len(weight_log) >= 3:
        window = min(7, len(weight_log))
        weight_log["ma7"] = weight_log["weight"].rolling(window=window, min_periods=1).mean()
        fig_weight.add_trace(go.Scatter(
            x=weight_log["date"], y=weight_log["ma7"],
            mode="lines", name="7일 이동평균",
            line=dict(color="#FBBF24", width=2, dash="dash"),
        ))

    target_wt = float(profile.get("target_weight", 0))
    if target_wt > 0:
        fig_weight.add_hline(
            y=target_wt, line_dash="dot", line_color="#4ADE80",
            annotation_text=f"목표 {target_wt}kg", annotation_position="right",
        )

    # 예측선
    if len(weight_log) >= 2 and target_wt > 0:
        w_start = float(weight_log.iloc[0]["weight"])
        w_end = float(weight_log.iloc[-1]["weight"])
        first_date = weight_log.iloc[0]["date"]
        last_date = weight_log.iloc[-1]["date"]
        elapsed = (datetime.date.fromisoformat(last_date) - datetime.date.fromisoformat(first_date)).days
        if elapsed > 0:
            daily_rate = (w_end - w_start) / elapsed
            if daily_rate != 0:
                days_to_goal = int((target_wt - w_end) / daily_rate)
                if 0 < days_to_goal < 365:
                    pred_date = (datetime.date.fromisoformat(last_date) + datetime.timedelta(days=days_to_goal)).isoformat()
                    fig_weight.add_trace(go.Scatter(
                        x=[last_date, pred_date], y=[w_end, target_wt],
                        mode="lines", name=f"예측",
                        line=dict(color="#4ADE80", width=2, dash="dot"),
                    ))
                    st.success(f"🎯 현재 페이스 유지 시 **{pred_date}**에 목표 {target_wt}kg 달성 예상")
                elif days_to_goal <= 0:
                    st.success(f"🎉 목표 체중 달성! 유지 단계입니다.")
                else:
                    st.warning("⚠️ 현재 페이스로는 1년 이상 소요됩니다. 감량 강도를 조정해 보세요.")

    fig_weight.update_layout(
        **PLOT_CFG, height=320,
        xaxis_title=None, yaxis_title="kg",
        margin=dict(l=40, r=15, t=30, b=30),
        xaxis=dict(tickangle=-45, tickfont=dict(size=10)),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=11)),
    )
    st.plotly_chart(fig_weight, use_container_width=True)

# ─── 칼로리 섭취 추이 ────────────────────────────────────────
st.markdown("#### 🔥 일별 칼로리 섭취")
st.caption("목표 선(빨간 점선) 대비 어떤 날이 많이/적게 먹었는지 확인하세요.")

if totals.empty:
    st.info("📝 식단 기록이 없습니다.")
else:
    fig_line = go.Figure()

    # 막대 차트 (목표 초과 빨강, 이하 초록)
    colors = ["#FB7185" if c > target else "#4ADE80" for c in totals["total_cal"]]
    fig_line.add_trace(go.Bar(
        x=totals["date"], y=totals["total_cal"],
        marker_color=colors, name="섭취",
    ))
    fig_line.add_hline(
        y=target, line_dash="dash", line_color="#F8FAFC",
        annotation_text=f"목표 {target:,}", annotation_position="right",
    )
    fig_line.update_layout(
        **PLOT_CFG, height=280,
        xaxis_title=None, yaxis_title="kcal",
        margin=dict(l=50, r=15, t=20, b=40), showlegend=False,
        xaxis=dict(tickangle=-45, tickfont=dict(size=10)),
        bargap=0.3,
    )
    st.plotly_chart(fig_line, use_container_width=True)

    # 인사이트 문장
    over_days = int((totals["total_cal"] > target).sum())
    under_days = int((totals["total_cal"] <= target).sum())
    total_days = len(totals)
    if over_days > total_days * 0.5:
        st.warning(f"⚠️ {total_days}일 중 {over_days}일 목표 초과 — 식단 조절이 필요합니다.")
    elif under_days > total_days * 0.7:
        st.success(f"✅ {total_days}일 중 {under_days}일 목표 이하 — 순항 중!")

# ═══════════════════════════════════════════════════════════════
# 섹션 3: 패턴 발견
# ═══════════════════════════════════════════════════════════════

st.markdown("---")
st.markdown("## 🔍 패턴 발견")

pc1, pc2 = st.columns(2)

# ─── 자주 먹은 음식 TOP 5 ────────────────────────────────────
with pc1:
    st.markdown("#### 🏆 자주 먹은 음식 TOP 5")
    st.caption("반복되는 음식을 즐겨찾기에 등록하면 입력이 빨라져요.")

    top_foods = get_top_foods(email, days)
    if top_foods.empty:
        st.caption("데이터 없음")
    else:
        fig_bar = go.Figure(go.Bar(
            x=top_foods["count"], y=top_foods["food_name"],
            orientation="h", marker_color="#8B5CF6",
            text=top_foods.apply(lambda r: f"{r['count']}회", axis=1),
            textposition="outside",
        ))
        fig_bar.update_layout(
            **PLOT_CFG, height=220,
            xaxis_title="", yaxis=dict(autorange="reversed"),
            margin=dict(l=80, r=40, t=10, b=30),
        )
        st.plotly_chart(fig_bar, use_container_width=True)

# ─── 요일별 평균 섭취 ──────────────────────────────────────
with pc2:
    st.markdown("#### 📅 요일별 섭취 패턴")
    st.caption("주말에 과식하는 경향이 있는지 확인하세요.")

    if totals.empty:
        st.caption("데이터 없음")
    else:
        t = totals.copy()
        t["date_dt"] = pd.to_datetime(t["date"])
        t["weekday"] = t["date_dt"].dt.dayofweek
        weekday_names = ["월", "화", "수", "목", "금", "토", "일"]
        weekday_avg = t.groupby("weekday")["total_cal"].mean().reset_index()
        weekday_avg["name"] = weekday_avg["weekday"].apply(lambda x: weekday_names[x])

        colors = ["#FB7185" if c > target else "#60A5FA" for c in weekday_avg["total_cal"]]
        fig_wd = go.Figure(go.Bar(
            x=weekday_avg["name"], y=weekday_avg["total_cal"],
            marker_color=colors,
            text=[f"{c:,.0f}" for c in weekday_avg["total_cal"]],
            textposition="outside",
        ))
        fig_wd.add_hline(
            y=target, line_dash="dash", line_color="#F8FAFC",
            annotation_text=f"목표", annotation_position="right",
        )
        fig_wd.update_layout(
            **PLOT_CFG, height=220,
            xaxis_title="", yaxis_title="평균 kcal",
            margin=dict(l=40, r=20, t=30, b=30),
        )
        st.plotly_chart(fig_wd, use_container_width=True)

# ─── 매크로 분포 (기간 전체) ─────────────────────────────────
if not totals.empty:
    st.markdown("#### 🥗 영양소 분포")
    st.caption(f"{period} 평균 영양소 섭취 비율입니다. 단백질 비율이 너무 낮지 않은지 확인하세요.")

    t_c = totals["total_carbs"].sum() if "total_carbs" in totals.columns else 0
    t_p = totals["total_protein"].sum() if "total_protein" in totals.columns else 0
    t_f = totals["total_fat"].sum() if "total_fat" in totals.columns else 0
    total_g = t_c + t_p + t_f

    if total_g > 0:
        avg_kcal_str = f"{totals['total_cal'].mean():,.0f}"
        fig_pie = go.Figure(go.Pie(
            labels=["탄수화물", "단백질", "지방"],
            values=[t_c, t_p, t_f],
            marker=dict(colors=["#4ADE80", "#60A5FA", "#FBBF24"]),
            textinfo="label+percent",
            textfont=dict(size=12),
            hole=0.55,
        ))
        fig_pie.update_layout(
            **PLOT_CFG, height=220, showlegend=False,
            margin=dict(l=0, r=0, t=0, b=0),
            annotations=[dict(
                text=f"<b>일평균</b><br>{avg_kcal_str} kcal",
                x=0.5, y=0.5, font=dict(size=14), showarrow=False,
            )],
        )
        # 도넛을 중앙에 배치 (모바일/PC 모두 적절한 크기)
        pc_left, pc_center, pc_right = st.columns([1, 2, 1])
        with pc_center:
            st.plotly_chart(fig_pie, use_container_width=True)

        # 단백질 체크
        pct_p = t_p / total_g * 100
        protein_mult = PROTEIN_MULTIPLIERS.get(profile.get("activity_level", "보통활동"), 1.3)
        target_p_per_day = latest_weight * protein_mult
        avg_p_per_day = t_p / len(totals)
        if avg_p_per_day < target_p_per_day * 0.8:
            st.warning(
                f"⚠️ 단백질 섭취가 부족합니다. "
                f"일평균 {avg_p_per_day:.0f}g (목표 {target_p_per_day:.0f}g · 체중×{protein_mult}g)"
            )
        elif avg_p_per_day >= target_p_per_day:
            st.success(
                f"✅ 단백질 섭취 충분! "
                f"일평균 {avg_p_per_day:.0f}g (목표 {target_p_per_day:.0f}g)"
            )

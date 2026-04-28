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

from config import PLOT_CFG, today_kst
from services.auth_service import require_auth
from services.sheets_service import (
    get_daily_totals, get_profile, get_weight_log, get_latest_weight, get_streak,
    get_exercise_log,
)
from services.calorie_service import calc_bmr, calc_tdee, evaluate_calorie_status

email = require_auth()
st.title("📊 트렌드")

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
base_target = round(tdee - deficit_level)
target = base_target  # 하위 호환: 기존 차트 참조용

# ─── 기간: 30일 고정 ─────────────────────────────────────────
days = 30
period = "30일"
today = today_kst()
start = (today - datetime.timedelta(days=days - 1)).isoformat()
end = today.isoformat()
totals = get_daily_totals(email, start, end)
weight_log = get_weight_log(email, start, end)

# 운동 burn 일자별 매핑 (트렌드 표 + 평가용)
ex_period = get_exercise_log(email, start, end)
if not ex_period.empty:
    burn_by_date = ex_period.groupby("date")["calories_burned"].sum().to_dict()
else:
    burn_by_date = {}

# 운동 보정 모드 (off / avg7 / daily) — 평가 방식 결정
_comp_raw = (profile.get("exercise_compensation") or "off").lower()
if _comp_raw == "on":
    _comp_raw = "avg7"
if _comp_raw not in ("off", "avg7", "daily"):
    _comp_raw = "off"
exercise_comp_mode = _comp_raw
# OFF면 gross intake로 평가, ON이면 net으로 평가
use_net_for_eval = exercise_comp_mode != "off"

# ═══════════════════════════════════════════════════════════════
# 섹션 1: 한눈에 보기 (핵심 지표 + 평가)
# ═══════════════════════════════════════════════════════════════

if totals.empty and weight_log.empty:
    st.info(
        "📝 아직 기록이 없습니다.\n\n"
        "식단 및 운동 기록 페이지에서 매일 체중과 식사를 기록하면, "
        "여기서 진행 상황과 패턴을 분석해 드립니다."
    )
    st.stop()

# 지표 데이터 준비
metric_data = []

# 1. 평균 섭취 (보정 모드에 따라 순/총 기반)
if not totals.empty:
    avg_gross = totals["total_cal"].mean()
    avg_burn = sum(burn_by_date.get(d, 0) for d in totals["date"]) / len(totals)
    avg_net = avg_gross - avg_burn
    eval_val = avg_net if use_net_for_eval else avg_gross
    eval_label, eval_color, _ = evaluate_calorie_status(eval_val, target)
    suffix = " (순)" if use_net_for_eval else ""
    metric_data.append(("평균 섭취" + suffix, f"{eval_val:,.0f} kcal", eval_label, eval_color))
else:
    metric_data.append(("평균 섭취", "기록 없음", "", "#64748B"))

# 2. 체중 변화
if not weight_log.empty and len(weight_log) >= 2:
    w_start = float(weight_log.iloc[0]["weight"])
    w_end = float(weight_log.iloc[-1]["weight"])
    w_change = w_end - w_start
    change_color = "#4ADE80" if w_change < 0 else ("#FB7185" if w_change > 0 else "#94A3B8")
    metric_data.append(("체중 변화", f"{w_end:.1f} kg", f"{w_change:+.1f} kg", change_color))
else:
    metric_data.append(("체중 변화", "—", "2일+ 기록 필요", "#64748B"))

# 3. 주당 감량
if not weight_log.empty and len(weight_log) >= 2:
    w_start = float(weight_log.iloc[0]["weight"])
    w_end = float(weight_log.iloc[-1]["weight"])
    first_date = weight_log.iloc[0]["date"]
    last_date = weight_log.iloc[-1]["date"]
    elapsed = (datetime.date.fromisoformat(last_date) - datetime.date.fromisoformat(first_date)).days
    if elapsed > 0:
        weekly = (w_end - w_start) / elapsed * 7
        if -1.0 <= weekly <= 0:
            eval_text, eval_color = "✅ 안전", "#4ADE80"
        elif weekly < -1.0:
            eval_text, eval_color = "⚠️ 빠름", "#FBBF24"
        elif weekly > 0:
            eval_text, eval_color = "⬆️ 증가", "#FB7185"
        else:
            eval_text, eval_color = "— 유지", "#94A3B8"
        metric_data.append(("주당 감량", f"{weekly:+.2f} kg", eval_text, eval_color))
    else:
        metric_data.append(("주당 감량", "—", "", "#64748B"))
else:
    metric_data.append(("주당 감량", "—", "", "#64748B"))

# 4. 연속 기록
streak = get_streak(email)
if streak >= 30:
    streak_eval, streak_color = "🏆 우수", "#FBBF24"
elif streak >= 7:
    streak_eval, streak_color = "🔥 좋음", "#FB7185"
elif streak >= 3:
    streak_eval, streak_color = "✨ 시작", "#60A5FA"
else:
    streak_eval, streak_color = "⬇️ 저조", "#94A3B8"
metric_data.append(("연속 기록", f"{streak}일", streak_eval, streak_color))

# HTML 그리드 (모바일 2x2 강제)
cards_html = "<div style='display:grid;grid-template-columns:1fr 1fr;gap:10px;'>"
for label, value, delta, color in metric_data:
    cards_html += (
        f"<div style='background:rgba(30,41,59,0.5);border-radius:12px;padding:14px;"
        f"border:1px solid rgba(148,163,184,0.1);'>"
        f"<div style='font-size:13px;color:#94A3B8;margin-bottom:6px;'>{label}</div>"
        f"<div style='font-size:24px;font-weight:700;color:#F8FAFC;line-height:1.2;'>{value}</div>"
        f"<div style='font-size:14px;color:{color};margin-top:4px;font-weight:500;'>{delta}</div>"
        f"</div>"
    )
cards_html += "</div>"
st.markdown(cards_html, unsafe_allow_html=True)

# ─── 종합 평가 한 줄 ──────────────────────────────────────────
eval_lines = []
if not totals.empty:
    _eval_val = avg_net if use_net_for_eval else avg_gross
    _eval_label, _, _eval_level = evaluate_calorie_status(_eval_val, target)
    eval_lines.append(f"{_eval_label} 칼로리")

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
    # 날짜를 M/D 포맷으로 변환
    wl_display = weight_log.copy()
    wl_display["date_label"] = pd.to_datetime(wl_display["date"]).apply(
        lambda d: f"{d.month}/{d.day}"
    )

    fig_weight = go.Figure()
    fig_weight.add_trace(go.Scatter(
        x=wl_display["date_label"], y=wl_display["weight"],
        mode="lines+markers", name="체중",
        line=dict(color="#8B5CF6", width=2), marker=dict(size=6),
    ))

    if len(wl_display) >= 3:
        window = min(7, len(wl_display))
        wl_display["ma7"] = wl_display["weight"].rolling(window=window, min_periods=1).mean()
        fig_weight.add_trace(go.Scatter(
            x=wl_display["date_label"], y=wl_display["ma7"],
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
                    pred_dt = datetime.date.fromisoformat(last_date) + datetime.timedelta(days=days_to_goal)
                    pred_date = pred_dt.isoformat()
                    pred_label = f"{pred_dt.month}/{pred_dt.day}"
                    last_label = wl_display.iloc[-1]["date_label"]
                    fig_weight.add_trace(go.Scatter(
                        x=[last_label, pred_label], y=[w_end, target_wt],
                        mode="lines", name=f"예측",
                        line=dict(color="#4ADE80", width=2, dash="dot"),
                    ))
                    st.success(f"🎯 현재 페이스 유지 시 **{pred_date}**에 목표 {target_wt}kg 달성 예상")
                elif days_to_goal <= 0:
                    st.success(f"🎉 목표 체중 달성! 유지 단계입니다.")
                else:
                    st.warning("⚠️ 현재 페이스로는 1년 이상 소요됩니다. 감량 강도를 조정해 보세요.")

    fig_weight.update_layout(
        **PLOT_CFG, height=280,
        xaxis_title=None, yaxis_title="kg",
        margin=dict(l=40, r=15, t=30, b=30),
        xaxis=dict(tickangle=-45, tickfont=dict(size=10), nticks=8),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=11)),
    )
    st.plotly_chart(fig_weight, use_container_width=True)

# ─── 에너지 균형 차트 (섭취·소모 막대 + 차이 라인) ────────────
st.markdown("#### ⚡ 일별 에너지 균형")
st.caption("섭취(주황)·소모(파랑) 막대 + 차이(초록 라인) — 라인이 0 아래면 적자")

if totals.empty:
    st.info("📝 식단 기록이 없습니다.")
else:
    bal_df = totals.copy()
    bal_df["date_dt"] = pd.to_datetime(bal_df["date"])
    weekday_names = ["월", "화", "수", "목", "금", "토", "일"]
    bal_df["label"] = bal_df["date_dt"].apply(
        lambda d: f"{d.month}/{d.day}({weekday_names[d.weekday()]})"
    )
    bal_df["burned"] = bal_df["date"].apply(lambda d: float(burn_by_date.get(d, 0)))
    bal_df["tdee_base"] = tdee
    bal_df["total_expend"] = bal_df["tdee_base"] + bal_df["burned"]
    bal_df["diff"] = bal_df["total_cal"] - bal_df["total_expend"]  # 섭취 - 소모

    fig_bal = go.Figure()
    fig_bal.add_trace(go.Bar(
        x=bal_df["label"], y=bal_df["total_cal"], name="섭취",
        marker_color="#FBBF24", opacity=0.85,
    ))
    fig_bal.add_trace(go.Bar(
        x=bal_df["label"], y=bal_df["total_expend"], name="소모",
        marker_color="#3B82F6", opacity=0.65,
    ))
    # 섭취 - 소모 라인 (보조 Y축)
    fig_bal.add_trace(go.Scatter(
        x=bal_df["label"], y=bal_df["diff"], name="섭취-소모",
        mode="lines+markers",
        line=dict(color="#4ADE80", width=2),
        marker=dict(size=6, color="#4ADE80"),
        yaxis="y2",
    ))
    fig_bal.update_layout(
        **PLOT_CFG, height=320, barmode="group",
        xaxis_title=None, yaxis_title="kcal (막대)",
        yaxis2=dict(
            title="섭취-소모 (라인)", overlaying="y", side="right",
            zeroline=True, zerolinecolor="rgba(148,163,184,0.5)",
            zerolinewidth=1.5, showgrid=False,
        ),
        margin=dict(l=40, r=50, t=30, b=30),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
    )
    st.plotly_chart(fig_bal, use_container_width=True)

    cum_total = bal_df["diff"].sum()
    cum_kg = cum_total / 7700
    cum_days = len(bal_df)
    st.markdown(
        f"<div style='text-align:center;font-size:13px;color:#94A3B8;margin:4px 0;'>"
        f"📊 {cum_days}일 누적: <b style='color:{'#4ADE80' if cum_total <= 0 else '#FB7185'};'>"
        f"{cum_total:+,.0f} kcal</b> ≈ <b>{cum_kg:+.2f} kg</b></div>",
        unsafe_allow_html=True,
    )


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
    get_daily_totals, get_top_foods, get_meals,
    get_profile, get_weight_log, get_latest_weight, get_streak,
    get_exercise_log,
)
from services.calorie_service import calc_bmr, calc_tdee, calc_protein_g, evaluate_calorie_status

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

# ─── 에너지 균형 차트 (섭취 vs 소모 비교) ─────────────────────
st.markdown("#### ⚡ 일별 에너지 균형")
st.caption("섭취(주황)와 소모(파랑)의 차이를 한눈에 비교하세요.")

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
    bal_df["deficit"] = bal_df["total_cal"] - bal_df["total_expend"]

    fig_bal = go.Figure()
    fig_bal.add_trace(go.Bar(
        x=bal_df["label"], y=bal_df["total_cal"], name="섭취",
        marker_color="#FBBF24", opacity=0.85,
    ))
    fig_bal.add_trace(go.Bar(
        x=bal_df["label"], y=bal_df["total_expend"], name="소모 (TDEE+운동)",
        marker_color="#3B82F6", opacity=0.65,
    ))
    fig_bal.add_hline(
        y=target, line_dash="dot", line_color="#4ADE80",
        annotation_text=f"목표 {target:,}", annotation_position="right",
    )
    fig_bal.update_layout(
        **PLOT_CFG, height=280, barmode="group",
        xaxis_title=None, yaxis_title="kcal",
        margin=dict(l=40, r=15, t=30, b=30),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
    )
    st.plotly_chart(fig_bal, use_container_width=True)

    # 누적 적자/흑자 차트
    bal_df["cum_deficit"] = bal_df["deficit"].cumsum()
    bal_df["cum_kg"] = bal_df["cum_deficit"] / 7700

    fig_cum = go.Figure()
    # 적자(음수) = 초록, 흑자(양수) = 빨강
    colors = ["#4ADE80" if v <= 0 else "#FB7185" for v in bal_df["cum_deficit"]]
    fig_cum.add_trace(go.Bar(
        x=bal_df["label"], y=bal_df["cum_deficit"],
        marker_color=colors, name="누적 칼로리",
        hovertemplate="%{x}<br>누적 %{y:,.0f} kcal<br>≈ %{customdata:+.2f} kg<extra></extra>",
        customdata=bal_df["cum_kg"],
    ))
    # 7,700 kcal 기준선 (1kg)
    max_abs = max(abs(bal_df["cum_deficit"].max()), abs(bal_df["cum_deficit"].min()), 3850)
    for kg_line in range(1, 4):
        if kg_line * 7700 <= max_abs * 1.3:
            fig_cum.add_hline(
                y=-kg_line * 7700, line_dash="dot", line_color="rgba(74,222,128,0.3)",
                annotation_text=f"-{kg_line}kg", annotation_position="left",
            )
    fig_cum.add_hline(y=0, line_color="rgba(148,163,184,0.4)")

    fig_cum.update_layout(
        **PLOT_CFG, height=240,
        xaxis_title=None, yaxis_title="누적 kcal",
        margin=dict(l=50, r=15, t=10, b=30),
        showlegend=False,
    )

    cum_total = bal_df["cum_deficit"].iloc[-1] if len(bal_df) > 0 else 0
    cum_kg = cum_total / 7700
    cum_days = len(bal_df)
    st.markdown(
        f"<div style='text-align:center;font-size:13px;color:#94A3B8;margin:-6px 0 4px;'>"
        f"📊 {cum_days}일 누적: <b style='color:{'#4ADE80' if cum_total <= 0 else '#FB7185'};'>"
        f"{cum_total:+,.0f} kcal</b> ≈ <b>{cum_kg:+.2f} kg</b></div>",
        unsafe_allow_html=True,
    )
    st.plotly_chart(fig_cum, use_container_width=True)

# ─── 칼로리 섭취 추이 (표 형식, 5단계 평가) ──────────────────
st.markdown("#### 🔥 일별 칼로리 상세")
_eval_mode_label = "순칼로리" if use_net_for_eval else "섭취 칼로리"
st.caption(f"{_eval_mode_label} 기준 평가 · 목표 {target:,} kcal")

if not totals.empty:
    totals_display = totals.copy()
    totals_display["date_dt"] = pd.to_datetime(totals_display["date"])
    totals_display["날짜"] = totals_display["date_dt"].apply(
        lambda d: f"{d.month}/{d.day} ({weekday_names[d.weekday()]})"
    )
    totals_display["burned"] = totals_display["date"].apply(
        lambda d: float(burn_by_date.get(d, 0))
    )
    totals_display["net"] = totals_display["total_cal"] - totals_display["burned"]

    # 보정 모드에 따라 평가 대상 결정
    eval_col = "net" if use_net_for_eval else "total_cal"

    totals_display["섭취"] = totals_display["total_cal"].apply(lambda c: f"{c:,.0f}")
    totals_display["운동"] = totals_display["burned"].apply(
        lambda c: f"-{c:,.0f}" if c > 0 else "—"
    )
    totals_display["순칼로리"] = totals_display["net"].apply(lambda c: f"{c:,.0f}")
    totals_display["차이"] = totals_display[eval_col].apply(
        lambda c: f"{int(c - target):+,}"
    )
    totals_display["평가"] = totals_display[eval_col].apply(
        lambda c: evaluate_calorie_status(c, target)[0]
    )

    if use_net_for_eval:
        cols = ["날짜", "섭취", "운동", "순칼로리", "차이", "평가"]
    else:
        cols = ["날짜", "섭취", "차이", "평가"]
    display_df = totals_display[cols].sort_values("날짜", ascending=False)
    st.dataframe(display_df, use_container_width=True, hide_index=True, height=min(len(display_df) * 36 + 38, 400))

    # 인사이트 (4단계 기반)
    eval_results = totals_display[eval_col].apply(lambda c: evaluate_calorie_status(c, target)[2])
    n_over = int((eval_results == "over").sum())
    n_too_low = int((eval_results == "too_low").sum())
    total_days = len(totals_display)

    if n_too_low > 0:
        st.warning(f"⚠️ {total_days}일 중 {n_too_low}일 칼로리 너무 적음 — 에너지 가용성 부족 위험 (근손실·호르몬 저하)")
    if n_over > total_days * 0.5:
        st.warning(f"⚠️ {total_days}일 중 {n_over}일 목표 초과 — 식단 조절이 필요합니다.")
    elif n_over == 0 and n_too_low == 0:
        st.success(f"✅ {total_days}일 모두 적정 범위 — 순항 중!")

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
        max_count = int(top_foods["count"].max())
        rank_html = "<div style='margin-top:8px;'>"
        for rank, (_, row) in enumerate(top_foods.iterrows(), 1):
            cnt = int(row["count"])
            pct = cnt / max_count * 100
            medal = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][rank - 1]
            rank_html += (
                f"<div style='margin-bottom:10px;'>"
                f"<div style='display:flex;align-items:center;gap:6px;font-size:14px;'>"
                f"<span>{medal}</span>"
                f"<span style='font-weight:600;color:#F8FAFC;'>{row['food_name']}</span>"
                f"<span style='margin-left:auto;font-size:13px;color:#94A3B8;'>{cnt}회</span>"
                f"</div>"
                f"<div style='background:rgba(30,41,59,0.6);border-radius:4px;height:6px;margin-top:4px;'>"
                f"<div style='width:{pct}%;height:100%;background:#8B5CF6;border-radius:4px;'></div>"
                f"</div></div>"
            )
        rank_html += "</div>"
        st.markdown(rank_html, unsafe_allow_html=True)

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
            **PLOT_CFG, height=240,
            xaxis_title="", yaxis_title="평균 kcal",
            margin=dict(l=40, r=20, t=30, b=30),
            bargap=0.4,
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
            textfont=dict(size=15, color="#F8FAFC"),
            hole=0.6,
        ))
        fig_pie.update_layout(
            **PLOT_CFG, height=260, showlegend=False,
            margin=dict(l=10, r=10, t=10, b=10),
            annotations=[dict(
                text=f"<span style='font-size:12px;color:#94A3B8;'>일평균</span><br>"
                     f"<b style='font-size:22px;'>{avg_kcal_str}</b><br>"
                     f"<span style='font-size:11px;color:#94A3B8;'>kcal</span>",
                x=0.5, y=0.5, showarrow=False,
            )],
        )
        # 도넛을 중앙에 배치
        pc_left, pc_center, pc_right = st.columns([1, 2, 1])
        with pc_center:
            st.plotly_chart(fig_pie, use_container_width=True)

        # 단백질 체크 — 감량 강도 기반 (정석)
        pct_p = t_p / total_g * 100
        target_p_per_day, protein_mult = calc_protein_g(latest_weight, deficit_level)
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

"""🏃 운동 기록 페이지 — 식단과 분리된 컴팩트 운동 입력."""

import datetime

import pandas as pd
import streamlit as st

from config import EXERCISE_OPTIONS, today_kst
from services.auth_service import require_auth
from services.sheets_service import (
    get_profile, get_latest_weight,
    save_exercise, get_exercise_log,
    delete_exercise_row, update_exercise_row,
)

email = require_auth()
st.title("🏃 운동 기록")

profile = get_profile(email) or {}
latest_weight = get_latest_weight(email) or float(profile.get("weight", 70))

# ─── 날짜 선택 ───────────────────────────────────────────────
if "ex_page_date" not in st.session_state:
    st.session_state.ex_page_date = today_kst()
if "ex_date_ver" not in st.session_state:
    st.session_state.ex_date_ver = 0

qp = st.query_params
if "ex_nav" in qp:
    nav = qp["ex_nav"]
    cur = st.session_state.ex_page_date
    if nav == "prev":
        st.session_state.ex_page_date = cur - datetime.timedelta(days=1)
    elif nav == "today":
        st.session_state.ex_page_date = today_kst()
    elif nav == "next":
        st.session_state.ex_page_date = cur + datetime.timedelta(days=1)
    st.session_state.ex_date_ver += 1
    del st.query_params["ex_nav"]
    st.rerun()

selected_date = st.date_input(
    "날짜", value=st.session_state.ex_page_date,
    key=f"ex_dp_{st.session_state.ex_date_ver}",
)
if selected_date != st.session_state.ex_page_date:
    st.session_state.ex_page_date = selected_date
date_str = st.session_state.ex_page_date.isoformat()

st.markdown(
    "<div style='display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px;margin:4px 0 8px;'>"
    "<a href='?ex_nav=prev' target='_self' style='background:rgba(30,41,59,0.5);"
    "border:1px solid rgba(148,163,184,0.2);color:#F8FAFC;padding:8px 0;"
    "border-radius:8px;text-align:center;text-decoration:none;font-size:13px;'>◀ 어제</a>"
    "<a href='?ex_nav=today' target='_self' style='background:rgba(30,41,59,0.5);"
    "border:1px solid rgba(148,163,184,0.2);color:#F8FAFC;padding:8px 0;"
    "border-radius:8px;text-align:center;text-decoration:none;font-size:13px;'>오늘</a>"
    "<a href='?ex_nav=next' target='_self' style='background:rgba(30,41,59,0.5);"
    "border:1px solid rgba(148,163,184,0.2);color:#F8FAFC;padding:8px 0;"
    "border-radius:8px;text-align:center;text-decoration:none;font-size:13px;'>내일 ▶</a>"
    "</div>",
    unsafe_allow_html=True,
)

# ─── 운동 입력 폼 ────────────────────────────────────────────
st.markdown("### ➕ 운동 추가")

if "ex_page_form_ver" not in st.session_state:
    st.session_state.ex_page_form_ver = 0
ev = st.session_state.ex_page_form_ver

# 운동 선택 — radio (모바일 키보드 활성화 방지)
ex_display = [f"{e['icon']} {e['name']}" for e in EXERCISE_OPTIONS if e['name'] != '직접 입력']

# 카테고리별 그룹 (스크롤 최소화)
selected_idx = st.radio(
    "운동 선택",
    options=range(len(ex_display)),
    format_func=lambda i: ex_display[i],
    key=f"ex_radio_{ev}",
    horizontal=False,
    label_visibility="collapsed",
)

dur = st.number_input(
    "시간 (분)",
    min_value=5, max_value=300, value=30, step=5,
    key=f"ex_dur_{ev}",
)

ex_info = EXERCISE_OPTIONS[selected_idx]
met = ex_info["met"] if ex_info["met"] > 0 else 5.0
expected_burn = round(met * latest_weight * dur / 60)
st.caption(f"예상 소모: **{expected_burn:,} kcal** (체중 {latest_weight:.0f}kg · MET {met})")

if st.button("🏃 운동 저장", use_container_width=True, type="primary"):
    save_exercise(email, date_str, ex_info["name"], dur, met, latest_weight)
    st.toast(f"✅ {ex_info['name']} {dur}분 ({expected_burn}kcal) 저장!", icon="🏃")
    st.session_state.ex_page_form_ver += 1
    st.rerun()

st.divider()

# ─── 오늘의 운동 기록 ────────────────────────────────────────
st.markdown(f"### 📋 {date_str} 운동 기록")

ex_today = get_exercise_log(email, date_str, date_str)
if ex_today.empty:
    st.markdown(
        "<div style='text-align:center;padding:24px 16px;background:rgba(30,41,59,0.3);"
        "border-radius:10px;color:#94A3B8;'>운동 기록이 없습니다</div>",
        unsafe_allow_html=True,
    )
else:
    total_burn = ex_today["calories_burned"].sum()
    st.markdown(
        f"<div style='background:rgba(34,197,94,0.1);border:1px solid rgba(34,197,94,0.3);"
        f"border-radius:10px;padding:10px 14px;margin:6px 0 12px;text-align:center;'>"
        f"<span style='color:#94A3B8;font-size:13px;'>총 소모</span> "
        f"<b style='font-size:20px;color:#4ADE80;'>{total_burn:,.0f} kcal</b> "
        f"<span style='color:#64748B;font-size:12px;'>· {len(ex_today)}개 운동</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    for idx, row in ex_today.iterrows():
        ex_key = f"ex_{date_str}_{idx}"
        is_editing = st.session_state.get("ex_editing") == ex_key

        if is_editing:
            with st.form(f"ex_edit_{ex_key}"):
                st.markdown(f"**{row['exercise_name']}** 수정")
                new_dur = st.number_input(
                    "시간 (분)", min_value=5, max_value=300,
                    value=int(row["duration_min"]), step=5,
                )
                new_met = float(row.get("met", 5))
                new_burn = round(new_met * latest_weight * new_dur / 60)
                st.caption(f"새 소모: {new_burn:,} kcal")

                ec1, ec2 = st.columns(2)
                if ec1.form_submit_button("저장", type="primary", use_container_width=True):
                    update_exercise_row(
                        email, date_str, row["exercise_name"],
                        str(row.get("created_at", "")), new_dur, latest_weight,
                    )
                    st.session_state.ex_editing = None
                    st.toast("✅ 수정됨", icon="✏️")
                    st.rerun()
                if ec2.form_submit_button("취소", use_container_width=True):
                    st.session_state.ex_editing = None
                    st.rerun()
        else:
            burn = int(row["calories_burned"])
            duration = int(row["duration_min"])
            st.markdown(
                f"<div style='background:rgba(30,41,59,0.4);border-radius:8px;padding:8px 12px;margin:4px 0;'>"
                f"<div style='display:flex;align-items:center;gap:8px;'>"
                f"<span style='font-weight:600;font-size:14px;'>{row['exercise_name']}</span>"
                f"<span style='color:#94A3B8;font-size:12px;'>{duration}분</span>"
                f"<span style='margin-left:auto;color:#4ADE80;font-weight:700;font-size:14px;'>-{burn} kcal</span>"
                f"</div></div>",
                unsafe_allow_html=True,
            )
            bc1, bc2, bc3 = st.columns([1, 1, 4])
            if bc1.button("수정", key=f"e_edit_{idx}", use_container_width=True):
                st.session_state.ex_editing = ex_key
                st.rerun()
            if bc2.button("삭제", key=f"e_del_{idx}", use_container_width=True):
                delete_exercise_row(
                    email, date_str, row["exercise_name"], str(row.get("created_at", "")),
                )
                st.toast(f"🗑️ {row['exercise_name']} 삭제", icon="🗑️")
                st.rerun()

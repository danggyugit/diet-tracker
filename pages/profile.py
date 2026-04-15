"""👤 프로필 페이지 — 신체정보 + 감량 강도 + BMR/TDEE/영양소 목표."""

import datetime

import streamlit as st

from config import ACTIVITY_MULTIPLIERS, PROTEIN_MULTIPLIERS, today_kst
from services.auth_service import require_auth
from services.sheets_service import (
    get_profile, save_profile, get_latest_weight,
    get_meals, get_weight_log, get_exercise_log,
)
from services.calorie_service import calc_bmr, calc_tdee

email = require_auth()
st.title("👤 프로필")

# ─── 기존 프로필 로드 ───────────────────────────────────────
profile = get_profile(email) or {}
latest_weight = get_latest_weight(email)

# ─── 활동 수준 설명 ──────────────────────────────────────────
ACTIVITY_DESC = {
    "비활동": "거의 운동 안 함 (사무직)",
    "가벼운활동": "주 1-3일 가벼운 운동",
    "보통활동": "주 3-5일 중간 강도",
    "활발한활동": "주 6-7일 운동",
    "매우활발": "매일 고강도, 육체노동",
}

# ─── 감량 강도 옵션 (간결한 라벨) ─────────────────────────────
DEFICIT_OPTIONS = {
    "🟢 가벼운 (-500)": 500,
    "🟡 보통 (-700)": 700,
    "🔴 강한 (-1000)": 1000,
    "⚪ 유지": 0,
}
DEFICIT_DESC = {
    500: "주 약 0.45kg 감량 — 무리 없이 꾸준히",
    700: "주 약 0.64kg 감량 — 균형 잡힌 속도",
    1000: "주 약 0.9kg 감량 — 빠르지만 식욕·근손실 주의",
    0: "현재 체중 유지",
}
DEFICIT_KEYS = list(DEFICIT_OPTIONS.keys())

try:
    saved_deficit = int(profile.get("deficit_level") or 700)
except (ValueError, TypeError):
    saved_deficit = 700

default_deficit_idx = 1
for i, (_, v) in enumerate(DEFICIT_OPTIONS.items()):
    if v == saved_deficit:
        default_deficit_idx = i
        break

# ─── 입력 폼 ─────────────────────────────────────────────
with st.form("profile_form"):
    st.markdown("**신체 정보**")
    col1, col2 = st.columns(2)
    with col1:
        gender = st.radio(
            "성별", ["남성", "여성"],
            index=0 if profile.get("gender", "남성") == "남성" else 1,
            horizontal=True,
        )
        age = st.number_input("나이", min_value=10, max_value=100, value=int(profile.get("age", 30)))
        height = st.number_input("키 (cm)", min_value=100.0, max_value=250.0, value=float(profile.get("height", 170)), step=0.5, format="%.1f")
    with col2:
        default_weight = latest_weight or float(profile.get("weight", 70))
        weight = st.number_input("현재 체중 (kg)", min_value=30.0, max_value=200.0, value=default_weight, step=0.1, format="%.1f")
        activity_options = list(ACTIVITY_MULTIPLIERS.keys())
        default_act_idx = (
            activity_options.index(profile.get("activity_level", "보통활동"))
            if profile.get("activity_level") in ACTIVITY_MULTIPLIERS else 2
        )
        activity_level = st.selectbox(
            "활동 수준", activity_options,
            index=default_act_idx,
            format_func=lambda x: f"{x} — {ACTIVITY_DESC[x]}",
        )

    st.markdown("---")
    st.markdown("**감량 강도**")
    deficit_choice = st.radio(
        "감량 강도 선택", DEFICIT_KEYS,
        index=default_deficit_idx, horizontal=True,
        label_visibility="collapsed",
    )
    deficit_level = DEFICIT_OPTIONS[deficit_choice]
    st.caption(DEFICIT_DESC[deficit_level])

    st.markdown("---")
    st.markdown("**목표 (참고)** — 감량 속도 예측용")
    gc1, gc2 = st.columns(2)
    with gc1:
        target_weight = st.number_input("목표 체중 (kg)", min_value=30.0, max_value=200.0,
            value=float(profile.get("target_weight", 0)) or default_weight - 10, step=0.5, format="%.1f")
    with gc2:
        saved_date = profile.get("target_date", "")
        default_date = datetime.date.fromisoformat(saved_date) if saved_date else today_kst() + datetime.timedelta(days=180)
        target_date = st.date_input("목표 날짜", value=default_date, min_value=today_kst())

    submitted = st.form_submit_button("저장", type="primary", use_container_width=True)

# ═══════════════════════════════════════════════════════════════
# 계산 결과
# ═══════════════════════════════════════════════════════════════

bmr = calc_bmr(weight, height, age, gender)
tdee = calc_tdee(bmr, activity_level)
daily_target = round(tdee - deficit_level)

protein_mult = PROTEIN_MULTIPLIERS.get(activity_level, 1.3)
protein_g = round(weight * protein_mult)
fat_g = round(daily_target * 0.30 / 9)
protein_cal = protein_g * 4
fat_cal = fat_g * 9
carbs_g = max(round((daily_target - protein_cal - fat_cal) / 4), 50)

st.divider()

# ─── 히어로 카드: 일일 섭취 목표 ──────────────────────────────
st.markdown(
    f"<div style='background:linear-gradient(135deg,rgba(34,197,94,0.15),rgba(59,130,246,0.15));"
    f"border:1px solid rgba(34,197,94,0.3);border-radius:14px;padding:18px;text-align:center;margin:8px 0 14px;'>"
    f"<div style='font-size:13px;color:#94A3B8;margin-bottom:4px;'>오늘의 섭취 목표</div>"
    f"<div style='font-size:36px;font-weight:800;color:#22C55E;line-height:1.1;'>{daily_target:,}</div>"
    f"<div style='font-size:13px;color:#CBD5E1;margin-top:2px;'>kcal / 일</div>"
    f"</div>",
    unsafe_allow_html=True,
)

# ─── 계산 결과 + 영양소 통합 카드 (HTML grid, 모바일 가로 강제) ───
st.markdown(
    f"<div style='display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-bottom:6px;'>"
    f"<div style='background:rgba(30,41,59,0.5);border:1px solid rgba(148,163,184,0.15);"
    f"border-radius:10px;padding:12px;text-align:center;'>"
    f"<div style='font-size:11px;color:#94A3B8;'>BMR</div>"
    f"<div style='font-size:18px;font-weight:700;margin-top:2px;'>{bmr:,.0f}</div>"
    f"<div style='font-size:10px;color:#64748B;'>기초대사량</div></div>"
    f"<div style='background:rgba(30,41,59,0.5);border:1px solid rgba(148,163,184,0.15);"
    f"border-radius:10px;padding:12px;text-align:center;'>"
    f"<div style='font-size:11px;color:#94A3B8;'>TDEE</div>"
    f"<div style='font-size:18px;font-weight:700;margin-top:2px;'>{tdee:,.0f}</div>"
    f"<div style='font-size:10px;color:#64748B;'>일일 소모</div></div>"
    f"<div style='background:rgba(30,41,59,0.5);border:1px solid rgba(148,163,184,0.15);"
    f"border-radius:10px;padding:12px;text-align:center;'>"
    f"<div style='font-size:11px;color:#94A3B8;'>일일 적자</div>"
    f"<div style='font-size:18px;font-weight:700;margin-top:2px;color:#F59E0B;'>-{deficit_level}</div>"
    f"<div style='font-size:10px;color:#64748B;'>kcal</div></div>"
    f"</div>",
    unsafe_allow_html=True,
)

# 영양소 카드
st.markdown(
    f"<div style='display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-bottom:14px;'>"
    f"<div style='background:rgba(74,222,128,0.1);border:1px solid rgba(74,222,128,0.3);"
    f"border-radius:10px;padding:12px;text-align:center;'>"
    f"<div style='font-size:11px;color:#4ADE80;'>🍚 탄수화물</div>"
    f"<div style='font-size:20px;font-weight:700;margin-top:2px;'>{carbs_g}g</div>"
    f"<div style='font-size:10px;color:#64748B;'>나머지</div></div>"
    f"<div style='background:rgba(96,165,250,0.1);border:1px solid rgba(96,165,250,0.3);"
    f"border-radius:10px;padding:12px;text-align:center;'>"
    f"<div style='font-size:11px;color:#60A5FA;'>🥩 단백질</div>"
    f"<div style='font-size:20px;font-weight:700;margin-top:2px;'>{protein_g}g</div>"
    f"<div style='font-size:10px;color:#64748B;'>×{protein_mult}g/kg</div></div>"
    f"<div style='background:rgba(251,191,36,0.1);border:1px solid rgba(251,191,36,0.3);"
    f"border-radius:10px;padding:12px;text-align:center;'>"
    f"<div style='font-size:11px;color:#FBBF24;'>🧈 지방</div>"
    f"<div style='font-size:20px;font-weight:700;margin-top:2px;'>{fat_g}g</div>"
    f"<div style='font-size:10px;color:#64748B;'>30%</div></div>"
    f"</div>",
    unsafe_allow_html=True,
)

st.caption(
    f"단백질 {weight:.0f}kg × {protein_mult} = {protein_g}g · "
    f"지방 {daily_target:,} × 30% = {fat_g}g · "
    f"탄수화물 = {carbs_g}g (나머지)"
)

# ─── 체중 진행률 바 ──────────────────────────────────────────
if target_weight and target_weight != weight:
    starting_weight = float(profile.get("weight", weight))
    if starting_weight == target_weight:
        starting_weight = weight + abs(weight - target_weight)

    if weight > target_weight:
        total_to_lose = max(starting_weight - target_weight, 0.1)
        lost = max(starting_weight - weight, 0)
        progress_pct = min(max(lost / total_to_lose * 100, 0), 100)
        remaining = max(weight - target_weight, 0)
        bar_color = "#22C55E"
        progress_label = f"{lost:.1f}kg 감량 / 총 {total_to_lose:.1f}kg"
        remain_label = f"남은 감량 {remaining:.1f}kg"
    else:
        total_to_gain = max(target_weight - starting_weight, 0.1)
        gained = max(weight - starting_weight, 0)
        progress_pct = min(max(gained / total_to_gain * 100, 0), 100)
        remaining = max(target_weight - weight, 0)
        bar_color = "#3B82F6"
        progress_label = f"{gained:.1f}kg 증량 / 총 {total_to_gain:.1f}kg"
        remain_label = f"남은 증량 {remaining:.1f}kg"

    st.divider()
    st.markdown("#### 🎯 체중 진행률")
    st.markdown(
        f"<div style='background:rgba(30,41,59,0.5);border:1px solid rgba(148,163,184,0.15);"
        f"border-radius:12px;padding:14px;margin:6px 0;'>"
        f"<div style='display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px;text-align:center;margin-bottom:10px;'>"
        f"<div><div style='font-size:11px;color:#64748B;'>시작</div>"
        f"<div style='font-size:16px;font-weight:600;'>{starting_weight:.1f}<span style='font-size:11px;color:#94A3B8;'>kg</span></div></div>"
        f"<div><div style='font-size:11px;color:#64748B;'>현재</div>"
        f"<div style='font-size:18px;font-weight:700;color:{bar_color};'>{weight:.1f}<span style='font-size:11px;color:#94A3B8;'>kg</span></div></div>"
        f"<div><div style='font-size:11px;color:#64748B;'>목표</div>"
        f"<div style='font-size:16px;font-weight:600;'>{target_weight:.1f}<span style='font-size:11px;color:#94A3B8;'>kg</span></div></div>"
        f"</div>"
        f"<div style='background:rgba(15,23,42,0.6);border-radius:8px;height:12px;overflow:hidden;position:relative;'>"
        f"<div style='background:linear-gradient(90deg,{bar_color},{bar_color}cc);"
        f"height:100%;width:{max(progress_pct, 3):.1f}%;border-radius:8px;min-width:8px;'></div></div>"
        f"<div style='display:flex;justify-content:space-between;font-size:11px;color:#94A3B8;margin-top:6px;'>"
        f"<span>{progress_label}</span><span style='color:{bar_color};font-weight:600;'>{progress_pct:.0f}%</span>"
        f"</div>"
        f"<div style='text-align:center;font-size:12px;color:#CBD5E1;margin-top:4px;'>{remain_label}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

# ─── 목표 도달 예측 ──────────────────────────────────────────
if deficit_level > 0 and target_weight < weight:
    weekly_loss = deficit_level * 7 / 7700
    kg_to_lose = weight - target_weight
    weeks_needed = kg_to_lose / weekly_loss if weekly_loss > 0 else 0
    predicted_date = today_kst() + datetime.timedelta(weeks=weeks_needed)

    st.markdown("#### 📅 목표 도달 예측")
    st.markdown(
        f"<div style='display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin:6px 0;'>"
        f"<div style='background:rgba(30,41,59,0.5);border:1px solid rgba(148,163,184,0.15);"
        f"border-radius:10px;padding:12px;text-align:center;'>"
        f"<div style='font-size:11px;color:#94A3B8;'>총 감량</div>"
        f"<div style='font-size:18px;font-weight:700;margin-top:2px;'>{kg_to_lose:.1f}<span style='font-size:11px;'>kg</span></div></div>"
        f"<div style='background:rgba(30,41,59,0.5);border:1px solid rgba(148,163,184,0.15);"
        f"border-radius:10px;padding:12px;text-align:center;'>"
        f"<div style='font-size:11px;color:#94A3B8;'>주당</div>"
        f"<div style='font-size:18px;font-weight:700;margin-top:2px;'>{weekly_loss:.2f}<span style='font-size:11px;'>kg</span></div></div>"
        f"<div style='background:rgba(30,41,59,0.5);border:1px solid rgba(148,163,184,0.15);"
        f"border-radius:10px;padding:12px;text-align:center;'>"
        f"<div style='font-size:11px;color:#94A3B8;'>도달일</div>"
        f"<div style='font-size:14px;font-weight:700;margin-top:4px;'>{predicted_date.isoformat()}</div></div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    if predicted_date <= datetime.date.fromisoformat(target_date.isoformat()):
        st.success(f"✅ 현 강도 유지 시 목표 날짜({target_date}) 이내 달성 가능!")
    else:
        diff_days = (predicted_date - datetime.date.fromisoformat(target_date.isoformat())).days
        st.info(
            f"💡 현 강도 유지 시 목표보다 약 {diff_days}일 늦을 수 있습니다.\n\n"
            f"감량 강도를 올리거나 목표 날짜·체중을 조정해 보세요. "
            f"(꾸준히만 해도 충분합니다 — 무리한 속도는 요요 위험)"
        )

st.caption(
    f"Mifflin-St Jeor · {gender} · {age}세 · {height}cm · {weight}kg "
    f"· 활동계수 {ACTIVITY_MULTIPLIERS.get(activity_level, 1.55):.3f}"
)

# ─── 저장 ────────────────────────────────────────────────
if submitted:
    save_profile(email, {
        "gender": gender, "age": age, "height": height, "weight": weight,
        "activity_level": activity_level, "target_calories": 0,
        "target_weight": target_weight, "target_date": target_date.isoformat(),
        "deficit_level": deficit_level,
    })
    st.success("프로필이 저장되었습니다!")
    st.rerun()

# ═══════════════════════════════════════════════════════════════
# 데이터 내보내기 (expander로 접기)
# ═══════════════════════════════════════════════════════════════

st.divider()
with st.expander("📥 내 데이터 내보내기 (CSV)"):
    st.caption("본인의 식단·체중·운동 기록을 CSV 파일로 다운로드합니다.")

    ec1, ec2 = st.columns(2)
    with ec1:
        export_start = st.date_input(
            "시작일", value=today_kst() - datetime.timedelta(days=30),
            key="export_start",
        )
    with ec2:
        export_end = st.date_input("종료일", value=today_kst(), key="export_end")

    ebtn1, ebtn2, ebtn3 = st.columns(3)

    meals_df = get_meals(email, export_start.isoformat(), export_end.isoformat())
    if not meals_df.empty:
        meals_csv = meals_df.to_csv(index=False).encode("utf-8-sig")
        ebtn1.download_button(
            "🍽️ 식단",
            data=meals_csv,
            file_name=f"diet_meals_{export_start}_{export_end}.csv",
            mime="text/csv",
            use_container_width=True,
        )
    else:
        ebtn1.button("🍽️ 없음", disabled=True, use_container_width=True)

    weight_df = get_weight_log(email, export_start.isoformat(), export_end.isoformat())
    if not weight_df.empty:
        weight_csv = weight_df.to_csv(index=False).encode("utf-8-sig")
        ebtn2.download_button(
            "⚖️ 체중",
            data=weight_csv,
            file_name=f"diet_weight_{export_start}_{export_end}.csv",
            mime="text/csv",
            use_container_width=True,
        )
    else:
        ebtn2.button("⚖️ 없음", disabled=True, use_container_width=True)

    ex_df = get_exercise_log(email, export_start.isoformat(), export_end.isoformat())
    if not ex_df.empty:
        ex_csv = ex_df.to_csv(index=False).encode("utf-8-sig")
        ebtn3.download_button(
            "🏃 운동",
            data=ex_csv,
            file_name=f"diet_exercise_{export_start}_{export_end}.csv",
            mime="text/csv",
            use_container_width=True,
        )
    else:
        ebtn3.button("🏃 없음", disabled=True, use_container_width=True)

    st.caption("💡 BOM 포함 UTF-8 — Excel/Google Sheets에서 한글 깨짐 없음")

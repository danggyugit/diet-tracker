"""⭐ 자주 먹는 음식 관리 페이지.

즐겨찾기 목록 확인, 수정, 삭제, 수동 추가.
"""

import streamlit as st

from services.auth_service import require_auth
from services.sheets_service import (
    get_favorites, delete_favorite, update_favorite,
    add_favorite, auto_add_favorites_from_meals,
)
from services.gemini_service import estimate_food_nutrition

email = require_auth()
st.title("⭐ 즐겨찾기")
st.caption("터치 한 번으로 식단에 추가할 음식을 관리합니다.")

if "fav_editing" not in st.session_state:
    st.session_state.fav_editing = None

# ─── 상단 액션 (추가 + 자동채우기) ──────────────────────────────
ac1, ac2 = st.columns(2)
with ac1:
    add_open = st.toggle("➕ 새 음식 추가", key="fav_add_toggle")
with ac2:
    if st.button("📥 식사 기록에서 채우기", use_container_width=True):
        added = auto_add_favorites_from_meals(email)
        if added:
            st.toast(f"✅ {len(added)}개 자동 등록!", icon="📥")
        else:
            st.toast("추가할 음식이 없습니다 (5회 이상 필요)", icon="ℹ️")
        st.rerun()

if add_open:
    with st.form("add_fav_form"):
        new_name = st.text_input("음식 이름", placeholder="예: 아메리카노")
        r1c1, r1c2 = st.columns(2)
        new_cal = r1c1.number_input("칼로리 (kcal)", value=0, min_value=0, key="nf_cal")
        new_amount = r1c2.text_input("양", value="1인분", key="nf_amount")
        r2c1, r2c2, r2c3 = st.columns(3)
        new_carbs = r2c1.number_input("탄수화물(g)", value=0, min_value=0, key="nf_carbs")
        new_prot = r2c2.number_input("단백질(g)", value=0, min_value=0, key="nf_prot")
        new_fat = r2c3.number_input("지방(g)", value=0, min_value=0, key="nf_fat")
        st.caption("💡 칼로리 0이면 AI가 자동 추정합니다.")

        if st.form_submit_button("추가", type="primary", use_container_width=True):
            if not new_name.strip():
                st.error("음식 이름을 입력하세요.")
            else:
                if new_cal == 0:
                    with st.spinner(f"'{new_name}' 영양 정보 추정 중..."):
                        try:
                            est = estimate_food_nutrition(new_name)
                            add_favorite(email, est)
                            st.success(f"✅ {est.get('name', new_name)} 추가! ({est.get('calories', 0)}kcal)")
                        except Exception as e:
                            st.error(f"추정 실패: {e}")
                else:
                    add_favorite(email, {
                        "name": new_name, "amount": new_amount,
                        "calories": new_cal, "carbs": new_carbs,
                        "protein": new_prot, "fat": new_fat,
                    })
                    st.success(f"✅ {new_name} 추가!")
                st.rerun()

# ─── 즐겨찾기 리스트 ─────────────────────────────────────────
favorites = get_favorites(email)

if not favorites:
    st.markdown(
        "<div style='text-align:center;padding:40px 20px;background:rgba(30,41,59,0.3);"
        "border-radius:12px;margin:20px 0;'>"
        "<div style='font-size:48px;'>⭐</div>"
        "<div style='color:#94A3B8;margin-top:8px;'>즐겨찾기가 비어있습니다</div>"
        "<div style='font-size:12px;color:#64748B;margin-top:4px;'>"
        "위의 '새 음식 추가'나 '식사 기록에서 채우기'를 사용해 보세요</div>"
        "</div>",
        unsafe_allow_html=True,
    )
else:
    st.divider()

    search = st.text_input("🔍 검색", placeholder="음식 이름으로 검색", label_visibility="collapsed")
    filtered = [f for f in favorites if search.lower() in f.get("food_name", "").lower()] if search else favorites

    st.caption(f"**{len(filtered)}개** {'(검색 결과)' if search else '등록됨'}")

    for i, fav in enumerate(filtered):
        fname = fav.get("food_name", "")
        cal = int(fav.get("calories", 0))
        carbs = int(fav.get("carbs", 0))
        prot = int(fav.get("protein", 0))
        fat = int(fav.get("fat", 0))
        amount = fav.get("amount", "")
        use_count = int(fav.get("use_count", 0))
        is_editing = st.session_state.fav_editing == fname

        if is_editing:
            with st.form(f"edit_fav_{i}"):
                st.markdown(f"**{fname}** 수정")
                r1c1, r1c2 = st.columns(2)
                e_cal = r1c1.number_input("kcal", value=cal, min_value=0, key=f"ef_cal_{i}")
                e_amount = r1c2.text_input("양", value=amount, key=f"ef_amt_{i}")
                r2c1, r2c2, r2c3 = st.columns(3)
                e_carbs = r2c1.number_input("탄(g)", value=carbs, min_value=0, key=f"ef_carbs_{i}")
                e_prot = r2c2.number_input("단(g)", value=prot, min_value=0, key=f"ef_prot_{i}")
                e_fat = r2c3.number_input("지(g)", value=fat, min_value=0, key=f"ef_fat_{i}")

                sc1, sc2 = st.columns(2)
                if sc1.form_submit_button("저장", use_container_width=True, type="primary"):
                    update_favorite(email, fname, {
                        "food_name": fname, "amount": e_amount,
                        "calories": e_cal, "carbs": e_carbs,
                        "protein": e_prot, "fat": e_fat,
                    })
                    st.session_state.fav_editing = None
                    st.rerun()
                if sc2.form_submit_button("취소", use_container_width=True):
                    st.session_state.fav_editing = None
                    st.rerun()
        else:
            st.markdown(
                f"<div style='background:rgba(30,41,59,0.4);border-radius:10px;padding:10px 14px;margin:6px 0;'>"
                f"<div style='display:flex;align-items:center;gap:8px;'>"
                f"<span style='font-weight:600;font-size:14px;'>{fname}</span>"
                f"<span style='font-size:12px;color:#94A3B8;'>{amount}</span>"
                f"<span style='margin-left:auto;font-weight:700;font-size:14px;'>{cal}kcal</span>"
                f"</div>"
                f"<div style='display:flex;gap:10px;font-size:12px;color:#94A3B8;margin-top:4px;'>"
                f"<span style='color:#4ADE80;'>탄 {carbs}g</span>"
                f"<span style='color:#60A5FA;'>단 {prot}g</span>"
                f"<span style='color:#FBBF24;'>지 {fat}g</span>"
                f"<span style='margin-left:auto;color:#64748B;'>사용 {use_count}회</span>"
                f"</div></div>",
                unsafe_allow_html=True,
            )
            bc1, bc2, bc3 = st.columns([1, 1, 4])
            if bc1.button("수정", key=f"fedit_{i}", use_container_width=True):
                st.session_state.fav_editing = fname
                st.rerun()
            if bc2.button("삭제", key=f"fdel_{i}", use_container_width=True):
                delete_favorite(email, fname)
                st.toast(f"🗑️ {fname} 삭제", icon="🗑️")
                st.rerun()

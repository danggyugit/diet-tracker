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
st.title("⭐ 자주 먹는 음식")
st.caption("여기서 즐겨찾기를 관리하면 식단 기록에서 터치 한 번으로 빠르게 추가할 수 있습니다.")

# ─── 세션 상태 ───────────────────────────────────────────────
if "fav_editing" not in st.session_state:
    st.session_state.fav_editing = None

# ─── 즐겨찾기 목록 ──────────────────────────────────────────
favorites = get_favorites(email)

if not favorites:
    st.info("즐겨찾기가 비어있습니다.")
    if st.button("📥 식사 기록에서 자동 채우기"):
        auto_add_favorites_from_meals(email)
        st.rerun()

# ─── 수동 추가 ───────────────────────────────────────────────
with st.expander("➕ 새 음식 추가", expanded=False):
    with st.form("add_fav_form"):
        new_name = st.text_input("음식 이름", placeholder="예: 아메리카노")
        nc1, nc2, nc3, nc4 = st.columns(4)
        new_cal = nc1.number_input("kcal", value=0, min_value=0, key="nf_cal")
        new_carbs = nc2.number_input("탄(g)", value=0, min_value=0, key="nf_carbs")
        new_prot = nc3.number_input("단(g)", value=0, min_value=0, key="nf_prot")
        new_fat = nc4.number_input("지(g)", value=0, min_value=0, key="nf_fat")
        new_amount = st.text_input("양", value="1인분", key="nf_amount")
        st.caption("칼로리를 0으로 두면 AI가 자동 추정합니다.")

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
if favorites:
    st.divider()
    st.markdown(f"**{len(favorites)}개 등록됨**")

    for i, fav in enumerate(favorites):
        fname = fav.get("food_name", "")
        is_editing = st.session_state.fav_editing == fname

        if is_editing:
            with st.form(f"edit_fav_{i}"):
                st.markdown(f"**{fname}** 수정")
                ec1, ec2, ec3, ec4 = st.columns(4)
                e_cal = ec1.number_input("kcal", value=int(fav.get("calories", 0)), min_value=0, key=f"ef_cal_{i}")
                e_carbs = ec2.number_input("탄(g)", value=int(fav.get("carbs", 0)), min_value=0, key=f"ef_carbs_{i}")
                e_prot = ec3.number_input("단(g)", value=int(fav.get("protein", 0)), min_value=0, key=f"ef_prot_{i}")
                e_fat = ec4.number_input("지(g)", value=int(fav.get("fat", 0)), min_value=0, key=f"ef_fat_{i}")
                e_amount = st.text_input("양", value=fav.get("amount", ""), key=f"ef_amt_{i}")

                sc1, sc2 = st.columns(2)
                if sc1.form_submit_button("저장", use_container_width=True):
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
                f"**{fname}** {fav.get('amount', '')} · "
                f"<span style='color:#94A3B8;'>"
                f"{fav.get('calories', 0)}kcal | "
                f"탄{fav.get('carbs', 0)} 단{fav.get('protein', 0)} 지{fav.get('fat', 0)}"
                f"</span>"
                f" · <span style='color:#64748B;font-size:12px;'>"
                f"사용 {fav.get('use_count', 0)}회</span>",
                unsafe_allow_html=True,
            )
            bc1, bc2, bc3 = st.columns([1, 1, 4])
            if bc1.button("수정", key=f"fedit_{i}", use_container_width=True):
                st.session_state.fav_editing = fname
                st.rerun()
            if bc2.button("삭제", key=f"fdel_{i}", use_container_width=True):
                delete_favorite(email, fname)
                st.rerun()

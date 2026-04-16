"""Google Sheets CRUD 서비스 (gspread + Service Account)."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials

from config import (
    SHEETS_NAME, WS_MEALS, WS_PROFILES, WS_MEMOS, WS_WEIGHT_LOG,
    WS_EXERCISE_LOG, WS_WATER_LOG, WS_FAVORITES,
    MEALS_HEADERS, PROFILES_HEADERS, MEMOS_HEADERS, WEIGHT_LOG_HEADERS,
    EXERCISE_LOG_HEADERS, WATER_LOG_HEADERS, FAVORITES_HEADERS,
)

KST = ZoneInfo("Asia/Seoul")


def _now_kst() -> str:
    return datetime.now(KST).isoformat()

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


@st.cache_resource
def _get_client() -> gspread.Client:
    try:
        creds_info = dict(st.secrets["gcp_service_account"])
        creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
        return gspread.authorize(creds)
    except KeyError:
        raise RuntimeError(
            "⚠️ 서비스 설정 오류\n\n"
            "Google Sheets 연결 정보가 설정되지 않았습니다. 관리자에게 문의해 주세요."
        )
    except Exception as e:
        raise RuntimeError(
            f"⚠️ Google Sheets 인증 실패\n\n"
            f"잠시 후 다시 시도해 주세요. 문제가 지속되면 로그아웃 후 재로그인해 주세요.\n\n"
            f"상세: {str(e)[:100]}"
        )


@st.cache_resource
def _get_spreadsheet() -> gspread.Spreadsheet:
    return _get_client().open(SHEETS_NAME)


@st.cache_resource
def _get_worksheet(name: str) -> gspread.Worksheet:
    ss = _get_spreadsheet()
    try:
        return ss.worksheet(name)
    except gspread.WorksheetNotFound:
        return ss.add_worksheet(title=name, rows=1000, cols=20)


def _ensure_headers(ws: gspread.Worksheet, headers: list[str]) -> None:
    """워크시트 헤더행이 비어있거나 열 수가 다르면 갱신."""
    first_row = ws.row_values(1)
    if not first_row:
        ws.append_row(headers)
    elif len(first_row) != len(headers) or first_row != headers:
        ws.update(f"A1:{chr(64 + len(headers))}1", [headers])


# ─── Profiles ────────────────────────────────────────────────

@st.cache_data(ttl=300)
def get_profile(_email: str) -> dict | None:
    ws = _get_worksheet(WS_PROFILES)
    _ensure_headers(ws, PROFILES_HEADERS)
    records = ws.get_all_records()
    for r in records:
        if r.get("email") == _email:
            return r
    return None


def save_profile(email: str, data: dict) -> None:
    ws = _get_worksheet(WS_PROFILES)
    _ensure_headers(ws, PROFILES_HEADERS)
    records = ws.get_all_records()

    row_idx = None
    for i, r in enumerate(records):
        if r.get("email") == email:
            row_idx = i + 2  # 1-indexed + header row
            break

    now = _now_kst()
    row = [
        email,
        data.get("gender", "남성"),
        data.get("age", 30),
        data.get("height", 170),
        data.get("weight", 70),
        data.get("activity_level", "보통활동"),
        data.get("target_calories", 0),
        data.get("target_weight", 0),
        data.get("target_date", ""),
        data.get("deficit_level", 700),
        data.get("exercise_compensation", "off"),
        now,
    ]

    if row_idx:
        ws.update(f"A{row_idx}:L{row_idx}", [row])
    else:
        ws.append_row(row)

    get_profile.clear()


# ─── Meals ────────────────────────────────────────────────

@st.cache_data(ttl=300)
def get_meals(_email: str, start_date: str, end_date: str) -> pd.DataFrame:
    ws = _get_worksheet(WS_MEALS)
    _ensure_headers(ws, MEALS_HEADERS)
    records = ws.get_all_records()
    if not records:
        return pd.DataFrame(columns=MEALS_HEADERS)
    df = pd.DataFrame(records)
    mask = (df["email"] == _email) & (df["date"] >= start_date) & (df["date"] <= end_date)
    return df[mask].reset_index(drop=True)


def get_meals_for_date(email: str, date: str) -> pd.DataFrame:
    return get_meals(email, date, date)


def save_meals(email: str, date: str, meal_type: str, foods: list[dict]) -> None:
    ws = _get_worksheet(WS_MEALS)
    _ensure_headers(ws, MEALS_HEADERS)
    now = _now_kst()

    rows = []
    for f in foods:
        qty = f.get("quantity", 1.0)
        cal = f.get("calories", 0)
        rows.append([
            email, date, meal_type,
            f.get("name", ""),
            f.get("amount", ""),
            cal,
            f.get("carbs", 0),
            f.get("protein", 0),
            f.get("fat", 0),
            qty,
            round(cal * qty),
            f.get("source", "ai"),
            now,
        ])

    if rows:
        ws.append_rows(rows)
    get_meals.clear()


def delete_meal_row(email: str, date: str, food_name: str, created_at: str) -> bool:
    """저장된 식사 기록에서 특정 행 삭제. email+date+food_name+created_at로 식별."""
    ws = _get_worksheet(WS_MEALS)
    _ensure_headers(ws, MEALS_HEADERS)
    records = ws.get_all_records()
    for i, r in enumerate(records):
        if (r.get("email") == email and r.get("date") == date
                and r.get("food_name") == food_name
                and str(r.get("created_at", "")) == str(created_at)):
            ws.delete_rows(i + 2)  # 1-indexed + header
            get_meals.clear()
            return True
    return False


def delete_meals_by_type(email: str, date: str, meal_type: str) -> int:
    """특정 식사 유형의 모든 기록 삭제. 삭제된 건수 반환."""
    ws = _get_worksheet(WS_MEALS)
    _ensure_headers(ws, MEALS_HEADERS)
    records = ws.get_all_records()
    rows_to_delete = []
    for i, r in enumerate(records):
        if (r.get("email") == email and r.get("date") == date
                and r.get("meal_type") == meal_type):
            rows_to_delete.append(i + 2)
    # 뒤에서부터 삭제 (인덱스 안 밀리게)
    for row_num in sorted(rows_to_delete, reverse=True):
        ws.delete_rows(row_num)
    if rows_to_delete:
        get_meals.clear()
    return len(rows_to_delete)


def update_meal_row(email: str, date: str, food_name: str, created_at: str,
                    new_calories: int, new_quantity: float,
                    new_carbs: int = None, new_protein: int = None, new_fat: int = None) -> bool:
    """저장된 식사 기록의 칼로리/수량/영양소 수정."""
    ws = _get_worksheet(WS_MEALS)
    _ensure_headers(ws, MEALS_HEADERS)
    records = ws.get_all_records()
    for i, r in enumerate(records):
        if (r.get("email") == email and r.get("date") == date
                and r.get("food_name") == food_name
                and str(r.get("created_at", "")) == str(created_at)):
            row_num = i + 2
            # calories=F, carbs=G, protein=H, fat=I, quantity=J, total_cal=K
            ws.update(f"F{row_num}", [[new_calories]])
            if new_carbs is not None:
                ws.update(f"G{row_num}", [[new_carbs]])
            if new_protein is not None:
                ws.update(f"H{row_num}", [[new_protein]])
            if new_fat is not None:
                ws.update(f"I{row_num}", [[new_fat]])
            ws.update(f"J{row_num}", [[new_quantity]])
            ws.update(f"K{row_num}", [[round(new_calories * new_quantity)]])
            get_meals.clear()
            return True
    return False


@st.cache_data(ttl=300)
def get_all_meals_for_year(_email: str, year: int) -> pd.DataFrame:
    start = f"{year}-01-01"
    end = f"{year}-12-31"
    return get_meals(_email, start, end)


# ─── Memos ────────────────────────────────────────────────

@st.cache_data(ttl=300)
def get_memo(_email: str, date: str) -> dict | None:
    ws = _get_worksheet(WS_MEMOS)
    _ensure_headers(ws, MEMOS_HEADERS)
    records = ws.get_all_records()
    for r in records:
        if r.get("email") == _email and r.get("date") == date:
            return r
    return None


def save_memo(email: str, date: str, condition: str, memo: str) -> None:
    ws = _get_worksheet(WS_MEMOS)
    _ensure_headers(ws, MEMOS_HEADERS)
    records = ws.get_all_records()
    now = _now_kst()
    row = [email, date, condition, memo, now]

    row_idx = None
    for i, r in enumerate(records):
        if r.get("email") == email and r.get("date") == date:
            row_idx = i + 2
            break

    if row_idx:
        ws.update(f"A{row_idx}:E{row_idx}", [row])
    else:
        ws.append_row(row)
    get_memo.clear()


# ─── Weight Log ──────────────────────────────────────────────

@st.cache_data(ttl=300)
def get_weight_log(_email: str, start_date: str, end_date: str) -> pd.DataFrame:
    ws = _get_worksheet(WS_WEIGHT_LOG)
    _ensure_headers(ws, WEIGHT_LOG_HEADERS)
    records = ws.get_all_records()
    if not records:
        return pd.DataFrame(columns=WEIGHT_LOG_HEADERS)
    df = pd.DataFrame(records)
    mask = (df["email"] == _email) & (df["date"] >= start_date) & (df["date"] <= end_date)
    result = df[mask].reset_index(drop=True)
    result["weight"] = pd.to_numeric(result["weight"], errors="coerce")
    return result.sort_values("date")


@st.cache_data(ttl=300)
def get_latest_weight(_email: str) -> float | None:
    ws = _get_worksheet(WS_WEIGHT_LOG)
    _ensure_headers(ws, WEIGHT_LOG_HEADERS)
    records = ws.get_all_records()
    user_records = [r for r in records if r.get("email") == _email]
    if not user_records:
        return None
    latest = max(user_records, key=lambda r: r.get("date", ""))
    try:
        return float(latest["weight"])
    except (ValueError, KeyError):
        return None


@st.cache_data(ttl=300)
def get_earliest_weight(_email: str) -> float | None:
    """가장 오래된 체중 기록 (시작 체중 표시용)."""
    ws = _get_worksheet(WS_WEIGHT_LOG)
    _ensure_headers(ws, WEIGHT_LOG_HEADERS)
    records = ws.get_all_records()
    user_records = [r for r in records if r.get("email") == _email and r.get("date")]
    if not user_records:
        return None
    earliest = min(user_records, key=lambda r: r.get("date", ""))
    try:
        return float(earliest["weight"])
    except (ValueError, KeyError):
        return None


def save_weight(email: str, date: str, weight: float) -> None:
    ws = _get_worksheet(WS_WEIGHT_LOG)
    _ensure_headers(ws, WEIGHT_LOG_HEADERS)
    records = ws.get_all_records()
    now = _now_kst()
    row = [email, date, weight, now]

    row_idx = None
    for i, r in enumerate(records):
        if r.get("email") == email and r.get("date") == date:
            row_idx = i + 2
            break

    if row_idx:
        ws.update(f"A{row_idx}:D{row_idx}", [row])
    else:
        ws.append_row(row)

    get_weight_log.clear()
    get_latest_weight.clear()
    get_earliest_weight.clear()


# ─── Aggregations ────────────────────────────────────────────

def get_daily_totals(email: str, start_date: str, end_date: str) -> pd.DataFrame:
    df = get_meals(email, start_date, end_date)
    if df.empty:
        return pd.DataFrame(columns=["date", "total_cal", "total_carbs", "total_protein", "total_fat"])
    numeric_cols = ["total_cal", "carbs", "protein", "fat", "quantity"]
    for c in numeric_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    agg = df.groupby("date").agg(
        total_cal=("total_cal", "sum"),
        total_carbs=pd.NamedAgg(column="carbs", aggfunc=lambda x: (x * df.loc[x.index, "quantity"]).sum()),
        total_protein=pd.NamedAgg(column="protein", aggfunc=lambda x: (x * df.loc[x.index, "quantity"]).sum()),
        total_fat=pd.NamedAgg(column="fat", aggfunc=lambda x: (x * df.loc[x.index, "quantity"]).sum()),
    ).reset_index()
    return agg.sort_values("date")


def get_streak(email: str) -> int:
    """오늘 또는 어제부터 거슬러 올라가며 연속으로 기록한 일수."""
    end = datetime.now(KST).date()
    start = end - timedelta(days=60)  # 최대 60일
    df = get_meals(email, start.isoformat(), end.isoformat())
    if df.empty:
        return 0
    recorded_dates = set(df["date"].unique())
    # 오늘부터 거슬러 올라가며 연속 기록 체크
    streak = 0
    current = end
    # 오늘 기록 없으면 어제부터 체크
    if current.isoformat() not in recorded_dates:
        current -= timedelta(days=1)
    while current.isoformat() in recorded_dates:
        streak += 1
        current -= timedelta(days=1)
    return streak


def get_recent_foods(email: str, days: int = 3, limit: int = 10) -> pd.DataFrame:
    """최근 N일 먹은 음식 (중복 제거, 최신순)."""
    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    df = get_meals(email, start, end)
    if df.empty:
        return pd.DataFrame(columns=["food_name", "amount", "calories", "carbs", "protein", "fat"])
    for c in ["calories", "carbs", "protein", "fat"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    df = df.sort_values("created_at", ascending=False)
    unique = df.drop_duplicates(subset=["food_name"]).head(limit)
    return unique[["food_name", "amount", "calories", "carbs", "protein", "fat"]]


def get_yesterday_meals(email: str, date_str: str) -> pd.DataFrame:
    """어제 식단 전체 반환 (복사용)."""
    d = datetime.strptime(date_str, "%Y-%m-%d").date() - timedelta(days=1)
    return get_meals(email, d.isoformat(), d.isoformat())


def get_top_foods(email: str, days: int = 30) -> pd.DataFrame:
    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    df = get_meals(email, start, end)
    if df.empty:
        return pd.DataFrame(columns=["food_name", "count", "avg_cal"])
    counts = df.groupby("food_name").agg(
        count=("food_name", "size"),
        avg_cal=("calories", "mean"),
    ).reset_index().sort_values("count", ascending=False).head(5)
    counts["avg_cal"] = counts["avg_cal"].round(0).astype(int)
    return counts


# ─── Exercise Log ────────────────────────────────────────────

def save_exercise(email: str, date: str, name: str, duration: int, met: float, weight: float) -> None:
    ws = _get_worksheet(WS_EXERCISE_LOG)
    _ensure_headers(ws, EXERCISE_LOG_HEADERS)
    cal_burned = round(met * weight * duration / 60)
    ws.append_row([email, date, name, duration, met, cal_burned, _now_kst()])
    get_exercise_log.clear()


def delete_exercise_row(email: str, date: str, exercise_name: str, created_at: str) -> bool:
    ws = _get_worksheet(WS_EXERCISE_LOG)
    _ensure_headers(ws, EXERCISE_LOG_HEADERS)
    records = ws.get_all_records()
    for i, r in enumerate(records):
        if (r.get("email") == email and r.get("date") == date
                and r.get("exercise_name") == exercise_name
                and str(r.get("created_at", "")) == str(created_at)):
            ws.delete_rows(i + 2)
            get_exercise_log.clear()
            return True
    return False


def update_exercise_row(email: str, date: str, exercise_name: str, created_at: str,
                        new_duration: int, weight: float) -> bool:
    ws = _get_worksheet(WS_EXERCISE_LOG)
    _ensure_headers(ws, EXERCISE_LOG_HEADERS)
    records = ws.get_all_records()
    for i, r in enumerate(records):
        if (r.get("email") == email and r.get("date") == date
                and r.get("exercise_name") == exercise_name
                and str(r.get("created_at", "")) == str(created_at)):
            row_num = i + 2
            met = float(r.get("met", 5))
            new_cal = round(met * weight * new_duration / 60)
            ws.update(f"D{row_num}", [[new_duration]])
            ws.update(f"F{row_num}", [[new_cal]])
            get_exercise_log.clear()
            return True
    return False


@st.cache_data(ttl=300)
def get_exercise_log(_email: str, start_date: str, end_date: str) -> pd.DataFrame:
    ws = _get_worksheet(WS_EXERCISE_LOG)
    _ensure_headers(ws, EXERCISE_LOG_HEADERS)
    records = ws.get_all_records()
    if not records:
        return pd.DataFrame(columns=EXERCISE_LOG_HEADERS)
    df = pd.DataFrame(records)
    mask = (df["email"] == _email) & (df["date"] >= start_date) & (df["date"] <= end_date)
    result = df[mask].reset_index(drop=True)
    for c in ["duration_min", "met", "calories_burned"]:
        if c in result.columns:
            result[c] = pd.to_numeric(result[c], errors="coerce").fillna(0)
    return result


def get_daily_burned(email: str, date: str) -> float:
    df = get_exercise_log(email, date, date)
    return float(df["calories_burned"].sum()) if not df.empty else 0


# ─── Water Log ───────────────────────────────────────────────

def save_water(email: str, date: str, ml: int) -> None:
    ws = _get_worksheet(WS_WATER_LOG)
    _ensure_headers(ws, WATER_LOG_HEADERS)
    ws.append_row([email, date, ml, _now_kst()])
    get_water_log.clear()


@st.cache_data(ttl=300)
def get_water_log(_email: str, date: str) -> int:
    ws = _get_worksheet(WS_WATER_LOG)
    _ensure_headers(ws, WATER_LOG_HEADERS)
    records = ws.get_all_records()
    total = 0
    for r in records:
        if r.get("email") == _email and r.get("date") == date:
            try:
                total += int(r["ml"])
            except (ValueError, KeyError):
                pass
    return total


def reset_water(email: str, date: str) -> None:
    """해당 날짜 물 섭취 기록 전체 삭제."""
    ws = _get_worksheet(WS_WATER_LOG)
    _ensure_headers(ws, WATER_LOG_HEADERS)
    records = ws.get_all_records()
    rows_to_delete = []
    for i, r in enumerate(records):
        if r.get("email") == email and r.get("date") == date:
            rows_to_delete.append(i + 2)
    for row_num in sorted(rows_to_delete, reverse=True):
        ws.delete_rows(row_num)
    get_water_log.clear()


# ─── Favorites ───────────────────────────────────────────────

@st.cache_data(ttl=300)
def get_favorites(_email: str) -> list[dict]:
    ws = _get_worksheet(WS_FAVORITES)
    _ensure_headers(ws, FAVORITES_HEADERS)
    records = ws.get_all_records()
    favs = [r for r in records if r.get("email") == _email]
    favs.sort(key=lambda r: int(r.get("use_count", 0)), reverse=True)
    return favs


def add_favorite(email: str, food: dict) -> None:
    ws = _get_worksheet(WS_FAVORITES)
    _ensure_headers(ws, FAVORITES_HEADERS)
    records = ws.get_all_records()

    # 이미 존재하면 use_count 증가
    for i, r in enumerate(records):
        if r.get("email") == email and r.get("food_name") == food.get("name"):
            row_idx = i + 2
            new_count = int(r.get("use_count", 0)) + 1
            ws.update(f"H{row_idx}", [[new_count]])
            ws.update(f"I{row_idx}", [[_now_kst()]])
            get_favorites.clear()
            return

    ws.append_row([
        email, food.get("name", ""), food.get("amount", ""),
        food.get("calories", 0), food.get("carbs", 0),
        food.get("protein", 0), food.get("fat", 0),
        1, _now_kst(),
    ])
    get_favorites.clear()


def delete_favorite(email: str, food_name: str) -> bool:
    ws = _get_worksheet(WS_FAVORITES)
    _ensure_headers(ws, FAVORITES_HEADERS)
    records = ws.get_all_records()
    for i, r in enumerate(records):
        if r.get("email") == email and r.get("food_name") == food_name:
            ws.delete_rows(i + 2)
            get_favorites.clear()
            return True
    return False


def update_favorite(email: str, food_name: str, data: dict) -> bool:
    ws = _get_worksheet(WS_FAVORITES)
    _ensure_headers(ws, FAVORITES_HEADERS)
    records = ws.get_all_records()
    for i, r in enumerate(records):
        if r.get("email") == email and r.get("food_name") == food_name:
            row_idx = i + 2
            ws.update(f"B{row_idx}:G{row_idx}", [[
                data.get("food_name", food_name),
                data.get("amount", ""),
                data.get("calories", 0),
                data.get("carbs", 0),
                data.get("protein", 0),
                data.get("fat", 0),
            ]])
            get_favorites.clear()
            return True
    return False


def auto_add_favorites_from_meals(email: str) -> None:
    """최근 식사 기록에서 3회 이상 먹은 음식을 자동으로 즐겨찾기에 추가."""
    top = get_top_foods(email, days=60)
    if top.empty:
        return
    existing = {f["food_name"] for f in get_favorites(email)}
    meals_df = get_meals(email,
                         (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d"),
                         datetime.now().strftime("%Y-%m-%d"))
    for _, row in top.iterrows():
        if row["count"] >= 3 and row["food_name"] not in existing:
            food_row = meals_df[meals_df["food_name"] == row["food_name"]].iloc[0]
            add_favorite(email, {
                "name": food_row.get("food_name", ""),
                "amount": food_row.get("amount", ""),
                "calories": int(food_row.get("calories", 0)),
                "carbs": int(food_row.get("carbs", 0)),
                "protein": int(food_row.get("protein", 0)),
                "fat": int(food_row.get("fat", 0)),
            })

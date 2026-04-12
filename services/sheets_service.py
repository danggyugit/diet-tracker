"""Google Sheets CRUD 서비스 (gspread + Service Account)."""

from datetime import datetime, timedelta

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials

from config import (
    SHEETS_NAME, WS_MEALS, WS_PROFILES, WS_MEMOS, WS_WEIGHT_LOG,
    MEALS_HEADERS, PROFILES_HEADERS, MEMOS_HEADERS, WEIGHT_LOG_HEADERS,
)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


@st.cache_resource
def _get_client() -> gspread.Client:
    creds_info = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    return gspread.authorize(creds)


def _get_spreadsheet() -> gspread.Spreadsheet:
    return _get_client().open(SHEETS_NAME)


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

    now = datetime.now().isoformat()
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
        now,
    ]

    if row_idx:
        ws.update(f"A{row_idx}:J{row_idx}", [row])
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
    now = datetime.now().isoformat()

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


def update_meal_row(email: str, date: str, food_name: str, created_at: str,
                    new_calories: int, new_quantity: float) -> bool:
    """저장된 식사 기록의 칼로리·수량 수정."""
    ws = _get_worksheet(WS_MEALS)
    _ensure_headers(ws, MEALS_HEADERS)
    records = ws.get_all_records()
    for i, r in enumerate(records):
        if (r.get("email") == email and r.get("date") == date
                and r.get("food_name") == food_name
                and str(r.get("created_at", "")) == str(created_at)):
            row_num = i + 2
            # calories=F, quantity=J, total_cal=K (1-indexed)
            ws.update(f"F{row_num}", [[new_calories]])
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

def get_memo(email: str, date: str) -> dict | None:
    ws = _get_worksheet(WS_MEMOS)
    _ensure_headers(ws, MEMOS_HEADERS)
    records = ws.get_all_records()
    for r in records:
        if r.get("email") == email and r.get("date") == date:
            return r
    return None


def save_memo(email: str, date: str, condition: str, memo: str) -> None:
    ws = _get_worksheet(WS_MEMOS)
    _ensure_headers(ws, MEMOS_HEADERS)
    records = ws.get_all_records()
    now = datetime.now().isoformat()
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


def save_weight(email: str, date: str, weight: float) -> None:
    ws = _get_worksheet(WS_WEIGHT_LOG)
    _ensure_headers(ws, WEIGHT_LOG_HEADERS)
    records = ws.get_all_records()
    now = datetime.now().isoformat()
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

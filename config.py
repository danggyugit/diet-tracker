"""Diet Tracker 전역 상수 정의."""

import datetime
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")


def today_kst() -> datetime.date:
    return datetime.datetime.now(KST).date()

# AI 모델 (Groq)
VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
TEXT_MODEL = "llama-3.3-70b-versatile"

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png"}
MAX_FILE_SIZE = 10 * 1024 * 1024

MEAL_TYPES = ["아침", "점심", "저녁", "간식"]

CONDITION_OPTIONS = ["😊 좋음", "😐 보통", "😩 피곤", "🤒 아픔", "😤 스트레스"]

ACTIVITY_MULTIPLIERS: dict[str, float] = {
    "비활동": 1.2,
    "가벼운활동": 1.375,
    "보통활동": 1.55,
    "활발한활동": 1.725,
    "매우활발": 1.9,
}

EXERCISE_TABLE = [
    {"name": "걷기 (빠른 걸음)", "met": 4.5, "category": "유산소", "icon": "🚶"},
    {"name": "달리기 (6km/h)",   "met": 9.8, "category": "유산소", "icon": "🏃"},
    {"name": "자전거",            "met": 7.5, "category": "유산소", "icon": "🚴"},
    {"name": "수영",              "met": 8.0, "category": "유산소", "icon": "🏊"},
    {"name": "스쿼트",            "met": 5.0, "category": "근력",   "icon": "🏋️"},
    {"name": "플랭크",            "met": 3.8, "category": "근력",   "icon": "💪"},
    {"name": "팔굽혀펴기",        "met": 8.0, "category": "근력",   "icon": "🤸"},
    {"name": "버피",              "met": 10.0, "category": "유산소+근력", "icon": "⚡"},
]

PLOT_CFG = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(15,23,42,0.5)",
    font=dict(color="#F8FAFC"),
)

SHEETS_NAME = "diet_tracker_db"
WS_MEALS = "meals"
WS_PROFILES = "profiles"
WS_MEMOS = "memos"

MEALS_HEADERS = [
    "email", "date", "meal_type", "food_name", "amount",
    "calories", "carbs", "protein", "fat", "quantity",
    "total_cal", "source", "created_at",
]
PROFILES_HEADERS = [
    "email", "gender", "age", "height", "weight",
    "activity_level", "target_calories",
    "target_weight", "target_date",
    "deficit_level",
    "updated_at",
]
MEMOS_HEADERS = ["email", "date", "condition", "memo", "created_at"]

WS_WEIGHT_LOG = "weight_log"
WEIGHT_LOG_HEADERS = ["email", "date", "weight", "created_at"]

WS_EXERCISE_LOG = "exercise_log"
EXERCISE_LOG_HEADERS = [
    "email", "date", "exercise_name", "duration_min",
    "met", "calories_burned", "created_at",
]

WS_WATER_LOG = "water_log"
WATER_LOG_HEADERS = ["email", "date", "ml", "created_at"]

WS_FAVORITES = "favorites"
FAVORITES_HEADERS = [
    "email", "food_name", "amount", "calories",
    "carbs", "protein", "fat", "use_count", "updated_at",
]

# 운동 선택 목록 (기록용, MET 포함)
EXERCISE_OPTIONS = [
    {"name": "걷기 (빠른 걸음)", "met": 4.5, "icon": "🚶"},
    {"name": "러닝 (조깅)",       "met": 7.0, "icon": "🏃"},
    {"name": "러닝 (빠른 페이스)","met": 9.8, "icon": "🏃‍♂️"},
    {"name": "자전거",            "met": 7.5, "icon": "🚴"},
    {"name": "수영",              "met": 8.0, "icon": "🏊"},
    {"name": "골프 (연습)",       "met": 3.5, "icon": "⛳"},
    {"name": "골프 (라운드)",     "met": 4.8, "icon": "⛳"},
    {"name": "등산",              "met": 6.0, "icon": "🥾"},
    {"name": "요가/스트레칭",     "met": 2.5, "icon": "🧘"},
    {"name": "웨이트 트레이닝",   "met": 5.0, "icon": "🏋️"},
    {"name": "배드민턴",          "met": 5.5, "icon": "🏸"},
    {"name": "테니스",            "met": 7.0, "icon": "🎾"},
    {"name": "축구",              "met": 7.0, "icon": "⚽"},
    {"name": "농구",              "met": 6.5, "icon": "🏀"},
    {"name": "강아지 산책",       "met": 3.0, "icon": "🐕"},
    {"name": "집안일/청소",       "met": 3.5, "icon": "🧹"},
    {"name": "계단 오르기",       "met": 8.0, "icon": "🪜"},
    {"name": "줄넘기",            "met": 10.0,"icon": "🪢"},
    {"name": "필라테스",          "met": 3.0, "icon": "🤸"},
    {"name": "직접 입력",         "met": 0,   "icon": "✏️"},
]

WATER_TARGET_ML = 2000  # 일일 물 섭취 목표 기본값

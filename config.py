"""Diet Tracker 전역 상수 정의."""

GEMINI_MODEL = "gemini-2.5-flash"

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
    "updated_at",
]
MEMOS_HEADERS = ["email", "date", "condition", "memo", "created_at"]

WS_WEIGHT_LOG = "weight_log"
WEIGHT_LOG_HEADERS = ["email", "date", "weight", "created_at"]

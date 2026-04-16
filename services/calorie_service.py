"""BMR / TDEE / 운동 소모 / 영양소 권장량 계산 서비스."""

import math

from config import (
    ACTIVITY_MULTIPLIERS, EXERCISE_TABLE,
    PROTEIN_BY_DEFICIT, FAT_MIN_PER_KG,
)


def calc_bmr(weight: float, height: float, age: int, gender: str) -> float:
    """Mifflin-St Jeor 공식으로 기초대사량(BMR) 계산.

    Args:
        weight: 체중(kg)
        height: 키(cm) — 기존 하드코딩(170/160) 대신 실제 값 사용
        age: 나이
        gender: "남성" 또는 "여성"
    """
    if gender == "남성":
        return (10 * weight) + (6.25 * height) - (5 * age) + 5
    return (10 * weight) + (6.25 * height) - (5 * age) - 161


def calc_tdee(bmr: float, activity_level: str) -> float:
    """일일 총 에너지 소비량(TDEE) = BMR × 활동계수."""
    multiplier = ACTIVITY_MULTIPLIERS.get(activity_level, 1.55)
    return bmr * multiplier


def calc_protein_g(weight: float, deficit_level: int) -> tuple[int, float]:
    """단백질 권장량 — 감량 강도 기반 (활동수준과 무관, 정석).

    Returns: (g, g/kg)
    """
    mult = PROTEIN_BY_DEFICIT.get(deficit_level, 1.4)
    return round(weight * mult), mult


def calc_fat_g(daily_target: int, weight: float) -> tuple[int, str]:
    """지방 권장량 — max(총 칼로리×30%, 체중×0.8g/kg).

    체중 기반 최소치는 호르몬·지용성 비타민 흡수 보장용.
    Returns: (g, source_label)
    """
    by_cal = daily_target * 0.30 / 9
    by_weight = weight * FAT_MIN_PER_KG
    if by_weight > by_cal:
        return round(by_weight), "체중 0.8g/kg"
    return round(by_cal), "총 칼로리 30%"


def calc_carbs_g(daily_target: int, protein_g: int, fat_g: int) -> int:
    """탄수화물 = 나머지 칼로리 ÷ 4 (최소 50g 보장)."""
    return max(round((daily_target - protein_g * 4 - fat_g * 9) / 4), 50)


def calc_daily_deficit(
    current_weight: float,
    target_weight: float,
    target_date: str,
    today: str | None = None,
) -> dict:
    """목표 체중 달성을 위한 일일 칼로리 적자 계산.

    Returns: {
        "deficit_per_day": 일일 필요 적자 kcal (양수=감량, 음수=증량),
        "total_kg": 총 감량 kg,
        "remaining_days": 남은 일수,
        "weekly_kg": 주당 감량 속도,
        "is_safe": 주당 1kg 이하인지,
    }
    """
    from datetime import date

    from config import today_kst
    today_dt = date.fromisoformat(today) if today else today_kst()
    try:
        target_dt = date.fromisoformat(target_date)
    except (ValueError, TypeError):
        return {"deficit_per_day": 0, "total_kg": 0, "remaining_days": 0,
                "weekly_kg": 0, "is_safe": True}

    remaining_days = (target_dt - today_dt).days
    if remaining_days <= 0:
        return {"deficit_per_day": 0, "total_kg": 0, "remaining_days": 0,
                "weekly_kg": 0, "is_safe": True}

    total_kg = current_weight - target_weight
    # 체지방 1kg ≈ 7,700 kcal
    total_deficit = total_kg * 7700
    deficit_per_day = round(total_deficit / remaining_days)
    weekly_kg = round(total_kg / (remaining_days / 7), 2)

    return {
        "deficit_per_day": deficit_per_day,
        "total_kg": round(total_kg, 1),
        "remaining_days": remaining_days,
        "weekly_kg": weekly_kg,
        "is_safe": abs(weekly_kg) <= 1.0,
    }


def _round_up_5(minutes: float) -> int:
    """5분 단위로 올림."""
    return math.ceil(minutes / 5) * 5


def calc_exercise_plan(total_calories: float, weight: float) -> list[dict]:
    """총 칼로리를 소모하기 위한 운동별 필요 시간 계산.

    MET × 체중(kg) / 60 = kcal/min → 5분 단위 올림.
    """
    plan = []
    for ex in EXERCISE_TABLE:
        kcal_per_min = ex["met"] * weight / 60
        required_min = total_calories / kcal_per_min if kcal_per_min > 0 else 0
        plan.append({
            "name": ex["name"],
            "category": ex["category"],
            "icon": ex["icon"],
            "rec_time": _round_up_5(required_min),
            "kcal_per_min": round(kcal_per_min, 1),
        })
    return plan

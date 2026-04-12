"""Gemini Vision 음식 분석 서비스.

- analyze_food_image: 사진 → 음식 인식 + 칼로리 추정
- estimate_food_nutrition: 음식명 텍스트 → 영양정보 추정 (수동 추가 자동완성용)
"""

import re
import json
import time

import streamlit as st
from google import genai
from google.genai import types

from config import GEMINI_MODEL

MAX_RETRIES = 2
RETRY_WAIT = 40  # 초

IMAGE_PROMPT = """다음 음식 사진을 분석하여 JSON만 반환하세요. 다른 텍스트는 절대 포함하지 마세요.
혼합 음식(예: 김밥, 비빔밥)은 하나의 항목으로 처리하세요.
음식의 양은 한국 일반 1인분 기준(Standard serving size)으로 추정하세요.

반환 형식:
{
  "foods": [
    {"name": "음식명", "amount": "추정량(예: 1인분, 200g)", "calories": 숫자, "carbs": 숫자, "protein": 숫자, "fat": 숫자, "quantity": 1.0}
  ],
  "total_calories": 숫자
}

carbs(탄수화물), protein(단백질), fat(지방)은 그램(g) 단위 정수로 추정하세요.

음식을 인식할 수 없으면:
{"foods": [], "total_calories": 0, "error": "음식을 인식할 수 없습니다"}"""

MANUAL_PROMPT = """다음 음식의 영양 정보를 추정하여 JSON만 반환하세요. 다른 텍스트는 절대 포함하지 마세요.
한국 일반 1인분 기준(Standard serving size)으로 추정하세요.

음식명: {food_name}

반환 형식:
{{"name": "음식명", "amount": "추정량(예: 1인분, 200g)", "calories": 숫자, "carbs": 숫자, "protein": 숫자, "fat": 숫자, "quantity": 1.0}}

carbs(탄수화물), protein(단백질), fat(지방)은 그램(g) 단위 정수로 추정하세요."""

MULTI_PROMPT = """다음 음식들의 영양 정보를 추정하여 JSON 배열만 반환하세요. 다른 텍스트는 절대 포함하지 마세요.
각 음식은 입력된 양을 기준으로 추정하세요. 양이 명시되지 않으면 한국 일반 1인분 기준으로 추정하세요.
"반인분"은 quantity를 0.5로, "2인분"은 quantity를 2.0으로 설정하세요.

음식 목록:
{food_list}

반환 형식:
[
  {{"name": "음식명", "amount": "추정량", "calories": 숫자, "carbs": 숫자, "protein": 숫자, "fat": 숫자, "quantity": 숫자}}
]

calories는 1인분 기준 칼로리입니다. quantity로 실제 먹은 양을 표현합니다.
carbs(탄수화물), protein(단백질), fat(지방)은 그램(g) 단위 정수로 추정하세요."""


def _get_client() -> genai.Client:
    api_key = st.secrets.get("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY가 secrets.toml에 설정되지 않았습니다")
    return genai.Client(api_key=api_key)


def _call_with_retry(func):
    """429 에러 시 자동 재시도."""
    for attempt in range(MAX_RETRIES + 1):
        try:
            return func()
        except Exception as e:
            if "429" in str(e) and attempt < MAX_RETRIES:
                time.sleep(RETRY_WAIT)
                continue
            raise


def _parse_json(raw_text: str) -> dict:
    match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if not match:
        raise ValueError("응답에서 JSON을 찾을 수 없습니다")
    return json.loads(match.group())


def _parse_json_array(raw_text: str) -> list[dict]:
    match = re.search(r"\[.*\]", raw_text, re.DOTALL)
    if not match:
        raise ValueError("응답에서 JSON 배열을 찾을 수 없습니다")
    return json.loads(match.group())


def analyze_food_image(image_bytes: bytes, media_type: str = "image/jpeg") -> dict:
    """Gemini Vision API로 음식 사진 분석."""
    client = _get_client()
    def _call():
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=media_type),
                IMAGE_PROMPT,
            ],
        )
        return _parse_json(response.text)
    return _call_with_retry(_call)


def estimate_food_nutrition(food_name: str) -> dict:
    """음식명 1개 → 영양정보 추정."""
    client = _get_client()
    def _call():
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[MANUAL_PROMPT.format(food_name=food_name)],
        )
        return _parse_json(response.text)
    return _call_with_retry(_call)


RECOMMEND_PROMPT = """당신은 다이어트 식단 전문가입니다. 아래 조건에 맞는 식단을 추천해 주세요.

## 사용자 정보
- 성별: {gender}, 나이: {age}세, 키: {height}cm, 체중: {weight}kg
- 활동 수준: {activity}
- 일일 칼로리 목표: {daily_budget}kcal
- 목표 영양소: 탄수화물 {target_carbs}g, 단백질 {target_protein}g, 지방 {target_fat}g

## 오늘 이미 먹은 음식
{eaten_summary}

## 남은 칼로리/영양소
- 남은 칼로리: {remaining_cal}kcal
- 남은 탄수화물: {remaining_carbs}g, 단백질: {remaining_protein}g, 지방: {remaining_fat}g

## 추천 요청
{request}

## 응답 형식 (JSON만 반환, 다른 텍스트 없이)
{{
  "recommendation": "한 줄 요약 (예: 단백질 보충이 필요한 저녁)",
  "meals": [
    {{
      "meal_type": "아침/점심/저녁",
      "menu_name": "메뉴 이름 (예: 닭가슴살 샐러드 정식)",
      "foods": [
        {{"name": "음식명", "amount": "양", "calories": 숫자, "carbs": 숫자, "protein": 숫자, "fat": 숫자, "quantity": 1.0}}
      ],
      "total_cal": 숫자,
      "reason": "추천 이유 (짧게)"
    }}
  ]
}}

한국인이 실제로 쉽게 먹을 수 있는 현실적인 메뉴를 추천하세요.
칼로리와 영양소 균형을 맞추고, 남은 영양소를 고려하세요."""


def recommend_meals(profile: dict, daily_budget: int,
                    target_carbs: int, target_protein: int, target_fat: int,
                    eaten_foods: list[dict],
                    eaten_cal: float, eaten_carbs: float,
                    eaten_protein: float, eaten_fat: float) -> dict:
    """프로필 + 오늘 섭취 현황 기반 식단 추천."""

    if eaten_foods:
        eaten_summary = "\n".join(
            f"- {f.get('food_name', f.get('name', ''))} {f.get('amount', '')} "
            f"({f.get('calories', 0)}kcal, 탄{f.get('carbs', 0)}g 단{f.get('protein', 0)}g 지{f.get('fat', 0)}g)"
            for f in eaten_foods
        )
    else:
        eaten_summary = "아직 아무것도 먹지 않았습니다."

    remaining_cal = max(daily_budget - eaten_cal, 0)
    remaining_carbs = max(target_carbs - eaten_carbs, 0)
    remaining_protein = max(target_protein - eaten_protein, 0)
    remaining_fat = max(target_fat - eaten_fat, 0)

    # 상황별 요청
    if eaten_cal == 0:
        request = "오늘 하루 전체 식단(아침, 점심, 저녁)을 추천해 주세요."
    elif remaining_cal > daily_budget * 0.5:
        request = "점심과 저녁 식단을 추천해 주세요. 아침에 먹은 것을 고려해서 균형을 맞춰주세요."
    else:
        request = "저녁 식단 1끼를 추천해 주세요. 오늘 먹은 것을 고려해서 남은 칼로리와 영양소에 맞춰주세요."

    prompt = RECOMMEND_PROMPT.format(
        gender=profile.get("gender", "남성"),
        age=profile.get("age", 30),
        height=profile.get("height", 170),
        weight=profile.get("weight", 70),
        activity=profile.get("activity_level", "보통활동"),
        daily_budget=daily_budget,
        target_carbs=target_carbs,
        target_protein=target_protein,
        target_fat=target_fat,
        eaten_summary=eaten_summary,
        remaining_cal=round(remaining_cal),
        remaining_carbs=round(remaining_carbs),
        remaining_protein=round(remaining_protein),
        remaining_fat=round(remaining_fat),
        request=request,
    )

    client = _get_client()
    def _call():
        response = client.models.generate_content(model=GEMINI_MODEL, contents=[prompt])
        return _parse_json(response.text)
    return _call_with_retry(_call)


def estimate_multiple_foods(food_lines: list[str]) -> list[dict]:
    """여러 음식을 한 번에 추정 (Gemini 1회 호출).

    Args:
        food_lines: ["연어스테이크 1인분", "함박스테이크 반인분", "와인 1병", ...]

    Returns: [{"name": ..., "calories": ..., "quantity": ...}, ...]
    """
    numbered = "\n".join(f"{i+1}. {line}" for i, line in enumerate(food_lines))
    client = _get_client()
    def _call():
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[MULTI_PROMPT.format(food_list=numbered)],
        )
        return _parse_json_array(response.text)
    return _call_with_retry(_call)

"""AI 음식 분석 서비스 (Google Gemini).

- analyze_food_image: 사진 → 음식 인식 + 칼로리 추정
- estimate_food_nutrition: 음식명 텍스트 → 영양정보 추정
- estimate_multiple_foods: 여러 음식 한번에 추정
"""

import re
import json

import streamlit as st
from google import genai
from google.genai import types

GEMINI_MODEL = "gemini-2.5-flash"

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


def _call_api(func):
    """API 호출 래퍼. 429 에러 시 친절한 메시지."""
    try:
        return func()
    except Exception as e:
        if "429" in str(e) or "rate_limit" in str(e).lower():
            raise RuntimeError("AI 요청 한도 초과. 잠시 후(1~2분) 다시 시도해 주세요.") from e
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
    return _call_api(_call)


def estimate_food_nutrition(food_name: str) -> dict:
    """음식명 1개 → 영양정보 추정."""
    client = _get_client()

    prompt = f"""다음 음식의 영양 정보를 추정하여 JSON만 반환하세요. 다른 텍스트는 절대 포함하지 마세요.
한국 일반 1인분 기준(Standard serving size)으로 추정하세요.

음식명: {food_name}

반환 형식:
{{"name": "음식명", "amount": "추정량(예: 1인분, 200g)", "calories": 숫자, "carbs": 숫자, "protein": 숫자, "fat": 숫자, "quantity": 1.0}}

carbs(탄수화물), protein(단백질), fat(지방)은 그램(g) 단위 정수로 추정하세요."""

    def _call():
        response = client.models.generate_content(
            model=GEMINI_MODEL, contents=[prompt],
        )
        return _parse_json(response.text)
    return _call_api(_call)


def estimate_multiple_foods(food_lines: list[str]) -> list[dict]:
    """여러 음식을 한 번에 추정 (1회 호출)."""
    numbered = "\n".join(f"{i+1}. {line}" for i, line in enumerate(food_lines))
    client = _get_client()

    def _call():
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[MULTI_PROMPT.format(food_list=numbered)],
        )
        return _parse_json_array(response.text)
    return _call_api(_call)

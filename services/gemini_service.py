"""AI 음식 분석 서비스 (Google Gemini).

- analyze_food_image: 사진 → 음식 인식 + 칼로리 추정
- estimate_food_nutrition: 음식명 텍스트 → 영양정보 추정
- estimate_multiple_foods: 여러 음식 한번에 추정
"""

import re
import json
import time

import streamlit as st
from google import genai
from google.genai import types

GEMINI_MODEL = "gemini-2.5-flash"


# ─── 분류된 분석 에러 (사용자 친화 메시지) ────────────────────
class FoodAnalysisError(Exception):
    """음식 분석 실패 기본 클래스 — UI에서 카테고리별 안내 표시용."""
    category = "unknown"
    icon = "⚠️"
    title = "분석 중 오류"
    suggestion = "잠시 후 다시 시도해 주세요."


class RecognitionError(FoodAnalysisError):
    """AI가 사진에서 음식을 인식하지 못함 — 사진 품질·구도 문제."""
    category = "recognition"
    icon = "🍽️"
    title = "음식을 인식할 수 없습니다"
    suggestion = (
        "조명이 밝은 곳에서 음식이 잘 보이도록 다시 촬영해 보세요.\n"
        "여러 음식이 겹쳐 있다면 개별 촬영이 더 정확합니다.\n"
        "또는 '✏️ 수동' 입력으로 음식 이름을 직접 적어 주세요."
    )


class RateLimitError(FoodAnalysisError):
    """API 분당/일별 호출 한도 초과 (429)."""
    category = "rate_limit"
    icon = "🚦"
    title = "AI 요청 한도 초과"
    suggestion = (
        "1~2분 후 다시 시도해 주세요.\n"
        "동일한 음식이라면 '✏️ 수동' 입력 시 즐겨찾기·최근 기록에서 자동으로 가져와 한도를 절약합니다."
    )


class ServerOverloadError(FoodAnalysisError):
    """Gemini 서버 일시 과부하 (503)."""
    category = "server"
    icon = "🛠️"
    title = "AI 서버 일시 장애"
    suggestion = "Google Gemini 서버가 잠시 응답이 없습니다. 1~2분 후 다시 시도해 주세요."


class InvalidResponseError(FoodAnalysisError):
    """AI 응답을 파싱할 수 없음 — 형식이 깨졌거나 비어있음."""
    category = "parse"
    icon = "📭"
    title = "AI 응답을 처리할 수 없습니다"
    suggestion = "다시 시도해 주세요. 반복되면 '✏️ 수동' 입력을 사용해 주세요."


class ConfigError(FoodAnalysisError):
    """API 키 등 설정 문제."""
    category = "config"
    icon = "🔧"
    title = "서비스 설정 오류"
    suggestion = "관리자에게 문의해 주세요. (GEMINI_API_KEY 확인 필요)"

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
        raise ConfigError()
    return genai.Client(api_key=api_key)


def _call_api(func):
    """API 호출 래퍼 — 503 자동 재시도, 그 외 에러는 분류된 예외로 변환."""
    for attempt in range(3):
        try:
            return func()
        except FoodAnalysisError:
            raise
        except Exception as e:
            err_str = str(e)
            err_lower = err_str.lower()
            if "503" in err_str or "unavailable" in err_lower or "overloaded" in err_lower:
                if attempt < 2:
                    time.sleep(3 * (attempt + 1))
                    continue
                raise ServerOverloadError() from e
            if "429" in err_str or "rate_limit" in err_lower or "quota" in err_lower:
                raise RateLimitError() from e
            if "401" in err_str or "403" in err_str or "api_key" in err_lower or "permission" in err_lower:
                raise ConfigError() from e
            # 기타 예기치 않은 에러 — 원본 메시지 보존
            raise FoodAnalysisError(err_str) from e


def _parse_json(raw_text: str) -> dict:
    match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if not match:
        raise InvalidResponseError("응답에서 JSON을 찾을 수 없습니다")
    try:
        return json.loads(match.group())
    except json.JSONDecodeError as e:
        raise InvalidResponseError(f"JSON 파싱 실패: {e}") from e


def _parse_json_array(raw_text: str) -> list[dict]:
    match = re.search(r"\[.*\]", raw_text, re.DOTALL)
    if not match:
        raise InvalidResponseError("응답에서 JSON 배열을 찾을 수 없습니다")
    try:
        return json.loads(match.group())
    except json.JSONDecodeError as e:
        raise InvalidResponseError(f"JSON 파싱 실패: {e}") from e


def analyze_food_image(image_bytes: bytes, media_type: str = "image/jpeg") -> dict:
    """Gemini Vision API로 음식 사진 분석.

    Raises:
        RecognitionError: AI가 음식을 못 찾음
        RateLimitError: 호출 한도 초과
        ServerOverloadError: 서버 과부하 (재시도 후에도 실패)
        InvalidResponseError: AI 응답 파싱 실패
        ConfigError: API 키 등 설정 문제
        FoodAnalysisError: 기타 분류 안 된 에러
    """
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

    result = _call_api(_call)
    # AI가 음식 인식 실패 응답을 보낸 경우
    if not result or not result.get("foods"):
        raise RecognitionError()
    return result


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

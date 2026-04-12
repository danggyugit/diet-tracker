"""바코드 스캔 + Open Food Facts API 영양정보 조회."""

import io
import json
import urllib.request

try:
    from pyzbar.pyzbar import decode as pyzbar_decode
    from PIL import Image
    PYZBAR_AVAILABLE = True
except ImportError:
    PYZBAR_AVAILABLE = False


def decode_barcode_from_image(image_bytes: bytes) -> str | None:
    """이미지에서 바코드 번호 추출. pyzbar 미설치 시 None 반환."""
    if not PYZBAR_AVAILABLE:
        return None
    img = Image.open(io.BytesIO(image_bytes))
    results = pyzbar_decode(img)
    if results:
        return results[0].data.decode("utf-8")
    return None


def lookup_barcode(barcode: str) -> dict | None:
    """Open Food Facts API로 바코드 기반 영양정보 조회.

    Returns: {"name": str, "amount": str, "calories": int, "carbs": int,
              "protein": int, "fat": int, "quantity": 1.0} or None
    """
    url = f"https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "DietTracker/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
    except Exception:
        return None

    if data.get("status") != 1:
        return None

    product = data.get("product", {})
    nutrients = product.get("nutriments", {})
    name = product.get("product_name", "") or product.get("product_name_ko", "")
    serving = product.get("serving_size", product.get("quantity", ""))

    if not name:
        return None

    return {
        "name": name,
        "amount": serving or "1개",
        "calories": round(nutrients.get("energy-kcal_100g", 0)),
        "carbs": round(nutrients.get("carbohydrates_100g", 0)),
        "protein": round(nutrients.get("proteins_100g", 0)),
        "fat": round(nutrients.get("fat_100g", 0)),
        "quantity": 1.0,
        "barcode": barcode,
        "note": "100g 기준 (포장 뒷면의 실제 섭취량으로 조정하세요)",
    }

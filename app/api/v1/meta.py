"""Meta. 단위 환산 명세 — 클라이언트 게이지 표시용.

- GET /api/v1/meta/units : API 응답 단위 ↔ 현장 표시 단위 환산 계수.

배경: API 는 SI 단위(kN, kA, cycle)로 응답하지만 현장 게이지는 kgf, A, ms
로 표시한다. 프론트가 환산식을 하드코딩하지 않도록 서버가 곱셈/덧셈 계수를
한 곳에서 노출한다.
"""

from fastapi import APIRouter

from app.core.response import ApiResponse, success_response

router = APIRouter(prefix="/meta", tags=["meta"])


# 환산식: display_value = api_value * multiplier
# (1 kN ≈ 101.9716 kgf, 1 kA = 1000 A, 1 cycle ≈ 16.6667 ms @ 60 Hz)
_UNITS: dict[str, dict] = {
    "force_kN": {
        "api_unit": "kN",
        "display_unit": "kgf",
        "to_display_multiplier": 101.9716,
        "decimals": 0,
        "label": "가압력",
    },
    "current_kA": {
        "api_unit": "kA",
        "display_unit": "A",
        "to_display_multiplier": 1000,
        "decimals": 0,
        "label": "용접 전류",
    },
    "weld_time_cycle": {
        "api_unit": "cycle",
        "display_unit": "ms",
        "to_display_multiplier": 16.6667,
        "decimals": 1,
        "label": "통전 시간",
    },
}


@router.get(
    "/units",
    response_model=ApiResponse[dict],
    summary="API 단위 ↔ 게이지 표시 단위 환산 명세",
)
async def get_units_endpoint():
    return success_response(data=_UNITS)

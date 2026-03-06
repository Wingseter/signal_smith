"""공통 검증 유틸리티"""

from fastapi import HTTPException


def validate_symbol(symbol: str) -> str:
    """6자리 한국 종목코드 검증. 유효하지 않으면 HTTPException 400."""
    if not symbol or len(symbol) != 6 or not symbol.isdigit():
        raise HTTPException(
            status_code=400,
            detail=f"유효하지 않은 종목코드: {symbol}. 6자리 숫자여야 합니다."
        )
    return symbol

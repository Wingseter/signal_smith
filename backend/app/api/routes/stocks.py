"""
Stock API Routes

주식 시세 및 정보 조회 API.
키움증권 REST API를 통해 실시간 데이터를 제공합니다.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth import get_current_user
from app.core.database import get_db
from app.models import Stock, StockPrice, StockAnalysis, User
from app.services.stock_service import stock_service

router = APIRouter()


# ========== Response Models ==========

class StockResponse(BaseModel):
    id: Optional[int] = None
    symbol: str
    name: str
    market: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    market_cap: Optional[int] = None

    class Config:
        from_attributes = True


class RealtimePriceResponse(BaseModel):
    symbol: str
    name: Optional[str] = None
    current_price: int
    change: int
    change_rate: float
    open_price: Optional[int] = None
    high_price: Optional[int] = None
    low_price: Optional[int] = None
    volume: int
    trade_amount: Optional[int] = None
    timestamp: str


class StockPriceResponse(BaseModel):
    symbol: Optional[str] = None
    date: Optional[str] = None
    open: int
    high: int
    low: int
    close: int
    volume: int
    change: Optional[int] = None
    change_rate: Optional[float] = None


class StockAnalysisResponse(BaseModel):
    id: int
    symbol: str
    analysis_type: str
    agent_name: str
    summary: str
    score: Optional[float] = None
    recommendation: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True


class WatchlistResponse(BaseModel):
    symbols: List[str]


# ========== 시세 조회 API ==========

@router.get("/price/{symbol}", response_model=RealtimePriceResponse)
async def get_realtime_price(
    symbol: str,
    current_user: User = Depends(get_current_user),
):
    """
    종목 현재가 조회 (실시간)

    키움증권 API를 통해 실시간 시세를 조회합니다.
    """
    price = await stock_service.get_current_price(symbol)
    if not price:
        raise HTTPException(status_code=404, detail="시세 정보를 찾을 수 없습니다.")
    return price


@router.post("/prices", response_model=List[RealtimePriceResponse])
async def get_multiple_prices(
    symbols: List[str],
    current_user: User = Depends(get_current_user),
):
    """
    복수 종목 현재가 조회

    최대 20개 종목까지 한번에 조회할 수 있습니다.
    """
    if len(symbols) > 20:
        raise HTTPException(status_code=400, detail="최대 20개 종목까지 조회 가능합니다.")

    prices = await stock_service.get_multiple_prices(symbols)
    return prices


@router.get("/{symbol}/history", response_model=List[StockPriceResponse])
async def get_price_history(
    symbol: str,
    period: str = Query("daily", description="daily 또는 minute"),
    count: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
):
    """
    가격 히스토리 조회

    - daily: 일봉 데이터
    - minute: 분봉 데이터
    """
    prices = await stock_service.get_price_history(symbol, period, count)
    if not prices:
        raise HTTPException(status_code=404, detail="가격 데이터를 찾을 수 없습니다.")
    return prices


# ========== 종목 정보 API ==========

@router.get("/", response_model=List[StockResponse])
async def list_stocks(
    market: Optional[str] = Query(None, description="Filter by market (KOSPI/KOSDAQ)"),
    sector: Optional[str] = Query(None, description="Filter by sector"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """저장된 종목 목록 조회"""
    query = select(Stock).where(Stock.is_active == True)

    if market:
        query = query.where(Stock.market == market)
    if sector:
        query = query.where(Stock.sector == sector)

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{symbol}", response_model=StockResponse)
async def get_stock(
    symbol: str,
    current_user: User = Depends(get_current_user),
):
    """종목 기본 정보 조회"""
    info = await stock_service.get_stock_info(symbol)
    if not info:
        raise HTTPException(status_code=404, detail="종목 정보를 찾을 수 없습니다.")
    return info


@router.get("/{symbol}/prices", response_model=List[StockPriceResponse])
async def get_stock_prices(
    symbol: str,
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """DB에 저장된 가격 히스토리 조회"""
    query = select(StockPrice).where(StockPrice.symbol == symbol)

    if start_date:
        query = query.where(StockPrice.date >= start_date)
    if end_date:
        query = query.where(StockPrice.date <= end_date)

    query = query.order_by(StockPrice.date.desc()).limit(limit)
    result = await db.execute(query)
    prices = result.scalars().all()

    return [
        {
            "date": p.date.isoformat() if p.date else None,
            "open": int(p.open),
            "high": int(p.high),
            "low": int(p.low),
            "close": int(p.close),
            "volume": p.volume,
        }
        for p in prices
    ]


# ========== AI 분석 API ==========

@router.get("/{symbol}/analysis", response_model=List[StockAnalysisResponse])
async def get_stock_analysis(
    symbol: str,
    analysis_type: Optional[str] = Query(None, description="Filter by type (quant/fundamental/news/technical)"),
    limit: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
):
    """AI 분석 결과 조회"""
    analyses = await stock_service.get_latest_analysis(symbol, analysis_type)
    if not analyses:
        return []
    return analyses[:limit]


# ========== 관심 종목 API ==========

@router.get("/watchlist/me", response_model=WatchlistResponse)
async def get_my_watchlist(
    current_user: User = Depends(get_current_user),
):
    """내 관심 종목 조회"""
    symbols = await stock_service.get_watchlist(current_user.id)
    return {"symbols": symbols}


@router.post("/watchlist/{symbol}")
async def add_to_watchlist(
    symbol: str,
    current_user: User = Depends(get_current_user),
):
    """관심 종목 추가"""
    await stock_service.add_to_watchlist(current_user.id, symbol)
    return {"message": f"{symbol} 관심 종목에 추가되었습니다."}


@router.delete("/watchlist/{symbol}")
async def remove_from_watchlist(
    symbol: str,
    current_user: User = Depends(get_current_user),
):
    """관심 종목 제거"""
    await stock_service.remove_from_watchlist(current_user.id, symbol)
    return {"message": f"{symbol} 관심 종목에서 제거되었습니다."}


# ========== 데이터 수집 API ==========

@router.post("/{symbol}/collect")
async def collect_price_data(
    symbol: str,
    current_user: User = Depends(get_current_user),
):
    """
    종목 가격 데이터 수집

    키움 API에서 일봉 데이터를 가져와 DB에 저장합니다.
    """
    # 가격 데이터 조회
    prices = await stock_service.get_price_history(symbol, "daily", 200)
    if not prices:
        raise HTTPException(status_code=404, detail="가격 데이터를 가져올 수 없습니다.")

    # DB에 저장
    saved_count = await stock_service.save_price_data(symbol, prices)

    return {
        "symbol": symbol,
        "fetched": len(prices),
        "saved": saved_count,
        "message": f"{saved_count}개의 새로운 가격 데이터가 저장되었습니다.",
    }

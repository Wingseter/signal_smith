from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth import get_current_user
from app.core.database import get_db
from app.models import Stock, StockPrice, StockAnalysis, User

router = APIRouter()


class StockResponse(BaseModel):
    id: int
    symbol: str
    name: str
    market: str
    sector: Optional[str]
    industry: Optional[str]
    market_cap: Optional[int]

    class Config:
        from_attributes = True


class StockPriceResponse(BaseModel):
    symbol: str
    date: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    change_percent: Optional[Decimal]

    class Config:
        from_attributes = True


class StockAnalysisResponse(BaseModel):
    id: int
    symbol: str
    analysis_type: str
    agent_name: str
    summary: str
    score: Optional[Decimal]
    recommendation: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("/", response_model=list[StockResponse])
async def list_stocks(
    market: Optional[str] = Query(None, description="Filter by market (KOSPI/KOSDAQ)"),
    sector: Optional[str] = Query(None, description="Filter by sector"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all stocks with optional filters."""
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
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get stock details by symbol."""
    result = await db.execute(select(Stock).where(Stock.symbol == symbol))
    stock = result.scalar_one_or_none()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    return stock


@router.get("/{symbol}/prices", response_model=list[StockPriceResponse])
async def get_stock_prices(
    symbol: str,
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get stock price history."""
    query = select(StockPrice).where(StockPrice.symbol == symbol)

    if start_date:
        query = query.where(StockPrice.date >= start_date)
    if end_date:
        query = query.where(StockPrice.date <= end_date)

    query = query.order_by(StockPrice.date.desc()).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{symbol}/analysis", response_model=list[StockAnalysisResponse])
async def get_stock_analysis(
    symbol: str,
    analysis_type: Optional[str] = Query(None, description="Filter by type (quant/fundamental/news/technical)"),
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get AI analysis for a stock."""
    query = select(StockAnalysis).where(StockAnalysis.symbol == symbol)

    if analysis_type:
        query = query.where(StockAnalysis.analysis_type == analysis_type)

    query = query.order_by(StockAnalysis.created_at.desc()).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

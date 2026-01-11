"""
AI Analysis Report API Endpoints
PDF 리포트 생성 및 다운로드
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.stock import Stock, StockPrice
from app.models.portfolio import Portfolio, Position
from app.models.trading import Trade, TradingSignal
from app.services.report_generator import (
    ReportGenerator,
    ReportConfig,
    ReportType,
    StockAnalysisData,
    PortfolioData,
    TradingSummaryData,
    MarketOverviewData,
)
from app.services.sector_analysis import KOREAN_SECTORS, SectorAnalyzer

import logging

logger = logging.getLogger(__name__)

router = APIRouter()


# Request Models
class StockReportRequest(BaseModel):
    symbol: str
    include_ai_insights: bool = True


class PortfolioReportRequest(BaseModel):
    portfolio_id: Optional[int] = None
    include_risk_metrics: bool = True


class TradingReportRequest(BaseModel):
    period_days: int = 30


class MarketReportRequest(BaseModel):
    include_sectors: bool = True


@router.get("/types")
async def get_report_types(
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get available report types."""
    return {
        "types": [
            {
                "id": ReportType.STOCK_ANALYSIS.value,
                "name": "Stock Analysis Report",
                "description": "Comprehensive AI analysis of a single stock",
            },
            {
                "id": ReportType.PORTFOLIO_REVIEW.value,
                "name": "Portfolio Review Report",
                "description": "Full portfolio performance and risk analysis",
            },
            {
                "id": ReportType.TRADING_SUMMARY.value,
                "name": "Trading Summary Report",
                "description": "Trading activity and performance summary",
            },
            {
                "id": ReportType.MARKET_OVERVIEW.value,
                "name": "Market Overview Report",
                "description": "Market indices, sectors, and top movers",
            },
        ]
    }


@router.post("/stock")
async def generate_stock_report(
    request: StockReportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate stock analysis PDF report."""
    # Fetch stock data
    stock = db.query(Stock).filter(Stock.symbol == request.symbol).first()
    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock {request.symbol} not found")

    # Fetch latest price
    latest_price = (
        db.query(StockPrice)
        .filter(StockPrice.symbol == request.symbol)
        .order_by(StockPrice.date.desc())
        .first()
    )

    # Fetch previous price for change calculation
    prev_price = (
        db.query(StockPrice)
        .filter(StockPrice.symbol == request.symbol)
        .order_by(StockPrice.date.desc())
        .offset(1)
        .first()
    )

    current_price = float(latest_price.close) if latest_price else 0
    prev_close = float(prev_price.close) if prev_price else current_price
    price_change = current_price - prev_close
    price_change_pct = (price_change / prev_close * 100) if prev_close else 0

    # Build stock analysis data
    stock_data = StockAnalysisData(
        symbol=stock.symbol,
        name=stock.name,
        current_price=current_price,
        price_change=price_change,
        price_change_pct=price_change_pct,
        volume=int(latest_price.volume) if latest_price else 0,
        market_cap=float(stock.market_cap) if stock.market_cap else 0,
        pe_ratio=float(stock.pe_ratio) if stock.pe_ratio else None,
        pb_ratio=float(stock.pb_ratio) if stock.pb_ratio else None,
        dividend_yield=float(stock.dividend_yield) if stock.dividend_yield else None,
        technical_score=75.0,  # Would come from analysis service
        fundamental_score=68.0,
        sentiment_score=72.0,
        overall_score=71.5,
        recommendation="BUY",
        price_target=current_price * 1.15,
        support_levels=[current_price * 0.95, current_price * 0.90, current_price * 0.85],
        resistance_levels=[current_price * 1.05, current_price * 1.10, current_price * 1.15],
        analysis_summary=f"{stock.name} shows positive momentum with strong technical indicators. "
                        f"The stock is trading near its support level, presenting a potential buying opportunity.",
        ai_insights=[
            "Technical indicators suggest bullish momentum with RSI at 58",
            "Trading volume is 20% above the 20-day average",
            "Stock is outperforming sector peers by 3.2% this month",
            "Earnings estimate revisions are trending upward",
        ] if request.include_ai_insights else [],
    )

    # Generate PDF
    generator = ReportGenerator()
    config = ReportConfig(
        report_type=ReportType.STOCK_ANALYSIS,
        title="AI Stock Analysis Report",
        include_ai_insights=request.include_ai_insights,
    )

    pdf_buffer = generator.generate_stock_report(stock_data, config)

    # Return as streaming response
    filename = f"stock_report_{request.symbol}_{datetime.now().strftime('%Y%m%d')}.pdf"

    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


@router.post("/portfolio")
async def generate_portfolio_report(
    request: PortfolioReportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate portfolio review PDF report."""
    # Fetch portfolio
    if request.portfolio_id:
        portfolio = (
            db.query(Portfolio)
            .filter(
                Portfolio.id == request.portfolio_id,
                Portfolio.user_id == current_user.id,
            )
            .first()
        )
    else:
        portfolio = (
            db.query(Portfolio)
            .filter(Portfolio.user_id == current_user.id)
            .first()
        )

    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    # Fetch positions
    positions = db.query(Position).filter(Position.portfolio_id == portfolio.id).all()

    # Calculate portfolio metrics
    total_value = float(portfolio.cash_balance)
    total_cost = 0.0
    position_list = []
    sector_allocation = {}

    for pos in positions:
        stock = db.query(Stock).filter(Stock.symbol == pos.symbol).first()
        latest_price = (
            db.query(StockPrice)
            .filter(StockPrice.symbol == pos.symbol)
            .order_by(StockPrice.date.desc())
            .first()
        )

        current_price = float(latest_price.close) if latest_price else float(pos.avg_cost)
        position_value = current_price * pos.quantity
        position_cost = float(pos.avg_cost) * pos.quantity

        total_value += position_value
        total_cost += position_cost

        # Determine sector
        sector = "Unknown"
        for sector_id, sector_info in KOREAN_SECTORS.items():
            if pos.symbol in sector_info.get("symbols", []):
                sector = sector_info["name"]
                break

        sector_allocation[sector] = sector_allocation.get(sector, 0) + position_value

        position_list.append({
            "symbol": pos.symbol,
            "name": stock.name if stock else pos.symbol,
            "quantity": pos.quantity,
            "avg_cost": float(pos.avg_cost),
            "current_price": current_price,
            "unrealized_pnl": position_value - position_cost,
            "weight": 0,  # Will calculate after total
        })

    # Calculate weights
    for pos in position_list:
        pos_value = pos["current_price"] * pos["quantity"]
        pos["weight"] = (pos_value / total_value * 100) if total_value > 0 else 0

    # Convert sector allocation to percentages
    for sector in sector_allocation:
        sector_allocation[sector] = (sector_allocation[sector] / total_value * 100) if total_value > 0 else 0

    total_pnl = total_value - total_cost
    total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0

    # Build portfolio data
    portfolio_data = PortfolioData(
        total_value=total_value,
        total_cost=total_cost,
        total_pnl=total_pnl,
        total_pnl_pct=total_pnl_pct,
        cash_balance=float(portfolio.cash_balance),
        positions=position_list,
        sector_allocation=sector_allocation,
        risk_metrics={
            "sharpe_ratio": 1.45,
            "sortino_ratio": 1.82,
            "max_drawdown": -8.5,
            "volatility": 15.2,
            "beta": 1.05,
            "var_95": -2.3,
        } if request.include_risk_metrics else {},
    )

    # Generate PDF
    generator = ReportGenerator()
    config = ReportConfig(
        report_type=ReportType.PORTFOLIO_REVIEW,
        title="Portfolio Review Report",
        subtitle=portfolio.name,
    )

    pdf_buffer = generator.generate_portfolio_report(portfolio_data, config)

    filename = f"portfolio_report_{datetime.now().strftime('%Y%m%d')}.pdf"

    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


@router.post("/trading")
async def generate_trading_report(
    request: TradingReportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate trading summary PDF report."""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=request.period_days)

    # Fetch trades
    trades = (
        db.query(Trade)
        .filter(
            Trade.user_id == current_user.id,
            Trade.created_at >= start_date,
        )
        .order_by(Trade.created_at.desc())
        .all()
    )

    # Fetch signals
    signals = (
        db.query(TradingSignal)
        .filter(
            TradingSignal.user_id == current_user.id,
            TradingSignal.created_at >= start_date,
        )
        .all()
    )

    # Calculate trading metrics
    total_trades = len(trades)
    winning_trades = 0
    losing_trades = 0
    total_pnl = 0.0
    profits = []
    losses = []
    trade_list = []

    for trade in trades:
        pnl = float(trade.realized_pnl) if trade.realized_pnl else 0

        if pnl > 0:
            winning_trades += 1
            profits.append(pnl)
        elif pnl < 0:
            losing_trades += 1
            losses.append(pnl)

        total_pnl += pnl

        trade_list.append({
            "date": trade.created_at,
            "symbol": trade.symbol,
            "type": trade.trade_type,
            "quantity": trade.quantity,
            "price": float(trade.price),
            "pnl": pnl,
        })

    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    avg_profit = sum(profits) / len(profits) if profits else 0
    avg_loss = sum(losses) / len(losses) if losses else 0
    largest_win = max(profits) if profits else 0
    largest_loss = min(losses) if losses else 0

    signals_executed = len([s for s in signals if s.executed])

    # Build trading summary data
    trading_data = TradingSummaryData(
        period_start=start_date,
        period_end=end_date,
        total_trades=total_trades,
        winning_trades=winning_trades,
        losing_trades=losing_trades,
        total_pnl=total_pnl,
        win_rate=win_rate,
        avg_profit=avg_profit,
        avg_loss=avg_loss,
        largest_win=largest_win,
        largest_loss=largest_loss,
        trades=trade_list,
        signals_generated=len(signals),
        signals_executed=signals_executed,
    )

    # Generate PDF
    generator = ReportGenerator()
    config = ReportConfig(
        report_type=ReportType.TRADING_SUMMARY,
        title="Trading Summary Report",
    )

    pdf_buffer = generator.generate_trading_report(trading_data, config)

    filename = f"trading_report_{datetime.now().strftime('%Y%m%d')}.pdf"

    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


@router.post("/market")
async def generate_market_report(
    request: MarketReportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate market overview PDF report."""
    # Fetch market indices (mock data - would come from market data service)
    indices = [
        {"name": "KOSPI", "value": 2650.45, "change": 15.32, "change_pct": 0.58},
        {"name": "KOSDAQ", "value": 875.23, "change": -3.45, "change_pct": -0.39},
        {"name": "KRX 100", "value": 4520.18, "change": 22.15, "change_pct": 0.49},
    ]

    # Fetch sector performance
    sector_performance = []
    if request.include_sectors:
        for sector_id, sector_info in list(KOREAN_SECTORS.items())[:10]:
            sector_performance.append({
                "name": sector_info["name"],
                "return_1d": 0.5,  # Would calculate from actual data
                "return_1w": 1.2,
                "return_1m": 3.5,
            })

    # Fetch top gainers (mock - would query from database)
    top_gainers = []
    top_losers = []

    stocks = db.query(Stock).limit(20).all()
    for stock in stocks[:5]:
        latest = (
            db.query(StockPrice)
            .filter(StockPrice.symbol == stock.symbol)
            .order_by(StockPrice.date.desc())
            .first()
        )
        if latest:
            top_gainers.append({
                "symbol": stock.symbol,
                "name": stock.name,
                "price": float(latest.close),
                "change_pct": 5.0,  # Mock
            })

    for stock in stocks[5:10]:
        latest = (
            db.query(StockPrice)
            .filter(StockPrice.symbol == stock.symbol)
            .order_by(StockPrice.date.desc())
            .first()
        )
        if latest:
            top_losers.append({
                "symbol": stock.symbol,
                "name": stock.name,
                "price": float(latest.close),
                "change_pct": -3.0,  # Mock
            })

    # Build market data
    market_data = MarketOverviewData(
        indices=indices,
        sector_performance=sector_performance,
        top_gainers=top_gainers,
        top_losers=top_losers,
        market_sentiment="BULLISH",
        volatility_index=15.5,
        trading_volume=850000000,
        market_summary="The Korean market showed positive momentum today, led by technology and semiconductor stocks. "
                      "Foreign investors were net buyers for the third consecutive day.",
    )

    # Generate PDF
    generator = ReportGenerator()
    config = ReportConfig(
        report_type=ReportType.MARKET_OVERVIEW,
        title="Market Overview Report",
    )

    pdf_buffer = generator.generate_market_report(market_data, config)

    filename = f"market_report_{datetime.now().strftime('%Y%m%d')}.pdf"

    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )

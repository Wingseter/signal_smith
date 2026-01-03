from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.routes.auth import get_current_user
from app.core.database import get_db
from app.models import Portfolio, PortfolioHolding, User

router = APIRouter()


class PortfolioCreate(BaseModel):
    name: str
    description: Optional[str] = None
    is_default: bool = False


class PortfolioResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    is_default: bool

    class Config:
        from_attributes = True


class HoldingCreate(BaseModel):
    symbol: str
    quantity: int
    avg_buy_price: Decimal


class HoldingResponse(BaseModel):
    id: int
    symbol: str
    quantity: int
    avg_buy_price: Decimal
    current_price: Optional[Decimal]
    profit_loss: Optional[Decimal]
    profit_loss_percent: Optional[Decimal]

    class Config:
        from_attributes = True


class PortfolioDetailResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    is_default: bool
    holdings: list[HoldingResponse]
    total_value: Decimal
    total_profit_loss: Decimal

    class Config:
        from_attributes = True


@router.get("/", response_model=list[PortfolioResponse])
async def list_portfolios(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all portfolios for current user."""
    result = await db.execute(
        select(Portfolio).where(Portfolio.user_id == current_user.id)
    )
    return result.scalars().all()


@router.post("/", response_model=PortfolioResponse, status_code=status.HTTP_201_CREATED)
async def create_portfolio(
    portfolio_data: PortfolioCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new portfolio."""
    portfolio = Portfolio(
        user_id=current_user.id,
        name=portfolio_data.name,
        description=portfolio_data.description,
        is_default=portfolio_data.is_default,
    )
    db.add(portfolio)
    await db.commit()
    await db.refresh(portfolio)
    return portfolio


@router.get("/{portfolio_id}", response_model=PortfolioDetailResponse)
async def get_portfolio(
    portfolio_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get portfolio details with holdings."""
    result = await db.execute(
        select(Portfolio)
        .options(selectinload(Portfolio.holdings))
        .where(Portfolio.id == portfolio_id, Portfolio.user_id == current_user.id)
    )
    portfolio = result.scalar_one_or_none()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    total_value = Decimal("0")
    total_profit_loss = Decimal("0")

    for holding in portfolio.holdings:
        if holding.current_price:
            total_value += holding.current_price * holding.quantity
            if holding.profit_loss:
                total_profit_loss += holding.profit_loss

    return PortfolioDetailResponse(
        id=portfolio.id,
        name=portfolio.name,
        description=portfolio.description,
        is_default=portfolio.is_default,
        holdings=portfolio.holdings,
        total_value=total_value,
        total_profit_loss=total_profit_loss,
    )


@router.post("/{portfolio_id}/holdings", response_model=HoldingResponse)
async def add_holding(
    portfolio_id: int,
    holding_data: HoldingCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a holding to portfolio."""
    result = await db.execute(
        select(Portfolio).where(
            Portfolio.id == portfolio_id, Portfolio.user_id == current_user.id
        )
    )
    portfolio = result.scalar_one_or_none()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    holding = PortfolioHolding(
        portfolio_id=portfolio_id,
        symbol=holding_data.symbol,
        quantity=holding_data.quantity,
        avg_buy_price=holding_data.avg_buy_price,
    )
    db.add(holding)
    await db.commit()
    await db.refresh(holding)
    return holding


@router.delete("/{portfolio_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_portfolio(
    portfolio_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a portfolio."""
    result = await db.execute(
        select(Portfolio).where(
            Portfolio.id == portfolio_id, Portfolio.user_id == current_user.id
        )
    )
    portfolio = result.scalar_one_or_none()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    await db.delete(portfolio)
    await db.commit()

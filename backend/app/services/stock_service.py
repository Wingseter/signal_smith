"""
Stock Service

주식 데이터 조회 및 관리를 위한 통합 서비스.
키움증권 API를 사용하여 시세, 종목 정보 등을 제공합니다.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_maker
from app.core.redis import get_redis
from app.models import Stock, StockPrice, StockAnalysis
from app.services.kiwoom.rest_client import kiwoom_client
from app.services.kiwoom.base import StockPrice as KiwoomStockPrice


class StockService:
    """주식 데이터 서비스"""

    def __init__(self):
        self.kiwoom = kiwoom_client

    # ========== 시세 조회 ==========

    async def get_current_price(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        현재가 조회

        1. Redis 캐시 확인
        2. 없으면 키움 API 호출
        3. 결과 캐시 및 반환
        """
        # Redis 캐시 확인
        redis = await get_redis()
        cache_key = f"price:{symbol}"
        cached = await redis.get(cache_key)

        if cached:
            import json
            return json.loads(cached)

        # API 호출
        price = await self.kiwoom.get_stock_price(symbol)
        if not price:
            return None

        result = {
            "symbol": price.symbol,
            "name": price.name,
            "current_price": price.current_price,
            "change": price.change,
            "change_rate": price.change_rate,
            "open_price": price.open_price,
            "high_price": price.high_price,
            "low_price": price.low_price,
            "volume": price.volume,
            "trade_amount": price.trade_amount,
            "timestamp": price.timestamp.isoformat(),
        }

        # 캐시 저장 (30초)
        import json
        await redis.set(cache_key, json.dumps(result), ex=30)

        return result

    async def get_multiple_prices(self, symbols: List[str]) -> List[Dict[str, Any]]:
        """복수 종목 현재가 조회"""
        prices = await self.kiwoom.get_stock_prices(symbols)
        return [
            {
                "symbol": p.symbol,
                "name": p.name,
                "current_price": p.current_price,
                "change": p.change,
                "change_rate": p.change_rate,
                "volume": p.volume,
                "timestamp": p.timestamp.isoformat(),
            }
            for p in prices
        ]

    async def get_price_history(
        self,
        symbol: str,
        period: str = "daily",
        count: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        가격 히스토리 조회

        Args:
            symbol: 종목 코드
            period: 'daily' 또는 'minute'
            count: 조회 개수
        """
        if period == "daily":
            prices = await self.kiwoom.get_daily_prices(symbol)
        else:
            prices = await self.kiwoom.get_minute_prices(symbol)

        return prices[:count]

    # ========== 종목 정보 ==========

    async def get_stock_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """종목 기본 정보 조회"""
        # DB에서 먼저 조회
        async with async_session_maker() as session:
            result = await session.execute(
                select(Stock).where(Stock.symbol == symbol)
            )
            stock = result.scalar_one_or_none()

            if stock:
                return {
                    "symbol": stock.symbol,
                    "name": stock.name,
                    "market": stock.market,
                    "sector": stock.sector,
                    "industry": stock.industry,
                    "market_cap": stock.market_cap,
                }

        # DB에 없으면 API 조회
        info = await self.kiwoom.get_stock_info(symbol)
        if info:
            # DB에 저장
            await self.save_stock_info(info)
        return info

    async def save_stock_info(self, info: Dict[str, Any]) -> None:
        """종목 정보 DB 저장"""
        async with async_session_maker() as session:
            # 기존 데이터 확인
            result = await session.execute(
                select(Stock).where(Stock.symbol == info["symbol"])
            )
            stock = result.scalar_one_or_none()

            if stock:
                # 업데이트
                stock.name = info.get("name", stock.name)
                stock.market = info.get("market", stock.market)
                stock.sector = info.get("sector", stock.sector)
            else:
                # 새로 생성
                stock = Stock(
                    symbol=info["symbol"],
                    name=info.get("name", ""),
                    market=info.get("market", ""),
                    sector=info.get("sector"),
                    industry=info.get("industry"),
                    market_cap=info.get("market_cap"),
                )
                session.add(stock)

            await session.commit()

    # ========== 가격 데이터 저장 ==========

    async def save_price_data(
        self,
        symbol: str,
        prices: List[Dict[str, Any]],
    ) -> int:
        """
        가격 데이터 DB 저장

        Returns:
            저장된 레코드 수
        """
        async with async_session_maker() as session:
            saved_count = 0

            for price_data in prices:
                # 날짜 파싱
                date_str = price_data.get("date")
                if not date_str:
                    continue

                try:
                    if len(date_str) == 8:  # YYYYMMDD
                        date = datetime.strptime(date_str, "%Y%m%d")
                    else:
                        date = datetime.fromisoformat(date_str)
                except ValueError:
                    continue

                # 중복 확인
                result = await session.execute(
                    select(StockPrice).where(
                        StockPrice.symbol == symbol,
                        StockPrice.date == date,
                    )
                )
                existing = result.scalar_one_or_none()

                if existing:
                    continue

                # 새 레코드 생성
                stock_price = StockPrice(
                    symbol=symbol,
                    date=date,
                    open=Decimal(str(price_data.get("open", 0))),
                    high=Decimal(str(price_data.get("high", 0))),
                    low=Decimal(str(price_data.get("low", 0))),
                    close=Decimal(str(price_data.get("close", 0))),
                    volume=price_data.get("volume", 0),
                    change_percent=Decimal(str(price_data.get("change_rate", 0))),
                )
                session.add(stock_price)
                saved_count += 1

            await session.commit()
            return saved_count

    # ========== 분석 데이터 ==========

    async def get_latest_analysis(
        self,
        symbol: str,
        analysis_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """최신 분석 결과 조회"""
        async with async_session_maker() as session:
            query = select(StockAnalysis).where(StockAnalysis.symbol == symbol)

            if analysis_type:
                query = query.where(StockAnalysis.analysis_type == analysis_type)

            query = query.order_by(StockAnalysis.created_at.desc()).limit(10)

            result = await session.execute(query)
            analyses = result.scalars().all()

            return [
                {
                    "id": a.id,
                    "symbol": a.symbol,
                    "analysis_type": a.analysis_type,
                    "agent_name": a.agent_name,
                    "summary": a.summary,
                    "score": float(a.score) if a.score else None,
                    "recommendation": a.recommendation,
                    "created_at": a.created_at.isoformat(),
                }
                for a in analyses
            ]

    async def save_analysis(
        self,
        symbol: str,
        analysis_type: str,
        agent_name: str,
        summary: str,
        score: Optional[float] = None,
        recommendation: Optional[str] = None,
        details: Optional[str] = None,
    ) -> int:
        """분석 결과 저장"""
        async with async_session_maker() as session:
            analysis = StockAnalysis(
                symbol=symbol,
                analysis_type=analysis_type,
                agent_name=agent_name,
                summary=summary,
                score=Decimal(str(score)) if score is not None else None,
                recommendation=recommendation,
                details=details,
            )
            session.add(analysis)
            await session.commit()
            await session.refresh(analysis)
            return analysis.id

    # ========== 관심 종목 ==========

    async def get_watchlist(self, user_id: int) -> List[str]:
        """사용자 관심 종목 조회"""
        redis = await get_redis()
        watchlist = await redis.smembers(f"watchlist:{user_id}")
        return list(watchlist) if watchlist else []

    async def add_to_watchlist(self, user_id: int, symbol: str) -> bool:
        """관심 종목 추가"""
        redis = await get_redis()
        await redis.sadd(f"watchlist:{user_id}", symbol)
        return True

    async def remove_from_watchlist(self, user_id: int, symbol: str) -> bool:
        """관심 종목 제거"""
        redis = await get_redis()
        await redis.srem(f"watchlist:{user_id}", symbol)
        return True


# 싱글톤 인스턴스
stock_service = StockService()

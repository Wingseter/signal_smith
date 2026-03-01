"""Signal scanning and universe refresh tasks.

Extracted from signal_tasks.py — scanning-related Celery tasks.
"""

import json
import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select

from app.core.celery_app import celery_app
from app.core.database import get_sync_db
from app.models.stock import Stock

from ._common import is_market_hours, run_async

logger = logging.getLogger(__name__)

# ── Fallback blue-chip symbols ──
FALLBACK_SYMBOLS = [
    "005930", "000660", "035420", "035720", "051910",
    "006400", "005380", "068270", "028260", "207940",
]


@celery_app.task(
    name="app.services.tasks.scan_signals",
    bind=True,
    max_retries=2,
    default_retry_delay=120,
    time_limit=600,
    soft_time_limit=540,
)
def scan_signals(self):
    """Quant signal scan (top 500 stocks by market cap)."""
    if not is_market_hours():
        logger.info("Market is closed. Skipping signal scan.")
        return {"status": "skipped", "reason": "market_closed"}

    try:
        symbols = _load_scan_universe(limit=500)
        logger.info(f"Signal scan starting: {len(symbols)} symbols")

        from app.services.signals import signal_scanner

        results = run_async(signal_scanner.scan_watchlist(symbols, max_concurrent=5))

        sell_triggered = run_async(_check_sell_signals_against_holdings(results))
        buy_triggered = run_async(_check_buy_signals_for_council(results))

        return {
            "status": "success",
            "scanned": len(symbols),
            "results": len(results),
            "sell_triggered": sell_triggered,
            "buy_triggered": buy_triggered,
            "top_signals": [
                {
                    "symbol": r.symbol,
                    "score": r.composite_score,
                    "action": r.action.value,
                }
                for r in results[:10]
            ],
        }

    except Exception as e:
        logger.error(f"Signal scan failed: {e}")
        self.retry(exc=e)


@celery_app.task(
    name="app.services.tasks.refresh_stock_universe",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    time_limit=300,
    soft_time_limit=240,
)
def refresh_stock_universe(self):
    """Refresh stock universe from Kiwoom API."""
    try:
        result = run_async(_refresh_universe_async())
        return result
    except Exception as e:
        logger.error(f"Stock universe refresh failed: {e}")
        self.retry(exc=e)


@celery_app.task(
    name="app.services.tasks.refresh_account_summary",
    bind=True,
    max_retries=2,
    default_retry_delay=15,
    time_limit=60,
    soft_time_limit=45,
)
def refresh_account_summary(self):
    """백그라운드에서 키움 계좌 요약(잔고+보유종목)을 갱신하여 Redis에 캐싱."""
    try:
        result = run_async(_refresh_account_summary_async())
        return result
    except Exception as e:
        logger.error(f"Account summary refresh failed: {e}")
        self.retry(exc=e)


# ── Helper functions ──


async def _refresh_account_summary_async() -> dict:
    """키움 API로 balance + holdings 조회 → Redis 캐시 갱신."""
    from app.core.redis import get_redis
    from app.services.trading_service import trading_service

    try:
        balance = await trading_service.get_account_balance()
        holdings = await trading_service.get_holdings()
    except Exception as e:
        logger.warning(f"키움 API 호출 실패 (account summary refresh): {e}")
        return {"status": "error", "reason": str(e)}

    updated_at = datetime.now().isoformat()
    result = {
        "balance": balance,
        "holdings": holdings,
        "count": len(holdings),
        "updated_at": updated_at,
    }

    try:
        redis = await get_redis()
        await redis.set("account:summary", json.dumps(result), ex=90)
        logger.debug(f"Account summary cached: {len(holdings)} holdings, updated_at={updated_at}")
    except Exception as e:
        logger.warning(f"Redis 캐시 저장 실패 (account summary): {e}")

    return {"status": "success", "holdings_count": len(holdings), "updated_at": updated_at}


def _load_scan_universe(limit: int = 500) -> List[str]:
    """Load scan target symbols (Redis cache → DB fallback → hardcoded)."""
    try:
        cached = run_async(_get_cached_universe())
        if cached:
            symbols = json.loads(cached)
            logger.info(f"Loaded {len(symbols)} symbols from Redis cache")
            return symbols[:limit]
    except Exception as e:
        logger.warning(f"Redis cache miss for stock universe: {e}")

    try:
        with get_sync_db() as db:
            from sqlalchemy import desc

            stocks = (
                db.execute(
                    select(Stock.symbol, Stock.market, Stock.market_cap)
                    .where(Stock.is_active == True)
                    .order_by(
                        desc(Stock.market_cap.isnot(None)),
                        Stock.market,
                        desc(Stock.market_cap),
                    )
                    .limit(limit)
                )
                .all()
            )

            if stocks:
                symbols = [s.symbol for s in stocks]
                logger.info(f"Loaded {len(symbols)} symbols from DB")
                return symbols
    except Exception as e:
        logger.warning(f"DB stock universe load failed: {e}")

    logger.warning("Using fallback symbol list")
    return FALLBACK_SYMBOLS


async def _get_cached_universe() -> Optional[str]:
    from app.core.redis import get_redis

    redis = await get_redis()
    return await redis.get("stock_universe:top500")


async def _refresh_universe_async() -> dict:
    from app.services.kiwoom.rest_client import kiwoom_client
    from app.core.redis import get_redis

    if not await kiwoom_client.is_connected():
        await kiwoom_client.connect()

    kospi_stocks = await kiwoom_client.get_market_stocks("KOSPI")
    kosdaq_stocks = await kiwoom_client.get_market_stocks("KOSDAQ")
    all_stocks = kospi_stocks + kosdaq_stocks

    logger.info(f"Fetched stocks: KOSPI={len(kospi_stocks)}, KOSDAQ={len(kosdaq_stocks)}")

    if not all_stocks:
        return {"status": "error", "reason": "no_stocks_fetched"}

    upserted = 0
    with get_sync_db() as db:
        for stock_data in all_stocks:
            symbol = stock_data.get("symbol", "")
            if not symbol:
                continue

            existing = db.execute(select(Stock).where(Stock.symbol == symbol)).scalar_one_or_none()

            if existing:
                existing.name = stock_data.get("name", existing.name)
                existing.market = stock_data.get("market", existing.market)
                existing.is_active = True
            else:
                new_stock = Stock(
                    symbol=symbol,
                    name=stock_data.get("name", ""),
                    market=stock_data.get("market", ""),
                    is_active=True,
                )
                db.add(new_stock)
            upserted += 1

        db.commit()

        from sqlalchemy import desc

        top_stocks = (
            db.execute(
                select(Stock.symbol)
                .where(Stock.is_active == True)
                .order_by(
                    desc(Stock.market_cap.isnot(None)),
                    Stock.market,
                    desc(Stock.market_cap),
                )
                .limit(500)
            )
            .scalars()
            .all()
        )

    top_symbols = list(top_stocks)

    try:
        redis = await get_redis()
        await redis.set("stock_universe:top500", json.dumps(top_symbols), ex=86400)
        logger.info(f"Cached {len(top_symbols)} symbols to Redis")
    except Exception as e:
        logger.warning(f"Redis cache failed: {e}")

    return {
        "status": "success",
        "total_fetched": len(all_stocks),
        "upserted": upserted,
        "universe_size": len(top_symbols),
    }


async def _check_sell_signals_against_holdings(results) -> int:
    from app.services.kiwoom.rest_client import kiwoom_client
    from app.services.council.orchestrator import council_orchestrator
    from .monitoring_tasks import (
        _get_cached_holdings, _check_sell_cooldown, _set_sell_cooldown,
        SELL_COOLDOWN_SECONDS,
    )

    try:
        holdings = await _get_cached_holdings()
        if not holdings:
            return 0

        held_map = {h.symbol: h for h in holdings}

        from app.services.signals.models import SignalAction

        sell_results = [
            r
            for r in results
            if r.action in (SignalAction.SELL, SignalAction.STRONG_SELL)
        ]

        triggered = 0
        for result in sell_results:
            if result.symbol not in held_map:
                continue

            if await _check_sell_cooldown(result.symbol):
                continue

            holding = held_map[result.symbol]

            await _set_sell_cooldown(result.symbol, ttl=SELL_COOLDOWN_SECONDS)

            sell_reason = (
                f"퀀트 스캔 {result.action.value} (점수: {result.composite_score}/100, "
                f"매도 트리거 {result.bearish_count}개)"
            )

            await council_orchestrator.start_sell_meeting(
                symbol=holding.symbol,
                company_name=holding.name,
                sell_reason=sell_reason,
                current_holdings=holding.quantity,
                avg_buy_price=holding.avg_price,
                current_price=holding.current_price,
            )

            triggered += 1
            logger.info(
                f"Quant scan sell trigger: {holding.symbol} ({holding.name}) "
                f"- {result.action.value}, score={result.composite_score}"
            )

        return triggered

    except Exception as e:
        logger.error(f"Sell signals cross-check failed: {e}")
        return 0


async def _check_buy_signals_for_council(results) -> int:
    """Check quant BUY signals and trigger council meetings for top candidates."""
    from app.services.council.orchestrator import council_orchestrator
    from app.services.signals.models import SignalAction
    from app.core.redis import get_redis
    from .monitoring_tasks import _get_cached_holdings

    try:
        buy_results = [
            r for r in results
            if r.action in (SignalAction.STRONG_BUY, SignalAction.BUY)
            and r.composite_score >= 65
        ][:3]

        if not buy_results:
            return 0

        holdings = await _get_cached_holdings()
        held_symbols = {h.symbol for h in holdings} if holdings else set()
        redis = await get_redis()
        triggered = 0

        for result in buy_results:
            if result.symbol in held_symbols:
                continue

            cooldown_key = f"quant_buy_council:cooldown:{result.symbol}"
            if await redis.exists(cooldown_key):
                continue

            company_name = result.symbol
            try:
                with get_sync_db() as db:
                    stock = db.execute(
                        select(Stock).where(Stock.symbol == result.symbol)
                    ).scalar_one_or_none()
                    if stock:
                        company_name = stock.name
            except Exception:
                pass

            await redis.setex(cooldown_key, 3600, "1")

            available_amount = 5000000
            try:
                from app.services.kiwoom.rest_client import kiwoom_client
                if not await kiwoom_client.is_connected():
                    await kiwoom_client.connect()
                balance = await kiwoom_client.get_balance()
                if balance.available_amount > 0:
                    available_amount = min(balance.available_amount, 5000000)
            except Exception as e:
                logger.warning(f"잔고 조회 실패, 기본값 사용: {e}")

            quant_triggers = {
                "composite_score": result.composite_score,
                "bullish_count": result.bullish_count,
                "bearish_count": result.bearish_count,
                "triggers": [
                    {
                        "id": t.trigger_id,
                        "name": t.name,
                        "signal": t.signal.value if hasattr(t.signal, "value") else str(t.signal),
                        "score": t.score,
                        "details": t.details,
                    }
                    for t in result.triggers
                    if t.signal.value != "neutral"
                ],
            }

            await council_orchestrator.start_meeting(
                symbol=result.symbol,
                company_name=company_name,
                news_title=(
                    f"퀀트 매수 신호: {result.action.value} "
                    f"(점수: {result.composite_score}/100, 매수 {result.bullish_count}개)"
                ),
                news_score=8 if result.action == SignalAction.STRONG_BUY else 7,
                available_amount=available_amount,
                current_price=result.indicators.current_price if result.indicators else 0,
                trigger_source="quant",
                quant_triggers=quant_triggers,
            )
            triggered += 1
            logger.info(f"Quant BUY → council: {result.symbol}, score={result.composite_score}")

        return triggered
    except Exception as e:
        logger.error(f"Buy signals council check failed: {e}")
        return 0

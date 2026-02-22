"""Signal monitoring and scanning tasks."""

import json
import logging
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import select

from app.core.celery_app import celery_app
from app.core.database import get_sync_db
from app.config import settings
from app.models.stock import Stock
from app.models.transaction import TradingSignal

from ._common import is_market_hours, run_async

logger = logging.getLogger(__name__)

# ── Sell-monitoring cooldown (seconds) ──
SELL_COOLDOWN_SECONDS = 1800

# ── Fallback blue-chip symbols ──
FALLBACK_SYMBOLS = [
    "005930", "000660", "035420", "035720", "051910",
    "006400", "005380", "068270", "028260", "207940",
]


@celery_app.task(
    name="app.services.tasks.monitor_signals",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def monitor_signals(self):
    """Monitor pending signals and check for execution conditions."""
    if not is_market_hours():
        return {"status": "skipped", "reason": "market_closed"}

    try:
        with get_sync_db() as db:
            pending_signals = (
                db.execute(
                    select(TradingSignal).where(TradingSignal.is_executed == False)
                )
                .scalars()
                .all()
            )

            if not pending_signals:
                return {"status": "success", "message": "no_pending_signals"}

            from app.services.kiwoom.rest_client import KiwoomRestClient
            from .notification_tasks import send_notification

            client = KiwoomRestClient()
            actions = []

            for signal in pending_signals:
                try:
                    current_price = run_async(client.get_current_price(signal.symbol))

                    if not current_price:
                        continue

                    price = current_price.get("close", 0)

                    if signal.stop_loss and price <= signal.stop_loss:
                        actions.append({
                            "signal_id": signal.id,
                            "action": "stop_loss_triggered",
                            "symbol": signal.symbol,
                            "price": price,
                        })
                        signal.is_executed = True
                        send_notification.delay(
                            "stop_loss", f"[손절] {signal.symbol}: {price:,}원 도달"
                        )

                    elif signal.target_price and price >= signal.target_price:
                        actions.append({
                            "signal_id": signal.id,
                            "action": "target_reached",
                            "symbol": signal.symbol,
                            "price": price,
                        })
                        send_notification.delay(
                            "target_reached", f"[목표가] {signal.symbol}: {price:,}원 도달"
                        )

                    elif signal.created_at < datetime.utcnow() - timedelta(hours=24):
                        signal.is_executed = True
                        actions.append({
                            "signal_id": signal.id,
                            "action": "expired",
                            "symbol": signal.symbol,
                        })

                except Exception as e:
                    logger.error(f"Error monitoring signal {signal.id}: {e}")

            db.commit()

            return {
                "status": "success",
                "monitored": len(pending_signals),
                "actions": actions,
            }

    except Exception as e:
        logger.error(f"Signal monitoring failed: {e}")
        self.retry(exc=e)


@celery_app.task(name="app.services.tasks.auto_execute_signal")
def auto_execute_signal(signal_id: int, quantity: int):
    """Auto-execute a trading signal if conditions are met."""
    if not settings.trading_enabled:
        return {"status": "error", "reason": "trading_disabled"}

    try:
        with get_sync_db() as db:
            signal = db.execute(
                select(TradingSignal).where(TradingSignal.id == signal_id)
            ).scalar_one_or_none()

            if not signal or signal.is_executed:
                return {"status": "error", "reason": "invalid_signal"}

            from app.services.trading_service import trading_service
            from .notification_tasks import send_notification

            side = "buy" if signal.signal_type == "buy" else "sell"
            price = int(signal.target_price) if signal.target_price else 0
            order_result = run_async(
                trading_service.place_order(
                    user_id=1,
                    symbol=signal.symbol,
                    side=side,
                    quantity=quantity,
                    price=price,
                    order_type="limit" if price > 0 else "market",
                )
            )

            if order_result.get("success"):
                signal.is_executed = True
                db.commit()

                send_notification.delay(
                    "order_executed",
                    f"[주문실행] {signal.signal_type.upper()} {signal.symbol} x {quantity}",
                )

            return {
                "status": "success" if order_result.get("success") else "failed",
                "signal_id": signal_id,
                "order_result": order_result,
            }

    except Exception as e:
        logger.error(f"Auto execution failed for signal {signal_id}: {e}")
        return {"status": "error", "error": str(e)}


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

        return {
            "status": "success",
            "scanned": len(symbols),
            "results": len(results),
            "sell_triggered": sell_triggered,
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
    name="app.services.tasks.monitor_holdings_sell",
    bind=True,
    time_limit=300,
    soft_time_limit=270,
)
def monitor_holdings_sell(self):
    """Monitor holdings for sell triggers (price-based)."""
    if not is_market_hours():
        logger.info("Market is closed. Skipping holdings sell monitor.")
        return {"status": "skipped", "reason": "market_closed"}

    try:
        holdings = run_async(_get_cached_holdings())

        if not holdings:
            logger.info("No holdings to monitor for sell.")
            return {"status": "skipped", "reason": "no_holdings"}

        logger.info(f"Monitoring {len(holdings)} holdings for sell triggers")

        triggered = []
        for holding in holdings:
            if run_async(_check_sell_cooldown(holding.symbol)):
                continue

            result = run_async(_evaluate_price_triggers(holding))
            if result:
                trigger_type, sell_reason = result
                run_async(_set_sell_cooldown(holding.symbol, ttl=SELL_COOLDOWN_SECONDS))

                from app.services.council.orchestrator import council_orchestrator

                meeting = run_async(
                    council_orchestrator.start_sell_meeting(
                        symbol=holding.symbol,
                        company_name=holding.name,
                        sell_reason=sell_reason,
                        current_holdings=holding.quantity,
                        avg_buy_price=holding.avg_price,
                        current_price=holding.current_price,
                    )
                )

                triggered.append({
                    "symbol": holding.symbol,
                    "name": holding.name,
                    "trigger_type": trigger_type,
                    "reason": sell_reason,
                    "meeting_id": meeting.id if meeting else None,
                })
                logger.info(
                    f"Sell trigger fired: {holding.symbol} ({holding.name}) "
                    f"- {trigger_type}: {sell_reason}"
                )

        return {
            "status": "success",
            "monitored": len(holdings),
            "triggered": len(triggered),
            "details": triggered,
        }

    except Exception as e:
        logger.error(f"Holdings sell monitor failed: {e}")
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


# ── Helper functions ──


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


async def _get_cached_holdings():
    from app.core.redis import get_redis
    from app.services.kiwoom.rest_client import kiwoom_client

    redis = await get_redis()
    cache_key = "sell_monitor:holdings"

    cached = await redis.get(cache_key)
    if cached:
        from app.services.kiwoom.base import Holding

        data_list = json.loads(cached)
        return [Holding(**d) for d in data_list]

    if not await kiwoom_client.is_connected():
        try:
            await kiwoom_client.connect()
        except Exception as e:
            logger.warning(f"키움 API 연결 실패 (holdings): {e}")
            return []

    holdings = await kiwoom_client.get_holdings()

    if holdings:
        data_list = [
            {
                "symbol": h.symbol,
                "name": h.name,
                "quantity": h.quantity,
                "avg_price": h.avg_price,
                "current_price": h.current_price,
                "evaluation": h.evaluation,
                "profit_loss": h.profit_loss,
                "profit_rate": h.profit_rate,
            }
            for h in holdings
        ]
        await redis.setex(cache_key, 60, json.dumps(data_list))

    return holdings


async def _check_sell_cooldown(symbol: str) -> bool:
    from app.core.redis import get_redis

    redis = await get_redis()
    return await redis.exists(f"sell_monitor:cooldown:{symbol}") > 0


async def _set_sell_cooldown(symbol: str, ttl: int = SELL_COOLDOWN_SECONDS):
    from app.core.redis import get_redis

    redis = await get_redis()
    await redis.setex(f"sell_monitor:cooldown:{symbol}", ttl, "1")


async def _check_sell_signals_against_holdings(results) -> int:
    from app.services.kiwoom.rest_client import kiwoom_client
    from app.services.council.orchestrator import council_orchestrator

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


async def _evaluate_price_triggers(holding):
    stop_loss_threshold = float(getattr(settings, "stop_loss_percent", 5.0)) * -1.0
    take_profit_threshold = float(getattr(settings, "take_profit_percent", 20.0))

    if holding.profit_rate <= stop_loss_threshold:
        return (
            "stop_loss",
            f"기계적 손절매 발동 ({stop_loss_threshold}% 도달): {holding.profit_rate:+.2f}%",
        )

    if holding.profit_rate >= take_profit_threshold:
        return (
            "take_profit",
            f"기계적 익절매 기회 ({take_profit_threshold}% 도달): {holding.profit_rate:+.2f}%",
        )

    try:
        from app.services.kiwoom.rest_client import kiwoom_client
        from app.services.council.technical_indicators import technical_calculator

        if not await kiwoom_client.is_connected():
            await kiwoom_client.connect()

        daily_prices = await kiwoom_client.get_daily_prices(holding.symbol)
        if daily_prices:
            tech_result = technical_calculator.analyze(holding.symbol, daily_prices)
            if tech_result.technical_score is not None and tech_result.technical_score <= 3:
                return (
                    "technical",
                    f"기술적 악화: 점수 {tech_result.technical_score}/10",
                )
    except Exception as e:
        logger.warning(f"Technical analysis failed for {holding.symbol}: {e}")

    return None

"""Signal monitoring and sell trigger tasks.

Extracted from signal_tasks.py — monitoring-related Celery tasks.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

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

            from app.services.kiwoom.rest_client import kiwoom_client
            from .notification_tasks import send_notification

            actions = []

            for signal in pending_signals:
                try:
                    stock_price = run_async(kiwoom_client.get_stock_price(signal.symbol))

                    if not stock_price:
                        continue

                    price = stock_price.current_price

                    if signal.stop_loss and price <= signal.stop_loss:
                        actions.append({
                            "signal_id": signal.id,
                            "action": "stop_loss_triggered",
                            "symbol": signal.symbol,
                            "price": price,
                        })
                        send_notification.delay(
                            "stop_loss", f"[손절] {signal.symbol}: {price:,}원 도달"
                        )
                        _trigger_sell_for_signal(signal, price, "stop_loss")
                        signal.is_executed = True

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
                        _trigger_sell_for_signal(signal, price, "take_profit")
                        signal.is_executed = True

                    elif signal.created_at < datetime.utcnow() - timedelta(hours=24):
                        signal.is_executed = True
                        signal.signal_status = "expired"
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


# ── Helper functions ──


def _trigger_sell_for_signal(signal: TradingSignal, current_price: int, trigger_type: str):
    """시그널 기반 매도 실행 트리거"""
    try:
        from app.services.council.orchestrator import council_orchestrator

        company_name = signal.symbol
        try:
            with get_sync_db() as db:
                stock = db.execute(
                    select(Stock).where(Stock.symbol == signal.symbol)
                ).scalar_one_or_none()
                if stock:
                    company_name = stock.name
        except Exception:
            pass

        holdings = run_async(_get_cached_holdings())
        held = next((h for h in (holdings or []) if h.symbol == signal.symbol), None)
        actual_holdings = held.quantity if held else 0
        actual_avg_price = held.avg_price if held else 0

        run_async(
            council_orchestrator.start_sell_meeting(
                symbol=signal.symbol,
                company_name=company_name,
                sell_reason=f"{trigger_type}: 시그널 가격 도달 ({current_price:,}원)",
                current_holdings=actual_holdings,
                avg_buy_price=actual_avg_price,
                current_price=current_price,
            )
        )
        logger.info(f"Sell meeting triggered for {signal.symbol}: {trigger_type} at {current_price:,}원")
    except Exception as e:
        logger.error(f"Failed to trigger sell for {signal.symbol}: {e}")


def _get_active_signal_prices(symbol: str) -> tuple:
    """해당 종목의 활성 BUY 시그널에서 GPT 손절가/목표가 조회"""
    try:
        with get_sync_db() as db:
            signal = db.execute(
                select(TradingSignal)
                .where(
                    TradingSignal.symbol == symbol,
                    TradingSignal.signal_type == "buy",
                    TradingSignal.is_executed == False,
                )
                .order_by(TradingSignal.created_at.desc())
                .limit(1)
            ).scalar_one_or_none()

            if signal:
                return (signal.stop_loss, signal.target_price)
    except Exception as e:
        logger.warning(f"Failed to get signal prices for {symbol}: {e}")

    return (None, None)


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


async def _evaluate_price_triggers(holding):
    # 1. DB에서 해당 종목 활성 BUY 시그널의 GPT 손절가/목표가 조회
    gpt_stop_loss, gpt_target_price = _get_active_signal_prices(holding.symbol)

    # 2. GPT 가격 기반 체크 (우선)
    if gpt_stop_loss and holding.current_price <= float(gpt_stop_loss):
        return (
            "stop_loss",
            f"GPT 손절가 도달 ({int(gpt_stop_loss):,}원): 현재가 {holding.current_price:,}원",
        )

    if gpt_target_price and holding.current_price >= float(gpt_target_price):
        return (
            "take_profit",
            f"GPT 목표가 도달 ({int(gpt_target_price):,}원): 현재가 {holding.current_price:,}원",
        )

    # 3. Fallback: config % 기반
    stop_loss_threshold = -settings.stop_loss_percent
    take_profit_threshold = settings.take_profit_percent

    if holding.profit_rate <= stop_loss_threshold:
        return (
            "stop_loss",
            f"% 기반 손절 ({stop_loss_threshold}%): {holding.profit_rate:+.2f}%",
        )

    if holding.profit_rate >= take_profit_threshold:
        return (
            "take_profit",
            f"% 기반 익절 ({take_profit_threshold}%): {holding.profit_rate:+.2f}%",
        )

    # 4. 기술적 악화 체크
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

"""Signal monitoring and scanning tasks."""

import json
import logging
from datetime import datetime, timedelta
from typing import List, Optional

import time

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
                        _trigger_sell_for_signal(signal, price, "stop_loss")

                    elif signal.target_price and price >= signal.target_price:
                        actions.append({
                            "signal_id": signal.id,
                            "action": "target_reached",
                            "symbol": signal.symbol,
                            "price": price,
                        })
                        signal.is_executed = True
                        send_notification.delay(
                            "target_reached", f"[목표가] {signal.symbol}: {price:,}원 도달"
                        )
                        _trigger_sell_for_signal(signal, price, "take_profit")

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
    name="app.services.tasks.process_council_queue",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def process_council_queue(self):
    """Process queued council executions when market opens."""
    if not is_market_hours():
        return {"status": "skipped", "reason": "market_closed"}

    try:
        from app.services.council.orchestrator import council_orchestrator

        queued = council_orchestrator.get_queued_executions()
        if not queued:
            return {"status": "success", "message": "no_queued_signals"}

        executed = run_async(council_orchestrator.process_queued_executions())

        return {
            "status": "success",
            "queued_before": len(queued),
            "executed": len(executed),
        }
    except Exception as e:
        logger.error(f"Council queue processing failed: {e}")
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


async def _check_buy_signals_for_council(results) -> int:
    """Check quant BUY signals and trigger council meetings for top candidates."""
    from app.services.council.orchestrator import council_orchestrator
    from app.services.signals.models import SignalAction
    from app.core.redis import get_redis

    try:
        buy_results = [
            r for r in results
            if r.action in (SignalAction.STRONG_BUY, SignalAction.BUY)
            and r.composite_score >= 75
        ][:3]  # 스캔당 최대 3건

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

            await redis.setex(cooldown_key, 3600, "1")  # 60분 쿨다운

            # 키움 API에서 실제 주문가능금액 조회
            available_amount = 5000000  # 기본값
            try:
                from app.services.kiwoom.rest_client import kiwoom_client
                if not await kiwoom_client.is_connected():
                    await kiwoom_client.connect()
                balance = await kiwoom_client.get_balance()
                if balance.available_amount > 0:
                    available_amount = min(balance.available_amount, 5000000)
            except Exception as e:
                logger.warning(f"잔고 조회 실패, 기본값 사용: {e}")

            # 퀀트 트리거 상세 정보 구축
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


def _trigger_sell_for_signal(signal: TradingSignal, current_price: int, trigger_type: str):
    """시그널 기반 매도 실행 트리거"""
    try:
        from app.services.council.orchestrator import council_orchestrator

        # DB에서 종목명 조회
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

        run_async(
            council_orchestrator.start_sell_meeting(
                symbol=signal.symbol,
                company_name=company_name,
                sell_reason=f"{trigger_type}: 시그널 가격 도달 ({current_price:,}원)",
                current_holdings=0,  # sell meeting에서 자체 조회
                avg_buy_price=0,
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

    # 3. Fallback: config % 기반 (GPT 값 없는 종목)
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

    # 4. 기술적 악화 체크 (기존 유지)
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


@celery_app.task(
    name="app.services.tasks.rebalance_holdings",
    bind=True,
    time_limit=600,
    soft_time_limit=540,
)
def rebalance_holdings(self):
    """장 마감 후 보유종목 일일 리밸런싱 재평가.

    매일 15:40 KST에 실행.
    보유종목별로 GPT 퀀트 분석을 재실행하여 target_price / stop_loss 갱신.
    GPT score ≤ 3이면 sell meeting 에스컬레이션.
    """
    # 평일 체크 (장 후 실행이므로 is_market_hours 사용 안 함)
    from app.services.council.trading_hours import trading_hours

    if not trading_hours.is_trading_day():
        logger.info("비거래일 — 리밸런싱 스킵")
        return {"status": "skipped", "reason": "not_trading_day"}

    try:
        holdings = run_async(_get_cached_holdings())

        if not holdings:
            logger.info("보유종목 없음 — 리밸런싱 스킵")
            return {"status": "skipped", "reason": "no_holdings"}

        logger.info(f"[리밸런싱] 보유종목 {len(holdings)}건 재평가 시작")

        from app.services.council.orchestrator import council_orchestrator

        reviewed = []
        escalated = []

        for holding in holdings:
            try:
                # 기존 시그널 가격 조회
                prev_stop, prev_target = _get_active_signal_prices(holding.symbol)

                # GPT 리밸런싱 재평가
                result = run_async(
                    council_orchestrator.start_rebalance_review(
                        symbol=holding.symbol,
                        company_name=holding.name,
                        current_holdings=holding.quantity,
                        avg_buy_price=holding.avg_price,
                        current_price=holding.current_price,
                        prev_target_price=int(prev_target) if prev_target else None,
                        prev_stop_loss=int(prev_stop) if prev_stop else None,
                    )
                )

                if not result:
                    continue

                # DB 시그널 가격 갱신
                change_reason = (
                    f"[리밸런싱 {datetime.now().strftime('%m/%d')}] "
                    f"score={result['score']}, "
                    f"target: {int(prev_target):,}→{result['new_target_price']:,}" if prev_target else
                    f"[리밸런싱 {datetime.now().strftime('%m/%d')}] "
                    f"score={result['score']}, "
                    f"target: 미설정→{result['new_target_price']:,}" if result.get('new_target_price') else ""
                )
                if result.get("new_stop_loss"):
                    stop_part = (
                        f", stop: {int(prev_stop):,}→{result['new_stop_loss']:,}" if prev_stop
                        else f", stop: 미설정→{result['new_stop_loss']:,}"
                    )
                    change_reason += stop_part

                if result.get("new_target_price") or result.get("new_stop_loss"):
                    _update_signal_prices(
                        symbol=holding.symbol,
                        new_target=result.get("new_target_price"),
                        new_stop=result.get("new_stop_loss"),
                        reason=change_reason,
                    )

                reviewed.append({
                    "symbol": holding.symbol,
                    "name": holding.name,
                    "score": result["score"],
                    "new_target": result.get("new_target_price"),
                    "new_stop": result.get("new_stop_loss"),
                    "recommend_sell": result.get("recommend_sell", False),
                })

                # GPT score ≤ 3 → sell meeting 에스컬레이션
                if result.get("recommend_sell"):
                    logger.warning(
                        f"[리밸런싱] {holding.symbol} score={result['score']} ≤ 3 → 매도 회의 에스컬레이션"
                    )
                    run_async(
                        council_orchestrator.start_sell_meeting(
                            symbol=holding.symbol,
                            company_name=holding.name,
                            sell_reason=f"리밸런싱 재평가 저점수 (score={result['score']})",
                            current_holdings=holding.quantity,
                            avg_buy_price=holding.avg_price,
                            current_price=result.get("current_price", holding.current_price),
                        )
                    )
                    escalated.append(holding.symbol)

            except Exception as e:
                logger.error(f"[리밸런싱] {holding.symbol} 개별 오류: {e}")

            # API rate limit 방지
            time.sleep(1)

        logger.info(
            f"[리밸런싱] 완료: {len(reviewed)}/{len(holdings)}건 재평가, "
            f"{len(escalated)}건 매도 에스컬레이션"
        )

        return {
            "status": "success",
            "total_holdings": len(holdings),
            "reviewed": len(reviewed),
            "escalated": len(escalated),
            "escalated_symbols": escalated,
            "details": reviewed,
        }

    except Exception as e:
        logger.error(f"[리밸런싱] 전체 오류: {e}")
        self.retry(exc=e)


def _update_signal_prices(
    symbol: str,
    new_target: Optional[int],
    new_stop: Optional[int],
    reason: str,
):
    """기존 활성 BUY 시그널의 target_price / stop_loss 갱신 + reason에 변경 이력 append."""
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

            if not signal:
                logger.info(f"[리밸런싱] {symbol} 활성 BUY 시그널 없음 → 갱신 스킵")
                return

            # 이력 기록: 기존 reason에 append
            prev_reason = signal.reason or ""
            separator = " | " if prev_reason else ""
            signal.reason = prev_reason + separator + reason

            if new_target is not None:
                signal.target_price = float(new_target)
            if new_stop is not None:
                signal.stop_loss = float(new_stop)

            db.commit()
            logger.info(
                f"[리밸런싱] {symbol} DB 갱신 완료: "
                f"target={new_target}, stop={new_stop}"
            )

    except Exception as e:
        logger.error(f"[리밸런싱] {symbol} DB 갱신 실패: {e}")

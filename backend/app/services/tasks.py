"""
Celery tasks for background processing.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import select

from app.core.celery_app import celery_app
from app.core.database import get_sync_db
from app.config import settings
from app.models.stock import Stock, StockPrice, StockAnalysis
from app.models.transaction import TradingSignal

logger = logging.getLogger(__name__)


def run_async(coro):
    """Helper to run async functions in sync context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


def is_market_hours() -> bool:
    """Check if Korean stock market is open (KST)."""
    from zoneinfo import ZoneInfo
    now_kst = datetime.now(ZoneInfo("Asia/Seoul"))
    if now_kst.weekday() >= 5:  # Saturday or Sunday
        return False
    market_open = now_kst.replace(hour=9, minute=0, second=0, microsecond=0)
    market_close = now_kst.replace(hour=15, minute=30, second=0, microsecond=0)
    return market_open <= now_kst <= market_close


# ============================================================
# 가격 데이터 수집 태스크
# ============================================================

@celery_app.task(
    name="app.services.tasks.collect_stock_prices",
    bind=True,
    max_retries=3,
    default_retry_delay=60
)
def collect_stock_prices(self):
    """
    Collect real-time stock prices for all tracked symbols.
    Runs every minute during market hours.
    """
    if not is_market_hours():
        logger.info("Market is closed. Skipping price collection.")
        return {"status": "skipped", "reason": "market_closed"}

    try:
        with get_sync_db() as db:
            stocks = db.execute(select(Stock).where(Stock.is_active == True)).scalars().all()

            if not stocks:
                logger.info("No active stocks to track.")
                return {"status": "skipped", "reason": "no_stocks"}

            symbols = [stock.symbol for stock in stocks]
            logger.info(f"Collecting prices for {len(symbols)} stocks")

            from app.services.kiwoom.rest_client import KiwoomRestClient

            client = KiwoomRestClient()
            collected_count = 0
            errors = []

            for symbol in symbols:
                try:
                    price_data = run_async(client.get_current_price(symbol))

                    if price_data:
                        stock_price = StockPrice(
                            symbol=symbol,
                            date=datetime.utcnow(),
                            open=price_data.get("open", 0),
                            high=price_data.get("high", 0),
                            low=price_data.get("low", 0),
                            close=price_data.get("close", 0),
                            volume=price_data.get("volume", 0),
                            change_percent=price_data.get("change_percent", price_data.get("change_rate", 0)),
                        )
                        db.add(stock_price)
                        collected_count += 1
                except Exception as e:
                    errors.append({"symbol": symbol, "error": str(e)})
                    logger.error(f"Error collecting price for {symbol}: {e}")

            db.commit()

            result = {
                "status": "success",
                "collected": collected_count,
                "total": len(symbols),
                "errors": errors[:10] if errors else [],
            }
            logger.info(f"Price collection complete: {result}")
            return result

    except Exception as e:
        logger.error(f"Price collection failed: {e}")
        self.retry(exc=e)


@celery_app.task(name="app.services.tasks.collect_historical_prices")
def collect_historical_prices(symbol: str, days: int = 365):
    """Collect historical price data for a specific stock."""
    try:
        with get_sync_db() as db:
            stock = db.execute(select(Stock).where(Stock.symbol == symbol)).scalar_one_or_none()

            if not stock:
                return {"status": "error", "reason": "stock_not_found"}

            from app.services.kiwoom.rest_client import KiwoomRestClient

            client = KiwoomRestClient()
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)

            history = run_async(client.get_price_history(
                symbol,
                start_date.strftime("%Y%m%d"),
                end_date.strftime("%Y%m%d")
            ))

            if not history:
                return {"status": "error", "reason": "no_data"}

            count = 0
            for item in history:
                date_value = item.get("date")
                if isinstance(date_value, str):
                    try:
                        if len(date_value) == 8 and date_value.isdigit():
                            date_value = datetime.strptime(date_value, "%Y%m%d")
                        else:
                            date_value = datetime.fromisoformat(date_value)
                    except ValueError:
                        continue

                existing = db.execute(
                    select(StockPrice).where(
                        StockPrice.symbol == stock.symbol,
                        StockPrice.date == date_value
                    )
                ).scalar_one_or_none()

                if not existing:
                    price = StockPrice(
                        symbol=stock.symbol,
                        date=date_value,
                        open=item["open"],
                        high=item["high"],
                        low=item["low"],
                        close=item["close"],
                        volume=item["volume"],
                        change_percent=item.get("change_percent", 0),
                    )
                    db.add(price)
                    count += 1

            db.commit()
            return {"status": "success", "symbol": symbol, "records_added": count}

    except Exception as e:
        logger.error(f"Historical price collection failed for {symbol}: {e}")
        return {"status": "error", "error": str(e)}


# ============================================================
# AI 분석 태스크
# ============================================================

@celery_app.task(
    name="app.services.tasks.analyze_market_news",
    bind=True,
    max_retries=2,
    default_retry_delay=120
)
def analyze_market_news(self):
    """
    Analyze market news using Gemini agent.
    Runs every 5 minutes.
    """
    async def _analyze():
        from app.agents.gemini_agent import GeminiNewsAgent

        agent = GeminiNewsAgent()
        market_sentiment = await agent.get_market_sentiment("KOSPI")

        logger.info(f"Market sentiment analysis: {market_sentiment.get('sentiment', 'unknown')}")

        # Cache the result in Redis
        from app.core.redis import get_redis
        redis = await get_redis()
        if redis:
            import json
            await redis.setex(
                "market_sentiment:KOSPI",
                300,  # 5 minutes TTL
                json.dumps(market_sentiment)
            )

        return market_sentiment

    try:
        market_sentiment = run_async(_analyze())

        return {
            "status": "success",
            "sentiment": market_sentiment.get("sentiment"),
            "score": market_sentiment.get("sentiment_score"),
        }

    except Exception as e:
        logger.error(f"Market news analysis failed: {e}")
        self.retry(exc=e)


@celery_app.task(
    name="app.services.tasks.run_ai_analysis",
    bind=True,
    max_retries=2,
    default_retry_delay=300
)
def run_ai_analysis(self):
    """
    Run full AI analysis on watchlist stocks.
    Runs every 15 minutes during market hours.
    """
    if not is_market_hours():
        logger.info("Market is closed. Skipping AI analysis.")
        return {"status": "skipped", "reason": "market_closed"}

    try:
        with get_sync_db() as db:
            from app.models.portfolio import Watchlist

            watchlist_items = db.execute(
                select(Watchlist.symbol).distinct()
            ).scalars().all()

            if not watchlist_items:
                watchlist_items = ["005930", "000660", "035420", "035720", "051910"]

            logger.info(f"Running AI analysis for {len(watchlist_items)} stocks")

            from app.agents.coordinator import AgentCoordinator

            coordinator = AgentCoordinator()
            results = []
            signals_generated = 0

            for symbol in watchlist_items[:10]:
                try:
                    result = run_async(coordinator.run_analysis(symbol=symbol, save_to_db=True))
                    final = result.get("final_recommendation") or {}
                    results.append({
                        "symbol": symbol,
                        "score": final.get("overall_score"),
                        "recommendation": final.get("recommendation"),
                    })
                    if result.get("trading_signal"):
                        signals_generated += 1
                except Exception as e:
                    logger.error(f"Analysis failed for {symbol}: {e}")
                    results.append({"symbol": symbol, "error": str(e)})

            return {
                "status": "success",
                "analyzed": len(results),
                "signals_generated": signals_generated,
                "results": results,
            }

    except Exception as e:
        logger.error(f"AI analysis task failed: {e}")
        self.retry(exc=e)


@celery_app.task(name="app.services.tasks.run_single_analysis")
def run_single_analysis(symbol: str, analysis_types: Optional[List[str]] = None):
    """Run AI analysis for a single stock (background task)."""
    try:
        from app.agents.coordinator import AgentCoordinator

        coordinator = AgentCoordinator()
        result = run_async(coordinator.run_analysis(symbol=symbol, save_to_db=True))
        final = result.get("final_recommendation") or {}
        confidence = final.get("confidence")
        if analysis_types:
            logger.info("run_single_analysis received analysis_types=%s (currently ignored by coordinator)", analysis_types)

        return {
            "status": "success",
            "symbol": symbol,
            "final_score": final.get("overall_score"),
            "recommendation": final.get("recommendation"),
            "confidence": confidence,
            "signal_generated": result.get("trading_signal") is not None,
        }

    except Exception as e:
        logger.error(f"Single analysis failed for {symbol}: {e}")
        return {"status": "error", "symbol": symbol, "error": str(e)}


@celery_app.task(name="app.services.tasks.run_quick_analysis")
def run_quick_analysis(symbol: str):
    """Run quick analysis (technical + quant only) for faster results."""
    try:
        from app.agents.coordinator import AgentCoordinator

        coordinator = AgentCoordinator()
        result = run_async(coordinator.run_quick_analysis(symbol))

        return {
            "status": "success",
            "symbol": symbol,
            "final_score": result.get("overall_score"),
            "recommendation": result.get("recommendation"),
        }

    except Exception as e:
        logger.error(f"Quick analysis failed for {symbol}: {e}")
        return {"status": "error", "symbol": symbol, "error": str(e)}


# ============================================================
# 신호 모니터링 태스크
# ============================================================

@celery_app.task(
    name="app.services.tasks.monitor_signals",
    bind=True,
    max_retries=3,
    default_retry_delay=60
)
def monitor_signals(self):
    """Monitor pending signals and check for execution conditions."""
    if not is_market_hours():
        return {"status": "skipped", "reason": "market_closed"}

    try:
        with get_sync_db() as db:
            pending_signals = db.execute(
                select(TradingSignal).where(
                    TradingSignal.is_executed == False,
                )
            ).scalars().all()

            if not pending_signals:
                return {"status": "success", "message": "no_pending_signals"}

            from app.services.kiwoom.rest_client import KiwoomRestClient

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
                            "stop_loss",
                            f"[손절] {signal.symbol}: {price:,}원 도달"
                        )

                    elif signal.target_price and price >= signal.target_price:
                        actions.append({
                            "signal_id": signal.id,
                            "action": "target_reached",
                            "symbol": signal.symbol,
                            "price": price,
                        })
                        send_notification.delay(
                            "target_reached",
                            f"[목표가] {signal.symbol}: {price:,}원 도달"
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

            side = "buy" if signal.signal_type == "buy" else "sell"
            price = int(signal.target_price) if signal.target_price else 0
            order_result = run_async(
                trading_service.place_order(
                    user_id=1,  # TradingSignal currently has no user_id mapping
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
                    f"[주문실행] {signal.signal_type.upper()} {signal.symbol} x {quantity}"
                )

            return {
                "status": "success" if order_result.get("success") else "failed",
                "signal_id": signal_id,
                "order_result": order_result,
            }

    except Exception as e:
        logger.error(f"Auto execution failed for signal {signal_id}: {e}")
        return {"status": "error", "error": str(e)}


# ============================================================
# 알림 태스크
# ============================================================

@celery_app.task(name="app.services.tasks.send_notification")
def send_notification(notification_type: str, message: str, data: Optional[dict] = None):
    """Send notifications via configured channels (Slack, Telegram)."""
    results = {"type": notification_type, "message": message, "channels": []}

    # Slack notification
    if settings.slack_webhook_url:
        try:
            import httpx

            slack_message = {
                "text": message,
                "attachments": [{
                    "color": _get_notification_color(notification_type),
                    "fields": [
                        {"title": k, "value": str(v), "short": True}
                        for k, v in (data or {}).items()
                    ]
                }] if data else []
            }

            response = httpx.post(
                settings.slack_webhook_url,
                json=slack_message,
                timeout=10
            )

            if response.status_code == 200:
                results["channels"].append("slack")

        except Exception as e:
            logger.error(f"Slack notification failed: {e}")

    # Telegram notification
    if settings.telegram_bot_token and settings.telegram_chat_id:
        try:
            import httpx

            telegram_url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"

            response = httpx.post(
                telegram_url,
                json={
                    "chat_id": settings.telegram_chat_id,
                    "text": message,
                    "parse_mode": "HTML",
                },
                timeout=10
            )

            if response.status_code == 200:
                results["channels"].append("telegram")

        except Exception as e:
            logger.error(f"Telegram notification failed: {e}")

    logger.info(f"Notification sent: {results}")
    return results


def _get_notification_color(notification_type: str) -> str:
    """Get color for notification type."""
    colors = {
        "buy_signal": "#36a64f",
        "sell_signal": "#ff4444",
        "stop_loss": "#ff0000",
        "target_reached": "#00ff00",
        "order_executed": "#2196F3",
        "error": "#ff0000",
    }
    return colors.get(notification_type, "#808080")


@celery_app.task(name="app.services.tasks.send_daily_report")
def send_daily_report():
    """Send daily trading report."""
    try:
        with get_sync_db() as db:
            today = datetime.now().date()

            signals = db.execute(
                select(TradingSignal).where(
                    TradingSignal.created_at >= today
                )
            ).scalars().all()

            from app.models.transaction import Transaction

            orders = db.execute(
                select(Transaction).where(
                    Transaction.created_at >= today
                )
            ).scalars().all()

            report = f"""
📊 <b>Signal Smith 일간 리포트</b>
📅 {today.strftime('%Y-%m-%d')}

📡 <b>시그널 생성</b>: {len(signals)}개
  - 매수: {len([s for s in signals if s.signal_type == 'buy'])}개
  - 매도: {len([s for s in signals if s.signal_type == 'sell'])}개
  - 보유: {len([s for s in signals if s.signal_type == 'hold'])}개

💹 <b>주문 실행</b>: {len(orders)}건

✅ 시스템 정상 운영 중
"""
            send_notification.delay("daily_report", report)

            return {"status": "success", "signals": len(signals), "orders": len(orders)}

    except Exception as e:
        logger.error(f"Daily report failed: {e}")
        return {"status": "error", "error": str(e)}


# ============================================================
# 데이터 정리 태스크
# ============================================================

# ============================================================
# 퀀트 시그널 스캔 태스크
# ============================================================

@celery_app.task(
    name="app.services.tasks.scan_signals",
    bind=True,
    max_retries=2,
    default_retry_delay=120,
    time_limit=600,       # 10분 하드 리밋
    soft_time_limit=540,  # 9분 소프트 리밋
)
def scan_signals(self):
    """
    퀀트 시그널 스캔 (상위 500종목).
    시가총액 기준 상위 500종목을 대상으로 42개 트리거 평가.
    15분마다 실행. Semaphore 기반 동시 5개 스캔.
    """
    if not is_market_hours():
        logger.info("Market is closed. Skipping signal scan.")
        return {"status": "skipped", "reason": "market_closed"}

    try:
        symbols = _load_scan_universe(limit=500)
        logger.info(f"Signal scan starting: {len(symbols)} symbols")

        from app.services.signals import signal_scanner

        results = run_async(signal_scanner.scan_watchlist(symbols, max_concurrent=5))

        # ── 보유 종목 매도 시그널 교차 검증 ──
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


def _load_scan_universe(limit: int = 500) -> List[str]:
    """스캔 대상 종목 로드 (Redis 캐시 → DB 폴백).

    Returns:
        시가총액 상위 종목코드 리스트
    """
    import json

    # 1) Redis 캐시 확인
    try:
        redis = run_async(_get_cached_universe())
        if redis:
            symbols = json.loads(redis)
            logger.info(f"Loaded {len(symbols)} symbols from Redis cache")
            return symbols[:limit]
    except Exception as e:
        logger.warning(f"Redis cache miss for stock universe: {e}")

    # 2) DB 폴백: Stock 테이블에서 시가총액 상위
    try:
        with get_sync_db() as db:
            from sqlalchemy import desc
            stocks = db.execute(
                select(Stock.symbol, Stock.market, Stock.market_cap)
                .where(Stock.is_active == True)
                .order_by(
                    desc(Stock.market_cap.isnot(None)),  # market_cap 있는 것 우선
                    Stock.market,  # KOSDAQ < KOSPI (KOSPI 우선 정렬)
                    desc(Stock.market_cap),
                )
                .limit(limit)
            ).all()

            if stocks:
                symbols = [s.symbol for s in stocks]
                logger.info(f"Loaded {len(symbols)} symbols from DB")
                return symbols
    except Exception as e:
        logger.warning(f"DB stock universe load failed: {e}")

    # 3) 하드코딩 폴백 (대형주 10개)
    logger.warning("Using fallback symbol list")
    return ["005930", "000660", "035420", "035720", "051910",
            "006400", "005380", "068270", "028260", "207940"]


async def _get_cached_universe() -> Optional[str]:
    """Redis에서 캐시된 종목 유니버스 조회"""
    from app.core.redis import get_redis
    redis = await get_redis()
    return await redis.get("stock_universe:top500")


@celery_app.task(
    name="app.services.tasks.refresh_stock_universe",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    time_limit=300,
    soft_time_limit=240,
)
def refresh_stock_universe(self):
    """
    종목 유니버스 갱신.
    KOSPI + KOSDAQ 전체 종목 조회 → Stock 테이블 upsert + Redis 캐시.
    매일 08:50 실행 (장 시작 전).
    """
    try:
        result = run_async(_refresh_universe_async())
        return result
    except Exception as e:
        logger.error(f"Stock universe refresh failed: {e}")
        self.retry(exc=e)


async def _refresh_universe_async() -> dict:
    """종목 유니버스 갱신 비동기 로직"""
    import json
    from app.services.kiwoom.rest_client import kiwoom_client
    from app.core.redis import get_redis

    if not await kiwoom_client.is_connected():
        await kiwoom_client.connect()

    # KOSPI + KOSDAQ 전체 종목 조회
    kospi_stocks = await kiwoom_client.get_market_stocks("KOSPI")
    kosdaq_stocks = await kiwoom_client.get_market_stocks("KOSDAQ")
    all_stocks = kospi_stocks + kosdaq_stocks

    logger.info(f"Fetched stocks: KOSPI={len(kospi_stocks)}, KOSDAQ={len(kosdaq_stocks)}")

    if not all_stocks:
        return {"status": "error", "reason": "no_stocks_fetched"}

    # DB upsert
    upserted = 0
    with get_sync_db() as db:
        for stock_data in all_stocks:
            symbol = stock_data.get("symbol", "")
            if not symbol:
                continue

            existing = db.execute(
                select(Stock).where(Stock.symbol == symbol)
            ).scalar_one_or_none()

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

        # 시가총액 상위 500 선별 (market_cap 있으면 기준, 없으면 KOSPI 우선)
        from sqlalchemy import desc
        top_stocks = db.execute(
            select(Stock.symbol)
            .where(Stock.is_active == True)
            .order_by(
                desc(Stock.market_cap.isnot(None)),
                Stock.market,  # KOSDAQ < KOSPI → KOSPI 우선
                desc(Stock.market_cap),
            )
            .limit(500)
        ).scalars().all()

    top_symbols = list(top_stocks)

    # Redis 캐시 (1일 TTL)
    try:
        redis = await get_redis()
        await redis.set(
            "stock_universe:top500",
            json.dumps(top_symbols),
            ex=86400,  # 24시간
        )
        logger.info(f"Cached {len(top_symbols)} symbols to Redis")
    except Exception as e:
        logger.warning(f"Redis cache failed: {e}")

    return {
        "status": "success",
        "total_fetched": len(all_stocks),
        "upserted": upserted,
        "universe_size": len(top_symbols),
    }


# ============================================================
# 보유 종목 매도 모니터링 태스크
# ============================================================

@celery_app.task(
    name="app.services.tasks.monitor_holdings_sell",
    bind=True,
    time_limit=300,
    soft_time_limit=270,
)
def monitor_holdings_sell(self):
    """
    보유 종목 매도 감시 (가격 기반 트리거).
    5분마다 실행. 손절/익절/기술적 악화 감지 → 매도 회의 소집.
    퀀트 스캔(scan_signals)과 쿨다운 키를 공유하여 중복 방지.
    """
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
            # 쿨다운 확인 (scan_signals과 공유)
            if run_async(_check_sell_cooldown(holding.symbol)):
                continue

            result = run_async(_evaluate_price_triggers(holding))
            if result:
                trigger_type, sell_reason = result
                run_async(_set_sell_cooldown(holding.symbol, ttl=1800))

                from app.services.council.orchestrator import council_orchestrator
                meeting = run_async(council_orchestrator.start_sell_meeting(
                    symbol=holding.symbol,
                    company_name=holding.name,
                    sell_reason=sell_reason,
                    current_holdings=holding.quantity,
                    avg_buy_price=holding.avg_price,
                    current_price=holding.current_price,
                ))

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


# ============================================================
# 매도 모니터링 헬퍼 함수
# ============================================================

async def _get_cached_holdings():
    """키움 보유종목 조회 (Redis 1분 캐시)."""
    import json
    from app.core.redis import get_redis
    from app.services.kiwoom.rest_client import kiwoom_client

    redis = await get_redis()
    cache_key = "sell_monitor:holdings"

    # 캐시 확인
    cached = await redis.get(cache_key)
    if cached:
        # 캐시된 데이터를 Holding 객체로 복원
        from app.services.kiwoom.base import Holding
        data_list = json.loads(cached)
        return [Holding(**d) for d in data_list]

    # 키움 API 조회
    if not await kiwoom_client.is_connected():
        try:
            await kiwoom_client.connect()
        except Exception as e:
            logger.warning(f"키움 API 연결 실패 (holdings): {e}")
            return []

    holdings = await kiwoom_client.get_holdings()

    if holdings:
        # Redis 캐시 (1분 TTL)
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
    """매도 쿨다운 확인. True면 쿨다운 중 (스킵해야 함)."""
    from app.core.redis import get_redis
    redis = await get_redis()
    return await redis.exists(f"sell_monitor:cooldown:{symbol}") > 0


async def _set_sell_cooldown(symbol: str, ttl: int = 1800):
    """매도 쿨다운 설정 (기본 30분)."""
    from app.core.redis import get_redis
    redis = await get_redis()
    await redis.setex(f"sell_monitor:cooldown:{symbol}", ttl, "1")


async def _check_sell_signals_against_holdings(results) -> int:
    """
    퀀트 스캔 결과와 보유 종목 교차 검증.
    SELL/STRONG_SELL 시그널이 보유 종목에 해당하면 매도 회의 소집.
    Returns: 매도 회의 소집 건수.
    """
    from app.services.kiwoom.rest_client import kiwoom_client
    from app.services.council.orchestrator import council_orchestrator

    try:
        # 보유 종목 조회 (캐시 활용)
        holdings = await _get_cached_holdings()
        if not holdings:
            return 0

        held_map = {h.symbol: h for h in holdings}

        # SELL/STRONG_SELL 필터
        from app.services.signals.models import SignalAction
        sell_results = [
            r for r in results
            if r.action in (SignalAction.SELL, SignalAction.STRONG_SELL)
        ]

        triggered = 0
        for result in sell_results:
            if result.symbol not in held_map:
                continue

            # 쿨다운 확인
            if await _check_sell_cooldown(result.symbol):
                continue

            holding = held_map[result.symbol]

            # 쿨다운 설정 후 매도 회의 소집
            await _set_sell_cooldown(result.symbol, ttl=1800)

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
    """
    가격 기반 매도 트리거 평가.
    Returns: (trigger_type, sell_reason) 또는 None.

    1. 손절: profit_rate <= -5%
    2. 익절: profit_rate >= 20%
    3. 기술 악화: technical_score <= 3
    """
    # 트리거 1: 손절
    if holding.profit_rate <= -5.0:
        return ("stop_loss", f"손절 발동: {holding.profit_rate:+.2f}%")

    # 트리거 2: 익절
    if holding.profit_rate >= 20.0:
        return ("take_profit", f"익절 기회: {holding.profit_rate:+.2f}%")

    # 트리거 3: 기술적 악화
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


@celery_app.task(name="app.services.tasks.cleanup_old_data")
def cleanup_old_data(days: int = 90):
    """Clean up old analysis data and expired signals."""
    try:
        with get_sync_db() as db:
            cutoff_date = datetime.utcnow() - timedelta(days=days)

            deleted_analyses = db.execute(
                StockAnalysis.__table__.delete().where(
                    StockAnalysis.created_at < cutoff_date
                )
            )

            db.execute(
                TradingSignal.__table__.update().where(
                    TradingSignal.created_at < cutoff_date
                ).values(is_active=False)
            )

            db.commit()

            return {
                "status": "success",
                "deleted_analyses": deleted_analyses.rowcount,
                "cutoff_date": cutoff_date.isoformat(),
            }

    except Exception as e:
        logger.error(f"Data cleanup failed: {e}")
        return {"status": "error", "error": str(e)}

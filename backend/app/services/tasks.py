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
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def is_market_hours() -> bool:
    """Check if Korean stock market is open."""
    now = datetime.now()
    if now.weekday() >= 5:  # Saturday or Sunday
        return False
    market_open = now.replace(hour=9, minute=0, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
    return market_open <= now <= market_close


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
                            stock_id=next((s.id for s in stocks if s.symbol == symbol), None),
                            date=datetime.now().date(),
                            open=price_data.get("open", 0),
                            high=price_data.get("high", 0),
                            low=price_data.get("low", 0),
                            close=price_data.get("close", 0),
                            volume=price_data.get("volume", 0),
                            change_percent=price_data.get("change_percent", 0),
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
                existing = db.execute(
                    select(StockPrice).where(
                        StockPrice.stock_id == stock.id,
                        StockPrice.date == item["date"]
                    )
                ).scalar_one_or_none()

                if not existing:
                    price = StockPrice(
                        stock_id=stock.id,
                        date=item["date"],
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
    try:
        from app.agents.gemini_agent import GeminiNewsAgent

        agent = GeminiNewsAgent()
        market_sentiment = run_async(agent.get_market_sentiment("KOSPI"))

        logger.info(f"Market sentiment analysis: {market_sentiment.get('sentiment', 'unknown')}")

        # Cache the result in Redis
        from app.core.redis import get_redis
        redis = run_async(get_redis())
        if redis:
            import json
            run_async(redis.setex(
                "market_sentiment:KOSPI",
                300,  # 5 minutes TTL
                json.dumps(market_sentiment)
            ))

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

            coordinator = AgentCoordinator(db)
            results = []
            signals_generated = 0

            for symbol in watchlist_items[:10]:
                try:
                    result = run_async(coordinator.run_full_analysis(symbol))
                    results.append({
                        "symbol": symbol,
                        "score": result.get("final_score"),
                        "recommendation": result.get("recommendation"),
                    })
                    if result.get("signal_generated"):
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
        with get_sync_db() as db:
            from app.agents.coordinator import AgentCoordinator

            coordinator = AgentCoordinator(db)
            result = run_async(coordinator.run_full_analysis(
                symbol,
                analysis_types=analysis_types or ["news", "quant", "fundamental", "technical"]
            ))

            return {
                "status": "success",
                "symbol": symbol,
                "final_score": result.get("final_score"),
                "recommendation": result.get("recommendation"),
                "confidence": result.get("confidence"),
                "signal_generated": result.get("signal_generated"),
            }

    except Exception as e:
        logger.error(f"Single analysis failed for {symbol}: {e}")
        return {"status": "error", "symbol": symbol, "error": str(e)}


@celery_app.task(name="app.services.tasks.run_quick_analysis")
def run_quick_analysis(symbol: str):
    """Run quick analysis (technical + quant only) for faster results."""
    try:
        with get_sync_db() as db:
            from app.agents.coordinator import AgentCoordinator

            coordinator = AgentCoordinator(db)
            result = run_async(coordinator.run_quick_analysis(symbol))

            return {
                "status": "success",
                "symbol": symbol,
                "final_score": result.get("final_score"),
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
                    TradingSignal.executed == False,
                    TradingSignal.is_active == True
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
                        signal.is_active = False
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
                        signal.is_active = False
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

            if not signal or signal.executed:
                return {"status": "error", "reason": "invalid_signal"}

            from app.services.trading_service import TradingService

            trading_service = TradingService(db)

            order_result = run_async(trading_service.execute_order(
                symbol=signal.symbol,
                transaction_type=signal.signal_type,
                quantity=quantity,
                price=signal.entry_price,
            ))

            if order_result.get("success"):
                signal.executed = True
                signal.executed_at = datetime.utcnow()
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

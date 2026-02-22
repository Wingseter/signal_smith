"""Notification and reporting tasks."""

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select

from app.core.celery_app import celery_app
from app.core.database import get_sync_db
from app.config import settings
from app.models.transaction import TradingSignal

logger = logging.getLogger(__name__)


@celery_app.task(name="app.services.tasks.send_notification")
def send_notification(notification_type: str, message: str, data: Optional[dict] = None):
    """Send notifications via configured channels (Slack, Telegram)."""
    results = {"type": notification_type, "message": message, "channels": []}

    if settings.slack_webhook_url:
        try:
            import httpx

            slack_message = {
                "text": message,
                "attachments": [
                    {
                        "color": _get_notification_color(notification_type),
                        "fields": [
                            {"title": k, "value": str(v), "short": True}
                            for k, v in (data or {}).items()
                        ],
                    }
                ]
                if data
                else [],
            }

            response = httpx.post(settings.slack_webhook_url, json=slack_message, timeout=10)

            if response.status_code == 200:
                results["channels"].append("slack")

        except Exception as e:
            logger.error(f"Slack notification failed: {e}")

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
                timeout=10,
            )

            if response.status_code == 200:
                results["channels"].append("telegram")

        except Exception as e:
            logger.error(f"Telegram notification failed: {e}")

    logger.info(f"Notification sent: {results}")
    return results


def _get_notification_color(notification_type: str) -> str:
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

            signals = (
                db.execute(select(TradingSignal).where(TradingSignal.created_at >= today))
                .scalars()
                .all()
            )

            from app.models.transaction import Transaction

            orders = (
                db.execute(select(Transaction).where(Transaction.created_at >= today))
                .scalars()
                .all()
            )

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

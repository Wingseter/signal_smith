"""
Notification service for sending alerts via multiple channels.
Supports Slack, Telegram, Email, and WebSocket push notifications.
"""

import asyncio
import logging
import smtplib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class NotificationType(str, Enum):
    """Types of notifications."""
    BUY_SIGNAL = "buy_signal"
    SELL_SIGNAL = "sell_signal"
    HOLD_SIGNAL = "hold_signal"
    STOP_LOSS = "stop_loss"
    TARGET_REACHED = "target_reached"
    ORDER_EXECUTED = "order_executed"
    ORDER_FAILED = "order_failed"
    PRICE_ALERT = "price_alert"
    ANALYSIS_COMPLETE = "analysis_complete"
    DAILY_REPORT = "daily_report"
    SYSTEM_ALERT = "system_alert"
    ERROR = "error"


class NotificationPriority(str, Enum):
    """Priority levels for notifications."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class NotificationMessage:
    """Notification message structure."""
    type: NotificationType
    title: str
    message: str
    priority: NotificationPriority = NotificationPriority.MEDIUM
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "title": self.title,
            "message": self.message,
            "priority": self.priority.value,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
        }


class NotificationChannel(ABC):
    """Abstract base class for notification channels."""

    @abstractmethod
    async def send(self, notification: NotificationMessage) -> bool:
        """Send notification. Returns True if successful."""
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """Check if channel is properly configured."""
        pass


class SlackNotificationChannel(NotificationChannel):
    """Slack webhook notification channel."""

    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or settings.slack_webhook_url

    def is_configured(self) -> bool:
        return bool(self.webhook_url)

    def _get_color(self, notification: NotificationMessage) -> str:
        """Get Slack attachment color based on notification type."""
        colors = {
            NotificationType.BUY_SIGNAL: "#36a64f",
            NotificationType.SELL_SIGNAL: "#ff4444",
            NotificationType.HOLD_SIGNAL: "#ffcc00",
            NotificationType.STOP_LOSS: "#ff0000",
            NotificationType.TARGET_REACHED: "#00ff00",
            NotificationType.ORDER_EXECUTED: "#2196F3",
            NotificationType.ORDER_FAILED: "#ff0000",
            NotificationType.PRICE_ALERT: "#9c27b0",
            NotificationType.ANALYSIS_COMPLETE: "#00bcd4",
            NotificationType.DAILY_REPORT: "#607d8b",
            NotificationType.SYSTEM_ALERT: "#ff9800",
            NotificationType.ERROR: "#f44336",
        }
        return colors.get(notification.type, "#808080")

    def _get_emoji(self, notification: NotificationMessage) -> str:
        """Get emoji based on notification type."""
        emojis = {
            NotificationType.BUY_SIGNAL: "📈",
            NotificationType.SELL_SIGNAL: "📉",
            NotificationType.HOLD_SIGNAL: "⏸️",
            NotificationType.STOP_LOSS: "🛑",
            NotificationType.TARGET_REACHED: "🎯",
            NotificationType.ORDER_EXECUTED: "✅",
            NotificationType.ORDER_FAILED: "❌",
            NotificationType.PRICE_ALERT: "🔔",
            NotificationType.ANALYSIS_COMPLETE: "🔍",
            NotificationType.DAILY_REPORT: "📊",
            NotificationType.SYSTEM_ALERT: "⚠️",
            NotificationType.ERROR: "🚨",
        }
        return emojis.get(notification.type, "📢")

    async def send(self, notification: NotificationMessage) -> bool:
        if not self.is_configured():
            logger.warning("Slack webhook URL not configured")
            return False

        try:
            emoji = self._get_emoji(notification)

            # Build Slack message
            slack_message = {
                "text": f"{emoji} *{notification.title}*",
                "attachments": [
                    {
                        "color": self._get_color(notification),
                        "text": notification.message,
                        "fields": [
                            {"title": k, "value": str(v), "short": True}
                            for k, v in notification.data.items()
                        ] if notification.data else [],
                        "footer": "Signal Smith",
                        "ts": int(notification.timestamp.timestamp()),
                    }
                ],
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.webhook_url,
                    json=slack_message,
                    timeout=10
                )

                if response.status_code == 200:
                    logger.info(f"Slack notification sent: {notification.title}")
                    return True
                else:
                    logger.error(f"Slack notification failed: {response.status_code}")
                    return False

        except Exception as e:
            logger.error(f"Slack notification error: {e}")
            return False


class TelegramNotificationChannel(NotificationChannel):
    """Telegram bot notification channel."""

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None
    ):
        self.bot_token = bot_token or settings.telegram_bot_token
        self.chat_id = chat_id or settings.telegram_chat_id
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"

    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    def _get_emoji(self, notification: NotificationMessage) -> str:
        """Get emoji based on notification type."""
        emojis = {
            NotificationType.BUY_SIGNAL: "📈",
            NotificationType.SELL_SIGNAL: "📉",
            NotificationType.HOLD_SIGNAL: "⏸️",
            NotificationType.STOP_LOSS: "🛑",
            NotificationType.TARGET_REACHED: "🎯",
            NotificationType.ORDER_EXECUTED: "✅",
            NotificationType.ORDER_FAILED: "❌",
            NotificationType.PRICE_ALERT: "🔔",
            NotificationType.ANALYSIS_COMPLETE: "🔍",
            NotificationType.DAILY_REPORT: "📊",
            NotificationType.SYSTEM_ALERT: "⚠️",
            NotificationType.ERROR: "🚨",
        }
        return emojis.get(notification.type, "📢")

    def _format_message(self, notification: NotificationMessage) -> str:
        """Format message for Telegram (HTML)."""
        emoji = self._get_emoji(notification)

        lines = [
            f"{emoji} <b>{notification.title}</b>",
            "",
            notification.message,
        ]

        if notification.data:
            lines.append("")
            for key, value in notification.data.items():
                lines.append(f"• <b>{key}</b>: {value}")

        lines.extend([
            "",
            f"<i>{notification.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</i>",
        ])

        return "\n".join(lines)

    async def send(self, notification: NotificationMessage) -> bool:
        if not self.is_configured():
            logger.warning("Telegram bot not configured")
            return False

        try:
            message_text = self._format_message(notification)

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/sendMessage",
                    json={
                        "chat_id": self.chat_id,
                        "text": message_text,
                        "parse_mode": "HTML",
                        "disable_web_page_preview": True,
                    },
                    timeout=10
                )

                if response.status_code == 200:
                    logger.info(f"Telegram notification sent: {notification.title}")
                    return True
                else:
                    logger.error(f"Telegram notification failed: {response.text}")
                    return False

        except Exception as e:
            logger.error(f"Telegram notification error: {e}")
            return False

    async def send_photo(self, chat_id: str, photo_url: str, caption: str) -> bool:
        """Send photo with caption."""
        if not self.is_configured():
            return False

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/sendPhoto",
                    json={
                        "chat_id": chat_id or self.chat_id,
                        "photo": photo_url,
                        "caption": caption,
                        "parse_mode": "HTML",
                    },
                    timeout=15
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Telegram photo error: {e}")
            return False


class EmailNotificationChannel(NotificationChannel):
    """Email notification channel using SMTP."""

    def __init__(
        self,
        smtp_host: Optional[str] = None,
        smtp_port: int = 587,
        smtp_user: Optional[str] = None,
        smtp_password: Optional[str] = None,
        from_email: Optional[str] = None,
        to_emails: Optional[List[str]] = None,
    ):
        self.smtp_host = smtp_host or getattr(settings, 'smtp_host', None)
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user or getattr(settings, 'smtp_user', None)
        self.smtp_password = smtp_password or getattr(settings, 'smtp_password', None)
        self.from_email = from_email or getattr(settings, 'from_email', None)
        self.to_emails = to_emails or getattr(settings, 'notification_emails', [])

    def is_configured(self) -> bool:
        return bool(
            self.smtp_host and
            self.smtp_user and
            self.smtp_password and
            self.from_email and
            self.to_emails
        )

    def _get_priority_badge(self, priority: NotificationPriority) -> str:
        badges = {
            NotificationPriority.LOW: "🟢",
            NotificationPriority.MEDIUM: "🟡",
            NotificationPriority.HIGH: "🟠",
            NotificationPriority.CRITICAL: "🔴",
        }
        return badges.get(priority, "⚪")

    def _create_html_body(self, notification: NotificationMessage) -> str:
        """Create HTML email body."""
        badge = self._get_priority_badge(notification.priority)

        data_rows = ""
        if notification.data:
            data_rows = "<table style='margin-top: 15px; border-collapse: collapse;'>"
            for key, value in notification.data.items():
                data_rows += f"""
                <tr>
                    <td style='padding: 5px 10px; border: 1px solid #ddd; font-weight: bold;'>{key}</td>
                    <td style='padding: 5px 10px; border: 1px solid #ddd;'>{value}</td>
                </tr>
                """
            data_rows += "</table>"

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #1a1a2e; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; background: #f9f9f9; }}
                .footer {{ text-align: center; padding: 10px; font-size: 12px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>{badge} Signal Smith Alert</h1>
                </div>
                <div class="content">
                    <h2>{notification.title}</h2>
                    <p>{notification.message}</p>
                    {data_rows}
                    <p style="margin-top: 20px; font-size: 12px; color: #666;">
                        Time: {notification.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
                    </p>
                </div>
                <div class="footer">
                    <p>Signal Smith - AI Stock Analysis System</p>
                </div>
            </div>
        </body>
        </html>
        """

    async def send(self, notification: NotificationMessage) -> bool:
        if not self.is_configured():
            logger.warning("Email not configured")
            return False

        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"[Signal Smith] {notification.title}"
            msg['From'] = self.from_email
            msg['To'] = ", ".join(self.to_emails)

            # Plain text version
            text_content = f"{notification.title}\n\n{notification.message}"
            if notification.data:
                text_content += "\n\n"
                for key, value in notification.data.items():
                    text_content += f"{key}: {value}\n"

            # HTML version
            html_content = self._create_html_body(notification)

            msg.attach(MIMEText(text_content, 'plain'))
            msg.attach(MIMEText(html_content, 'html'))

            # Send email (run in thread pool to avoid blocking)
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._send_email, msg)

            logger.info(f"Email notification sent: {notification.title}")
            return True

        except Exception as e:
            logger.error(f"Email notification error: {e}")
            return False

    def _send_email(self, msg: MIMEMultipart):
        """Send email via SMTP (blocking)."""
        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            server.starttls()
            server.login(self.smtp_user, self.smtp_password)
            server.send_message(msg)


class NotificationService:
    """
    Main notification service that manages multiple channels.
    """

    def __init__(self):
        self.channels: Dict[str, NotificationChannel] = {}
        self._initialize_channels()

    def _initialize_channels(self):
        """Initialize all configured notification channels."""
        # Slack
        slack = SlackNotificationChannel()
        if slack.is_configured():
            self.channels["slack"] = slack
            logger.info("Slack notification channel initialized")

        # Telegram
        telegram = TelegramNotificationChannel()
        if telegram.is_configured():
            self.channels["telegram"] = telegram
            logger.info("Telegram notification channel initialized")

        # Email
        email = EmailNotificationChannel()
        if email.is_configured():
            self.channels["email"] = email
            logger.info("Email notification channel initialized")

    def add_channel(self, name: str, channel: NotificationChannel):
        """Add a custom notification channel."""
        self.channels[name] = channel

    def remove_channel(self, name: str):
        """Remove a notification channel."""
        self.channels.pop(name, None)

    def get_active_channels(self) -> List[str]:
        """Get list of active channel names."""
        return list(self.channels.keys())

    async def send(
        self,
        notification: NotificationMessage,
        channels: Optional[List[str]] = None
    ) -> Dict[str, bool]:
        """
        Send notification to specified channels (or all if not specified).
        Returns dict of channel -> success status.
        """
        target_channels = channels or list(self.channels.keys())
        results = {}

        tasks = []
        for channel_name in target_channels:
            if channel_name in self.channels:
                tasks.append(
                    self._send_to_channel(channel_name, notification)
                )

        if tasks:
            channel_results = await asyncio.gather(*tasks, return_exceptions=True)
            for channel_name, result in zip(target_channels, channel_results):
                if isinstance(result, Exception):
                    logger.error(f"Channel {channel_name} error: {result}")
                    results[channel_name] = False
                else:
                    results[channel_name] = result

        return results

    async def _send_to_channel(
        self,
        channel_name: str,
        notification: NotificationMessage
    ) -> bool:
        """Send notification to a specific channel."""
        channel = self.channels.get(channel_name)
        if channel:
            return await channel.send(notification)
        return False

    # Convenience methods for common notifications

    async def send_buy_signal(
        self,
        symbol: str,
        price: float,
        target_price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        reason: str = "",
        strength: int = 0,
    ) -> Dict[str, bool]:
        """Send buy signal notification."""
        data = {
            "종목": symbol,
            "현재가": f"{price:,.0f}원",
            "신호강도": f"{strength}%",
        }
        if target_price:
            data["목표가"] = f"{target_price:,.0f}원"
        if stop_loss:
            data["손절가"] = f"{stop_loss:,.0f}원"

        notification = NotificationMessage(
            type=NotificationType.BUY_SIGNAL,
            title=f"매수 시그널: {symbol}",
            message=reason or f"{symbol} 종목에 대한 매수 신호가 생성되었습니다.",
            priority=NotificationPriority.HIGH if strength >= 70 else NotificationPriority.MEDIUM,
            data=data,
        )
        return await self.send(notification)

    async def send_sell_signal(
        self,
        symbol: str,
        price: float,
        reason: str = "",
        strength: int = 0,
    ) -> Dict[str, bool]:
        """Send sell signal notification."""
        notification = NotificationMessage(
            type=NotificationType.SELL_SIGNAL,
            title=f"매도 시그널: {symbol}",
            message=reason or f"{symbol} 종목에 대한 매도 신호가 생성되었습니다.",
            priority=NotificationPriority.HIGH if strength >= 70 else NotificationPriority.MEDIUM,
            data={
                "종목": symbol,
                "현재가": f"{price:,.0f}원",
                "신호강도": f"{strength}%",
            },
        )
        return await self.send(notification)

    async def send_stop_loss_alert(
        self,
        symbol: str,
        trigger_price: float,
        loss_percent: float,
    ) -> Dict[str, bool]:
        """Send stop loss triggered notification."""
        notification = NotificationMessage(
            type=NotificationType.STOP_LOSS,
            title=f"손절가 도달: {symbol}",
            message=f"{symbol} 종목이 손절가에 도달했습니다. 즉시 확인이 필요합니다.",
            priority=NotificationPriority.CRITICAL,
            data={
                "종목": symbol,
                "현재가": f"{trigger_price:,.0f}원",
                "손실률": f"{loss_percent:.2f}%",
            },
        )
        return await self.send(notification)

    async def send_target_reached_alert(
        self,
        symbol: str,
        current_price: float,
        target_price: float,
        profit_percent: float,
    ) -> Dict[str, bool]:
        """Send target price reached notification."""
        notification = NotificationMessage(
            type=NotificationType.TARGET_REACHED,
            title=f"목표가 도달: {symbol}",
            message=f"{symbol} 종목이 목표가에 도달했습니다!",
            priority=NotificationPriority.HIGH,
            data={
                "종목": symbol,
                "현재가": f"{current_price:,.0f}원",
                "목표가": f"{target_price:,.0f}원",
                "수익률": f"+{profit_percent:.2f}%",
            },
        )
        return await self.send(notification)

    async def send_order_executed(
        self,
        symbol: str,
        order_type: str,
        quantity: int,
        price: float,
        order_id: str,
    ) -> Dict[str, bool]:
        """Send order executed notification."""
        notification = NotificationMessage(
            type=NotificationType.ORDER_EXECUTED,
            title=f"주문 체결: {symbol}",
            message=f"{symbol} {order_type} 주문이 체결되었습니다.",
            priority=NotificationPriority.HIGH,
            data={
                "종목": symbol,
                "유형": order_type.upper(),
                "수량": f"{quantity:,}주",
                "가격": f"{price:,.0f}원",
                "주문번호": order_id,
            },
        )
        return await self.send(notification)

    async def send_price_alert(
        self,
        symbol: str,
        current_price: float,
        alert_price: float,
        direction: str,  # "above" or "below"
    ) -> Dict[str, bool]:
        """Send price alert notification."""
        notification = NotificationMessage(
            type=NotificationType.PRICE_ALERT,
            title=f"가격 알림: {symbol}",
            message=f"{symbol} 가격이 설정한 {'상한' if direction == 'above' else '하한'}가에 도달했습니다.",
            priority=NotificationPriority.MEDIUM,
            data={
                "종목": symbol,
                "현재가": f"{current_price:,.0f}원",
                "알림가": f"{alert_price:,.0f}원",
            },
        )
        return await self.send(notification)

    async def send_analysis_complete(
        self,
        symbol: str,
        score: float,
        recommendation: str,
        summary: str,
    ) -> Dict[str, bool]:
        """Send analysis complete notification."""
        notification = NotificationMessage(
            type=NotificationType.ANALYSIS_COMPLETE,
            title=f"분석 완료: {symbol}",
            message=summary[:200] + "..." if len(summary) > 200 else summary,
            priority=NotificationPriority.LOW,
            data={
                "종목": symbol,
                "점수": f"{score:+.1f}",
                "추천": recommendation.upper(),
            },
        )
        return await self.send(notification)

    async def send_error_alert(
        self,
        title: str,
        error_message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, bool]:
        """Send error alert notification."""
        notification = NotificationMessage(
            type=NotificationType.ERROR,
            title=title,
            message=error_message,
            priority=NotificationPriority.CRITICAL,
            data=details or {},
        )
        return await self.send(notification)


# Global notification service instance
notification_service = NotificationService()


async def get_notification_service() -> NotificationService:
    """Get notification service instance."""
    return notification_service

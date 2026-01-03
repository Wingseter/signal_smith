"""
Notification API endpoints.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.services.notification_service import (
    NotificationMessage,
    NotificationPriority,
    NotificationService,
    NotificationType,
    get_notification_service,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


# ============================================================
# Pydantic Schemas
# ============================================================

class NotificationSettingsUpdate(BaseModel):
    """Settings for notification preferences."""
    slack_enabled: bool = True
    telegram_enabled: bool = True
    email_enabled: bool = False
    buy_signals: bool = True
    sell_signals: bool = True
    price_alerts: bool = True
    order_updates: bool = True
    daily_reports: bool = True
    min_signal_strength: int = Field(default=50, ge=0, le=100)


class NotificationSettings(NotificationSettingsUpdate):
    """Full notification settings with metadata."""
    user_id: int
    updated_at: datetime


class TestNotificationRequest(BaseModel):
    """Request to send a test notification."""
    channel: str = Field(..., description="Channel: slack, telegram, email")
    message: Optional[str] = "This is a test notification from Signal Smith"


class SendNotificationRequest(BaseModel):
    """Request to send a custom notification."""
    type: str = Field(..., description="Notification type")
    title: str
    message: str
    priority: str = "medium"
    data: Dict[str, Any] = Field(default_factory=dict)
    channels: Optional[List[str]] = None


class PriceAlertCreate(BaseModel):
    """Create price alert request."""
    symbol: str
    price_above: Optional[float] = None
    price_below: Optional[float] = None
    note: Optional[str] = None


class PriceAlert(PriceAlertCreate):
    """Price alert response."""
    id: int
    user_id: int
    triggered: bool = False
    triggered_at: Optional[datetime] = None
    created_at: datetime


class NotificationChannelStatus(BaseModel):
    """Status of a notification channel."""
    name: str
    configured: bool
    enabled: bool


class NotificationStatusResponse(BaseModel):
    """Overall notification status response."""
    channels: List[NotificationChannelStatus]
    total_sent_today: int = 0
    last_notification: Optional[datetime] = None


# ============================================================
# Endpoints
# ============================================================

@router.get("/status")
async def get_notification_status(
    notification_service: NotificationService = Depends(get_notification_service),
    current_user: User = Depends(get_current_user),
) -> NotificationStatusResponse:
    """Get notification system status."""
    active_channels = notification_service.get_active_channels()

    channels = [
        NotificationChannelStatus(
            name="slack",
            configured="slack" in active_channels,
            enabled=True,
        ),
        NotificationChannelStatus(
            name="telegram",
            configured="telegram" in active_channels,
            enabled=True,
        ),
        NotificationChannelStatus(
            name="email",
            configured="email" in active_channels,
            enabled=True,
        ),
    ]

    return NotificationStatusResponse(
        channels=channels,
        total_sent_today=0,  # TODO: Track this in Redis
        last_notification=None,
    )


@router.get("/channels")
async def get_active_channels(
    notification_service: NotificationService = Depends(get_notification_service),
    current_user: User = Depends(get_current_user),
) -> List[str]:
    """Get list of active notification channels."""
    return notification_service.get_active_channels()


@router.post("/test")
async def send_test_notification(
    request: TestNotificationRequest,
    notification_service: NotificationService = Depends(get_notification_service),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Send a test notification to a specific channel."""
    if request.channel not in notification_service.get_active_channels():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Channel '{request.channel}' is not configured or not available"
        )

    notification = NotificationMessage(
        type=NotificationType.SYSTEM_ALERT,
        title="테스트 알림",
        message=request.message,
        priority=NotificationPriority.LOW,
        data={
            "사용자": current_user.email,
            "채널": request.channel,
        },
    )

    results = await notification_service.send(notification, channels=[request.channel])

    return {
        "success": results.get(request.channel, False),
        "channel": request.channel,
        "message": "Test notification sent" if results.get(request.channel) else "Failed to send notification",
    }


@router.post("/send")
async def send_notification(
    request: SendNotificationRequest,
    notification_service: NotificationService = Depends(get_notification_service),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Send a custom notification."""
    try:
        notification_type = NotificationType(request.type)
    except ValueError:
        notification_type = NotificationType.SYSTEM_ALERT

    try:
        priority = NotificationPriority(request.priority)
    except ValueError:
        priority = NotificationPriority.MEDIUM

    notification = NotificationMessage(
        type=notification_type,
        title=request.title,
        message=request.message,
        priority=priority,
        data=request.data,
    )

    results = await notification_service.send(notification, channels=request.channels)

    return {
        "success": any(results.values()),
        "results": results,
        "notification": notification.to_dict(),
    }


@router.post("/signal/buy")
async def send_buy_signal_notification(
    symbol: str,
    price: float,
    target_price: Optional[float] = None,
    stop_loss: Optional[float] = None,
    reason: str = "",
    strength: int = 50,
    notification_service: NotificationService = Depends(get_notification_service),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Send buy signal notification."""
    results = await notification_service.send_buy_signal(
        symbol=symbol,
        price=price,
        target_price=target_price,
        stop_loss=stop_loss,
        reason=reason,
        strength=strength,
    )

    return {
        "success": any(results.values()),
        "results": results,
    }


@router.post("/signal/sell")
async def send_sell_signal_notification(
    symbol: str,
    price: float,
    reason: str = "",
    strength: int = 50,
    notification_service: NotificationService = Depends(get_notification_service),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Send sell signal notification."""
    results = await notification_service.send_sell_signal(
        symbol=symbol,
        price=price,
        reason=reason,
        strength=strength,
    )

    return {
        "success": any(results.values()),
        "results": results,
    }


# ============================================================
# Price Alerts
# ============================================================

@router.get("/alerts")
async def get_price_alerts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """Get user's price alerts."""
    from app.models.portfolio import Watchlist

    items = await db.execute(
        select(Watchlist).where(
            Watchlist.user_id == current_user.id,
            (Watchlist.alert_price_above.isnot(None)) | (Watchlist.alert_price_below.isnot(None))
        )
    )
    alerts = items.scalars().all()

    return [
        {
            "id": alert.id,
            "symbol": alert.symbol,
            "price_above": float(alert.alert_price_above) if alert.alert_price_above else None,
            "price_below": float(alert.alert_price_below) if alert.alert_price_below else None,
            "note": alert.notes,
            "created_at": alert.created_at.isoformat(),
        }
        for alert in alerts
    ]


@router.post("/alerts")
async def create_price_alert(
    alert: PriceAlertCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Create a new price alert."""
    from app.models.portfolio import Watchlist

    if not alert.price_above and not alert.price_below:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one of price_above or price_below must be set"
        )

    # Check if already exists
    existing = await db.execute(
        select(Watchlist).where(
            Watchlist.user_id == current_user.id,
            Watchlist.symbol == alert.symbol
        )
    )
    watchlist_item = existing.scalar_one_or_none()

    if watchlist_item:
        # Update existing
        watchlist_item.alert_price_above = alert.price_above
        watchlist_item.alert_price_below = alert.price_below
        watchlist_item.notes = alert.note
    else:
        # Create new
        watchlist_item = Watchlist(
            user_id=current_user.id,
            symbol=alert.symbol,
            alert_price_above=alert.price_above,
            alert_price_below=alert.price_below,
            notes=alert.note,
        )
        db.add(watchlist_item)

    await db.commit()
    await db.refresh(watchlist_item)

    return {
        "id": watchlist_item.id,
        "symbol": watchlist_item.symbol,
        "price_above": float(watchlist_item.alert_price_above) if watchlist_item.alert_price_above else None,
        "price_below": float(watchlist_item.alert_price_below) if watchlist_item.alert_price_below else None,
        "created_at": watchlist_item.created_at.isoformat(),
    }


@router.delete("/alerts/{alert_id}")
async def delete_price_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, str]:
    """Delete a price alert."""
    from app.models.portfolio import Watchlist

    result = await db.execute(
        select(Watchlist).where(
            Watchlist.id == alert_id,
            Watchlist.user_id == current_user.id
        )
    )
    watchlist_item = result.scalar_one_or_none()

    if not watchlist_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found"
        )

    # Clear alert prices instead of deleting (keep watchlist item)
    watchlist_item.alert_price_above = None
    watchlist_item.alert_price_below = None

    await db.commit()

    return {"message": "Alert deleted successfully"}


# ============================================================
# Notification Settings
# ============================================================

@router.get("/settings")
async def get_notification_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get user's notification settings."""
    # TODO: Implement user-specific settings storage
    # For now, return default settings
    return {
        "user_id": current_user.id,
        "slack_enabled": True,
        "telegram_enabled": True,
        "email_enabled": False,
        "buy_signals": True,
        "sell_signals": True,
        "price_alerts": True,
        "order_updates": True,
        "daily_reports": True,
        "min_signal_strength": 50,
    }


@router.put("/settings")
async def update_notification_settings(
    settings: NotificationSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Update user's notification settings."""
    # TODO: Implement user-specific settings storage
    return {
        "user_id": current_user.id,
        "updated_at": datetime.now().isoformat(),
        **settings.model_dump(),
    }

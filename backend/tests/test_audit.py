"""감사 이벤트 테스트 — Phase 3 E4 (P1).

audit.py의 sync/async 함수, SignalEvent 모델, 구조화 로그.
"""

import logging
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── Test 1: gate block → signal_events 행 기록 ──

@pytest.mark.asyncio
async def test_gate_block_creates_signal_event():
    """Gate block → log_signal_event_async writes SignalEvent to DB."""
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    mock_session_maker = MagicMock(return_value=mock_session)

    # async_session_maker is imported lazily inside the function
    with patch("app.core.database.async_session_maker", mock_session_maker):
        from app.core.audit import log_signal_event_async

        await log_signal_event_async(
            event_type="gate_block_min_position",
            symbol="005930",
            action="BUY",
            signal_id=42,
            details={"reason": "Gate A 최소 포지션 미달"},
        )

        # Verify session.add was called with a SignalEvent
        mock_session.add.assert_called_once()
        event = mock_session.add.call_args[0][0]
        from app.models.transaction import SignalEvent

        assert isinstance(event, SignalEvent)
        assert event.event_type == "gate_block_min_position"
        assert event.symbol == "005930"
        assert event.action == "BUY"
        assert event.signal_id == 42
        assert event.details["reason"] == "Gate A 최소 포지션 미달"

        mock_session.commit.assert_called_once()


# ── Test 2: 주문 제출 → signal_events에 order_no 포함 ──

@pytest.mark.asyncio
async def test_order_event_includes_order_no():
    """Order execution event includes order_no in details."""
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session_maker = MagicMock(return_value=mock_session)

    with patch("app.core.database.async_session_maker", mock_session_maker):
        from app.core.audit import log_signal_event_async

        await log_signal_event_async(
            event_type="order_executed",
            symbol="005930",
            action="BUY",
            signal_id=42,
            details={"order_no": "ORD123", "source": "queue"},
        )

        event = mock_session.add.call_args[0][0]
        assert event.details["order_no"] == "ORD123"
        assert event.details["source"] == "queue"


# ── Test 3: sync audit function works ──

def test_sync_log_signal_event():
    """Sync log_signal_event (Celery) writes to DB via get_sync_db."""
    mock_db = MagicMock()
    mock_db.__enter__ = MagicMock(return_value=mock_db)
    mock_db.__exit__ = MagicMock(return_value=False)

    with patch("app.core.database.get_sync_db", return_value=mock_db):
        from app.core.audit import log_signal_event

        log_signal_event(
            event_type="gate_block_cash_reserve",
            symbol="000660",
            action="BUY",
            signal_id=99,
            details={"reason": "현금 부족"},
        )

        mock_db.add.assert_called_once()
        event = mock_db.add.call_args[0][0]
        from app.models.transaction import SignalEvent

        assert isinstance(event, SignalEvent)
        assert event.event_type == "gate_block_cash_reserve"
        assert event.symbol == "000660"


# ── Test 4: DB 실패 시 non-fatal (로그만 남기고 진행) ──

@pytest.mark.asyncio
async def test_audit_db_failure_is_non_fatal():
    """DB write failure → logged warning, no exception propagated."""
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.commit.side_effect = Exception("DB connection lost")
    mock_session_maker = MagicMock(return_value=mock_session)

    with patch("app.core.database.async_session_maker", mock_session_maker):
        from app.core.audit import log_signal_event_async

        # Should NOT raise — non-fatal
        await log_signal_event_async(
            event_type="order_executed",
            symbol="005930",
            action="SELL",
            signal_id=10,
        )


# ── Test 5: JSON 로그에 extra_data 필드 포함 ──

def test_structured_log_contains_extra_data(caplog):
    """log_signal_event emits structured log with extra_data dict."""
    # Bypass DB write by making get_sync_db raise
    with (
        patch("app.core.database.get_sync_db", side_effect=Exception("no db")),
        caplog.at_level(logging.INFO, logger="app.core.audit"),
    ):
        from app.core.audit import log_signal_event

        log_signal_event(
            event_type="signal_created",
            symbol="005930",
            action="BUY",
            signal_id=7,
            details={"confidence": 0.85},
        )

        assert len(caplog.records) >= 1
        # Find the info record (not the warning about DB failure)
        info_records = [r for r in caplog.records if r.levelno == logging.INFO]
        assert len(info_records) >= 1
        record = info_records[0]
        assert "signal_event" in record.message
        assert "005930" in record.message

        # extra_data should be attached to the log record
        extra = getattr(record, "extra_data", None)
        assert extra is not None
        assert extra["event_type"] == "signal_created"
        assert extra["symbol"] == "005930"
        assert extra["signal_id"] == 7


# ── Test 6: SignalEvent 모델 필드 확인 ──

def test_signal_event_model_fields():
    """SignalEvent model has expected fields as constructor kwargs."""
    from app.models.transaction import SignalEvent

    # In the mocked environment, __table__ may not be fully populated,
    # so test via constructor instead
    event = SignalEvent(
        signal_id=1,
        event_type="test_event",
        symbol="005930",
        action="BUY",
        details={"key": "value"},
    )
    assert event.event_type == "test_event"
    assert event.symbol == "005930"
    assert event.action == "BUY"
    assert event.signal_id == 1
    assert event.details == {"key": "value"}

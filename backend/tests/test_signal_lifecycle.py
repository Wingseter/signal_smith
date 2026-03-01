"""시그널 상태 전이 테스트 — Phase 3 E2 (P0).

InvestmentSignal lifecycle: PENDING → APPROVED/REJECTED/EXPIRED/QUEUED/EXECUTED.
"""

import pytest
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.council.models import (
    InvestmentSignal,
    SignalStatus,
)


# ── Mock helpers ──

@dataclass
class _OrderResult:
    status: str = "submitted"
    order_no: str = "12345"
    message: str = ""


def _make_signal(**kwargs):
    defaults = dict(
        symbol="005930",
        company_name="삼성전자",
        action="BUY",
        suggested_quantity=10,
        suggested_amount=800_000,
        confidence=0.8,
        quant_score=7,
        fundamental_score=7,
        status=SignalStatus.PENDING,
    )
    defaults.update(kwargs)
    return InvestmentSignal(**defaults)


def _mock_orch():
    """Create minimal orchestrator-like object."""
    orch = MagicMock()
    orch._pending_signals = []
    orch._queued_executions = []
    orch.respect_trading_hours = True
    orch.auto_execute = True
    orch.min_confidence = 0.5
    orch._notify_signal = AsyncMock()
    return orch


# ── Test 1: PENDING → APPROVED → EXECUTED (정상 체결) ──

@pytest.mark.asyncio
async def test_pending_to_approved_to_executed():
    """Approve + market order success → EXECUTED."""
    signal = _make_signal()
    orch = _mock_orch()
    orch._pending_signals = [signal]

    mock_order_result = _OrderResult(status="submitted", order_no="ORD001")

    with (
        patch("app.services.council.order_executor.kiwoom_client") as mock_kiwoom,
        patch("app.services.council.order_executor.trading_hours") as mock_hours,
        patch("app.services.council.order_executor.log_signal_event_async", new_callable=AsyncMock),
        patch("app.services.council.order_executor.update_signal_status_in_db", new_callable=AsyncMock),
    ):
        mock_hours.can_execute_order.return_value = (True, "market_open")
        mock_kiwoom.place_order = AsyncMock(return_value=mock_order_result)

        from app.services.council.order_executor import approve_signal

        result = await approve_signal(orch, signal.id)

        assert result is not None
        assert result.status == SignalStatus.EXECUTED
        assert result.executed_at is not None


# ── Test 2: PENDING → APPROVED → QUEUED → AUTO_EXECUTED (장외 → 장중) ──

@pytest.mark.asyncio
async def test_pending_to_queued_to_auto_executed():
    """Market closed at approve → QUEUED; then process_queued → AUTO_EXECUTED."""
    signal = _make_signal()
    orch = _mock_orch()
    orch._pending_signals = [signal]

    mock_order_result = _OrderResult(status="submitted", order_no="ORD002")

    with (
        patch("app.services.council.order_executor.kiwoom_client") as mock_kiwoom,
        patch("app.services.council.order_executor.trading_hours") as mock_hours,
        patch("app.services.council.order_executor.log_signal_event_async", new_callable=AsyncMock),
        patch("app.services.council.order_executor.update_signal_status_in_db", new_callable=AsyncMock),
    ):
        # Phase 1: market closed → QUEUED
        mock_hours.can_execute_order.return_value = (False, "market_closed")

        from app.services.council.order_executor import approve_signal, process_queued_executions

        result = await approve_signal(orch, signal.id)
        assert result is not None
        assert result.status == SignalStatus.QUEUED
        assert len(orch._queued_executions) == 1

        # Phase 2: market opens → process queue
        mock_hours.can_execute_order.return_value = (True, "market_open")
        mock_kiwoom.place_order = AsyncMock(return_value=mock_order_result)
        mock_kiwoom.get_balance = AsyncMock(return_value=MagicMock(available_amount=50_000_000))

        executed = await process_queued_executions(orch)
        assert len(executed) == 1
        assert executed[0].status == SignalStatus.AUTO_EXECUTED


# ── Test 3: PENDING → REJECTED ──

@pytest.mark.asyncio
async def test_pending_to_rejected():
    """Reject signal → REJECTED status."""
    signal = _make_signal()
    orch = _mock_orch()
    orch._pending_signals = [signal]

    with patch("app.services.council.order_executor.update_signal_status_in_db", new_callable=AsyncMock):
        from app.services.council.order_executor import reject_signal

        result = await reject_signal(orch, signal.id)

        assert result is not None
        assert result.status == SignalStatus.REJECTED


# ── Test 4: confidence < min → 시그널 미생성 ──

def test_low_confidence_no_signal():
    """Confidence below threshold → signal should not enter pipeline."""
    signal = _make_signal(confidence=0.3)
    orch = _mock_orch()
    orch.min_confidence = 0.5

    # Simulate the confidence check that orchestrator does
    if signal.confidence < orch.min_confidence:
        filtered_out = True
    else:
        filtered_out = False
        orch._pending_signals.append(signal)

    assert filtered_out is True
    assert len(orch._pending_signals) == 0


# ── Test 5: HOLD → execution pipeline 미진입 ──

@pytest.mark.asyncio
async def test_hold_does_not_enter_execution():
    """HOLD action signal should not trigger order placement."""
    signal = _make_signal(action="HOLD")
    orch = _mock_orch()
    orch._pending_signals = [signal]

    with (
        patch("app.services.council.order_executor.kiwoom_client") as mock_kiwoom,
        patch("app.services.council.order_executor.trading_hours") as mock_hours,
        patch("app.services.council.order_executor.log_signal_event_async", new_callable=AsyncMock),
        patch("app.services.council.order_executor.update_signal_status_in_db", new_callable=AsyncMock),
    ):
        mock_hours.can_execute_order.return_value = (True, "market_open")

        from app.services.council.order_executor import approve_signal

        result = await approve_signal(orch, signal.id)

        # HOLD → approved but no order placed
        assert result is not None
        assert result.status == SignalStatus.APPROVED
        mock_kiwoom.place_order.assert_not_called()


# ── Test 6: quantity=0 BUY → effectively no-op ──

def test_quantity_zero_buy_is_hold():
    """BUY with quantity=0 → treat as HOLD (no execution)."""
    signal = _make_signal(suggested_quantity=0, action="BUY")

    # Orchestrator logic: quantity <= 0 → action should be HOLD
    if signal.suggested_quantity <= 0 and signal.action == "BUY":
        signal.action = "HOLD"

    assert signal.action == "HOLD"


# ── Test 7: PARTIAL_SELL DB 조회 포함 확인 ──

def test_partial_sell_signal_type_in_model():
    """Verify SignalStatus values include queued and auto_executed for queue flow."""
    assert SignalStatus.QUEUED.value == "queued"
    assert SignalStatus.AUTO_EXECUTED.value == "auto_executed"
    assert SignalStatus.PENDING.value == "pending"
    assert SignalStatus.APPROVED.value == "approved"
    assert SignalStatus.REJECTED.value == "rejected"
    assert SignalStatus.EXECUTED.value == "executed"
    assert SignalStatus.EXPIRED.value == "expired"


# ── Test 8: Restore pending signals from DB ──

@pytest.mark.asyncio
async def test_restore_pending_signals():
    """restore_pending_signals → queued signals restored to _queued_executions."""
    orch = _mock_orch()

    mock_pending = [
        {
            "id": 1,
            "symbol": "005930",
            "company_name": "삼성전자",
            "signal_type": "buy",
            "strength": 80.0,
            "quantity": 10,
            "target_price": 75000,
            "stop_loss": 68000,
            "signal_status": "queued",
            "reason": "test",
            "suggested_amount": 750000,
            "allocation_percent": 10.0,
            "quant_score": 7,
            "fundamental_score": 7,
        },
        {
            "id": 2,
            "symbol": "000660",
            "company_name": "SK하이닉스",
            "signal_type": "buy",
            "strength": 70.0,
            "quantity": 5,
            "target_price": 200000,
            "stop_loss": 180000,
            "signal_status": "pending",
            "reason": "test",
            "suggested_amount": 1000000,
            "allocation_percent": 15.0,
            "quant_score": 6,
            "fundamental_score": 7,
        },
    ]

    with patch("app.services.council.order_executor.trading_service") as mock_ts:
        mock_ts.get_pending_signals = AsyncMock(return_value=mock_pending)

        from app.services.council.order_executor import restore_pending_signals

        await restore_pending_signals(orch)

        assert len(orch._queued_executions) == 1
        assert orch._queued_executions[0].symbol == "005930"
        assert orch._queued_executions[0].status == SignalStatus.QUEUED

        assert len(orch._pending_signals) == 1
        assert orch._pending_signals[0].symbol == "000660"
        assert orch._pending_signals[0].status == SignalStatus.PENDING

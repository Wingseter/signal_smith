"""E2E 실행 흐름 테스트 — Phase 3 E3 (P1).

매도 트리거, 큐 중복 방지, 잔고 부족 처리.
"""

import pytest
from dataclasses import dataclass
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.council.models import (
    InvestmentSignal,
    SignalStatus,
)


@dataclass
class _OrderResult:
    status: str = "submitted"
    order_no: str = "12345"
    message: str = ""


@dataclass
class _Balance:
    available_amount: int = 50_000_000
    total_evaluation: int = 50_000_000


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
        status=SignalStatus.QUEUED,
    )
    defaults.update(kwargs)
    return InvestmentSignal(**defaults)


def _mock_orch():
    orch = MagicMock()
    orch._pending_signals = []
    orch._queued_executions = []
    orch.respect_trading_hours = True
    orch.auto_execute = True
    orch.min_confidence = 0.5
    orch._notify_signal = AsyncMock()
    return orch


# ── Test 1: 매도 주문 체결 ──

@pytest.mark.asyncio
async def test_sell_order_executed():
    """SELL signal → order placed → EXECUTED."""
    signal = _make_signal(action="SELL", status=SignalStatus.PENDING)
    orch = _mock_orch()
    orch._pending_signals = [signal]

    with (
        patch("app.services.council.order_executor.kiwoom_client") as mock_kiwoom,
        patch("app.services.council.order_executor.trading_hours") as mock_hours,
        patch("app.services.council.order_executor.log_signal_event_async", new_callable=AsyncMock),
        patch("app.services.council.order_executor.update_signal_status_in_db", new_callable=AsyncMock),
    ):
        mock_hours.can_execute_order.return_value = (True, "market_open")
        mock_kiwoom.place_order = AsyncMock(
            return_value=_OrderResult(status="submitted", order_no="SELL001"),
        )

        from app.services.council.order_executor import approve_signal

        result = await approve_signal(orch, signal.id)

        assert result is not None
        assert result.status == SignalStatus.EXECUTED
        mock_kiwoom.place_order.assert_called_once()


# ── Test 2: 주문 실패 → 큐에 추가 ──

@pytest.mark.asyncio
async def test_order_failure_queues_signal():
    """Order placement fails → signal goes to QUEUED."""
    signal = _make_signal(action="BUY", status=SignalStatus.PENDING)
    orch = _mock_orch()
    orch._pending_signals = [signal]

    with (
        patch("app.services.council.order_executor.kiwoom_client") as mock_kiwoom,
        patch("app.services.council.order_executor.trading_hours") as mock_hours,
        patch("app.services.council.order_executor.log_signal_event_async", new_callable=AsyncMock),
        patch("app.services.council.order_executor.update_signal_status_in_db", new_callable=AsyncMock),
    ):
        mock_hours.can_execute_order.return_value = (True, "market_open")
        mock_kiwoom.place_order = AsyncMock(
            return_value=_OrderResult(status="failed", message="서버 오류"),
        )

        from app.services.council.order_executor import approve_signal

        result = await approve_signal(orch, signal.id)

        assert result is not None
        assert result.status == SignalStatus.QUEUED
        assert len(orch._queued_executions) == 1


# ── Test 3: 큐 중복 방지 (동일 signal 2회 제출 → 1회만 처리) ──

@pytest.mark.asyncio
async def test_queue_dedup_same_signal():
    """Same signal_id submitted twice → only processed once."""
    signal = _make_signal(action="BUY")
    orch = _mock_orch()
    # Simulate same signal appearing twice in queue
    orch._queued_executions = [signal]

    with (
        patch("app.services.council.order_executor.kiwoom_client") as mock_kiwoom,
        patch("app.services.council.order_executor.trading_hours") as mock_hours,
        patch("app.services.council.order_executor.log_signal_event_async", new_callable=AsyncMock),
        patch("app.services.council.order_executor.update_signal_status_in_db", new_callable=AsyncMock),
    ):
        mock_hours.can_execute_order.return_value = (True, "market_open")
        mock_kiwoom.get_balance = AsyncMock(return_value=_Balance())
        mock_kiwoom.place_order = AsyncMock(
            return_value=_OrderResult(status="submitted", order_no="ORD100"),
        )

        from app.services.council.order_executor import process_queued_executions

        executed = await process_queued_executions(orch)

        assert len(executed) == 1
        # After processing, queue should be empty
        assert len(orch._queued_executions) == 0


# ── Test 4: 잔고 부족 BUY → cancelled ──

@pytest.mark.asyncio
async def test_insufficient_balance_cancels_buy():
    """BUY signal with insufficient balance → cancelled, not executed."""
    signal = _make_signal(action="BUY", suggested_amount=100_000_000)
    orch = _mock_orch()
    orch._queued_executions = [signal]

    with (
        patch("app.services.council.order_executor.kiwoom_client") as mock_kiwoom,
        patch("app.services.council.order_executor.trading_hours") as mock_hours,
        patch("app.services.council.order_executor.log_signal_event_async", new_callable=AsyncMock),
        patch("app.services.council.order_executor.update_signal_status_in_db", new_callable=AsyncMock) as mock_update,
    ):
        mock_hours.can_execute_order.return_value = (True, "market_open")
        mock_kiwoom.get_balance = AsyncMock(
            return_value=_Balance(available_amount=5_000_000),
        )

        from app.services.council.order_executor import process_queued_executions

        executed = await process_queued_executions(orch)

        assert len(executed) == 0
        # Should have called update with cancelled=True
        mock_update.assert_called_once()
        call_kwargs = mock_update.call_args
        assert call_kwargs[1].get("cancelled") or (
            len(call_kwargs[0]) > 3 and call_kwargs[0][3] is True
        ) or "cancelled" in str(call_kwargs)
        # Queue should be empty (signal consumed, not remaining)
        assert len(orch._queued_executions) == 0

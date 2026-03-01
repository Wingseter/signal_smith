"""risk_gate.py 경계값 테스트 — Phase 3 E1 (P0).

Gate A/B/C, 데이터 품질 게이트, determine_action, clamp 함수.
"""

import pytest
from dataclasses import dataclass
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch


# ── Mock helpers ──

@dataclass
class _Balance:
    available_amount: int = 0
    total_evaluation: int = 0


@dataclass
class _Holding:
    symbol: str = ""
    quantity: int = 0


def _make_holdings(symbols: List[str]) -> List[_Holding]:
    return [_Holding(symbol=s, quantity=10) for s in symbols]


# kiwoom_client is imported lazily inside check_buy_gates via
# "from app.services.kiwoom.rest_client import kiwoom_client"
# so we patch at the source module level.
_KIWOOM_PATCH = "app.services.kiwoom.rest_client.kiwoom_client"


# ── Gate A: min_position ──

@pytest.mark.asyncio
async def test_gate_a_blocks_below_min_position():
    """Gate A: suggested_amount < total_assets * min_position_pct → blocked."""
    mock_client = AsyncMock()
    mock_client.get_balance.return_value = _Balance(
        available_amount=10_000_000, total_evaluation=0,
    )
    mock_client.get_holdings.return_value = []

    with (
        patch(_KIWOOM_PATCH, mock_client),
        patch("app.services.council.risk_gate.log_signal_event_async", new_callable=AsyncMock),
        patch("app.services.council.risk_gate.settings") as mock_settings,
    ):
        mock_settings.min_position_pct = 8.0
        mock_settings.min_cash_reserve_pct = 5.0
        mock_settings.max_positions = 10

        from app.services.council.risk_gate import check_buy_gates

        # 10M * 8% = 800K, suggest 500K → blocked
        result = await check_buy_gates("005930", 500_000)
        assert result.blocked is True
        assert result.gate_name == "A"


@pytest.mark.asyncio
async def test_gate_a_passes_at_boundary():
    """Gate A: suggested_amount == min → passes gate A."""
    mock_client = AsyncMock()
    mock_client.get_balance.return_value = _Balance(
        available_amount=10_000_000, total_evaluation=0,
    )
    mock_client.get_holdings.return_value = []

    with (
        patch(_KIWOOM_PATCH, mock_client),
        patch("app.services.council.risk_gate.log_signal_event_async", new_callable=AsyncMock),
        patch("app.services.council.risk_gate.settings") as mock_settings,
    ):
        mock_settings.min_position_pct = 8.0
        mock_settings.min_cash_reserve_pct = 5.0
        mock_settings.max_positions = 10

        from app.services.council.risk_gate import check_buy_gates

        # 10M * 8% = 800K, suggest 800K → passes A
        result = await check_buy_gates("005930", 800_000)
        assert result.blocked is False


# ── Gate B: cash_reserve ──

@pytest.mark.asyncio
async def test_gate_b_blocks_insufficient_cash():
    """Gate B: available - suggested < total * min_cash_reserve_pct → blocked."""
    mock_client = AsyncMock()
    mock_client.get_balance.return_value = _Balance(
        available_amount=2_000_000, total_evaluation=8_000_000,
    )
    mock_client.get_holdings.return_value = []

    with (
        patch(_KIWOOM_PATCH, mock_client),
        patch("app.services.council.risk_gate.log_signal_event_async", new_callable=AsyncMock),
        patch("app.services.council.risk_gate.settings") as mock_settings,
    ):
        mock_settings.min_position_pct = 8.0
        mock_settings.min_cash_reserve_pct = 5.0  # 10M * 5% = 500K
        mock_settings.max_positions = 10

        from app.services.council.risk_gate import check_buy_gates

        # available=2M, buy=1.6M → cash_after=400K < min_cash=500K → blocked
        result = await check_buy_gates("005930", 1_600_000)
        assert result.blocked is True
        assert result.gate_name == "B"


@pytest.mark.asyncio
async def test_gate_b_passes_at_boundary():
    """Gate B: cash_after_buy == min_cash → passes."""
    mock_client = AsyncMock()
    mock_client.get_balance.return_value = _Balance(
        available_amount=2_000_000, total_evaluation=8_000_000,
    )
    mock_client.get_holdings.return_value = []

    with (
        patch(_KIWOOM_PATCH, mock_client),
        patch("app.services.council.risk_gate.log_signal_event_async", new_callable=AsyncMock),
        patch("app.services.council.risk_gate.settings") as mock_settings,
    ):
        mock_settings.min_position_pct = 8.0
        mock_settings.min_cash_reserve_pct = 5.0  # min_cash = 500K
        mock_settings.max_positions = 10

        from app.services.council.risk_gate import check_buy_gates

        # available=2M, buy=1.5M → cash_after=500K == min_cash=500K → passes
        result = await check_buy_gates("005930", 1_500_000)
        assert result.blocked is False


# ── Gate C: max_positions ──

@pytest.mark.asyncio
async def test_gate_c_blocks_new_symbol_at_max():
    """Gate C: new symbol + current_count >= max_positions → blocked."""
    mock_client = AsyncMock()
    mock_client.get_balance.return_value = _Balance(
        available_amount=50_000_000, total_evaluation=50_000_000,
    )
    mock_client.get_holdings.return_value = _make_holdings(
        [f"0000{i:02d}" for i in range(10)]
    )

    with (
        patch(_KIWOOM_PATCH, mock_client),
        patch("app.services.council.risk_gate.log_signal_event_async", new_callable=AsyncMock),
        patch("app.services.council.risk_gate.settings") as mock_settings,
    ):
        mock_settings.min_position_pct = 1.0
        mock_settings.min_cash_reserve_pct = 1.0
        mock_settings.max_positions = 10

        from app.services.council.risk_gate import check_buy_gates

        result = await check_buy_gates("999999", 5_000_000)
        assert result.blocked is True
        assert result.gate_name == "C"


@pytest.mark.asyncio
async def test_gate_c_passes_additional_buy():
    """Gate C: same symbol additional buy even at max_positions → passes."""
    mock_client = AsyncMock()
    symbols = [f"0000{i:02d}" for i in range(10)]
    mock_client.get_balance.return_value = _Balance(
        available_amount=50_000_000, total_evaluation=50_000_000,
    )
    mock_client.get_holdings.return_value = _make_holdings(symbols)

    with (
        patch(_KIWOOM_PATCH, mock_client),
        patch("app.services.council.risk_gate.log_signal_event_async", new_callable=AsyncMock),
        patch("app.services.council.risk_gate.settings") as mock_settings,
    ):
        mock_settings.min_position_pct = 1.0
        mock_settings.min_cash_reserve_pct = 1.0
        mock_settings.max_positions = 10

        from app.services.council.risk_gate import check_buy_gates

        # Additional buy for existing holding
        result = await check_buy_gates(symbols[0], 5_000_000)
        assert result.blocked is False


# ── Data quality gate ──

def test_data_quality_gate_blocks_on_two_failures():
    from app.services.council.risk_gate import check_data_quality_gate

    result = check_data_quality_gate("005930", failures=2)
    assert result.blocked is True
    assert result.gate_name == "data_quality"


def test_data_quality_gate_passes_on_one_failure():
    from app.services.council.risk_gate import check_data_quality_gate

    result = check_data_quality_gate("005930", failures=1)
    assert result.blocked is False


# ── determine_action boundary values ──

def test_determine_action_buy_news_trigger():
    from app.services.council.risk_gate import determine_action

    # final_percent >= 10, avg_score >= 6 → BUY
    result = determine_action(
        final_percent=10.0, quant_score=6, fundamental_score=6,
        news_score=7, trigger_source="news",
    )
    assert result == "BUY"


def test_determine_action_hold_below_threshold():
    from app.services.council.risk_gate import determine_action

    # final_percent=9 < 10, avg_score=5.5 < 6 → HOLD for news trigger
    result = determine_action(
        final_percent=9.0, quant_score=5, fundamental_score=6,
        news_score=6, trigger_source="news",
    )
    assert result == "HOLD"


def test_determine_action_sell_negative_percent():
    from app.services.council.risk_gate import determine_action

    result = determine_action(
        final_percent=-5.0, quant_score=7, fundamental_score=7,
        news_score=8, trigger_source="news",
    )
    assert result == "SELL"


def test_determine_action_sell_low_news_score():
    from app.services.council.risk_gate import determine_action

    result = determine_action(
        final_percent=20.0, quant_score=8, fundamental_score=8,
        news_score=3, trigger_source="news",
    )
    assert result == "SELL"


# ── clamp_stop_loss / clamp_target_price ──

def test_clamp_stop_loss_within_bounds():
    with patch("app.services.council.risk_gate.settings") as mock_settings:
        mock_settings.max_stop_loss_percent = 15.0
        mock_settings.min_stop_loss_percent = 3.0
        mock_settings.stop_loss_percent = 5.0

        from app.services.council.risk_gate import clamp_stop_loss

        # current=100000, min=85000, max=97000
        result = clamp_stop_loss(90000, 100000)
        assert result == 90000


def test_clamp_stop_loss_default_when_none():
    with patch("app.services.council.risk_gate.settings") as mock_settings:
        mock_settings.max_stop_loss_percent = 15.0
        mock_settings.min_stop_loss_percent = 3.0
        mock_settings.stop_loss_percent = 5.0

        from app.services.council.risk_gate import clamp_stop_loss

        # None → default: current * (1 - stop_loss_percent/100) = 95000
        result = clamp_stop_loss(None, 100000)
        assert result == 95000


def test_clamp_target_price_within_bounds():
    with patch("app.services.council.risk_gate.settings") as mock_settings:
        mock_settings.min_take_profit_percent = 5.0
        mock_settings.max_take_profit_percent = 50.0
        mock_settings.take_profit_percent = 20.0

        from app.services.council.risk_gate import clamp_target_price

        # current=100000, min=105000, max=150000
        result = clamp_target_price(120000, 100000)
        assert result == 120000


def test_clamp_target_price_default_when_none():
    with patch("app.services.council.risk_gate.settings") as mock_settings:
        mock_settings.min_take_profit_percent = 5.0
        mock_settings.max_take_profit_percent = 50.0
        mock_settings.take_profit_percent = 20.0

        from app.services.council.risk_gate import clamp_target_price

        # None → default: current * (1 + take_profit_percent/100) = 120000
        result = clamp_target_price(None, 100000)
        assert result == 120000

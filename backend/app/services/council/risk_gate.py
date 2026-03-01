"""매수/매도 게이트 검증 및 액션 결정 로직.

orchestrator.py에서 추출. 모든 함수는 순수 함수이거나
kiwoom_client / settings만 참조 (orchestrator 의존 없음).
"""

import logging
from dataclasses import dataclass
from typing import Optional

from app.config import settings
from app.core.audit import log_signal_event_async

logger = logging.getLogger(__name__)


@dataclass
class GateResult:
    blocked: bool
    reason: str
    gate_name: str


async def check_buy_gates(
    symbol: str,
    suggested_amount: int,
    signal_id: Optional[int] = None,
) -> GateResult:
    """체결 전 3중 게이트 (BUY 시그널만).

    Gate A: 최소 포지션 금액
    Gate B: 현금 보유 비율
    Gate C: 최대 보유 종목 수
    """
    from app.services.kiwoom.rest_client import kiwoom_client

    try:
        balance = await kiwoom_client.get_balance()
        holdings = await kiwoom_client.get_holdings()
        total_assets = balance.available_amount + balance.total_evaluation

        if total_assets <= 0:
            total_assets = suggested_amount  # fallback

        # Gate A: 최소 포지션 금액
        min_position_amount = int(total_assets * settings.min_position_pct / 100)
        if suggested_amount < min_position_amount:
            reason = (
                f"Gate A 최소 포지션 미달: "
                f"제안 {suggested_amount:,}원 < "
                f"최소 {min_position_amount:,}원 "
                f"(총자산 {total_assets:,}원 x {settings.min_position_pct}%)"
            )
            await log_signal_event_async(
                "gate_block_min_position", symbol, "BUY",
                signal_id=signal_id, details={"reason": reason},
            )
            return GateResult(blocked=True, reason=reason, gate_name="A")

        # Gate B: 현금 보유 비율
        cash_after_buy = balance.available_amount - suggested_amount
        min_cash = int(total_assets * settings.min_cash_reserve_pct / 100)
        if cash_after_buy < min_cash:
            reason = (
                f"Gate B 현금 보유 부족: "
                f"매수 후 예상 현금 {cash_after_buy:,}원 < "
                f"최소 {min_cash:,}원 "
                f"(총자산 {total_assets:,}원 x {settings.min_cash_reserve_pct}%)"
            )
            await log_signal_event_async(
                "gate_block_cash_reserve", symbol, "BUY",
                signal_id=signal_id, details={"reason": reason},
            )
            return GateResult(blocked=True, reason=reason, gate_name="B")

        # Gate C: 최대 보유 종목 수
        current_holding_count = len([h for h in holdings if h.quantity > 0])
        is_additional_buy = any(
            h.symbol == symbol for h in holdings if h.quantity > 0
        )
        if current_holding_count >= settings.max_positions and not is_additional_buy:
            reason = (
                f"Gate C 최대 종목 수 초과: "
                f"현재 {current_holding_count}종목 >= "
                f"최대 {settings.max_positions}종목"
            )
            await log_signal_event_async(
                "gate_block_max_positions", symbol, "BUY",
                signal_id=signal_id, details={"reason": reason},
            )
            return GateResult(blocked=True, reason=reason, gate_name="C")

    except Exception as e:
        reason = f"게이트 검증 오류: {e}"
        logger.warning(f"게이트 검증 실패, 안전하게 차단: {symbol} - {e}")
        await log_signal_event_async(
            "gate_block_error", symbol, "BUY",
            signal_id=signal_id, details={"error": str(e)},
        )
        return GateResult(blocked=True, reason=reason, gate_name="error")

    return GateResult(blocked=False, reason="", gate_name="")


def check_data_quality_gate(
    symbol: str,
    failures: int,
    signal_id: Optional[int] = None,
) -> GateResult:
    """데이터 품질 게이트 — 2건 이상 분석 실패 시 차단."""
    if failures >= 2:
        reason = (
            f"데이터 품질 게이트 차단: {symbol} — "
            f"분석 실패 {failures}건 (2건 이상, 시그널 폐기)"
        )
        return GateResult(blocked=True, reason=reason, gate_name="data_quality")
    return GateResult(blocked=False, reason="", gate_name="")


def determine_action(
    final_percent: float,
    quant_score: int,
    fundamental_score: int,
    news_score: int,
    trigger_source: str = "news",
) -> str:
    """투자 액션 결정 (BUY/SELL/HOLD)."""
    avg_score = (quant_score + fundamental_score) / 2

    # SELL 조건
    if trigger_source == "news" and news_score <= 3:
        logger.info(f"SELL 결정: 부정적 뉴스 (점수: {news_score})")
        return "SELL"

    if avg_score <= 4:
        logger.info(f"SELL 결정: 낮은 분석 점수 (평균: {avg_score:.1f})")
        return "SELL"

    if final_percent < 0:
        logger.info(f"SELL 결정: AI 매도 권장 (비율: {final_percent}%)")
        return "SELL"

    # 퀀트 트리거 BUY 조건 (뉴스 점수 무시)
    if trigger_source == "quant":
        if final_percent >= 10 and avg_score >= 5.5:
            logger.info(f"BUY 결정 [퀀트]: 분석 긍정 (비율: {final_percent}%, 평균: {avg_score:.1f})")
            return "BUY"
        if final_percent >= 15 and avg_score >= 5:
            logger.info(f"BUY 결정 [퀀트]: 높은 비율 (비율: {final_percent}%, 평균: {avg_score:.1f})")
            return "BUY"

    # 뉴스 트리거 BUY 조건
    if final_percent >= 10 and avg_score >= 6:
        logger.info(f"BUY 결정: 긍정적 분석 (비율: {final_percent}%, 평균: {avg_score:.1f})")
        return "BUY"

    if news_score >= 8 and avg_score >= 5:
        logger.info(f"BUY 결정: 강한 뉴스 신호 (뉴스: {news_score}, 평균: {avg_score:.1f})")
        return "BUY"

    # HOLD
    logger.info(f"HOLD 결정: 조건 미충족 (비율: {final_percent}%, 평균: {avg_score:.1f}, 트리거: {trigger_source})")
    return "HOLD"


def clamp_stop_loss(gpt_stop_loss: Optional[int], current_price: int) -> Optional[int]:
    """GPT 손절가를 config 바운드 내로 제한."""
    if not current_price:
        return None

    min_price = int(current_price * (1 - settings.max_stop_loss_percent / 100))
    max_price = int(current_price * (1 - settings.min_stop_loss_percent / 100))

    if gpt_stop_loss:
        return max(min_price, min(max_price, gpt_stop_loss))

    return int(current_price * (1 - settings.stop_loss_percent / 100))


def clamp_target_price(gpt_target: Optional[int], current_price: int) -> Optional[int]:
    """GPT 목표가를 config 바운드 내로 제한."""
    if not current_price:
        return None

    min_price = int(current_price * (1 + settings.min_take_profit_percent / 100))
    max_price = int(current_price * (1 + settings.max_take_profit_percent / 100))

    if gpt_target:
        return max(min_price, min(max_price, gpt_target))

    return int(current_price * (1 + settings.take_profit_percent / 100))

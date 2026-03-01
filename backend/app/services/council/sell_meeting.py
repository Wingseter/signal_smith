"""매도 회의 및 리밸런싱 리뷰 로직.

orchestrator.py에서 추출. orchestrator 인스턴스를 첫 번째 인자로 받아
mutable state 접근 (circular import 회피).
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from app.config import settings
from app.services.kiwoom.rest_client import kiwoom_client, OrderSide, OrderType
from .models import (
    CouncilMeeting, CouncilMessage, InvestmentSignal,
    SignalStatus, AnalystRole,
)
from .quant_analyst import quant_analyst
from .trading_hours import trading_hours, get_kst_now
from .cost_manager import cost_manager, AnalysisDepth

logger = logging.getLogger(__name__)


async def run_sell_meeting(
    orch,
    symbol: str,
    company_name: str,
    sell_reason: str,
    current_holdings: int,
    avg_buy_price: int,
    current_price: int,
) -> CouncilMeeting:
    """SELL 전용 회의 실행.

    Args:
        orch: CouncilOrchestrator instance (mutable state 접근).
    """
    meeting = CouncilMeeting(
        symbol=symbol,
        company_name=company_name,
        news_title=f"매도 검토: {sell_reason}",
        news_score=3,
    )

    # 1. 매도 검토 소집 메시지
    profit_loss = (
        (current_price - avg_buy_price) / avg_buy_price * 100
        if avg_buy_price > 0 else 0.0
    )
    opening_msg = CouncilMessage(
        role=AnalystRole.MODERATOR,
        speaker="회의 중재자",
        content=f"""🔴 **매도 검토 회의 소집**

종목: {company_name} ({symbol})
매도 사유: {sell_reason}

📊 포지션 현황:
• 보유 수량: {current_holdings:,}주
• 평균 매입가: {avg_buy_price:,}원
• 현재가: {current_price:,}원
• 수익률: {profit_loss:+.1f}%

각 분석가의 매도 의견을 청취합니다.""",
        data={
            "meeting_type": "sell",
            "current_holdings": current_holdings,
            "avg_buy_price": avg_buy_price,
            "current_price": current_price,
            "profit_loss_rate": profit_loss,
        },
    )
    meeting.add_message(opening_msg)
    await orch._notify_meeting_update(meeting)

    # 기술적 데이터 조회
    technical_data = await orch._fetch_technical_data(symbol)

    # 2. GPT 퀀트 매도 분석
    meeting.current_round = 1
    try:
        quant_msg = await asyncio.wait_for(
            quant_analyst.analyze(
                symbol=symbol,
                company_name=company_name,
                news_title=f"매도 검토: {sell_reason}",
                previous_messages=meeting.messages,
                technical_data=technical_data,
                request=(
                    f"현재 보유 중인 종목의 매도 타이밍을 분석해주세요. "
                    f"수익률 {profit_loss:+.1f}%, 사유: {sell_reason}"
                ),
            ),
            timeout=60.0,
        )
        meeting.add_message(quant_msg)
        await orch._notify_meeting_update(meeting)
    except (asyncio.TimeoutError, Exception) as e:
        logger.error(f"매도 검토 중 퀀트 분석가 API 호출 실패 또는 타임아웃: {e}")
        quant_msg = CouncilMessage(
            role=AnalystRole.GPT_QUANT,
            speaker="시스템",
            content=(
                f"[시스템 경고] 분석 지연 발생. "
                f"수익률 {profit_loss:+.1f}% 기반 기계적 매도를 우선 고려합니다."
            ),
            data={
                "suggested_percent": 30 if profit_loss >= 0 else 100,
                "score": 5,
            },
        )
        meeting.add_message(quant_msg)
        await orch._notify_meeting_update(meeting)

    # 3. SELL 시그널 생성
    quant_score = quant_msg.data.get("score", 5) if quant_msg.data else 5

    if profit_loss < -settings.stop_loss_percent:
        sell_percent = 100
        action = "SELL"
    elif profit_loss > settings.take_profit_percent:
        sell_percent = 50
        action = "PARTIAL_SELL"
    else:
        sell_percent = quant_msg.data.get("suggested_percent", 30) if quant_msg.data else 30
        action = "SELL" if sell_percent >= 50 else "PARTIAL_SELL"

    sell_quantity = int(current_holdings * sell_percent / 100)
    sell_amount = sell_quantity * current_price

    signal = InvestmentSignal(
        symbol=symbol,
        company_name=company_name,
        action=action,
        allocation_percent=sell_percent,
        suggested_amount=sell_amount,
        suggested_quantity=sell_quantity,
        quant_summary=f"매도 분석: {quant_msg.content[:100]}...",
        fundamental_summary=sell_reason,
        consensus_reason=f"매도 사유: {sell_reason}, 수익률: {profit_loss:+.1f}%",
        confidence=0.7 + (0.2 if abs(profit_loss) > 10 else 0),
        quant_score=quant_score,
        fundamental_score=5,
    )

    # 자동 체결 처리
    if orch.auto_execute:
        can_trade, trade_reason = trading_hours.can_execute_order()
        if can_trade or not orch.respect_trading_hours:
            try:
                order_result = await kiwoom_client.place_order(
                    symbol=symbol,
                    side=OrderSide.SELL,
                    quantity=sell_quantity,
                    price=0,
                    order_type=OrderType.MARKET,
                )
                if order_result.status == "submitted":
                    signal.status = SignalStatus.AUTO_EXECUTED
                    signal.executed_at = get_kst_now()
                    logger.info(
                        f"✅ 자동 매도 성공: {symbol} {sell_quantity}주 "
                        f"(주문번호: {order_result.order_no})"
                    )
                else:
                    signal.status = SignalStatus.QUEUED
                    orch._queued_executions.append(signal)
                    logger.warning(
                        f"⚠️ 자동 매도 실패, 대기 큐 추가: {symbol} - {order_result.message}"
                    )
            except Exception as e:
                signal.status = SignalStatus.QUEUED
                orch._queued_executions.append(signal)
                logger.error(f"❌ 자동 매도 오류, 대기 큐 추가: {symbol} - {e}")
        else:
            signal.status = SignalStatus.QUEUED
            orch._queued_executions.append(signal)
            logger.info(f"⏳ 매도 거래 시간 대기: {symbol} - {trade_reason}")
    else:
        signal.status = SignalStatus.PENDING

    meeting.signal = signal
    meeting.consensus_reached = True
    meeting.ended_at = datetime.now()

    # 결론 메시지
    conclusion_msg = CouncilMessage(
        role=AnalystRole.MODERATOR,
        speaker="회의 중재자",
        content=f"""⚖️ **매도 회의 결론**

📌 결정: {action}
💰 매도 비율: {sell_percent}%
📦 매도 수량: {sell_quantity:,}주
💵 예상 금액: {sell_amount:,}원

상태: {"✅ 자동 체결됨" if signal.status == SignalStatus.AUTO_EXECUTED else "⏳ 구매 대기 중 (장 개시 후 자동 체결)" if signal.status == SignalStatus.QUEUED else "⏳ 승인 대기 중"}""",
        data=signal.to_dict(),
    )
    meeting.add_message(conclusion_msg)
    await orch._notify_meeting_update(meeting)

    # 저장
    orch._meetings.append(meeting)
    if signal.status == SignalStatus.PENDING:
        orch._pending_signals.append(signal)

    await orch._notify_signal(signal)
    await orch._persist_signal_to_db(signal, trigger_source=meeting.trigger_source)

    cost_manager.record_analysis(symbol, AnalysisDepth.LIGHT)

    return meeting


async def run_rebalance_review(
    orch,
    symbol: str,
    company_name: str,
    current_holdings: int,
    avg_buy_price: int,
    current_price: int,
    prev_target_price: Optional[int] = None,
    prev_stop_loss: Optional[int] = None,
) -> Optional[dict]:
    """보유종목 일일 리밸런싱 재평가 (GPT LIGHT 단독)."""
    from .risk_gate import clamp_target_price, clamp_stop_loss

    try:
        # 1. 최신 차트 데이터 조회
        technical_data = await orch._fetch_technical_data(symbol)
        if not technical_data:
            logger.warning(f"[리밸런싱] {symbol} 차트 데이터 없음 → 스킵")
            return None

        if technical_data.current_price > 0:
            current_price = technical_data.current_price

        profit_rate = (
            (current_price - avg_buy_price) / avg_buy_price * 100
            if avg_buy_price > 0 else 0
        )

        # 2. GPT 퀀트 분석
        prev_target_str = f"{prev_target_price:,}원" if prev_target_price else "미설정"
        prev_stop_str = f"{prev_stop_loss:,}원" if prev_stop_loss else "미설정"

        request_prompt = (
            f"보유종목 일일 재평가. "
            f"보유수량 {current_holdings:,}주, 평균매입가 {avg_buy_price:,}원, "
            f"현재가 {current_price:,}원, 수익률 {profit_rate:+.1f}%. "
            f"이전 목표가 {prev_target_str}, 이전 손절가 {prev_stop_str}. "
            f"최신 차트 기반으로 목표가와 손절가를 재설정해주세요."
        )

        quant_msg = await asyncio.wait_for(
            quant_analyst.analyze(
                symbol=symbol,
                company_name=company_name,
                news_title=f"일일 리밸런싱 재평가 (수익률 {profit_rate:+.1f}%)",
                previous_messages=[],
                technical_data=technical_data,
                request=request_prompt,
            ),
            timeout=60.0,
        )

        # 3. 응답에서 값 추출 → clamp 적용
        new_target = quant_msg.data.get("target_price") if quant_msg.data else None
        new_stop = quant_msg.data.get("stop_loss") if quant_msg.data else None
        score = quant_msg.data.get("score", 5) if quant_msg.data else 5

        new_target = clamp_target_price(new_target, current_price)
        new_stop = clamp_stop_loss(new_stop, current_price)

        # 4. 비용 기록
        cost_manager.record_analysis(symbol, AnalysisDepth.LIGHT)

        result = {
            "symbol": symbol,
            "company_name": company_name,
            "current_price": current_price,
            "profit_rate": profit_rate,
            "new_target_price": new_target,
            "new_stop_loss": new_stop,
            "prev_target_price": prev_target_price,
            "prev_stop_loss": prev_stop_loss,
            "score": score,
            "analysis": quant_msg.content[:500],
            "recommend_sell": score <= 3,
        }

        logger.info(
            f"[리밸런싱] {symbol} ({company_name}) "
            f"score={score}, target={new_target}, stop={new_stop}, "
            f"recommend_sell={result['recommend_sell']}"
        )

        return result

    except asyncio.TimeoutError:
        logger.error(f"[리밸런싱] {symbol} GPT 타임아웃")
        return None
    except Exception as e:
        logger.error(f"[리밸런싱] {symbol} 오류: {e}")
        return None

"""주문 실행 · 큐 관리 · DB 동기화 로직.

orchestrator.py에서 추출. 모든 함수는 orchestrator 인스턴스를
첫 번째 인자로 받아 mutable state에 접근.
"""

import logging
from datetime import date
from typing import Optional, List

from app.core.audit import log_signal_event_async
from app.services.kiwoom.rest_client import kiwoom_client, OrderSide, OrderType
from .models import InvestmentSignal, SignalStatus
from .trading_hours import trading_hours, get_kst_now
from app.services.trading_service import trading_service

logger = logging.getLogger(__name__)


async def approve_signal(orch, signal_id: str) -> Optional[InvestmentSignal]:
    """시그널 승인 — BUY/SELL이면 즉시 체결 시도 또는 대기열 추가."""
    for signal in orch._pending_signals:
        if signal.id == signal_id and signal.status == SignalStatus.PENDING:
            signal.status = SignalStatus.APPROVED
            logger.info(f"시그널 승인됨: {signal.symbol} {signal.action}")
            await update_signal_status_in_db(orch, signal)

            if signal.action in ["BUY", "SELL"]:
                can_trade, reason = trading_hours.can_execute_order()

                if can_trade or not orch.respect_trading_hours:
                    try:
                        side = OrderSide.BUY if signal.action == "BUY" else OrderSide.SELL
                        order_result = await kiwoom_client.place_order(
                            symbol=signal.symbol,
                            side=side,
                            quantity=signal.suggested_quantity,
                            price=0,
                            order_type=OrderType.MARKET,
                        )

                        if order_result.status == "submitted":
                            signal.status = SignalStatus.EXECUTED
                            signal.executed_at = get_kst_now()
                            logger.info(
                                f"✅ 승인 후 즉시 체결: {signal.symbol} {signal.action} "
                                f"{signal.suggested_quantity}주 (주문번호: {order_result.order_no})"
                            )
                            await log_signal_event_async(
                                "order_executed", signal.symbol, signal.action,
                                signal_id=getattr(signal, "_db_id", None),
                                details={"order_no": order_result.order_no},
                            )
                            await update_signal_status_in_db(orch, signal, executed=True)
                        else:
                            logger.warning(
                                f"주문 실패, 대기열에 추가: {signal.symbol} - {order_result.message}"
                            )
                            signal.status = SignalStatus.QUEUED
                            orch._queued_executions.append(signal)
                            await update_signal_status_in_db(orch, signal)
                    except Exception as e:
                        logger.error(f"주문 오류, 대기열에 추가: {signal.symbol} - {e}")
                        signal.status = SignalStatus.QUEUED
                        orch._queued_executions.append(signal)
                        await update_signal_status_in_db(orch, signal)
                else:
                    logger.info(
                        f"거래 시간 외, 대기열에 추가: {signal.symbol} {signal.action} - {reason}"
                    )
                    signal.status = SignalStatus.QUEUED
                    orch._queued_executions.append(signal)
                    await update_signal_status_in_db(orch, signal)

            return signal
    return None


async def reject_signal(orch, signal_id: str) -> Optional[InvestmentSignal]:
    """시그널 거부."""
    for signal in orch._pending_signals:
        if signal.id == signal_id and signal.status == SignalStatus.PENDING:
            signal.status = SignalStatus.REJECTED
            logger.info(f"시그널 거부됨: {signal.symbol}")
            await update_signal_status_in_db(orch, signal, cancelled=True)
            return signal
    return None


async def execute_signal(orch, signal_id: str) -> Optional[InvestmentSignal]:
    """시그널 체결 (실제 주문 실행)."""
    for signal in orch._pending_signals:
        if signal.id == signal_id and signal.status == SignalStatus.APPROVED:
            can_trade, reason = trading_hours.can_execute_order()
            if not can_trade and orch.respect_trading_hours:
                logger.warning(f"거래 시간이 아님: {reason} - 대기 큐에 추가")
                orch._queued_executions.append(signal)
                return signal

            try:
                side = OrderSide.BUY if signal.action == "BUY" else OrderSide.SELL
                order_result = await kiwoom_client.place_order(
                    symbol=signal.symbol,
                    side=side,
                    quantity=signal.suggested_quantity,
                    price=0,
                    order_type=OrderType.MARKET,
                )

                if order_result.status == "submitted":
                    signal.status = SignalStatus.EXECUTED
                    signal.executed_at = get_kst_now()
                    logger.info(
                        f"✅ 시그널 체결 성공: {signal.symbol} {signal.action} "
                        f"{signal.suggested_quantity}주 (주문번호: {order_result.order_no})"
                    )
                    await log_signal_event_async(
                        "order_executed", signal.symbol, signal.action,
                        signal_id=getattr(signal, "_db_id", None),
                        details={"order_no": order_result.order_no},
                    )
                    await update_signal_status_in_db(orch, signal, executed=True)
                else:
                    logger.error(f"❌ 주문 실패: {signal.symbol} - {order_result.message}")
                    return None

            except Exception as e:
                logger.error(f"❌ 주문 실행 중 오류: {signal.symbol} - {e}")
                return None

            return signal
    return None


async def process_queued_executions(orch) -> List[InvestmentSignal]:
    """대기 중인 체결 처리 (거래 시간에 호출)."""
    can_trade, _ = trading_hours.can_execute_order()

    if not can_trade:
        logger.debug("거래 시간이 아님 - 대기 큐 처리 스킵")
        return []

    executed: List[InvestmentSignal] = []
    remaining: List[InvestmentSignal] = []

    available_balance = None
    try:
        balance = await kiwoom_client.get_balance()
        available_balance = balance.available_amount
    except Exception as e:
        logger.warning(f"잔고 조회 실패, 잔고 체크 없이 진행: {e}")

    for signal in orch._queued_executions:
        if signal.status in (SignalStatus.QUEUED, SignalStatus.PENDING, SignalStatus.APPROVED):
            if signal.action == "BUY" and available_balance is not None:
                if available_balance < signal.suggested_amount:
                    logger.warning(
                        f"잔고 부족 — 시그널 취소: {signal.symbol} "
                        f"(필요 {signal.suggested_amount:,}원 > 가용 {available_balance:,}원)"
                    )
                    await update_signal_status_in_db(orch, signal, executed=False, cancelled=True)
                    continue

            try:
                side = OrderSide.BUY if signal.action == "BUY" else OrderSide.SELL
                order_result = await kiwoom_client.place_order(
                    symbol=signal.symbol,
                    side=side,
                    quantity=signal.suggested_quantity,
                    price=0,
                    order_type=OrderType.MARKET,
                )

                if order_result.status == "submitted":
                    signal.status = SignalStatus.AUTO_EXECUTED
                    signal.executed_at = get_kst_now()
                    executed.append(signal)
                    logger.info(
                        f"✅ 대기 큐 체결: {signal.symbol} {signal.action} "
                        f"{signal.suggested_quantity}주 (주문번호: {order_result.order_no})"
                    )
                    await log_signal_event_async(
                        "order_executed", signal.symbol, signal.action,
                        signal_id=getattr(signal, "_db_id", None),
                        details={"order_no": order_result.order_no, "source": "queue"},
                    )
                    await orch._notify_signal(signal)
                    await update_signal_status_in_db(orch, signal, executed=True)
                else:
                    logger.error(
                        f"❌ 대기 큐 주문 실패: {signal.symbol} - {order_result.message}"
                    )
                    remaining.append(signal)

            except Exception as e:
                logger.error(f"❌ 대기 큐 체결 실패: {signal.symbol} - {e}")
                remaining.append(signal)
        else:
            remaining.append(signal)

    orch._queued_executions = remaining
    return executed


async def persist_signal_to_db(
    orch,
    signal: InvestmentSignal,
    trigger_source: str = "news",
    trigger_details: Optional[dict] = None,
    holding_deadline: Optional[date] = None,
) -> None:
    """Council 시그널을 DB에 저장."""
    try:
        is_executed = signal.status == SignalStatus.AUTO_EXECUTED
        db_id = await trading_service.create_trading_signal(
            symbol=signal.symbol,
            company_name=signal.company_name,
            signal_type=signal.action.lower(),
            strength=signal.confidence * 100,
            source_agent=trigger_source,
            reason=signal.consensus_reason[:1000],
            target_price=float(signal.target_price) if signal.target_price else None,
            stop_loss=float(signal.stop_loss_price) if signal.stop_loss_price else None,
            quantity=signal.suggested_quantity,
            signal_status=signal.status.value,
            trigger_details=trigger_details,
            holding_deadline=holding_deadline,
            quant_score=signal.quant_score,
            fundamental_score=signal.fundamental_score,
            allocation_percent=signal.allocation_percent,
            suggested_amount=signal.suggested_amount,
            is_executed=is_executed,
        )
        signal._db_id = db_id
        logger.info(f"Council signal → DB: {signal.symbol} {signal.action} (id={db_id})")
    except Exception as e:
        logger.error(f"Council signal DB 저장 실패: {signal.symbol} - {e}")


async def restore_pending_signals(orch) -> None:
    """서버 재시작 시 DB에서 미체결 시그널 복원."""
    try:
        pending_db_signals = await trading_service.get_pending_signals(limit=50)

        restored_queued = 0
        restored_pending = 0

        for s in pending_db_signals:
            quantity = s.get("quantity")
            if not quantity or quantity <= 0:
                logger.debug(f"수량 없는 시그널 스킵: {s['symbol']} (id={s['id']})")
                continue

            action = s["signal_type"].upper()
            if action == "HOLD":
                continue

            confidence = s["strength"] / 100.0

            target_price = int(s["target_price"]) if s.get("target_price") else None
            suggested_amount = s.get("suggested_amount") or (
                quantity * target_price if target_price else 0
            )
            signal = InvestmentSignal(
                id=f"r{s['id']}",
                symbol=s["symbol"],
                company_name=s.get("company_name", ""),
                action=action,
                suggested_quantity=quantity,
                suggested_amount=suggested_amount,
                allocation_percent=s.get("allocation_percent", 0.0),
                target_price=target_price,
                stop_loss_price=int(s["stop_loss"]) if s.get("stop_loss") else None,
                consensus_reason=s.get("reason", ""),
                confidence=confidence,
                quant_score=s.get("quant_score", 0),
                fundamental_score=s.get("fundamental_score", 0),
            )
            signal._db_id = s["id"]

            original_status = s.get("signal_status", "")
            if original_status == "queued":
                signal.status = SignalStatus.QUEUED
                orch._queued_executions.append(signal)
                restored_queued += 1
            elif original_status == "pending":
                signal.status = SignalStatus.PENDING
                orch._pending_signals.append(signal)
                restored_pending += 1
            else:
                if orch.auto_execute and confidence >= orch.min_confidence:
                    signal.status = SignalStatus.QUEUED
                    orch._queued_executions.append(signal)
                    restored_queued += 1
                else:
                    signal.status = SignalStatus.PENDING
                    orch._pending_signals.append(signal)
                    restored_pending += 1

        if restored_queued or restored_pending:
            logger.info(
                f"✅ 미체결 시그널 복원 완료: "
                f"대기큐 {restored_queued}건, 승인대기 {restored_pending}건"
            )
        else:
            logger.info("미체결 시그널 없음 (복원 대상 0건)")

    except Exception as e:
        logger.error(f"미체결 시그널 복원 실패: {e}")


async def update_signal_status_in_db(
    orch,
    signal: InvestmentSignal,
    executed: bool = False,
    cancelled: bool = False,
) -> None:
    """DB 시그널 상태 업데이트."""
    db_id = getattr(signal, "_db_id", None)
    if not db_id:
        return
    try:
        from app.core.database import async_session_maker
        from app.models import TradingSignal as TradingSignalModel
        from sqlalchemy import select

        async with async_session_maker() as session:
            result = await session.execute(
                select(TradingSignalModel).where(TradingSignalModel.id == db_id)
            )
            db_signal = result.scalar_one_or_none()
            if db_signal:
                db_signal.is_executed = executed
                db_signal.signal_status = (
                    "cancelled" if cancelled else signal.status.value
                )
                await session.commit()
    except Exception as e:
        logger.error(f"DB 시그널 상태 업데이트 실패 (id={db_id}): {e}")

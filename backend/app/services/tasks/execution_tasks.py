"""Signal execution and queue processing tasks.

Extracted from signal_tasks.py — execution-related Celery tasks.
"""

import json
import logging
import time
from datetime import date, datetime
from typing import Optional

from sqlalchemy import select

from app.core.celery_app import celery_app
from app.core.database import get_sync_db
from app.config import settings
from app.models.transaction import TradingSignal

from ._common import is_market_hours, run_async

logger = logging.getLogger(__name__)


@celery_app.task(name="app.services.tasks.auto_execute_signal")
def auto_execute_signal(signal_id: int, quantity: int):
    """Auto-execute a trading signal if conditions are met."""
    if not settings.trading_enabled:
        return {"status": "error", "reason": "trading_disabled"}

    try:
        with get_sync_db() as db:
            signal = db.execute(
                select(TradingSignal).where(TradingSignal.id == signal_id)
            ).scalar_one_or_none()

            if not signal or signal.is_executed:
                return {"status": "error", "reason": "invalid_signal"}

            from app.services.trading_service import trading_service
            from .notification_tasks import send_notification

            side = "buy" if signal.signal_type == "buy" else "sell"
            price = int(signal.target_price) if signal.target_price else 0
            order_result = run_async(
                trading_service.place_order(
                    user_id=1,
                    symbol=signal.symbol,
                    side=side,
                    quantity=quantity,
                    price=price,
                    order_type="limit" if price > 0 else "market",
                )
            )

            if order_result.get("success"):
                signal.is_executed = True
                db.commit()

                send_notification.delay(
                    "order_executed",
                    f"[주문실행] {signal.signal_type.upper()} {signal.symbol} x {quantity}",
                )

            return {
                "status": "success" if order_result.get("success") else "failed",
                "signal_id": signal_id,
                "order_result": order_result,
            }

    except Exception as e:
        logger.error(f"Auto execution failed for signal {signal_id}: {e}")
        return {"status": "error", "error": str(e)}


@celery_app.task(
    name="app.services.tasks.process_council_queue",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def process_council_queue(self):
    """Process queued council executions when market opens (DB-based)."""
    if not is_market_hours():
        return {"status": "skipped", "reason": "market_closed"}

    try:
        return run_async(_process_council_queue_from_db())
    except Exception as e:
        logger.error(f"Council queue processing failed: {e}")
        self.retry(exc=e)


@celery_app.task(
    name="app.services.tasks.rebalance_holdings",
    bind=True,
    time_limit=600,
    soft_time_limit=540,
)
def rebalance_holdings(self):
    """장 마감 후 보유종목 일일 리밸런싱 재평가.

    매일 15:40 KST에 실행.
    """
    from app.services.council.trading_hours import trading_hours

    if not trading_hours.is_trading_day():
        logger.info("비거래일 — 리밸런싱 스킵")
        return {"status": "skipped", "reason": "not_trading_day"}

    try:
        from .monitoring_tasks import _get_cached_holdings, _get_active_signal_prices

        holdings = run_async(_get_cached_holdings())

        if not holdings:
            logger.info("보유종목 없음 — 리밸런싱 스킵")
            return {"status": "skipped", "reason": "no_holdings"}

        logger.info(f"[리밸런싱] 보유종목 {len(holdings)}건 재평가 시작")

        from app.services.council.orchestrator import council_orchestrator

        reviewed = []
        escalated = []

        for holding in holdings:
            try:
                prev_stop, prev_target = _get_active_signal_prices(holding.symbol)

                result = run_async(
                    council_orchestrator.start_rebalance_review(
                        symbol=holding.symbol,
                        company_name=holding.name,
                        current_holdings=holding.quantity,
                        avg_buy_price=holding.avg_price,
                        current_price=holding.current_price,
                        prev_target_price=int(prev_target) if prev_target else None,
                        prev_stop_loss=int(prev_stop) if prev_stop else None,
                    )
                )

                if not result:
                    continue

                change_reason = (
                    f"[리밸런싱 {datetime.now().strftime('%m/%d')}] "
                    f"score={result['score']}, "
                    f"target: {int(prev_target):,}→{result['new_target_price']:,}" if prev_target else
                    f"[리밸런싱 {datetime.now().strftime('%m/%d')}] "
                    f"score={result['score']}, "
                    f"target: 미설정→{result['new_target_price']:,}" if result.get('new_target_price') else ""
                )
                if result.get("new_stop_loss"):
                    stop_part = (
                        f", stop: {int(prev_stop):,}→{result['new_stop_loss']:,}" if prev_stop
                        else f", stop: 미설정→{result['new_stop_loss']:,}"
                    )
                    change_reason += stop_part

                if result.get("new_target_price") or result.get("new_stop_loss"):
                    _update_signal_prices(
                        symbol=holding.symbol,
                        new_target=result.get("new_target_price"),
                        new_stop=result.get("new_stop_loss"),
                        reason=change_reason,
                    )

                reviewed.append({
                    "symbol": holding.symbol,
                    "name": holding.name,
                    "score": result["score"],
                    "new_target": result.get("new_target_price"),
                    "new_stop": result.get("new_stop_loss"),
                    "recommend_sell": result.get("recommend_sell", False),
                })

                if result.get("recommend_sell"):
                    logger.warning(
                        f"[리밸런싱] {holding.symbol} score={result['score']} ≤ 3 → 매도 회의 에스컬레이션"
                    )
                    run_async(
                        council_orchestrator.start_sell_meeting(
                            symbol=holding.symbol,
                            company_name=holding.name,
                            sell_reason=f"리밸런싱 재평가 저점수 (score={result['score']})",
                            current_holdings=holding.quantity,
                            avg_buy_price=holding.avg_price,
                            current_price=result.get("current_price", holding.current_price),
                        )
                    )
                    escalated.append(holding.symbol)

            except Exception as e:
                logger.error(f"[리밸런싱] {holding.symbol} 개별 오류: {e}")

            time.sleep(1)

        logger.info(
            f"[리밸런싱] 완료: {len(reviewed)}/{len(holdings)}건 재평가, "
            f"{len(escalated)}건 매도 에스컬레이션"
        )

        deadline_triggered = run_async(_check_holding_deadlines(holdings))

        return {
            "status": "success",
            "total_holdings": len(holdings),
            "reviewed": len(reviewed),
            "escalated": len(escalated),
            "escalated_symbols": escalated,
            "deadline_triggered": deadline_triggered,
            "details": reviewed,
        }

    except Exception as e:
        logger.error(f"[리밸런싱] 전체 오류: {e}")
        self.retry(exc=e)


# ── Helper functions ──


async def _process_council_queue_from_db() -> dict:
    """DB의 queued 시그널을 직접 조회해서 체결 시도."""
    from app.services.kiwoom.rest_client import kiwoom_client
    from app.services.kiwoom.base import OrderSide, OrderType
    from app.models.transaction import TradingSignal as TradingSignalModel

    if not await kiwoom_client.is_connected():
        try:
            await kiwoom_client.connect()
        except Exception as e:
            logger.warning(f"키움 API 연결 실패: {e}")
            return {"status": "error", "reason": str(e)}

    with get_sync_db() as db:
        queued_signals = (
            db.execute(
                select(TradingSignalModel).where(
                    TradingSignalModel.signal_status == "queued",
                    TradingSignalModel.is_executed == False,
                    TradingSignalModel.signal_type.in_(["buy", "sell", "partial_sell"]),
                    TradingSignalModel.quantity > 0,
                )
            )
            .scalars()
            .all()
        )

    if not queued_signals:
        return {"status": "success", "message": "no_queued_signals"}

    executed = []
    failed = []

    from app.core.redis import get_redis_sync

    redis = get_redis_sync()

    for signal in queued_signals:
        try:
            # Redis dedup: 동일 시그널 동시 처리 방지 (5분 TTL)
            dedup_key = f"council_queue:processing:{signal.id}"
            if not redis.set(dedup_key, "1", nx=True, ex=300):
                logger.info(f"시그널 이미 처리 중, 스킵: {signal.symbol} (id={signal.id})")
                continue

            with get_sync_db() as db:
                db_check = db.execute(
                    select(TradingSignalModel)
                    .where(TradingSignalModel.id == signal.id)
                    .with_for_update()
                ).scalar_one_or_none()
                if not db_check or db_check.is_executed:
                    logger.info(f"시그널 이미 체결됨, 스킵: {signal.symbol} (id={signal.id})")
                    redis.delete(dedup_key)
                    continue

            side = OrderSide.BUY if signal.signal_type == "buy" else OrderSide.SELL
            order_result = await kiwoom_client.place_order(
                symbol=signal.symbol,
                side=side,
                quantity=signal.quantity,
                price=0,
                order_type=OrderType.MARKET,
            )

            with get_sync_db() as db:
                db_signal = db.execute(
                    select(TradingSignalModel).where(TradingSignalModel.id == signal.id)
                ).scalar_one_or_none()
                if db_signal:
                    if order_result.status == "submitted":
                        from app.services.council.models import SignalStatus
                        db_signal.signal_status = SignalStatus.AUTO_EXECUTED.value
                        db_signal.is_executed = True
                        executed.append(signal.symbol)
                        logger.info(
                            f"✅ DB 큐 체결: {signal.symbol} {signal.signal_type} "
                            f"{signal.quantity}주 (주문번호: {order_result.order_no})"
                        )
                    else:
                        failed.append(signal.symbol)
                        logger.warning(f"⚠️ DB 큐 체결 실패: {signal.symbol} - {order_result.message}")
                    db.commit()

        except Exception as e:
            logger.error(f"❌ DB 큐 체결 오류: {signal.symbol} - {e}")
            failed.append(signal.symbol)

    return {
        "status": "success",
        "queued": len(queued_signals),
        "executed": len(executed),
        "failed": len(failed),
        "executed_symbols": executed,
    }


async def _check_holding_deadlines(holdings) -> int:
    """보유 기한 만료 종목 체크 → 매도 회의 소집."""
    from app.services.council.orchestrator import council_orchestrator

    triggered = 0
    today = date.today()

    held_map = {h.symbol: h for h in holdings} if holdings else {}
    if not held_map:
        return 0

    with get_sync_db() as db:
        expired_signals = (
            db.execute(
                select(TradingSignal).where(
                    TradingSignal.signal_type == "buy",
                    TradingSignal.is_executed == False,
                    TradingSignal.holding_deadline.isnot(None),
                    TradingSignal.holding_deadline <= today,
                )
            )
            .scalars()
            .all()
        )

    for signal in expired_signals:
        holding = held_map.get(signal.symbol)
        if not holding:
            continue

        if signal.target_price and holding.current_price >= float(signal.target_price):
            continue

        logger.info(
            f"[기한만료] {signal.symbol}: deadline={signal.holding_deadline}, "
            f"current={holding.current_price:,}, target={signal.target_price}"
        )

        try:
            await council_orchestrator.start_sell_meeting(
                symbol=holding.symbol,
                company_name=holding.name,
                sell_reason=(
                    f"보유 기한 만료 ({signal.holding_deadline.strftime('%Y-%m-%d')}): "
                    f"목표가 미달, 자본 재투자 목적 매도"
                ),
                current_holdings=holding.quantity,
                avg_buy_price=holding.avg_price,
                current_price=holding.current_price,
            )
            triggered += 1
        except Exception as e:
            logger.error(f"[기한만료] {signal.symbol} 매도 회의 소집 실패: {e}")

    if triggered:
        logger.info(f"[기한만료] {triggered}건 매도 회의 소집 완료")

    return triggered


def _update_signal_prices(
    symbol: str,
    new_target: Optional[int],
    new_stop: Optional[int],
    reason: str,
):
    """기존 활성 BUY 시그널의 target_price / stop_loss 갱신."""
    try:
        with get_sync_db() as db:
            signal = db.execute(
                select(TradingSignal)
                .where(
                    TradingSignal.symbol == symbol,
                    TradingSignal.signal_type == "buy",
                    TradingSignal.is_executed == False,
                )
                .order_by(TradingSignal.created_at.desc())
                .limit(1)
            ).scalar_one_or_none()

            if not signal:
                logger.info(f"[리밸런싱] {symbol} 활성 BUY 시그널 없음 → 갱신 스킵")
                return

            prev_reason = signal.reason or ""
            separator = " | " if prev_reason else ""
            signal.reason = prev_reason + separator + reason

            if new_target is not None:
                signal.target_price = float(new_target)
            if new_stop is not None:
                signal.stop_loss = float(new_stop)

            db.commit()
            logger.info(
                f"[리밸런싱] {symbol} DB 갱신 완료: "
                f"target={new_target}, stop={new_stop}"
            )

    except Exception as e:
        logger.error(f"[리밸런싱] {symbol} DB 갱신 실패: {e}")

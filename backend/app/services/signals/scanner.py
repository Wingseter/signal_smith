"""
시그널 스캐너

종목 스캔 → 지표 계산 → 트리거 평가 → 시그널 생성
결과는 Redis에 저장되어 Celery worker와 FastAPI 간 공유
"""

import json
import logging
import asyncio
from datetime import datetime
from typing import Optional, List, Callable, Awaitable

from .models import SignalResult, TriggerSignal
from .indicators import quant_calculator
from .triggers import trigger_evaluator

logger = logging.getLogger(__name__)

# Redis 키 상수
REDIS_KEY_RESULTS = "quant:signals:results"      # Hash: symbol → JSON
REDIS_KEY_SCORES = "quant:signals:scores"         # Sorted Set: symbol → score
REDIS_KEY_LAST_SCAN = "quant:signals:last_scan_at"  # String: ISO timestamp
REDIS_TTL = 24 * 3600  # 24시간


def _get_sync_redis():
    """동기 Redis 클라이언트 (Celery worker용 폴백)."""
    import redis as sync_redis
    from app.config import settings
    return sync_redis.from_url(settings.redis_url, decode_responses=True)


class SignalScanner:
    """퀀트 시그널 스캐너"""

    def __init__(self):
        self._results: List[SignalResult] = []
        self._signal_callbacks: List[Callable[[SignalResult], Awaitable[None]]] = []
        self._scan_callbacks: List[Callable[[dict], Awaitable[None]]] = []
        self._is_scanning: bool = False
        self._last_scan_at: Optional[datetime] = None

    # ============ 콜백 ============

    def add_signal_callback(self, callback: Callable[[SignalResult], Awaitable[None]]):
        """시그널 생성 시 콜백 등록"""
        self._signal_callbacks.append(callback)

    def add_scan_callback(self, callback: Callable[[dict], Awaitable[None]]):
        """스캔 상태 업데이트 콜백 등록"""
        self._scan_callbacks.append(callback)

    async def _notify_signal(self, result: SignalResult):
        """시그널 알림"""
        for callback in self._signal_callbacks:
            try:
                await callback(result)
            except Exception as e:
                logger.error(f"시그널 콜백 오류: {e}")

    async def _notify_scan_update(self, update: dict):
        """스캔 상태 알림"""
        for callback in self._scan_callbacks:
            try:
                await callback(update)
            except Exception as e:
                logger.error(f"스캔 콜백 오류: {e}")

    # ============ 스캔 ============

    async def scan_stock(self, symbol: str) -> Optional[SignalResult]:
        """단일 종목 스캔

        Args:
            symbol: 종목코드

        Returns:
            SignalResult or None
        """
        try:
            # 키움 API에서 일봉 데이터 조회
            from app.services.kiwoom.rest_client import kiwoom_client

            if not await kiwoom_client.is_connected():
                try:
                    await kiwoom_client.connect()
                except Exception as conn_error:
                    logger.warning(f"키움 API 연결 실패: {conn_error}")
                    return None

            daily_prices = await kiwoom_client.get_daily_prices(symbol)

            if not daily_prices:
                logger.warning(f"[{symbol}] 일봉 데이터 없음")
                return None

            logger.info(f"[{symbol}] 일봉 데이터 {len(daily_prices)}개 조회")

            # 지표 계산
            indicators = quant_calculator.calculate_all(symbol, daily_prices)

            # 트리거 평가
            triggers = trigger_evaluator.evaluate_all(indicators)

            # 종합 점수
            composite_score = trigger_evaluator.calculate_composite_score(triggers)
            action = trigger_evaluator.determine_action(composite_score, triggers)

            # 통계
            bullish = sum(1 for t in triggers if t.signal == TriggerSignal.BULLISH)
            bearish = sum(1 for t in triggers if t.signal == TriggerSignal.BEARISH)
            neutral = sum(1 for t in triggers if t.signal == TriggerSignal.NEUTRAL)

            # 종목명 조회 (DB)
            company_name = ""
            try:
                from sqlalchemy import select as sa_select
                from app.models.stock import Stock
                from app.core.database import get_sync_db
                with get_sync_db() as db:
                    row = db.execute(sa_select(Stock.name).where(Stock.symbol == symbol)).first()
                    if row:
                        company_name = row[0] or ""
            except Exception:
                pass

            result = SignalResult(
                symbol=symbol,
                company_name=company_name,
                indicators=indicators,
                triggers=triggers,
                composite_score=composite_score,
                bullish_count=bullish,
                bearish_count=bearish,
                neutral_count=neutral,
                action=action,
            )

            # 결과 저장 (인메모리 + Redis)
            self._store_result(result)

            logger.info(
                f"[{symbol}] 스캔 완료 - "
                f"점수: {composite_score}/100, 행동: {action.value}, "
                f"매수:{bullish} / 매도:{bearish} / 중립:{neutral}"
            )

            return result

        except Exception as e:
            logger.error(f"[{symbol}] 스캔 실패: {e}")
            return None

    async def scan_watchlist(
        self, symbols: List[str], max_concurrent: int = 5
    ) -> List[SignalResult]:
        """워치리스트 종목 동시 스캔

        Args:
            symbols: 종목코드 리스트
            max_concurrent: 최대 동시 스캔 수 (기본 5)

        Returns:
            스캔 결과 리스트 (점수 내림차순)
        """
        self._is_scanning = True
        total = len(symbols)
        scanned_count = 0
        semaphore = asyncio.Semaphore(max_concurrent)

        await self._notify_scan_update({
            "type": "scan_started",
            "total": total,
            "timestamp": datetime.now().isoformat(),
        })

        async def _scan_one(symbol: str) -> Optional[SignalResult]:
            nonlocal scanned_count
            async with semaphore:
                try:
                    result = await self.scan_stock(symbol)
                    scanned_count += 1

                    if result:
                        await self._notify_signal(result)

                    # 진행 상황 알림 (50개 단위)
                    if scanned_count % 50 == 0 or scanned_count == total:
                        await self._notify_scan_update({
                            "type": "scan_progress",
                            "current": scanned_count,
                            "total": total,
                            "symbol": symbol,
                            "score": result.composite_score if result else None,
                        })

                    # API rate limit 보호
                    await asyncio.sleep(0.3)
                    return result

                except Exception as e:
                    logger.error(f"[{symbol}] 스캔 오류: {e}")
                    scanned_count += 1
                    return None

        tasks = [_scan_one(s) for s in symbols]
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)
        results = [r for r in raw_results if isinstance(r, SignalResult)]

        self._is_scanning = False
        self._last_scan_at = datetime.now()

        # Redis에 마지막 스캔 시각 기록
        try:
            r = _get_sync_redis()
            r.set(REDIS_KEY_LAST_SCAN, self._last_scan_at.isoformat(), ex=REDIS_TTL)
        except Exception as e:
            logger.warning(f"Redis last_scan_at 저장 실패: {e}")

        # 점수순 정렬
        results.sort(key=lambda r: r.composite_score, reverse=True)

        await self._notify_scan_update({
            "type": "scan_completed",
            "total_scanned": total,
            "results_count": len(results),
            "timestamp": datetime.now().isoformat(),
        })

        logger.info(f"스캔 완료: {total}종목 중 {len(results)}개 결과")
        return results

    async def get_top_signals(self, limit: int = 20) -> List[SignalResult]:
        """상위 시그널 종목 반환 (Redis 우선)

        Args:
            limit: 반환할 최대 종목 수

        Returns:
            점수 상위 시그널 결과
        """
        try:
            r = _get_sync_redis()
            # Sorted Set에서 점수 내림차순 상위 N개 symbol 조회
            top_symbols = r.zrevrange(REDIS_KEY_SCORES, 0, limit - 1)
            if top_symbols:
                pipeline = r.pipeline()
                for sym in top_symbols:
                    pipeline.hget(REDIS_KEY_RESULTS, sym)
                raw_list = pipeline.execute()

                results = []
                for raw in raw_list:
                    if raw:
                        results.append(self._deserialize_result(raw))
                return results
        except Exception as e:
            logger.warning(f"Redis top signals 조회 실패, 인메모리 폴백: {e}")

        # 인메모리 폴백
        sorted_results = sorted(
            self._results, key=lambda r: r.composite_score, reverse=True
        )
        return sorted_results[:limit]

    # ============ 상태 ============

    def get_status(self) -> dict:
        """스캐너 상태 (Redis 포함)"""
        total_results = len(self._results)
        last_scan = self._last_scan_at.isoformat() if self._last_scan_at else None

        # Redis에서 보강
        try:
            r = _get_sync_redis()
            redis_count = r.hlen(REDIS_KEY_RESULTS)
            if redis_count > total_results:
                total_results = redis_count
            redis_last = r.get(REDIS_KEY_LAST_SCAN)
            if redis_last:
                last_scan = redis_last
        except Exception:
            pass

        return {
            "is_scanning": self._is_scanning,
            "last_scan_at": last_scan,
            "total_results": total_results,
        }

    def get_recent_results(self, limit: int = 50) -> List[SignalResult]:
        """최근 스캔 결과 (Redis 우선)"""
        try:
            r = _get_sync_redis()
            # Sorted Set에서 점수 내림차순으로 전체 조회 (최근 결과를 점수순으로)
            all_symbols = r.zrevrange(REDIS_KEY_SCORES, 0, limit - 1)
            if all_symbols:
                pipeline = r.pipeline()
                for sym in all_symbols:
                    pipeline.hget(REDIS_KEY_RESULTS, sym)
                raw_list = pipeline.execute()

                results = []
                for raw in raw_list:
                    if raw:
                        results.append(self._deserialize_result(raw))

                if results:
                    return results
        except Exception as e:
            logger.warning(f"Redis 결과 조회 실패, 인메모리 폴백: {e}")

        # 인메모리 폴백
        return self._results[-limit:]

    def _store_result(self, result: SignalResult):
        """결과 저장 (인메모리 + Redis)"""
        # 인메모리 저장 (기존 방식 유지)
        self._results = [r for r in self._results if r.symbol != result.symbol]
        self._results.append(result)
        if len(self._results) > 500:
            self._results = self._results[-500:]

        # Redis 저장
        try:
            r = _get_sync_redis()
            data = json.dumps(result.to_dict(), ensure_ascii=False)

            pipeline = r.pipeline()
            pipeline.hset(REDIS_KEY_RESULTS, result.symbol, data)
            pipeline.zadd(REDIS_KEY_SCORES, {result.symbol: result.composite_score})
            pipeline.expire(REDIS_KEY_RESULTS, REDIS_TTL)
            pipeline.expire(REDIS_KEY_SCORES, REDIS_TTL)
            pipeline.execute()
        except Exception as e:
            logger.warning(f"Redis 시그널 저장 실패 ({result.symbol}): {e}")

    @staticmethod
    def _deserialize_result(raw_json: str) -> SignalResult:
        """Redis JSON → SignalResult (UI 표시용 최소 복원)"""
        from .models import SignalAction, TriggerResult as TriggerResultModel
        from .models import TriggerSignal, SignalStrength

        data = json.loads(raw_json) if isinstance(raw_json, str) else raw_json

        triggers = []
        for t in data.get("triggers", []):
            triggers.append(TriggerResultModel(
                trigger_id=t.get("trigger_id", ""),
                name=t.get("name", ""),
                signal=TriggerSignal(t.get("signal", "neutral")),
                strength=SignalStrength(t.get("strength", "none")),
                score=t.get("score", 0),
                details=t.get("details", ""),
                values=t.get("values", {}),
            ))

        action_str = data.get("action", "hold")
        try:
            action = SignalAction(action_str)
        except ValueError:
            action = SignalAction.HOLD

        scanned_at_str = data.get("scanned_at")
        scanned_at = (
            datetime.fromisoformat(scanned_at_str)
            if scanned_at_str
            else datetime.now()
        )

        return SignalResult(
            id=data.get("id", ""),
            symbol=data.get("symbol", ""),
            company_name=data.get("company_name", ""),
            indicators=None,  # 지표 원본은 Redis에서 복원 불필요 (UI 미사용)
            triggers=triggers,
            composite_score=data.get("composite_score", 0),
            bullish_count=data.get("bullish_count", 0),
            bearish_count=data.get("bearish_count", 0),
            neutral_count=data.get("neutral_count", 0),
            action=action,
            scanned_at=scanned_at,
        )


# 싱글톤 인스턴스
signal_scanner = SignalScanner()

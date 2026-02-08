"""
시그널 스캐너

종목 스캔 → 지표 계산 → 트리거 평가 → 시그널 생성
"""

import logging
import asyncio
from datetime import datetime
from typing import Optional, List, Callable, Awaitable

from .models import SignalResult, TriggerSignal
from .indicators import quant_calculator
from .triggers import trigger_evaluator

logger = logging.getLogger(__name__)


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

            result = SignalResult(
                symbol=symbol,
                indicators=indicators,
                triggers=triggers,
                composite_score=composite_score,
                bullish_count=bullish,
                bearish_count=bearish,
                neutral_count=neutral,
                action=action,
            )

            # 결과 저장
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

    async def scan_watchlist(self, symbols: List[str]) -> List[SignalResult]:
        """워치리스트 종목 스캔

        Args:
            symbols: 종목코드 리스트

        Returns:
            스캔 결과 리스트
        """
        self._is_scanning = True
        results = []
        total = len(symbols)

        await self._notify_scan_update({
            "type": "scan_started",
            "total": total,
            "timestamp": datetime.now().isoformat(),
        })

        for i, symbol in enumerate(symbols):
            try:
                result = await self.scan_stock(symbol)
                if result:
                    results.append(result)
                    await self._notify_signal(result)

                await self._notify_scan_update({
                    "type": "scan_progress",
                    "current": i + 1,
                    "total": total,
                    "symbol": symbol,
                    "score": result.composite_score if result else None,
                })

                # API 호출 간 딜레이
                if i < total - 1:
                    await asyncio.sleep(0.5)

            except Exception as e:
                logger.error(f"[{symbol}] 스캔 오류: {e}")

        self._is_scanning = False
        self._last_scan_at = datetime.now()

        # 점수순 정렬
        results.sort(key=lambda r: r.composite_score, reverse=True)

        await self._notify_scan_update({
            "type": "scan_completed",
            "total_scanned": total,
            "results_count": len(results),
            "timestamp": datetime.now().isoformat(),
        })

        return results

    async def get_top_signals(self, limit: int = 20) -> List[SignalResult]:
        """상위 시그널 종목 반환

        Args:
            limit: 반환할 최대 종목 수

        Returns:
            점수 상위 시그널 결과
        """
        sorted_results = sorted(
            self._results, key=lambda r: r.composite_score, reverse=True
        )
        return sorted_results[:limit]

    # ============ 상태 ============

    def get_status(self) -> dict:
        """스캐너 상태"""
        return {
            "is_scanning": self._is_scanning,
            "last_scan_at": self._last_scan_at.isoformat() if self._last_scan_at else None,
            "total_results": len(self._results),
        }

    def get_recent_results(self, limit: int = 50) -> List[SignalResult]:
        """최근 스캔 결과"""
        return self._results[-limit:]

    def _store_result(self, result: SignalResult):
        """결과 저장 (최대 500개 유지)"""
        # 같은 종목 기존 결과 제거
        self._results = [r for r in self._results if r.symbol != result.symbol]
        self._results.append(result)

        # 최대 보관 수 제한
        if len(self._results) > 500:
            self._results = self._results[-500:]


# 싱글톤 인스턴스
signal_scanner = SignalScanner()

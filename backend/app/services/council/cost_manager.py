"""
AI API 비용 관리자

비용 효율적인 AI 호출을 위한 규칙 및 관리
- 티어별 분석 깊이 조절
- 일일/월간 비용 제한
- 캐싱 및 중복 호출 방지
- 스마트 분석 스케줄링
"""

import logging
from datetime import datetime, date, timedelta
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
import hashlib
import asyncio

logger = logging.getLogger(__name__)


class AnalysisDepth(str, Enum):
    """분석 깊이 레벨"""
    QUICK = "quick"           # 키워드 기반 빠른 분석 (비용: 없음)
    LIGHT = "light"           # 단일 AI만 사용 (비용: $0.01~0.02)
    STANDARD = "standard"     # Gemini + GPT (비용: $0.05~0.10)
    FULL = "full"             # 전체 AI Council (비용: $0.15~0.25)
    DEEP = "deep"             # 심층 분석 + 추가 라운드 (비용: $0.30~0.50)


class SignalPriority(str, Enum):
    """시그널 우선순위"""
    LOW = "low"               # 낮음: 일반 뉴스
    MEDIUM = "medium"         # 중간: 중요 뉴스
    HIGH = "high"             # 높음: 긴급 뉴스
    CRITICAL = "critical"     # 긴급: 중대 이벤트


@dataclass
class AnalysisCost:
    """분석 비용 기록"""
    timestamp: datetime
    depth: AnalysisDepth
    symbol: str
    estimated_cost: float
    actual_tokens_used: int = 0
    success: bool = True


@dataclass
class CostLimits:
    """비용 제한 설정"""
    daily_limit_usd: float = 5.0          # 일일 한도 ($5)
    monthly_limit_usd: float = 100.0       # 월간 한도 ($100)
    max_full_analysis_per_day: int = 20    # 일일 전체 분석 최대 횟수
    max_deep_analysis_per_day: int = 5     # 일일 심층 분석 최대 횟수
    cooldown_same_symbol_minutes: int = 30 # 같은 종목 재분석 대기 시간


# 예상 비용 테이블 (USD)
ESTIMATED_COSTS = {
    AnalysisDepth.QUICK: 0.0,
    AnalysisDepth.LIGHT: 0.015,
    AnalysisDepth.STANDARD: 0.075,
    AnalysisDepth.FULL: 0.20,
    AnalysisDepth.DEEP: 0.40,
}


class CostManager:
    """AI 비용 관리자"""

    def __init__(self, limits: Optional[CostLimits] = None):
        self.limits = limits or CostLimits()
        self._cost_history: List[AnalysisCost] = []
        self._analysis_cache: Dict[str, Tuple[datetime, any]] = {}  # 캐시
        self._last_analysis: Dict[str, datetime] = {}  # 종목별 마지막 분석 시간
        self._daily_counts: Dict[str, int] = {}  # 깊이별 일일 횟수

    def _get_cache_key(self, symbol: str, news_title: str) -> str:
        """캐시 키 생성"""
        content = f"{symbol}:{news_title[:50]}"
        return hashlib.md5(content.encode()).hexdigest()[:16]

    def _reset_daily_counts(self):
        """일일 카운터 리셋"""
        today = date.today()
        if not hasattr(self, '_last_reset') or self._last_reset != today:
            self._daily_counts = {}
            self._last_reset = today

    def get_daily_cost(self) -> float:
        """오늘 사용한 비용"""
        today = date.today()
        return sum(
            c.estimated_cost
            for c in self._cost_history
            if c.timestamp.date() == today
        )

    def get_monthly_cost(self) -> float:
        """이번 달 사용한 비용"""
        this_month = datetime.now().replace(day=1)
        return sum(
            c.estimated_cost
            for c in self._cost_history
            if c.timestamp >= this_month
        )

    def get_remaining_budget(self) -> Tuple[float, float]:
        """남은 예산 (일일, 월간)"""
        daily_remaining = self.limits.daily_limit_usd - self.get_daily_cost()
        monthly_remaining = self.limits.monthly_limit_usd - self.get_monthly_cost()
        return max(0, daily_remaining), max(0, monthly_remaining)

    def can_afford(self, depth: AnalysisDepth) -> Tuple[bool, str]:
        """분석 비용 여유 확인"""
        self._reset_daily_counts()

        cost = ESTIMATED_COSTS.get(depth, 0)
        daily_remaining, monthly_remaining = self.get_remaining_budget()

        if cost > daily_remaining:
            return False, f"일일 예산 초과 (남은 예산: ${daily_remaining:.2f})"

        if cost > monthly_remaining:
            return False, f"월간 예산 초과 (남은 예산: ${monthly_remaining:.2f})"

        # 깊이별 일일 횟수 제한
        depth_key = depth.value
        current_count = self._daily_counts.get(depth_key, 0)

        if depth == AnalysisDepth.FULL:
            if current_count >= self.limits.max_full_analysis_per_day:
                return False, f"일일 전체 분석 한도 초과 ({self.limits.max_full_analysis_per_day}회)"

        if depth == AnalysisDepth.DEEP:
            if current_count >= self.limits.max_deep_analysis_per_day:
                return False, f"일일 심층 분석 한도 초과 ({self.limits.max_deep_analysis_per_day}회)"

        return True, "분석 가능"

    def is_in_cooldown(self, symbol: str) -> Tuple[bool, int]:
        """쿨다운 상태 확인, (쿨다운중 여부, 남은 분)"""
        if symbol not in self._last_analysis:
            return False, 0

        last_time = self._last_analysis[symbol]
        cooldown_end = last_time + timedelta(minutes=self.limits.cooldown_same_symbol_minutes)

        if datetime.now() < cooldown_end:
            remaining = int((cooldown_end - datetime.now()).total_seconds() // 60)
            return True, remaining

        return False, 0

    def get_cached_result(self, symbol: str, news_title: str) -> Optional[any]:
        """캐시된 결과 조회 (1시간 유효)"""
        cache_key = self._get_cache_key(symbol, news_title)

        if cache_key in self._analysis_cache:
            timestamp, result = self._analysis_cache[cache_key]
            if datetime.now() - timestamp < timedelta(hours=1):
                logger.info(f"캐시 히트: {symbol}")
                return result

            # 만료된 캐시 삭제
            del self._analysis_cache[cache_key]

        return None

    def cache_result(self, symbol: str, news_title: str, result: any):
        """결과 캐싱"""
        cache_key = self._get_cache_key(symbol, news_title)
        self._analysis_cache[cache_key] = (datetime.now(), result)

        # 캐시 크기 제한 (최대 100개)
        if len(self._analysis_cache) > 100:
            oldest_key = min(self._analysis_cache, key=lambda k: self._analysis_cache[k][0])
            del self._analysis_cache[oldest_key]

    def determine_analysis_depth(
        self,
        news_score: int,
        symbol: str,
        is_holding: bool = False,
        portfolio_weight: float = 0.0,
        signal_priority: SignalPriority = SignalPriority.MEDIUM,
    ) -> Tuple[AnalysisDepth, str]:
        """
        분석 깊이 결정 로직

        규칙:
        1. 뉴스 점수 < 5: QUICK (부정적 뉴스 - 빠른 판단)
        2. 뉴스 점수 5-6: LIGHT (중립 - 가벼운 분석)
        3. 뉴스 점수 7-8: STANDARD (긍정적 - 일반 분석)
        4. 뉴스 점수 9-10: FULL (강한 긍정 - 전체 분석)
        5. 보유 종목 + 높은 비중: FULL 이상
        6. 긴급 우선순위: DEEP
        """
        self._reset_daily_counts()

        # 기본 깊이 결정 (뉴스 점수 기반)
        if news_score <= 3:
            base_depth = AnalysisDepth.QUICK
            reason = f"부정적 뉴스 (점수: {news_score})"
        elif news_score <= 4:
            base_depth = AnalysisDepth.LIGHT
            reason = f"약한 신호 (점수: {news_score})"
        elif news_score <= 6:
            base_depth = AnalysisDepth.LIGHT
            reason = f"중립 신호 (점수: {news_score})"
        elif news_score <= 7:
            base_depth = AnalysisDepth.STANDARD
            reason = f"긍정적 신호 (점수: {news_score})"
        elif news_score <= 8:
            base_depth = AnalysisDepth.FULL
            reason = f"강한 긍정 신호 (점수: {news_score})"
        else:
            base_depth = AnalysisDepth.FULL
            reason = f"매우 강한 신호 (점수: {news_score})"

        # 보유 종목이면 깊이 상향
        if is_holding:
            if portfolio_weight >= 10.0:  # 10% 이상 비중
                if base_depth in [AnalysisDepth.QUICK, AnalysisDepth.LIGHT]:
                    base_depth = AnalysisDepth.STANDARD
                    reason += f" + 주요 보유종목 ({portfolio_weight:.1f}%)"
                elif base_depth == AnalysisDepth.STANDARD:
                    base_depth = AnalysisDepth.FULL
                    reason += f" + 주요 보유종목 ({portfolio_weight:.1f}%)"

        # 긴급 우선순위면 DEEP으로 상향
        if signal_priority == SignalPriority.CRITICAL:
            base_depth = AnalysisDepth.DEEP
            reason = f"긴급 분석 필요 - {reason}"

        # 예산 확인하여 하향 조정
        can_afford_result, _ = self.can_afford(base_depth)
        if not can_afford_result:
            # 예산 부족 시 하향
            depth_order = [
                AnalysisDepth.DEEP,
                AnalysisDepth.FULL,
                AnalysisDepth.STANDARD,
                AnalysisDepth.LIGHT,
                AnalysisDepth.QUICK,
            ]
            current_idx = depth_order.index(base_depth)

            for lower_depth in depth_order[current_idx + 1:]:
                if self.can_afford(lower_depth)[0]:
                    base_depth = lower_depth
                    reason += " (예산 부족으로 하향 조정)"
                    break

        return base_depth, reason

    def record_analysis(self, symbol: str, depth: AnalysisDepth, success: bool = True):
        """분석 기록"""
        self._reset_daily_counts()

        cost = ESTIMATED_COSTS.get(depth, 0)
        record = AnalysisCost(
            timestamp=datetime.now(),
            depth=depth,
            symbol=symbol,
            estimated_cost=cost,
            success=success,
        )
        self._cost_history.append(record)

        # 마지막 분석 시간 기록
        self._last_analysis[symbol] = datetime.now()

        # 깊이별 카운트 증가
        depth_key = depth.value
        self._daily_counts[depth_key] = self._daily_counts.get(depth_key, 0) + 1

        # 히스토리 크기 제한 (최근 1000개)
        if len(self._cost_history) > 1000:
            self._cost_history = self._cost_history[-500:]

        logger.info(
            f"분석 기록: {symbol} - {depth.value} "
            f"(예상 비용: ${cost:.3f}, 일일 누적: ${self.get_daily_cost():.2f})"
        )

    def get_stats(self) -> dict:
        """통계 조회"""
        self._reset_daily_counts()
        daily_remaining, monthly_remaining = self.get_remaining_budget()

        return {
            "daily_cost": round(self.get_daily_cost(), 2),
            "monthly_cost": round(self.get_monthly_cost(), 2),
            "daily_remaining": round(daily_remaining, 2),
            "monthly_remaining": round(monthly_remaining, 2),
            "daily_limit": self.limits.daily_limit_usd,
            "monthly_limit": self.limits.monthly_limit_usd,
            "cache_size": len(self._analysis_cache),
            "history_size": len(self._cost_history),
            "daily_counts": dict(self._daily_counts),
        }

    def should_batch_analysis(self, symbols: List[str]) -> Tuple[bool, str]:
        """배치 분석 여부 결정"""
        if len(symbols) >= 5:
            return True, "다수 종목 - 배치 분석 권장"

        # 남은 예산이 적으면 배치로
        daily_remaining, _ = self.get_remaining_budget()
        if daily_remaining < 1.0 and len(symbols) >= 3:
            return True, "예산 부족 - 배치 분석으로 비용 절감"

        return False, "개별 분석"


# 싱글톤 인스턴스
cost_manager = CostManager()

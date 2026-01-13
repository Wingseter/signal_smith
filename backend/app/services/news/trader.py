"""
뉴스 기반 자동매매 서비스

뉴스 분석 결과를 바탕으로 AI 회의를 소집하고 투자 결정을 내립니다.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Callable
from dataclasses import dataclass, field

from app.config import settings
from .models import NewsArticle
from .monitor import news_monitor, NewsMonitor
from .analyzer import news_analyzer, NewsAnalyzer

logger = logging.getLogger(__name__)


@dataclass
class TradingConfig:
    """자동매매 설정"""
    enabled: bool = False                    # 자동매매 활성화
    council_threshold: int = 7               # AI 회의 소집 기준 점수 (이상)
    sell_threshold: int = 3                  # 매도 기준 점수 (이하)
    max_position_per_stock: int = 500000     # 종목당 최대 투자금
    max_daily_trades: int = 10               # 일일 최대 거래 횟수
    cooldown_minutes: int = 30               # 같은 종목 재매매 대기 시간
    require_symbol: bool = True              # 종목코드 필수 여부
    min_confidence: float = 0.7              # 최소 신뢰도
    auto_execute: bool = False               # 자동 체결 (False면 승인 필요)


@dataclass
class TradeRecord:
    """거래 기록"""
    symbol: str
    company_name: str
    action: str  # BUY or SELL or COUNCIL
    score: int
    reason: str
    news_title: str
    executed_at: datetime
    meeting_id: Optional[str] = None         # AI 회의 ID
    success: bool = True
    error_message: Optional[str] = None


class NewsTrader:
    """뉴스 기반 자동매매 (AI 회의 시스템 통합)"""

    def __init__(self, config: Optional[TradingConfig] = None):
        self.config = config or TradingConfig()
        self._running = False
        self._trade_history: List[TradeRecord] = []
        self._recent_trades: Dict[str, datetime] = {}
        self._daily_trade_count = 0
        self._last_reset_date: Optional[datetime] = None

        # AI 회의 오케스트레이터
        self._council = None

        # 콜백
        self._meeting_callbacks: List[Callable] = []

    def _get_council(self):
        """회의 오케스트레이터 가져오기 (지연 임포트)"""
        if self._council is None:
            from app.services.council import council_orchestrator
            self._council = council_orchestrator
            self._council.auto_execute = self.config.auto_execute
        return self._council

    def add_meeting_callback(self, callback: Callable):
        """회의 업데이트 콜백 등록"""
        self._meeting_callbacks.append(callback)
        council = self._get_council()
        council.add_meeting_callback(callback)

    def _reset_daily_counter(self):
        """일일 거래 횟수 리셋"""
        today = datetime.now().date()
        if self._last_reset_date != today:
            self._daily_trade_count = 0
            self._last_reset_date = today
            logger.info("일일 거래 횟수 리셋")

    def _can_trade(self, symbol: str) -> tuple[bool, str]:
        """거래 가능 여부 확인"""
        self._reset_daily_counter()

        # 일일 거래 한도
        if self._daily_trade_count >= self.config.max_daily_trades:
            return False, f"일일 거래 한도 초과 ({self.config.max_daily_trades}회)"

        # 쿨다운 체크
        if symbol in self._recent_trades:
            last_trade = self._recent_trades[symbol]
            cooldown_end = last_trade + timedelta(minutes=self.config.cooldown_minutes)
            if datetime.now() < cooldown_end:
                remaining = (cooldown_end - datetime.now()).seconds // 60
                return False, f"쿨다운 중 ({remaining}분 남음)"

        return True, "거래 가능"

    async def on_news_detected(self, article: NewsArticle):
        """뉴스 감지 시 콜백"""
        logger.info(f"뉴스 감지: {article.title}")

        # 종목코드 필수 체크
        if self.config.require_symbol and not article.symbol:
            logger.debug(f"종목코드 없음, 스킵: {article.title}")
            return

        # Gemini로 초기 분석
        analysis = await news_analyzer.analyze(article)

        logger.info(
            f"Gemini 분석: {article.title[:30]}... -> "
            f"점수={analysis.score}, 신뢰도={analysis.confidence}"
        )

        # 신뢰도 체크
        if analysis.confidence < self.config.min_confidence:
            logger.debug(f"신뢰도 부족 ({analysis.confidence}), 스킵")
            return

        symbol = article.symbol
        company_name = article.company_name or symbol

        # 거래 가능 여부 확인
        can_trade, reason = self._can_trade(symbol)
        if not can_trade:
            logger.info(f"거래 불가: {symbol} - {reason}")
            return

        # 점수가 높으면 AI 회의 소집
        if analysis.score >= self.config.council_threshold:
            logger.info(f"🔔 AI 회의 소집: {company_name} (점수: {analysis.score})")

            # 회의 시작
            council = self._get_council()

            # 가용 자금 조회 (실제로는 키움 API에서)
            available_amount = self.config.max_position_per_stock

            meeting = await council.start_meeting(
                symbol=symbol,
                company_name=company_name,
                news_title=article.title,
                news_score=analysis.score,
                available_amount=available_amount,
                current_price=0,  # 실제로는 현재가 조회 필요
            )

            # 거래 기록
            record = TradeRecord(
                symbol=symbol,
                company_name=company_name,
                action="COUNCIL",
                score=analysis.score,
                reason=f"AI 회의 소집 - {meeting.signal.action if meeting.signal else 'N/A'}",
                news_title=article.title,
                executed_at=datetime.now(),
                meeting_id=meeting.id,
                success=True,
            )
            self._trade_history.append(record)
            self._recent_trades[symbol] = datetime.now()
            self._daily_trade_count += 1

        elif analysis.score <= self.config.sell_threshold:
            # 매도 신호 (회의 없이 바로)
            logger.info(f"📉 매도 신호: {company_name} (점수: {analysis.score})")

            record = TradeRecord(
                symbol=symbol,
                company_name=company_name,
                action="SELL_SIGNAL",
                score=analysis.score,
                reason=analysis.analysis_reason,
                news_title=article.title,
                executed_at=datetime.now(),
                success=True,
            )
            self._trade_history.append(record)

        else:
            logger.debug(
                f"조건 미충족: {company_name} 점수={analysis.score} "
                f"(회의소집>={self.config.council_threshold})"
            )

    async def start(self, poll_interval: int = 60):
        """자동매매 시작"""
        if self._running:
            logger.warning("자동매매가 이미 실행 중입니다")
            return

        self._running = True

        # 뉴스 모니터에 콜백 등록
        news_monitor.add_callback(self.on_news_detected)

        # 뉴스 모니터 시작
        if not news_monitor.is_running():
            await news_monitor.start(poll_interval=poll_interval)

        logger.info(
            f"뉴스 자동매매 시작 - "
            f"회의소집>={self.config.council_threshold}, "
            f"매도<={self.config.sell_threshold}, "
            f"자동체결={self.config.auto_execute}"
        )

    async def stop(self):
        """자동매매 중지"""
        self._running = False
        news_monitor.remove_callback(self.on_news_detected)
        await news_monitor.stop()
        logger.info("뉴스 자동매매 중지")

    def get_trade_history(self, limit: int = 50) -> List[TradeRecord]:
        """거래 기록 조회"""
        return self._trade_history[-limit:]

    def get_pending_signals(self):
        """대기 중인 시그널"""
        council = self._get_council()
        return council.get_pending_signals()

    def get_recent_meetings(self, limit: int = 10):
        """최근 회의 목록"""
        council = self._get_council()
        return council.get_recent_meetings(limit)

    async def approve_signal(self, signal_id: str):
        """시그널 승인"""
        council = self._get_council()
        return await council.approve_signal(signal_id)

    async def reject_signal(self, signal_id: str):
        """시그널 거부"""
        council = self._get_council()
        return await council.reject_signal(signal_id)

    async def execute_signal(self, signal_id: str):
        """시그널 체결"""
        council = self._get_council()
        return await council.execute_signal(signal_id)

    def get_stats(self) -> dict:
        """통계 조회"""
        self._reset_daily_counter()
        council = self._get_council()
        return {
            "running": self._running,
            "auto_execute": self.config.auto_execute,
            "daily_trades": self._daily_trade_count,
            "daily_limit": self.config.max_daily_trades,
            "total_trades": len(self._trade_history),
            "council_threshold": self.config.council_threshold,
            "sell_threshold": self.config.sell_threshold,
            "pending_signals": len(council.get_pending_signals()),
            "total_meetings": len(council.get_recent_meetings(100)),
        }

    def update_config(self, **kwargs):
        """설정 업데이트"""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
                logger.info(f"설정 변경: {key} = {value}")

        # 자동체결 설정 동기화
        if "auto_execute" in kwargs:
            council = self._get_council()
            council.set_auto_execute(kwargs["auto_execute"])


# 싱글톤 인스턴스
news_trader = NewsTrader()

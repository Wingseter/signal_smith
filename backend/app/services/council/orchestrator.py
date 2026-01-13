"""
AI 투자 회의 오케스트레이터

회의 진행을 관리하고 합의를 도출하는 오케스트레이터
"""

import logging
from datetime import datetime
from typing import Optional, List, Callable, Awaitable
import asyncio

from app.config import settings
from .models import (
    CouncilMeeting, CouncilMessage, InvestmentSignal,
    SignalStatus, AnalystRole
)
from .quant_analyst import quant_analyst
from .fundamental_analyst import fundamental_analyst

logger = logging.getLogger(__name__)


class CouncilOrchestrator:
    """AI 투자 회의 오케스트레이터"""

    def __init__(self):
        self._meetings: List[CouncilMeeting] = []
        self._pending_signals: List[InvestmentSignal] = []
        self._signal_callbacks: List[Callable[[InvestmentSignal], Awaitable[None]]] = []
        self._meeting_callbacks: List[Callable[[CouncilMeeting], Awaitable[None]]] = []

        # 설정
        self.auto_execute = False          # 자동 체결 여부
        self.min_confidence = 0.6          # 최소 신뢰도
        self.meeting_trigger_score = 7     # 회의 소집 기준 점수

    def add_signal_callback(self, callback: Callable[[InvestmentSignal], Awaitable[None]]):
        """시그널 생성 시 콜백 등록"""
        self._signal_callbacks.append(callback)

    def add_meeting_callback(self, callback: Callable[[CouncilMeeting], Awaitable[None]]):
        """회의 업데이트 시 콜백 등록 (실시간 스트리밍용)"""
        self._meeting_callbacks.append(callback)

    async def _notify_signal(self, signal: InvestmentSignal):
        """시그널 알림"""
        for callback in self._signal_callbacks:
            try:
                await callback(signal)
            except Exception as e:
                logger.error(f"시그널 콜백 오류: {e}")

    async def _notify_meeting_update(self, meeting: CouncilMeeting):
        """회의 업데이트 알림"""
        for callback in self._meeting_callbacks:
            try:
                await callback(meeting)
            except Exception as e:
                logger.error(f"회의 콜백 오류: {e}")

    async def start_meeting(
        self,
        symbol: str,
        company_name: str,
        news_title: str,
        news_score: int,
        available_amount: int = 1000000,
        current_price: int = 0,
    ) -> CouncilMeeting:
        """AI 투자 회의 시작"""

        # 회의 생성
        meeting = CouncilMeeting(
            symbol=symbol,
            company_name=company_name,
            news_title=news_title,
            news_score=news_score,
        )

        # 1. 회의 소집 메시지
        opening_msg = CouncilMessage(
            role=AnalystRole.GEMINI_JUDGE,
            speaker="Gemini 뉴스 판단",
            content=f"""🔔 **AI 투자 회의 소집**

트리거 뉴스: "{news_title}"
뉴스 점수: {news_score}/10

이 뉴스가 {company_name}({symbol})의 주가에 긍정적 영향을 줄 것으로 판단됩니다.
투자 회의를 시작합니다.""",
            data={"news_score": news_score, "trigger": "news"},
        )
        meeting.add_message(opening_msg)
        await self._notify_meeting_update(meeting)

        # 2. 라운드 1: 초기 분석
        meeting.current_round = 1

        # GPT 퀀트 분석
        quant_msg = await quant_analyst.analyze(
            symbol=symbol,
            company_name=company_name,
            news_title=news_title,
            previous_messages=meeting.messages,
        )
        meeting.add_message(quant_msg)
        await self._notify_meeting_update(meeting)

        quant_percent = quant_msg.data.get("suggested_percent", 0) if quant_msg.data else 0
        quant_score = quant_msg.data.get("score", 5) if quant_msg.data else 5

        # Claude 펀더멘털 분석
        fundamental_msg = await fundamental_analyst.analyze(
            symbol=symbol,
            company_name=company_name,
            news_title=news_title,
            previous_messages=meeting.messages,
        )
        meeting.add_message(fundamental_msg)
        await self._notify_meeting_update(meeting)

        fundamental_percent = fundamental_msg.data.get("suggested_percent", 0) if fundamental_msg.data else 0
        fundamental_score = fundamental_msg.data.get("score", 5) if fundamental_msg.data else 5

        # 3. 라운드 2: 상호 검토 및 조정
        meeting.current_round = 2

        # GPT가 Claude 의견에 응답
        quant_response = await quant_analyst.respond_to(
            symbol=symbol,
            company_name=company_name,
            news_title=news_title,
            previous_messages=meeting.messages,
            other_analysis=fundamental_msg.content,
        )
        meeting.add_message(quant_response)
        await self._notify_meeting_update(meeting)

        # 업데이트된 퀀트 제안
        if quant_response.data and "suggested_percent" in quant_response.data:
            quant_percent = quant_response.data["suggested_percent"]

        # Claude가 GPT 응답에 응답
        fundamental_response = await fundamental_analyst.respond_to(
            symbol=symbol,
            company_name=company_name,
            news_title=news_title,
            previous_messages=meeting.messages,
            other_analysis=quant_response.content,
        )
        meeting.add_message(fundamental_response)
        await self._notify_meeting_update(meeting)

        # 업데이트된 펀더멘털 제안
        if fundamental_response.data and "suggested_percent" in fundamental_response.data:
            fundamental_percent = fundamental_response.data["suggested_percent"]

        # 4. 라운드 3: 합의 도출
        meeting.current_round = 3

        # 최종 합의안
        consensus_msg = await fundamental_analyst.propose_consensus(
            symbol=symbol,
            company_name=company_name,
            news_title=news_title,
            previous_messages=meeting.messages,
            quant_percent=quant_percent,
            fundamental_percent=fundamental_percent,
        )
        meeting.add_message(consensus_msg)
        await self._notify_meeting_update(meeting)

        # 최종 투자 비율 결정
        final_percent = consensus_msg.data.get("suggested_percent", 0) if consensus_msg.data else 0
        if final_percent == 0:
            final_percent = (quant_percent + fundamental_percent) / 2

        # 5. 시그널 생성
        suggested_amount = int(available_amount * final_percent / 100)
        suggested_quantity = suggested_amount // current_price if current_price > 0 else 0

        # 신뢰도 계산
        confidence = (quant_score + fundamental_score) / 20  # 0-1 스케일

        signal = InvestmentSignal(
            symbol=symbol,
            company_name=company_name,
            action="BUY" if final_percent > 0 else "HOLD",
            allocation_percent=final_percent,
            suggested_amount=suggested_amount,
            suggested_quantity=suggested_quantity,
            quant_summary=quant_msg.content[:100] + "..." if len(quant_msg.content) > 100 else quant_msg.content,
            fundamental_summary=fundamental_msg.content[:100] + "..." if len(fundamental_msg.content) > 100 else fundamental_msg.content,
            consensus_reason=consensus_msg.content[:200] + "..." if len(consensus_msg.content) > 200 else consensus_msg.content,
            confidence=confidence,
            quant_score=quant_score,
            fundamental_score=fundamental_score,
        )

        # 자동 체결 여부 결정
        if self.auto_execute and confidence >= self.min_confidence:
            signal.status = SignalStatus.AUTO_EXECUTED
            signal.executed_at = datetime.now()
        else:
            signal.status = SignalStatus.PENDING

        meeting.signal = signal
        meeting.consensus_reached = True
        meeting.ended_at = datetime.now()

        # 6. 최종 결론 메시지
        conclusion_msg = CouncilMessage(
            role=AnalystRole.MODERATOR,
            speaker="회의 중재자",
            content=f"""⚖️ **회의 결론**

📌 최종 결정: {signal.action}
💰 투자 비율: {signal.allocation_percent:.1f}%
💵 제안 금액: {signal.suggested_amount:,}원
📊 신뢰도: {signal.confidence:.0%}

퀀트 점수: {signal.quant_score}/10
펀더멘털 점수: {signal.fundamental_score}/10

상태: {"✅ 자동 체결됨" if signal.status == SignalStatus.AUTO_EXECUTED else "⏳ 승인 대기 중"}""",
            data=signal.to_dict(),
        )
        meeting.add_message(conclusion_msg)
        await self._notify_meeting_update(meeting)

        # 저장
        self._meetings.append(meeting)
        if signal.status == SignalStatus.PENDING:
            self._pending_signals.append(signal)

        # 콜백 알림
        await self._notify_signal(signal)

        logger.info(f"AI 회의 완료: {company_name} - {signal.action} {signal.allocation_percent}%")

        return meeting

    def get_pending_signals(self) -> List[InvestmentSignal]:
        """대기 중인 시그널 목록"""
        return [s for s in self._pending_signals if s.status == SignalStatus.PENDING]

    def get_meeting(self, meeting_id: str) -> Optional[CouncilMeeting]:
        """회의 조회"""
        for meeting in self._meetings:
            if meeting.id == meeting_id:
                return meeting
        return None

    def get_recent_meetings(self, limit: int = 10) -> List[CouncilMeeting]:
        """최근 회의 목록"""
        return self._meetings[-limit:]

    async def approve_signal(self, signal_id: str) -> Optional[InvestmentSignal]:
        """시그널 승인"""
        for signal in self._pending_signals:
            if signal.id == signal_id and signal.status == SignalStatus.PENDING:
                signal.status = SignalStatus.APPROVED
                logger.info(f"시그널 승인됨: {signal.symbol} {signal.action}")
                return signal
        return None

    async def reject_signal(self, signal_id: str) -> Optional[InvestmentSignal]:
        """시그널 거부"""
        for signal in self._pending_signals:
            if signal.id == signal_id and signal.status == SignalStatus.PENDING:
                signal.status = SignalStatus.REJECTED
                logger.info(f"시그널 거부됨: {signal.symbol}")
                return signal
        return None

    async def execute_signal(self, signal_id: str) -> Optional[InvestmentSignal]:
        """시그널 체결 (실제 주문 실행)"""
        for signal in self._pending_signals:
            if signal.id == signal_id and signal.status == SignalStatus.APPROVED:
                # 여기서 실제 키움 API 호출
                # from app.services.kiwoom.rest_client import kiwoom_client
                # await kiwoom_client.buy_stock(...)

                signal.status = SignalStatus.EXECUTED
                signal.executed_at = datetime.now()
                logger.info(f"시그널 체결됨: {signal.symbol} {signal.action} {signal.suggested_amount:,}원")
                return signal
        return None

    def set_auto_execute(self, enabled: bool):
        """자동 체결 설정"""
        self.auto_execute = enabled
        logger.info(f"자동 체결 {'활성화' if enabled else '비활성화'}")


# 싱글톤 인스턴스
council_orchestrator = CouncilOrchestrator()

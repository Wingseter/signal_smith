"""
AI 투자 회의 오케스트레이터

회의 진행을 관리하고 합의를 도출하는 오케스트레이터

v2: 키움증권 실제 차트 데이터 연동
v3: 자동 매매, SELL 시그널, 거래 시간 체크, 비용 관리 추가
v4: risk_gate / sell_meeting / order_executor 모듈로 분해
"""

import logging
import asyncio
from datetime import date, datetime, timedelta
from typing import Optional, List, Callable, Awaitable

from app.config import settings
from app.services.kiwoom.rest_client import kiwoom_client, OrderSide, OrderType
from .models import (
    CouncilMeeting, CouncilMessage, InvestmentSignal,
    SignalStatus, AnalystRole
)
from .quant_analyst import quant_analyst
from .fundamental_analyst import fundamental_analyst
from .technical_indicators import technical_calculator, TechnicalAnalysisResult
from .llm_utils import call_analyst_with_timeout
from app.services.dart_client import dart_client, FinancialData
from .trading_hours import trading_hours, MarketSession, get_kst_now
from .cost_manager import cost_manager, AnalysisDepth
from .risk_gate import (
    check_buy_gates, check_data_quality_gate, determine_action,
    clamp_stop_loss, clamp_target_price,
)

logger = logging.getLogger(__name__)


class CouncilOrchestrator:
    """AI 투자 회의 오케스트레이터"""

    def __init__(self):
        self._meetings: List[CouncilMeeting] = []
        self._pending_signals: List[InvestmentSignal] = []
        self._signal_callbacks: List[Callable[[InvestmentSignal], Awaitable[None]]] = []
        self._meeting_callbacks: List[Callable[[CouncilMeeting], Awaitable[None]]] = []

        # 설정
        self.auto_execute = True           # 자동 체결 여부 (기본 ON)
        self.min_confidence = 0.6          # 최소 신뢰도
        self.meeting_trigger_score = 7     # 회의 소집 기준 점수
        self.respect_trading_hours = True  # 거래 시간 존중 여부
        self._queued_executions: List[InvestmentSignal] = []  # 거래 시간 대기 큐

    # ─── Callbacks ───

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

    # ─── Data Fetching ───

    async def _fetch_technical_data(self, symbol: str) -> Optional[TechnicalAnalysisResult]:
        """키움증권에서 차트 데이터 조회 및 기술적 지표 계산"""
        try:
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

            logger.info(f"[{symbol}] 일봉 데이터 {len(daily_prices)}개 조회 완료")

            technical_result = technical_calculator.analyze(symbol, daily_prices)

            logger.info(
                f"[{symbol}] 기술적 분석 완료 - "
                f"현재가: {technical_result.current_price:,}원, "
                f"RSI: {technical_result.rsi_14}, "
                f"점수: {technical_result.technical_score}/10"
            )

            return technical_result

        except ImportError:
            logger.error("키움 클라이언트 모듈 임포트 실패")
            return None
        except Exception as e:
            logger.error(f"기술적 데이터 조회 오류 [{symbol}]: {e}")
            return None

    async def _fetch_financial_data(self, symbol: str) -> Optional[FinancialData]:
        """DART에서 재무제표 데이터 조회"""
        try:
            financial_data = await dart_client.get_financial_data_by_stock_code(symbol)

            if not financial_data:
                logger.warning(f"[{symbol}] DART 재무제표 데이터 없음")
                return None

            logger.info(
                f"[{symbol}] DART 재무제표 조회 완료 - "
                f"매출: {financial_data.revenue:,}원, "
                f"PER: {financial_data.per}, "
                f"ROE: {financial_data.roe}%"
                if financial_data.revenue else f"[{symbol}] DART 재무제표 일부 데이터 없음"
            )

            return financial_data

        except Exception as e:
            logger.error(f"DART 재무제표 조회 오류 [{symbol}]: {e}")
            return None

    # ─── BUY Meeting ───

    async def start_meeting(
        self,
        symbol: str,
        company_name: str,
        news_title: str,
        news_score: int,
        available_amount: int = 1000000,
        current_price: int = 0,
        trigger_source: str = "news",
        quant_triggers: Optional[dict] = None,
    ) -> CouncilMeeting:
        """AI 투자 회의 시작"""

        meeting = CouncilMeeting(
            symbol=symbol,
            company_name=company_name,
            news_title=news_title,
            news_score=news_score,
            trigger_source=trigger_source,
        )

        # 0. 키움증권에서 실제 차트 데이터 조회
        technical_data = await self._fetch_technical_data(symbol)
        financial_data = await self._fetch_financial_data(symbol)

        if technical_data and technical_data.current_price > 0:
            current_price = technical_data.current_price

        # 1. 회의 소집 메시지
        chart_status = "📈 키움증권 실시간 데이터" if technical_data else "⚠️ 차트 데이터 없음"
        dart_status = "📋 DART 재무제표" if financial_data else "⚠️ 재무제표 없음"
        data_status = f"{chart_status} | {dart_status}"

        if trigger_source == "quant" and quant_triggers:
            bullish = quant_triggers.get("bullish_count", 0)
            bearish = quant_triggers.get("bearish_count", 0)
            score = quant_triggers.get("composite_score", 0)
            trigger_names = [t.get("name", t.get("id", "")) for t in quant_triggers.get("triggers", []) if t.get("signal") == "bullish"]
            trigger_summary = ", ".join(trigger_names[:5]) if trigger_names else "복수 지표"
            opening_content = f"""🔔 **AI 투자 회의 소집**

트리거: 퀀트 룰 기반 매수 신호
종합 점수: {score}/100 (매수 {bullish}개 | 매도 {bearish}개)
주요 신호: {trigger_summary}

{company_name}({symbol})에 대해 룰 기반 퀀트 분석이 매수 신호를 발생시켰습니다.
AI 회의를 통해 투자 여부를 최종 결정합니다.

{data_status}"""
            opening_data = {
                "news_score": news_score,
                "trigger": "quant",
                "composite_score": score,
                "has_chart_data": technical_data is not None,
                "has_financial_data": financial_data is not None,
            }
        else:
            opening_content = f"""🔔 **AI 투자 회의 소집**

트리거 뉴스: "{news_title}"
뉴스 점수: {news_score}/10

이 뉴스가 {company_name}({symbol})의 주가에 긍정적 영향을 줄 것으로 판단됩니다.
투자 회의를 시작합니다.

{data_status}"""
            opening_data = {
                "news_score": news_score,
                "trigger": "news",
                "has_chart_data": technical_data is not None,
                "has_financial_data": financial_data is not None,
            }

        opening_msg = CouncilMessage(
            role=AnalystRole.GEMINI_JUDGE,
            speaker="Gemini 뉴스 판단",
            content=opening_content,
            data=opening_data,
        )
        meeting.add_message(opening_msg)
        await self._notify_meeting_update(meeting)

        # 데이터 품질 추적
        analysis_failures = 0

        # 2. 라운드 1: 초기 분석
        meeting.current_round = 1

        # GPT 퀀트 분석
        quant_msg, quant_ok = await call_analyst_with_timeout(
            quant_analyst.analyze(
                symbol=symbol,
                company_name=company_name,
                news_title=news_title,
                previous_messages=meeting.messages,
                technical_data=technical_data,
                quant_trigger_data=quant_triggers if trigger_source == "quant" else None,
            ),
            fallback_role=AnalystRole.GPT_QUANT,
            fallback_speaker="퀀트 분석가",
            fallback_content="[시스템 경고] 퀀트 분석가 API 응답 지연으로 기본 판단을 적용합니다. 차트 및 기술적 지표 단독 결정에 유의하세요.",
            fallback_data={"suggested_percent": 0, "score": 5},
        )
        if not quant_ok:
            analysis_failures += 1
        meeting.add_message(quant_msg)
        await self._notify_meeting_update(meeting)
        quant_percent = quant_msg.data.get("suggested_percent", 0) if quant_msg.data else 0
        quant_score = quant_msg.data.get("score", 5) if quant_msg.data else 5

        # Claude 펀더멘털 분석
        fundamental_msg, fund_ok = await call_analyst_with_timeout(
            fundamental_analyst.analyze(
                symbol=symbol,
                company_name=company_name,
                news_title=news_title,
                previous_messages=meeting.messages,
                financial_data=financial_data,
            ),
            fallback_role=AnalystRole.CLAUDE_FUNDAMENTAL,
            fallback_speaker="기본적 분석가",
            fallback_content="[시스템 경고] 기본적 분석가 API 응답 지연으로 기본 판단을 적용합니다. 재무 데이터 단독 결정에 유의하세요.",
            fallback_data={"suggested_percent": 0, "score": 5},
        )
        if not fund_ok:
            analysis_failures += 1
        meeting.add_message(fundamental_msg)
        await self._notify_meeting_update(meeting)
        fundamental_percent = fundamental_msg.data.get("suggested_percent", 0) if fundamental_msg.data else 0
        fundamental_score = fundamental_msg.data.get("score", 5) if fundamental_msg.data else 5

        # 3. 라운드 2: 상호 검토 및 조정
        meeting.current_round = 2

        quant_response, qr_ok = await call_analyst_with_timeout(
            quant_analyst.respond_to(
                symbol=symbol,
                company_name=company_name,
                news_title=news_title,
                previous_messages=meeting.messages,
                other_analysis=fundamental_msg.content,
                technical_data=technical_data,
                quant_trigger_data=quant_triggers if trigger_source == "quant" else None,
            ),
            fallback_role=AnalystRole.GPT_QUANT,
            fallback_speaker="퀀트 응답",
            fallback_content="[시스템 경고] 퀀트 분석가 상호 검토 응답 지연으로 기존 의견을 유지합니다.",
            fallback_data={"suggested_percent": quant_percent, "score": quant_score},
        )
        meeting.add_message(quant_response)
        if qr_ok:
            await self._notify_meeting_update(meeting)
            if quant_response.data and "suggested_percent" in quant_response.data:
                quant_percent = quant_response.data["suggested_percent"]

        fundamental_response, fr_ok = await call_analyst_with_timeout(
            fundamental_analyst.respond_to(
                symbol=symbol,
                company_name=company_name,
                news_title=news_title,
                previous_messages=meeting.messages,
                other_analysis=quant_response.content,
            ),
            fallback_role=AnalystRole.CLAUDE_FUNDAMENTAL,
            fallback_speaker="기본적 응답",
            fallback_content="[시스템 경고] 기본적 분석가 상호 검토 응답 지연으로 기존 의견을 유지합니다.",
            fallback_data={"suggested_percent": fundamental_percent, "score": fundamental_score},
        )
        meeting.add_message(fundamental_response)
        if fr_ok:
            await self._notify_meeting_update(meeting)
            if fundamental_response.data and "suggested_percent" in fundamental_response.data:
                fundamental_percent = fundamental_response.data["suggested_percent"]

        # 4. 라운드 3: 합의 도출
        meeting.current_round = 3

        consensus_msg, cons_ok = await call_analyst_with_timeout(
            fundamental_analyst.propose_consensus(
                symbol=symbol,
                company_name=company_name,
                news_title=news_title,
                previous_messages=meeting.messages,
                quant_percent=quant_percent,
                fundamental_percent=fundamental_percent,
            ),
            fallback_role=AnalystRole.CLAUDE_FUNDAMENTAL,
            fallback_speaker="최종 합의",
            fallback_content="[시스템 경고] 의견 통합 과정 지연으로 양측 분석가 의견의 산술 평균을 최종 비율로 적용합니다.",
            fallback_data={"suggested_percent": (quant_percent + fundamental_percent) / 2},
        )
        meeting.add_message(consensus_msg)
        if cons_ok:
            await self._notify_meeting_update(meeting)
        final_percent = consensus_msg.data.get("suggested_percent", 0) if consensus_msg.data else 0

        if final_percent == 0:
            final_percent = (quant_percent + fundamental_percent) / 2

        # 단일 매매 최대 25% 제한 (부호 보존)
        if final_percent >= 0:
            final_percent = min(25, final_percent)
        else:
            final_percent = max(-25, final_percent)

        # 데이터 품질 게이트
        dq_gate = check_data_quality_gate(symbol, analysis_failures)
        if dq_gate.blocked:
            logger.warning(f"🚫 {dq_gate.reason}")
            gate_msg = CouncilMessage(
                role=AnalystRole.MODERATOR,
                speaker="리스크 관리자",
                content=(
                    f"🚫 **데이터 품질 게이트 차단**\n\n"
                    f"AI 분석가 {analysis_failures}명 모두 분석 실패.\n"
                    f"불완전한 데이터로 매매 결정을 내릴 수 없어 시그널을 폐기합니다."
                ),
                data={"gate": "data_quality", "failures": analysis_failures},
            )
            meeting.add_message(gate_msg)
            await self._notify_meeting_update(meeting)
            meeting.ended_at = datetime.now()
            return meeting

        # 보유 기한 결정
        holding_days = 7
        if consensus_msg.data:
            raw_days = consensus_msg.data.get("holding_days", 7)
            holding_days = min(10, int(raw_days))
        holding_deadline = date.today() + timedelta(days=holding_days)

        # 5. 시그널 생성
        suggested_amount = int(available_amount * final_percent / 100)
        suggested_quantity = suggested_amount // current_price if current_price > 0 else 0

        base_confidence = (quant_score + fundamental_score) / 20
        score_diff = abs(quant_score - fundamental_score)
        agreement_bonus = max(0, (5 - score_diff) * 0.02)
        confidence = min(0.95, base_confidence + agreement_bonus)

        if analysis_failures == 1:
            confidence = max(0, confidence - 0.15)
            logger.info(
                f"데이터 품질 경고: {symbol} — 분석 1건 실패, "
                f"신뢰도 -0.15 적용 → {confidence:.2f}"
            )

        entry_price = quant_msg.data.get("entry_price") if quant_msg.data else None
        stop_loss = quant_msg.data.get("stop_loss") if quant_msg.data else None
        target_price = quant_msg.data.get("target_price") if quant_msg.data else None

        action = determine_action(
            final_percent=final_percent,
            quant_score=quant_score,
            fundamental_score=fundamental_score,
            news_score=news_score,
            trigger_source=trigger_source,
        )

        # SELL 시그널 보유 여부 확인
        if action == "SELL":
            try:
                holdings = await kiwoom_client.get_holdings()
                held_symbols = [h.symbol for h in holdings]
                if symbol not in held_symbols:
                    logger.info(f"SELL → HOLD 변경: {symbol} 미보유 종목")
                    action = "HOLD"
            except Exception as e:
                logger.warning(f"보유 확인 실패, SELL → HOLD: {symbol} - {e}")
                action = "HOLD"

        # 3중 게이트 (BUY 시그널만)
        if action == "BUY":
            gate_result = await check_buy_gates(symbol, suggested_amount)
            if gate_result.blocked:
                logger.info(f"🚫 게이트 차단: {symbol} — {gate_result.reason}")
                action = "HOLD"
                gate_msg = CouncilMessage(
                    role=AnalystRole.MODERATOR,
                    speaker="리스크 관리자",
                    content=(
                        f"🚫 **매수 차단 (포트폴리오 규율)**\n\n"
                        f"{gate_result.reason}\n\n"
                        f"원래 결정(BUY {final_percent:.1f}%)을 HOLD로 전환합니다."
                    ),
                    data={"gate_blocked": True, "gate_reason": gate_result.reason},
                )
                meeting.add_message(gate_msg)
                await self._notify_meeting_update(meeting)

        signal = InvestmentSignal(
            symbol=symbol,
            company_name=company_name,
            action=action,
            allocation_percent=abs(final_percent),
            suggested_amount=suggested_amount,
            suggested_quantity=suggested_quantity,
            target_price=clamp_target_price(target_price, current_price),
            stop_loss_price=clamp_stop_loss(stop_loss, current_price),
            quant_summary=quant_msg.content[:100] + "..." if len(quant_msg.content) > 100 else quant_msg.content,
            fundamental_summary=fundamental_msg.content[:100] + "..." if len(fundamental_msg.content) > 100 else fundamental_msg.content,
            consensus_reason=consensus_msg.content[:200] + "..." if len(consensus_msg.content) > 200 else consensus_msg.content,
            confidence=confidence,
            quant_score=quant_score,
            fundamental_score=fundamental_score,
        )

        # quantity=0이면 HOLD 전환
        if action in ("BUY", "SELL") and signal.suggested_quantity <= 0:
            logger.info(
                f"HOLD 전환: {symbol} quantity=0 "
                f"(투자금액 {suggested_amount:,}원 < 1주 가격 {current_price:,}원)"
            )
            signal.action = "HOLD"
            action = "HOLD"

        if action == "HOLD":
            signal.status = SignalStatus.PENDING
        elif self.auto_execute and confidence >= self.min_confidence:
            if action == "BUY":
                try:
                    balance = await kiwoom_client.get_balance()
                    if balance.available_amount < signal.suggested_amount:
                        logger.warning(
                            f"잔고 부족 — 시그널 취소: {symbol} "
                            f"(필요 {signal.suggested_amount:,}원 > 가용 {balance.available_amount:,}원)"
                        )
                        return meeting
                except Exception as e:
                    logger.warning(f"잔고 확인 실패, 계속 진행: {e}")
            can_trade, trade_reason = trading_hours.can_execute_order()

            if can_trade or not self.respect_trading_hours:
                try:
                    side = OrderSide.BUY if action == "BUY" else OrderSide.SELL
                    order_result = await kiwoom_client.place_order(
                        symbol=symbol,
                        side=side,
                        quantity=signal.suggested_quantity,
                        price=0,
                        order_type=OrderType.MARKET,
                    )

                    if order_result.status == "submitted":
                        signal.status = SignalStatus.AUTO_EXECUTED
                        signal.executed_at = get_kst_now()
                        logger.info(
                            f"✅ 자동 체결 성공: {symbol} {action} "
                            f"{signal.suggested_quantity}주 (주문번호: {order_result.order_no})"
                        )
                    else:
                        signal.status = SignalStatus.QUEUED
                        self.queue_execution(signal)
                        logger.warning(
                            f"⚠️ 자동 체결 실패, 대기 큐 추가: {symbol} {action} - {order_result.message}"
                        )
                except Exception as e:
                    signal.status = SignalStatus.QUEUED
                    self.queue_execution(signal)
                    logger.error(f"❌ 자동 체결 오류, 대기 큐 추가: {symbol} {action} - {e}")
            else:
                signal.status = SignalStatus.QUEUED
                self.queue_execution(signal)
                logger.info(f"⏳ 거래 시간 대기: {symbol} {action} - {trade_reason}")
        else:
            if self.auto_execute:
                logger.info(f"자동매매 모드 — 신뢰도 미달 시그널 버림: {symbol} (신뢰도 {confidence:.0%} < {self.min_confidence:.0%})")
                return meeting
            signal.status = SignalStatus.PENDING

        cost_manager.record_analysis(symbol, AnalysisDepth.FULL)

        meeting.signal = signal
        meeting.consensus_reached = True
        meeting.ended_at = datetime.now()

        # 6. 최종 결론 메시지
        price_info = ""
        if signal.action == "BUY" and entry_price:
            price_info = f"""
📍 매매 전략:
• 진입가: {entry_price:,}원
• 손절가: {stop_loss:,}원
• 목표가: {target_price:,}원"""

        if signal.action == "BUY":
            deadline_info = f"⏰ 보유 기한: {holding_deadline.strftime('%Y-%m-%d')} ({holding_days}일, 목표가 미달 시 자동 매도)"
        else:
            deadline_info = ""

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
{price_info}
{deadline_info}
상태: {"✅ 자동 체결됨" if signal.status == SignalStatus.AUTO_EXECUTED else "⏳ 구매 대기 중 (장 개시 후 자동 체결)" if signal.status == SignalStatus.QUEUED else "⏳ 승인 대기 중"}

📊 데이터 소스:
{"• 📈 키움증권 실시간 차트 데이터" if technical_data else "• ⚠️ 차트 데이터 없음"}
{"• 📋 DART 전자공시 재무제표" if financial_data else "• ⚠️ 재무제표 없음"}""",
            data=signal.to_dict(),
        )
        meeting.add_message(conclusion_msg)
        await self._notify_meeting_update(meeting)

        self.add_meeting(meeting)
        if signal.status == SignalStatus.PENDING:
            self.add_pending_signal(signal)

        await self._notify_signal(signal)
        await self._persist_signal_to_db(
            signal,
            trigger_source=meeting.trigger_source,
            trigger_details=quant_triggers,
            holding_deadline=holding_deadline if signal.action == "BUY" else None,
        )

        logger.info(f"AI 회의 완료: {company_name} - {signal.action} {signal.allocation_percent}%")

        return meeting

    # ─── State Mutation Interface ───

    def add_meeting(self, meeting: CouncilMeeting) -> None:
        self._meetings.append(meeting)

    def add_pending_signal(self, signal: InvestmentSignal) -> None:
        self._pending_signals.append(signal)

    def queue_execution(self, signal: InvestmentSignal) -> None:
        self._queued_executions.append(signal)

    def set_queued_executions(self, signals: List[InvestmentSignal]) -> None:
        self._queued_executions = signals

    def iter_pending_signals(self) -> List[InvestmentSignal]:
        return list(self._pending_signals)

    # ─── Getters ───

    def get_pending_signals(self) -> List[InvestmentSignal]:
        return [s for s in self._pending_signals if s.status == SignalStatus.PENDING]

    def get_meeting(self, meeting_id: str) -> Optional[CouncilMeeting]:
        for meeting in self._meetings:
            if meeting.id == meeting_id:
                return meeting
        return None

    def get_recent_meetings(self, limit: int = 10) -> List[CouncilMeeting]:
        return self._meetings[-limit:]

    def get_queued_executions(self) -> List[InvestmentSignal]:
        return self._queued_executions.copy()

    def get_trading_status(self) -> dict:
        session = trading_hours.get_market_session()
        can_trade, reason = trading_hours.can_execute_order()
        return {
            "session": session.value,
            "can_trade": can_trade,
            "reason": reason,
            "status_message": trading_hours.get_status_message(),
            "queued_count": len(self._queued_executions),
            "auto_execute": self.auto_execute,
            "respect_trading_hours": self.respect_trading_hours,
        }

    def get_cost_stats(self) -> dict:
        return cost_manager.get_stats()

    def set_auto_execute(self, enabled: bool):
        self.auto_execute = enabled
        logger.info(f"자동 체결 {'활성화' if enabled else '비활성화'}")

    # ─── Delegated to order_executor ───

    async def approve_signal(self, signal_id: str) -> Optional[InvestmentSignal]:
        from .order_executor import approve_signal
        return await approve_signal(self, signal_id)

    async def reject_signal(self, signal_id: str) -> Optional[InvestmentSignal]:
        from .order_executor import reject_signal
        return await reject_signal(self, signal_id)

    async def execute_signal(self, signal_id: str) -> Optional[InvestmentSignal]:
        from .order_executor import execute_signal
        return await execute_signal(self, signal_id)

    async def process_queued_executions(self):
        from .order_executor import process_queued_executions
        return await process_queued_executions(self)

    async def _persist_signal_to_db(self, signal, **kwargs):
        from .order_executor import persist_signal_to_db
        return await persist_signal_to_db(self, signal, **kwargs)

    async def restore_pending_signals(self):
        from .order_executor import restore_pending_signals
        return await restore_pending_signals(self)

    async def _update_signal_status_in_db(self, signal, **kwargs):
        from .order_executor import update_signal_status_in_db
        return await update_signal_status_in_db(self, signal, **kwargs)

    # ─── Delegated to sell_meeting ───

    async def start_sell_meeting(self, **kwargs) -> CouncilMeeting:
        from .sell_meeting import run_sell_meeting
        return await run_sell_meeting(self, **kwargs)

    async def start_rebalance_review(self, **kwargs) -> Optional[dict]:
        from .sell_meeting import run_rebalance_review
        return await run_rebalance_review(self, **kwargs)


# 싱글톤 인스턴스
council_orchestrator = CouncilOrchestrator()

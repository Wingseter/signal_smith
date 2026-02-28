"""
AI 투자 회의 오케스트레이터

회의 진행을 관리하고 합의를 도출하는 오케스트레이터

v2: 키움증권 실제 차트 데이터 연동
v3: 자동 매매, SELL 시그널, 거래 시간 체크, 비용 관리 추가
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
from app.services.dart_client import dart_client, FinancialData
from .trading_hours import trading_hours, MarketSession, get_kst_now
from .cost_manager import cost_manager, AnalysisDepth
from app.services.trading_service import trading_service

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

    async def _fetch_technical_data(self, symbol: str) -> Optional[TechnicalAnalysisResult]:
        """키움증권에서 차트 데이터 조회 및 기술적 지표 계산"""
        try:
            from app.services.kiwoom.rest_client import kiwoom_client

            # 키움 API 연결 확인
            if not await kiwoom_client.is_connected():
                try:
                    await kiwoom_client.connect()
                except Exception as conn_error:
                    logger.warning(f"키움 API 연결 실패: {conn_error}")
                    return None

            # 일봉 데이터 조회 (최근 100일)
            daily_prices = await kiwoom_client.get_daily_prices(symbol)

            if not daily_prices:
                logger.warning(f"[{symbol}] 일봉 데이터 없음")
                return None

            logger.info(f"[{symbol}] 일봉 데이터 {len(daily_prices)}개 조회 완료")

            # 기술적 지표 계산
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
            # 종목코드로 재무제표 조회
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

        # 회의 생성
        meeting = CouncilMeeting(
            symbol=symbol,
            company_name=company_name,
            news_title=news_title,
            news_score=news_score,
            trigger_source=trigger_source,
        )

        # 0. 키움증권에서 실제 차트 데이터 조회
        technical_data = await self._fetch_technical_data(symbol)

        # 0-2. DART에서 재무제표 데이터 조회
        financial_data = await self._fetch_financial_data(symbol)

        # 실시간 현재가 업데이트
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

        # 데이터 품질 추적 (Phase 1)
        analysis_failures = 0

        # 2. 라운드 1: 초기 분석
        meeting.current_round = 1

        # GPT 퀀트 분석 (실제 차트 데이터 전달, 퀀트 트리거 시 룰 기반 결과도 포함)
        try:
            quant_msg = await asyncio.wait_for(
                quant_analyst.analyze(
                    symbol=symbol,
                    company_name=company_name,
                    news_title=news_title,
                    previous_messages=meeting.messages,
                    technical_data=technical_data,  # 실제 차트 데이터 전달
                    quant_trigger_data=quant_triggers if trigger_source == "quant" else None,
                ),
                timeout=60.0  # 타임아웃 15초 강제
            )
            meeting.add_message(quant_msg)
            await self._notify_meeting_update(meeting)

            quant_percent = quant_msg.data.get("suggested_percent", 0) if quant_msg.data else 0
            quant_score = quant_msg.data.get("score", 5) if quant_msg.data else 5
        except (asyncio.TimeoutError, Exception) as e:
            logger.error(f"퀀트 분석가 API 호출 실패 또는 타임아웃: {e}")
            analysis_failures += 1
            # Fallback 로직: 기본값 할당 및 에러 메시지 생성
            quant_msg = CouncilMessage(
                role=AnalystRole.GPT_QUANT,
                speaker="시스템",
                content="[시스템 경고] 퀀트 분석가 API 응답 지연으로 기본 판단을 적용합니다. 차트 및 기술적 지표 단독 결정에 유의하세요.",
                data={"suggested_percent": 0, "score": 5}
            )
            meeting.add_message(quant_msg)
            await self._notify_meeting_update(meeting)
            quant_percent = 0
            quant_score = 5

        # Claude 펀더멘털 분석 (DART 실제 재무제표 전달)
        try:
            fundamental_msg = await asyncio.wait_for(
                fundamental_analyst.analyze(
                    symbol=symbol,
                    company_name=company_name,
                    news_title=news_title,
                    previous_messages=meeting.messages,
                    financial_data=financial_data,  # DART 재무제표 데이터 전달
                ),
                timeout=60.0  # 타임아웃 15초 강제
            )
            meeting.add_message(fundamental_msg)
            await self._notify_meeting_update(meeting)

            fundamental_percent = fundamental_msg.data.get("suggested_percent", 0) if fundamental_msg.data else 0
            fundamental_score = fundamental_msg.data.get("score", 5) if fundamental_msg.data else 5
        except (asyncio.TimeoutError, Exception) as e:
            logger.error(f"기본적 분석가 API 호출 실패 또는 타임아웃: {e}")
            analysis_failures += 1
            # Fallback 로직: 기본값 할당 및 에러 메시지 생성
            fundamental_msg = CouncilMessage(
                role=AnalystRole.FUNDAMENTAL,
                speaker="시스템",
                content="[시스템 경고] 기본적 분석가 API 응답 지연으로 기본 판단을 적용합니다. 재무 데이터 단독 결정에 유의하세요.",
                data={"suggested_percent": 0, "score": 5}
            )
            meeting.add_message(fundamental_msg)
            await self._notify_meeting_update(meeting)
            fundamental_percent = 0
            fundamental_score = 5

        # 3. 라운드 2: 상호 검토 및 조정
        meeting.current_round = 2

        # GPT가 Claude 의견에 응답 (차트 데이터 유지)
        try:
            quant_response = await asyncio.wait_for(
                quant_analyst.respond_to(
                    symbol=symbol,
                    company_name=company_name,
                    news_title=news_title,
                    previous_messages=meeting.messages,
                    other_analysis=fundamental_msg.content,
                    technical_data=technical_data,  # 실제 차트 데이터 전달
                    quant_trigger_data=quant_triggers if trigger_source == "quant" else None,
                ),
                timeout=60.0  # 타임아웃 강제
            )
            meeting.add_message(quant_response)
            await self._notify_meeting_update(meeting)

            # 업데이트된 퀀트 제안
            if quant_response.data and "suggested_percent" in quant_response.data:
                quant_percent = quant_response.data["suggested_percent"]
        except (asyncio.TimeoutError, Exception) as e:
            logger.error(f"퀀트 응답 API 호출 실패 또는 타임아웃: {e}")
            quant_response = CouncilMessage(
                role=AnalystRole.GPT_QUANT,
                speaker="시스템",
                content="[시스템 경고] 퀀트 분석가 상호 검토 응답 지연으로 기존 의견을 유지합니다.",
                data={"suggested_percent": quant_percent, "score": quant_score}
            )
            meeting.add_message(quant_response)

        # Claude가 GPT 응답에 응답
        try:
            fundamental_response = await asyncio.wait_for(
                fundamental_analyst.respond_to(
                    symbol=symbol,
                    company_name=company_name,
                    news_title=news_title,
                    previous_messages=meeting.messages,
                    other_analysis=quant_response.content,
                ),
                timeout=60.0  # 타임아웃 강제
            )
            meeting.add_message(fundamental_response)
            await self._notify_meeting_update(meeting)

            # 업데이트된 펀더멘털 제안
            if fundamental_response.data and "suggested_percent" in fundamental_response.data:
                fundamental_percent = fundamental_response.data["suggested_percent"]
        except (asyncio.TimeoutError, Exception) as e:
            logger.error(f"기본적 응답 API 호출 실패 또는 타임아웃: {e}")
            fundamental_response = CouncilMessage(
                role=AnalystRole.FUNDAMENTAL,
                speaker="시스템",
                content="[시스템 경고] 기본적 분석가 상호 검토 응답 지연으로 기존 의견을 유지합니다.",
                data={"suggested_percent": fundamental_percent, "score": fundamental_score}
            )
            meeting.add_message(fundamental_response)

        # 4. 라운드 3: 합의 도출
        meeting.current_round = 3

        # 최종 합의안
        try:
            consensus_msg = await asyncio.wait_for(
                fundamental_analyst.propose_consensus(
                    symbol=symbol,
                    company_name=company_name,
                    news_title=news_title,
                    previous_messages=meeting.messages,
                    quant_percent=quant_percent,
                    fundamental_percent=fundamental_percent,
                ),
                timeout=60.0  # 타임아웃 강제
            )
            meeting.add_message(consensus_msg)
            await self._notify_meeting_update(meeting)

            # 최종 투자 비율 결정
            final_percent = consensus_msg.data.get("suggested_percent", 0) if consensus_msg.data else 0
        except (asyncio.TimeoutError, Exception) as e:
            logger.error(f"최종 합의 도출 API 호출 실패 또는 타임아웃: {e}")
            final_percent = (quant_percent + fundamental_percent) / 2
            consensus_msg = CouncilMessage(
                role=AnalystRole.FUNDAMENTAL,
                speaker="시스템",
                content="[시스템 경고] 의견 통합 과정 지연으로 양측 분석가 의견의 산술 평균을 최종 비율로 적용합니다.",
                data={"suggested_percent": final_percent}
            )
            meeting.add_message(consensus_msg)

        if final_percent == 0:
            final_percent = (quant_percent + fundamental_percent) / 2

        # 단일 매매 최대 25% 제한 (부호 보존)
        if final_percent >= 0:
            final_percent = min(25, final_percent)
        else:
            final_percent = max(-25, final_percent)

        # ─── Phase 1: 데이터 품질 게이트 ───
        if analysis_failures >= 2:
            logger.warning(
                f"🚫 데이터 품질 게이트 차단: {symbol} — "
                f"분석 실패 {analysis_failures}건 (2건 이상, 시그널 폐기)"
            )
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

        # 보유 기한 결정 (consensus_msg.data에서 holding_days 추출)
        holding_days = 7  # 기본값
        if consensus_msg.data:
            raw_days = consensus_msg.data.get("holding_days", 7)
            holding_days = min(10, int(raw_days))
        holding_deadline = date.today() + timedelta(days=holding_days)

        # 5. 시그널 생성
        suggested_amount = int(available_amount * final_percent / 100)
        suggested_quantity = suggested_amount // current_price if current_price > 0 else 0

        # 신뢰도 계산 - 점수 기반 동적 계산
        base_confidence = (quant_score + fundamental_score) / 20  # 0-1 스케일
        # 두 분석가의 의견 일치도에 따라 신뢰도 조정
        score_diff = abs(quant_score - fundamental_score)
        agreement_bonus = max(0, (5 - score_diff) * 0.02)  # 의견 일치시 최대 +0.1
        confidence = min(0.95, base_confidence + agreement_bonus)

        # 데이터 품질 페널티: 1건 실패 시 신뢰도 -0.15
        if analysis_failures == 1:
            confidence = max(0, confidence - 0.15)
            logger.info(
                f"데이터 품질 경고: {symbol} — 분석 1건 실패, "
                f"신뢰도 -0.15 적용 → {confidence:.2f}"
            )

        # 기술적 분석 데이터가 있으면 진입가/손절가/목표가 포함
        entry_price = quant_msg.data.get("entry_price") if quant_msg.data else None
        stop_loss = quant_msg.data.get("stop_loss") if quant_msg.data else None
        target_price = quant_msg.data.get("target_price") if quant_msg.data else None

        # 액션 결정 로직 개선 (SELL 시그널 포함)
        action = self._determine_action(
            final_percent=final_percent,
            quant_score=quant_score,
            fundamental_score=fundamental_score,
            news_score=news_score,
            trigger_source=trigger_source,
        )

        # SELL 시그널인 경우 보유 여부 확인 — 보유하지 않은 종목은 HOLD로 변경
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

        # ─── Phase 1: 체결 전 3중 게이트 (BUY 시그널만) ───
        if action == "BUY":
            gate_blocked = False
            gate_reason = ""

            try:
                balance = await kiwoom_client.get_balance()
                holdings = await kiwoom_client.get_holdings()
                total_assets = balance.available_amount + balance.total_evaluation

                if total_assets <= 0:
                    total_assets = available_amount  # fallback

                # Gate A: 최소 포지션 금액
                min_position_amount = int(total_assets * settings.min_position_pct / 100)
                if suggested_amount < min_position_amount:
                    gate_blocked = True
                    gate_reason = (
                        f"Gate A 최소 포지션 미달: "
                        f"제안 {suggested_amount:,}원 < "
                        f"최소 {min_position_amount:,}원 "
                        f"(총자산 {total_assets:,}원 x {settings.min_position_pct}%)"
                    )

                # Gate B: 현금 보유 비율
                if not gate_blocked:
                    cash_after_buy = balance.available_amount - suggested_amount
                    min_cash = int(total_assets * settings.min_cash_reserve_pct / 100)
                    if cash_after_buy < min_cash:
                        gate_blocked = True
                        gate_reason = (
                            f"Gate B 현금 보유 부족: "
                            f"매수 후 예상 현금 {cash_after_buy:,}원 < "
                            f"최소 {min_cash:,}원 "
                            f"(총자산 {total_assets:,}원 x {settings.min_cash_reserve_pct}%)"
                        )

                # Gate C: 최대 보유 종목 수
                if not gate_blocked:
                    current_holding_count = len([h for h in holdings if h.quantity > 0])
                    is_additional_buy = any(
                        h.symbol == symbol for h in holdings if h.quantity > 0
                    )
                    if current_holding_count >= settings.max_positions and not is_additional_buy:
                        gate_blocked = True
                        gate_reason = (
                            f"Gate C 최대 종목 수 초과: "
                            f"현재 {current_holding_count}종목 >= "
                            f"최대 {settings.max_positions}종목"
                        )

            except Exception as e:
                logger.warning(f"게이트 검증 실패, 안전하게 차단: {symbol} - {e}")
                gate_blocked = True
                gate_reason = f"게이트 검증 오류: {e}"

            if gate_blocked:
                logger.info(f"🚫 게이트 차단: {symbol} — {gate_reason}")
                action = "HOLD"
                gate_msg = CouncilMessage(
                    role=AnalystRole.MODERATOR,
                    speaker="리스크 관리자",
                    content=(
                        f"🚫 **매수 차단 (포트폴리오 규율)**\n\n"
                        f"{gate_reason}\n\n"
                        f"원래 결정(BUY {final_percent:.1f}%)을 HOLD로 전환합니다."
                    ),
                    data={"gate_blocked": True, "gate_reason": gate_reason},
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
            target_price=self._clamp_target_price(target_price, current_price),
            stop_loss_price=self._clamp_stop_loss(stop_loss, current_price),
            quant_summary=quant_msg.content[:100] + "..." if len(quant_msg.content) > 100 else quant_msg.content,
            fundamental_summary=fundamental_msg.content[:100] + "..." if len(fundamental_msg.content) > 100 else fundamental_msg.content,
            consensus_reason=consensus_msg.content[:200] + "..." if len(consensus_msg.content) > 200 else consensus_msg.content,
            confidence=confidence,
            quant_score=quant_score,
            fundamental_score=fundamental_score,
        )

        # quantity=0이면 체결 불가 → HOLD 전환 (1주 가격 > 투자금액)
        if action in ("BUY", "SELL") and signal.suggested_quantity <= 0:
            logger.info(
                f"HOLD 전환: {symbol} quantity=0 "
                f"(투자금액 {suggested_amount:,}원 < 1주 가격 {current_price:,}원)"
            )
            signal.action = "HOLD"
            action = "HOLD"

        # HOLD는 체결 대상이 아님 — auto_execute 로직 건너뜀
        if action == "HOLD":
            signal.status = SignalStatus.PENDING

        # 자동 체결 여부 결정 (BUY/SELL만)
        elif self.auto_execute and confidence >= self.min_confidence:
            # 잔고 확인 (BUY 시)
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
                # 실제 키움 API 주문 실행
                try:
                    side = OrderSide.BUY if action == "BUY" else OrderSide.SELL
                    order_result = await kiwoom_client.place_order(
                        symbol=symbol,
                        side=side,
                        quantity=signal.suggested_quantity,
                        price=0,  # 시장가 주문
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
                        # 주문 실패 시 대기 큐에 추가
                        signal.status = SignalStatus.QUEUED
                        self._queued_executions.append(signal)
                        logger.warning(
                            f"⚠️ 자동 체결 실패, 대기 큐 추가: {symbol} {action} - {order_result.message}"
                        )
                except Exception as e:
                    # 예외 발생 시 대기 큐에 추가
                    signal.status = SignalStatus.QUEUED
                    self._queued_executions.append(signal)
                    logger.error(f"❌ 자동 체결 오류, 대기 큐 추가: {symbol} {action} - {e}")
            else:
                # 거래 시간이 아니면 대기 큐에 추가
                signal.status = SignalStatus.QUEUED
                self._queued_executions.append(signal)
                logger.info(f"⏳ 거래 시간 대기: {symbol} {action} - {trade_reason}")
        else:
            # 자동매매 켜진 경우 pending 시그널 버림
            if self.auto_execute:
                logger.info(f"자동매매 모드 — 신뢰도 미달 시그널 버림: {symbol} (신뢰도 {confidence:.0%} < {self.min_confidence:.0%})")
                return meeting
            signal.status = SignalStatus.PENDING

        # 비용 기록
        cost_manager.record_analysis(symbol, AnalysisDepth.FULL)

        meeting.signal = signal
        meeting.consensus_reached = True
        meeting.ended_at = datetime.now()

        # 6. 최종 결론 메시지
        # BUY 시그널일 때만 매매 전략 및 보유 기한 표시
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

        # 저장
        self._meetings.append(meeting)
        if signal.status == SignalStatus.PENDING:
            self._pending_signals.append(signal)

        # 콜백 알림
        await self._notify_signal(signal)
        await self._persist_signal_to_db(
            signal,
            trigger_source=meeting.trigger_source,
            trigger_details=quant_triggers,
            holding_deadline=holding_deadline if signal.action == "BUY" else None,
        )

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
        """시그널 승인 - BUY/SELL인 경우 자동으로 체결 시도 또는 대기열 추가"""
        for signal in self._pending_signals:
            if signal.id == signal_id and signal.status == SignalStatus.PENDING:
                signal.status = SignalStatus.APPROVED
                logger.info(f"시그널 승인됨: {signal.symbol} {signal.action}")
                await self._update_signal_status_in_db(signal)

                # HOLD가 아닌 경우 (BUY/SELL) 체결 시도
                if signal.action in ["BUY", "SELL"]:
                    can_trade, reason = trading_hours.can_execute_order()

                    if can_trade or not self.respect_trading_hours:
                        # 거래 가능 시간 - 즉시 체결 시도
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
                                await self._update_signal_status_in_db(signal, executed=True)
                            else:
                                logger.warning(f"주문 실패, 대기열에 추가: {signal.symbol} - {order_result.message}")
                                self._queued_executions.append(signal)
                        except Exception as e:
                            logger.error(f"주문 오류, 대기열에 추가: {signal.symbol} - {e}")
                            self._queued_executions.append(signal)
                    else:
                        # 거래 불가 시간 - 대기열에 추가
                        logger.info(f"거래 시간 외, 대기열에 추가: {signal.symbol} {signal.action} - {reason}")
                        self._queued_executions.append(signal)

                return signal
        return None

    async def reject_signal(self, signal_id: str) -> Optional[InvestmentSignal]:
        """시그널 거부"""
        for signal in self._pending_signals:
            if signal.id == signal_id and signal.status == SignalStatus.PENDING:
                signal.status = SignalStatus.REJECTED
                logger.info(f"시그널 거부됨: {signal.symbol}")
                await self._update_signal_status_in_db(signal, cancelled=True)
                return signal
        return None

    async def execute_signal(self, signal_id: str) -> Optional[InvestmentSignal]:
        """시그널 체결 (실제 주문 실행)"""
        for signal in self._pending_signals:
            if signal.id == signal_id and signal.status == SignalStatus.APPROVED:
                # 거래 시간 체크
                can_trade, reason = trading_hours.can_execute_order()
                if not can_trade and self.respect_trading_hours:
                    logger.warning(f"거래 시간이 아님: {reason} - 대기 큐에 추가")
                    self._queued_executions.append(signal)
                    return signal

                # 실제 키움 API 호출
                try:
                    side = OrderSide.BUY if signal.action == "BUY" else OrderSide.SELL
                    order_result = await kiwoom_client.place_order(
                        symbol=signal.symbol,
                        side=side,
                        quantity=signal.suggested_quantity,
                        price=0,  # 시장가 주문
                        order_type=OrderType.MARKET,
                    )

                    if order_result.status == "submitted":
                        signal.status = SignalStatus.EXECUTED
                        signal.executed_at = get_kst_now()
                        logger.info(
                            f"✅ 시그널 체결 성공: {signal.symbol} {signal.action} "
                            f"{signal.suggested_quantity}주 (주문번호: {order_result.order_no})"
                        )
                        await self._update_signal_status_in_db(signal, executed=True)
                    else:
                        logger.error(
                            f"❌ 주문 실패: {signal.symbol} - {order_result.message}"
                        )
                        # 실패해도 상태는 유지하고 에러 로그만 남김
                        return None

                except Exception as e:
                    logger.error(f"❌ 주문 실행 중 오류: {signal.symbol} - {e}")
                    return None

                return signal
        return None

    def set_auto_execute(self, enabled: bool):
        """자동 체결 설정"""
        self.auto_execute = enabled
        logger.info(f"자동 체결 {'활성화' if enabled else '비활성화'}")

    def _clamp_stop_loss(self, gpt_stop_loss: Optional[int], current_price: int) -> Optional[int]:
        """GPT 손절가를 config 바운드 내로 제한"""
        if not current_price:
            return None

        min_price = int(current_price * (1 - settings.max_stop_loss_percent / 100))
        max_price = int(current_price * (1 - settings.min_stop_loss_percent / 100))

        if gpt_stop_loss:
            return max(min_price, min(max_price, gpt_stop_loss))

        # GPT 값 없으면 기본 % 적용
        return int(current_price * (1 - settings.stop_loss_percent / 100))

    def _clamp_target_price(self, gpt_target: Optional[int], current_price: int) -> Optional[int]:
        """GPT 목표가를 config 바운드 내로 제한"""
        if not current_price:
            return None

        min_price = int(current_price * (1 + settings.min_take_profit_percent / 100))
        max_price = int(current_price * (1 + settings.max_take_profit_percent / 100))

        if gpt_target:
            return max(min_price, min(max_price, gpt_target))

        return int(current_price * (1 + settings.take_profit_percent / 100))

    def _determine_action(
        self,
        final_percent: float,
        quant_score: int,
        fundamental_score: int,
        news_score: int,
        trigger_source: str = "news",
    ) -> str:
        """
        투자 액션 결정 (BUY/SELL/HOLD)

        SELL 조건:
        1. 뉴스 점수가 3 이하 (부정적 뉴스) — 뉴스 트리거만
        2. 퀀트 + 펀더멘털 평균 점수 4 이하
        3. 투자 비율이 음수로 제안됨 (AI가 매도 권장)

        BUY 조건 (뉴스 트리거):
        1. 비율 10%+ AND 평균 점수 6+
        2. 뉴스 점수 8+ AND 평균 점수 5+

        BUY 조건 (퀀트 트리거 — 뉴스 점수 무시):
        1. 비율 10%+ AND 평균 점수 5.5+
        2. 비율 15%+ AND 평균 점수 5+

        HOLD: 그 외
        """
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

        # 퀀트 트리거 BUY 조건 (뉴스 점수 무시, 이미 룰 기반 스캔 통과)
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

    async def _persist_signal_to_db(
        self,
        signal: InvestmentSignal,
        trigger_source: str = "news",
        trigger_details: Optional[dict] = None,
        holding_deadline: Optional[date] = None,
    ):
        """Council 시그널을 DB에 저장"""
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
            signal._db_id = db_id  # DB ID 참조 저장
            logger.info(f"Council signal → DB: {signal.symbol} {signal.action} (id={db_id})")
        except Exception as e:
            logger.error(f"Council signal DB 저장 실패: {signal.symbol} - {e}")

    async def start_rebalance_review(
        self,
        symbol: str,
        company_name: str,
        current_holdings: int,
        avg_buy_price: int,
        current_price: int,
        prev_target_price: Optional[int] = None,
        prev_stop_loss: Optional[int] = None,
    ) -> Optional[dict]:
        """보유종목 일일 리밸런싱 재평가 (GPT LIGHT 단독)

        장 마감 후 보유종목별로 최신 차트를 기반으로
        target_price / stop_loss를 재산출하고 결과 dict를 반환.
        GPT score ≤ 3이면 recommend_sell: True 포함.
        """
        try:
            # 1. 최신 차트 데이터 조회
            technical_data = await self._fetch_technical_data(symbol)
            if not technical_data:
                logger.warning(f"[리밸런싱] {symbol} 차트 데이터 없음 → 스킵")
                return None

            # 실시간 현재가 업데이트
            if technical_data.current_price > 0:
                current_price = technical_data.current_price

            # 수익률 계산
            profit_rate = (current_price - avg_buy_price) / avg_buy_price * 100 if avg_buy_price > 0 else 0

            # 2. GPT 퀀트 분석 (보유 맥락 전달)
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

            # 3. 응답에서 target_price, stop_loss 추출 → clamp 적용
            new_target = quant_msg.data.get("target_price") if quant_msg.data else None
            new_stop = quant_msg.data.get("stop_loss") if quant_msg.data else None
            score = quant_msg.data.get("score", 5) if quant_msg.data else 5

            new_target = self._clamp_target_price(new_target, current_price)
            new_stop = self._clamp_stop_loss(new_stop, current_price)

            # 4. 비용 기록
            cost_manager.record_analysis(symbol, AnalysisDepth.LIGHT)

            # 5. 결과 반환
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

    async def start_sell_meeting(
        self,
        symbol: str,
        company_name: str,
        sell_reason: str,
        current_holdings: int,
        avg_buy_price: int,
        current_price: int,
    ) -> CouncilMeeting:
        """SELL 전용 회의 시작"""

        meeting = CouncilMeeting(
            symbol=symbol,
            company_name=company_name,
            news_title=f"매도 검토: {sell_reason}",
            news_score=3,  # 매도 기준
        )

        # 1. 매도 검토 소집 메시지
        profit_loss = (current_price - avg_buy_price) / avg_buy_price * 100 if avg_buy_price > 0 else 0.0
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
        await self._notify_meeting_update(meeting)

        # 기술적 데이터 조회
        technical_data = await self._fetch_technical_data(symbol)

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
                    request=f"현재 보유 중인 종목의 매도 타이밍을 분석해주세요. 수익률 {profit_loss:+.1f}%, 사유: {sell_reason}",
                ),
                timeout=60.0  # 타임아웃 강제
            )
            meeting.add_message(quant_msg)
            await self._notify_meeting_update(meeting)
        except (asyncio.TimeoutError, Exception) as e:
            logger.error(f"매도 검토 중 퀀트 분석가 API 호출 실패 또는 타임아웃: {e}")
            quant_msg = CouncilMessage(
                role=AnalystRole.GPT_QUANT,
                speaker="시스템",
                content=f"[시스템 경고] 분석 지연 발생. 수익률 {profit_loss:+.1f}% 기반 기계적 매도를 우선 고려합니다.",
                data={"suggested_percent": 30 if profit_loss >= 0 else 100, "score": 5}
            )
            meeting.add_message(quant_msg)
            await self._notify_meeting_update(meeting)

        # 3. SELL 시그널 생성
        quant_score = quant_msg.data.get("score", 5) if quant_msg.data else 5

        # 매도 비율 결정 (손실 구간이면 전량, 수익 구간이면 일부)
        if profit_loss < -settings.stop_loss_percent:  # 손절
            sell_percent = 100
            action = "SELL"
        elif profit_loss > settings.take_profit_percent:  # 익절
            sell_percent = 50  # 절반 익절
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
            confidence=0.7 + (0.2 if abs(profit_loss) > 10 else 0),  # 큰 변동시 신뢰도 증가
            quant_score=quant_score,
            fundamental_score=5,  # 매도시 펀더멘털은 중립
        )

        # 자동 체결 처리
        if self.auto_execute:
            can_trade, trade_reason = trading_hours.can_execute_order()
            if can_trade or not self.respect_trading_hours:
                # 실제 키움 API 매도 주문 실행
                try:
                    order_result = await kiwoom_client.place_order(
                        symbol=symbol,
                        side=OrderSide.SELL,
                        quantity=sell_quantity,
                        price=0,  # 시장가 주문
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
                        self._queued_executions.append(signal)
                        logger.warning(
                            f"⚠️ 자동 매도 실패, 대기 큐 추가: {symbol} - {order_result.message}"
                        )
                except Exception as e:
                    signal.status = SignalStatus.QUEUED
                    self._queued_executions.append(signal)
                    logger.error(f"❌ 자동 매도 오류, 대기 큐 추가: {symbol} - {e}")
            else:
                signal.status = SignalStatus.QUEUED
                self._queued_executions.append(signal)
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
        await self._notify_meeting_update(meeting)

        # 저장
        self._meetings.append(meeting)
        if signal.status == SignalStatus.PENDING:
            self._pending_signals.append(signal)

        await self._notify_signal(signal)
        await self._persist_signal_to_db(signal, trigger_source=meeting.trigger_source)

        cost_manager.record_analysis(symbol, AnalysisDepth.LIGHT)  # 매도는 가벼운 분석

        return meeting

    async def process_queued_executions(self):
        """대기 중인 체결 처리 (거래 시간에 호출)"""
        can_trade, _ = trading_hours.can_execute_order()

        if not can_trade:
            logger.debug("거래 시간이 아님 - 대기 큐 처리 스킵")
            return []

        executed = []
        remaining = []

        # 현재 잔고 조회 (한 번만)
        available_balance = None
        try:
            balance = await kiwoom_client.get_balance()
            available_balance = balance.available_amount
        except Exception as e:
            logger.warning(f"잔고 조회 실패, 잔고 체크 없이 진행: {e}")

        for signal in self._queued_executions:
            if signal.status in (SignalStatus.QUEUED, SignalStatus.PENDING, SignalStatus.APPROVED):
                # 잔고 부족 시 시그널 취소
                if signal.action == "BUY" and available_balance is not None:
                    if available_balance < signal.suggested_amount:
                        logger.warning(
                            f"잔고 부족 — 시그널 취소: {signal.symbol} "
                            f"(필요 {signal.suggested_amount:,}원 > 가용 {available_balance:,}원)"
                        )
                        await self._update_signal_status_in_db(signal, executed=False, cancelled=True)
                        continue

                try:
                    # 실제 키움 API 호출
                    side = OrderSide.BUY if signal.action == "BUY" else OrderSide.SELL
                    order_result = await kiwoom_client.place_order(
                        symbol=signal.symbol,
                        side=side,
                        quantity=signal.suggested_quantity,
                        price=0,  # 시장가 주문
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
                        await self._notify_signal(signal)
                        await self._update_signal_status_in_db(signal, executed=True)
                    else:
                        logger.error(f"❌ 대기 큐 주문 실패: {signal.symbol} - {order_result.message}")
                        remaining.append(signal)

                except Exception as e:
                    logger.error(f"❌ 대기 큐 체결 실패: {signal.symbol} - {e}")
                    remaining.append(signal)
            else:
                remaining.append(signal)

        self._queued_executions = remaining
        return executed

    def get_queued_executions(self) -> List[InvestmentSignal]:
        """대기 중인 체결 목록"""
        return self._queued_executions.copy()

    def get_trading_status(self) -> dict:
        """거래 상태 정보"""
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
        """비용 통계"""
        return cost_manager.get_stats()

    async def restore_pending_signals(self):
        """서버 재시작 시 DB에서 미체결 시그널 복원"""
        try:
            pending_db_signals = await trading_service.get_pending_signals(limit=50)

            restored_queued = 0
            restored_pending = 0

            for s in pending_db_signals:
                # 수량이 없으면 복원 불가
                quantity = s.get("quantity")
                if not quantity or quantity <= 0:
                    logger.debug(f"수량 없는 시그널 스킵: {s['symbol']} (id={s['id']})")
                    continue

                action = s["signal_type"].upper()
                # HOLD 시그널은 체결 대상이 아님
                if action == "HOLD":
                    continue

                confidence = s["strength"] / 100.0

                target_price = int(s["target_price"]) if s.get("target_price") else None
                suggested_amount = s.get("suggested_amount") or (quantity * target_price if target_price else 0)
                signal = InvestmentSignal(
                    id=f"r{s['id']}",  # 복원된 시그널 구분용 prefix
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

                # 원래 상태에 따라 복원
                original_status = s.get("signal_status", "")
                if original_status == "queued":
                    signal.status = SignalStatus.QUEUED
                    self._queued_executions.append(signal)
                    restored_queued += 1
                elif original_status == "pending":
                    signal.status = SignalStatus.PENDING
                    self._pending_signals.append(signal)
                    restored_pending += 1
                else:
                    # 상태 불분명한 경우 auto_execute 기준으로 결정
                    if self.auto_execute and confidence >= self.min_confidence:
                        signal.status = SignalStatus.QUEUED
                        self._queued_executions.append(signal)
                        restored_queued += 1
                    else:
                        signal.status = SignalStatus.PENDING
                        self._pending_signals.append(signal)
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

    async def _update_signal_status_in_db(self, signal: InvestmentSignal, executed: bool = False, cancelled: bool = False):
        """DB 시그널 상태 업데이트"""
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
                    db_signal.signal_status = "cancelled" if cancelled else signal.status.value
                    await session.commit()
        except Exception as e:
            logger.error(f"DB 시그널 상태 업데이트 실패 (id={db_id}): {e}")


# 싱글톤 인스턴스
council_orchestrator = CouncilOrchestrator()

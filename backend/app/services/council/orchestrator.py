"""
AI 투자 회의 오케스트레이터

회의 진행을 관리하고 합의를 도출하는 오케스트레이터

v2: 키움증권 실제 차트 데이터 연동
v3: 자동 매매, SELL 시그널, 거래 시간 체크, 비용 관리 추가
"""

import logging
import asyncio
from datetime import datetime
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
from .dart_client import dart_client, FinancialData
from .trading_hours import trading_hours, MarketSession, get_kst_now
from .cost_manager import cost_manager, AnalysisDepth

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
    ) -> CouncilMeeting:
        """AI 투자 회의 시작"""

        # 회의 생성
        meeting = CouncilMeeting(
            symbol=symbol,
            company_name=company_name,
            news_title=news_title,
            news_score=news_score,
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

        opening_msg = CouncilMessage(
            role=AnalystRole.GEMINI_JUDGE,
            speaker="Gemini 뉴스 판단",
            content=f"""🔔 **AI 투자 회의 소집**

트리거 뉴스: "{news_title}"
뉴스 점수: {news_score}/10

이 뉴스가 {company_name}({symbol})의 주가에 긍정적 영향을 줄 것으로 판단됩니다.
투자 회의를 시작합니다.

{data_status}""",
            data={
                "news_score": news_score,
                "trigger": "news",
                "has_chart_data": technical_data is not None,
                "has_financial_data": financial_data is not None,
            },
        )
        meeting.add_message(opening_msg)
        await self._notify_meeting_update(meeting)

        # 2. 라운드 1: 초기 분석
        meeting.current_round = 1

        # GPT 퀀트 분석 (실제 차트 데이터 전달)
        quant_msg = await quant_analyst.analyze(
            symbol=symbol,
            company_name=company_name,
            news_title=news_title,
            previous_messages=meeting.messages,
            technical_data=technical_data,  # 실제 차트 데이터 전달
        )
        meeting.add_message(quant_msg)
        await self._notify_meeting_update(meeting)

        quant_percent = quant_msg.data.get("suggested_percent", 0) if quant_msg.data else 0
        quant_score = quant_msg.data.get("score", 5) if quant_msg.data else 5

        # Claude 펀더멘털 분석 (DART 실제 재무제표 전달)
        fundamental_msg = await fundamental_analyst.analyze(
            symbol=symbol,
            company_name=company_name,
            news_title=news_title,
            previous_messages=meeting.messages,
            financial_data=financial_data,  # DART 재무제표 데이터 전달
        )
        meeting.add_message(fundamental_msg)
        await self._notify_meeting_update(meeting)

        fundamental_percent = fundamental_msg.data.get("suggested_percent", 0) if fundamental_msg.data else 0
        fundamental_score = fundamental_msg.data.get("score", 5) if fundamental_msg.data else 5

        # 3. 라운드 2: 상호 검토 및 조정
        meeting.current_round = 2

        # GPT가 Claude 의견에 응답 (차트 데이터 유지)
        quant_response = await quant_analyst.respond_to(
            symbol=symbol,
            company_name=company_name,
            news_title=news_title,
            previous_messages=meeting.messages,
            other_analysis=fundamental_msg.content,
            technical_data=technical_data,  # 실제 차트 데이터 전달
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
        suggested_amount = int(available_amount * abs(final_percent) / 100)
        suggested_quantity = suggested_amount // current_price if current_price > 0 else 0

        # 신뢰도 계산 - 점수 기반 동적 계산
        base_confidence = (quant_score + fundamental_score) / 20  # 0-1 스케일
        # 두 분석가의 의견 일치도에 따라 신뢰도 조정
        score_diff = abs(quant_score - fundamental_score)
        agreement_bonus = max(0, (5 - score_diff) * 0.02)  # 의견 일치시 최대 +0.1
        confidence = min(0.95, base_confidence + agreement_bonus)

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
        )

        signal = InvestmentSignal(
            symbol=symbol,
            company_name=company_name,
            action=action,
            allocation_percent=abs(final_percent),
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
            signal.status = SignalStatus.PENDING

        # 비용 기록
        cost_manager.record_analysis(symbol, AnalysisDepth.FULL)

        meeting.signal = signal
        meeting.consensus_reached = True
        meeting.ended_at = datetime.now()

        # 6. 최종 결론 메시지
        price_info = ""
        if entry_price:
            price_info = f"""
📍 매매 전략:
• 진입가: {entry_price:,}원
• 손절가: {stop_loss:,}원
• 목표가: {target_price:,}원"""

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

    def _determine_action(
        self,
        final_percent: float,
        quant_score: int,
        fundamental_score: int,
        news_score: int,
    ) -> str:
        """
        투자 액션 결정 (BUY/SELL/HOLD)

        SELL 조건:
        1. 뉴스 점수가 3 이하 (부정적 뉴스)
        2. 퀀트 + 펀더멘털 평균 점수 4 이하
        3. 투자 비율이 음수로 제안됨 (AI가 매도 권장)

        BUY 조건:
        1. 뉴스 점수 7 이상
        2. 퀀트 + 펀더멘털 평균 점수 6 이상
        3. 투자 비율 10% 이상

        HOLD: 그 외
        """
        avg_score = (quant_score + fundamental_score) / 2

        # SELL 조건
        if news_score <= 3:
            logger.info(f"SELL 결정: 부정적 뉴스 (점수: {news_score})")
            return "SELL"

        if avg_score <= 4:
            logger.info(f"SELL 결정: 낮은 분석 점수 (평균: {avg_score:.1f})")
            return "SELL"

        if final_percent < 0:
            logger.info(f"SELL 결정: AI 매도 권장 (비율: {final_percent}%)")
            return "SELL"

        # BUY 조건
        if final_percent >= 10 and avg_score >= 6:
            logger.info(f"BUY 결정: 긍정적 분석 (비율: {final_percent}%, 평균: {avg_score:.1f})")
            return "BUY"

        if news_score >= 8 and avg_score >= 5:
            logger.info(f"BUY 결정: 강한 뉴스 신호 (뉴스: {news_score}, 평균: {avg_score:.1f})")
            return "BUY"

        # HOLD
        logger.info(f"HOLD 결정: 조건 미충족 (비율: {final_percent}%, 평균: {avg_score:.1f})")
        return "HOLD"

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
        profit_loss = (current_price - avg_buy_price) / avg_buy_price * 100
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
        quant_msg = await quant_analyst.analyze(
            symbol=symbol,
            company_name=company_name,
            news_title=f"매도 검토: {sell_reason}",
            previous_messages=meeting.messages,
            technical_data=technical_data,
            request=f"현재 보유 중인 종목의 매도 타이밍을 분석해주세요. 수익률 {profit_loss:+.1f}%, 사유: {sell_reason}",
        )
        meeting.add_message(quant_msg)
        await self._notify_meeting_update(meeting)

        # 3. SELL 시그널 생성
        quant_score = quant_msg.data.get("score", 5) if quant_msg.data else 5

        # 매도 비율 결정 (손실 구간이면 전량, 수익 구간이면 일부)
        if profit_loss < -5:  # 손절
            sell_percent = 100
            action = "SELL"
        elif profit_loss > 20:  # 익절
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

        for signal in self._queued_executions:
            if signal.status in (SignalStatus.QUEUED, SignalStatus.PENDING, SignalStatus.APPROVED):
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


# 싱글톤 인스턴스
council_orchestrator = CouncilOrchestrator()

"""
GPT 퀀트 분석가

기술적 분석을 담당하는 GPT 기반 분석가
- RSI, MACD, 볼린저밴드 등 기술적 지표 분석
- 거래량 분석
- 차트 패턴 분석
- 리스크 관리 관점의 투자 비율 제안

v2: 키움증권 실제 차트 데이터 연동
v3: 독립 시그널 생성 기능 추가 (기술적 지표 기반 자동 매매 트리거)
"""

import logging
from typing import Optional, Tuple
import json

from openai import AsyncOpenAI

from app.config import settings
from .models import CouncilMessage, AnalystRole
from .technical_indicators import TechnicalAnalysisResult

logger = logging.getLogger(__name__)


class QuantAnalyst:
    """GPT 기반 퀀트 분석가"""

    SYSTEM_PROMPT = """당신은 전문 퀀트 애널리스트입니다.
기술적 분석과 수치 기반 투자 판단을 담당합니다.

분석 영역:
1. 기술적 지표: RSI, MACD, 볼린저밴드, 이동평균선
2. 거래량 분석: 거래량 추이, 거래대금
3. 차트 패턴: 지지/저항선, 추세선, 패턴
4. 리스크 관리: 변동성, 손절가, 포지션 사이징

응답 형식:
- 제공된 실제 기술적 지표 데이터를 기반으로 분석
- 투자 비율은 총 자금 대비 %로 제안
- 한국어로 간결하게 답변"""

    ANALYSIS_PROMPT = """다음 종목에 대한 퀀트/기술적 분석을 수행해주세요.

[종목 정보]
종목코드: {symbol}
종목명: {company_name}
뉴스: {news_title}

[실제 기술적 지표 데이터]
{technical_data}

[이전 대화]
{conversation}

[요청]
{request}

[응답 형식]
다음 JSON 형식으로 응답해주세요:
{{
    "analysis": "기술적 분석 내용 (2-3문장, 위의 실제 지표 데이터 기반)",
    "score": 1-10 사이 점수,
    "suggested_percent": 제안 투자 비율 (0-100),
    "reasoning": "투자 비율 산정 근거 (실제 지표값 인용)",
    "risk_factors": ["리스크 요소 1", "리스크 요소 2"],
    "entry_price": 권장 진입가 (정수),
    "stop_loss": 손절가 (정수),
    "target_price": 목표가 (정수),
    "reply_to_other": "다른 분석가에게 하고 싶은 말 (선택)"
}}"""

    # 기술적 데이터 없이 뉴스만으로 분석할 때 사용
    ANALYSIS_PROMPT_NO_DATA = """다음 종목에 대한 퀀트/기술적 분석을 수행해주세요.

[종목 정보]
종목코드: {symbol}
종목명: {company_name}
뉴스: {news_title}

[기술적 데이터]
⚠️ 실시간 차트 데이터를 조회할 수 없습니다. 일반적인 기술적 분석 관점에서 의견을 제시해주세요.

[이전 대화]
{conversation}

[요청]
{request}

[응답 형식]
다음 JSON 형식으로 응답해주세요:
{{
    "analysis": "기술적 분석 관점의 의견 (2-3문장)",
    "score": 1-10 사이 점수,
    "suggested_percent": 제안 투자 비율 (0-100),
    "reasoning": "투자 비율 산정 근거",
    "risk_factors": ["리스크 요소 1", "리스크 요소 2"],
    "reply_to_other": "다른 분석가에게 하고 싶은 말 (선택)"
}}"""

    def __init__(self):
        self._client: Optional[AsyncOpenAI] = None
        self._initialized = False

    def _initialize(self):
        """OpenAI 클라이언트 초기화"""
        if self._initialized:
            return

        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다")

        self._client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )
        self._initialized = True
        logger.info(f"GPT 퀀트 분석가 초기화 (모델: {settings.openai_model})")

    def _build_conversation(self, messages: list[CouncilMessage]) -> str:
        """이전 대화 내용 구성"""
        if not messages:
            return "(첫 번째 발언입니다)"

        lines = []
        for msg in messages[-6:]:  # 최근 6개 메시지만
            speaker = msg.speaker
            content = msg.content[:200]  # 길이 제한
            lines.append(f"[{speaker}]: {content}")

        return "\n".join(lines)

    async def analyze(
        self,
        symbol: str,
        company_name: str,
        news_title: str,
        previous_messages: list[CouncilMessage],
        technical_data: Optional[TechnicalAnalysisResult] = None,
        request: str = "기술적 분석을 수행하고 투자 비율을 제안해주세요."
    ) -> CouncilMessage:
        """퀀트 분석 수행"""
        self._initialize()

        conversation = self._build_conversation(previous_messages)

        # 기술적 데이터 유무에 따라 프롬프트 선택
        if technical_data and technical_data.current_price > 0:
            prompt = self.ANALYSIS_PROMPT.format(
                symbol=symbol,
                company_name=company_name,
                news_title=news_title,
                technical_data=technical_data.to_prompt_text(),
                conversation=conversation,
                request=request,
            )
            logger.info(f"[퀀트분석] {symbol} - 실제 차트 데이터 사용 (현재가: {technical_data.current_price:,}원)")
        else:
            prompt = self.ANALYSIS_PROMPT_NO_DATA.format(
                symbol=symbol,
                company_name=company_name,
                news_title=news_title,
                conversation=conversation,
                request=request,
            )
            logger.warning(f"[퀀트분석] {symbol} - 차트 데이터 없이 분석")

        try:
            response = await self._client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=2048,
            )

            response_text = response.choices[0].message.content

            # JSON 파싱 시도
            try:
                # JSON 블록 추출
                if "```json" in response_text:
                    json_str = response_text.split("```json")[1].split("```")[0]
                elif "```" in response_text:
                    json_str = response_text.split("```")[1].split("```")[0]
                else:
                    json_str = response_text

                data = json.loads(json_str.strip())

                # 기술적 데이터가 있는 경우 추가 정보 포함
                content = f"""📊 **퀀트 분석 결과**

{data.get('analysis', '')}

• 기술적 점수: {data.get('score', 5)}/10
• 제안 투자 비율: {data.get('suggested_percent', 0)}%
• 근거: {data.get('reasoning', '')}"""

                # 매매 가격 정보 (있는 경우)
                if data.get('entry_price'):
                    content += f"""

💰 매매 전략:
• 진입가: {data.get('entry_price'):,}원
• 손절가: {data.get('stop_loss', 0):,}원
• 목표가: {data.get('target_price', 0):,}원"""

                content += f"""

⚠️ 리스크 요소:
{chr(10).join(f"- {r}" for r in data.get('risk_factors', []))}"""

                if data.get('reply_to_other'):
                    content += f"\n\n💬 {data.get('reply_to_other')}"

                # 실제 데이터 사용 여부 표시
                if technical_data and technical_data.current_price > 0:
                    content += f"\n\n📈 *키움증권 실시간 데이터 기반 분석*"

            except json.JSONDecodeError:
                # JSON 파싱 실패 시 원본 텍스트 사용
                content = f"📊 **퀀트 분석**\n\n{response_text}"
                data = {"score": 5, "suggested_percent": 0}

            return CouncilMessage(
                role=AnalystRole.GPT_QUANT,
                speaker="GPT 퀀트 분석가",
                content=content,
                data=data,
            )

        except Exception as e:
            logger.error(f"GPT 퀀트 분석 오류: {e}")
            return CouncilMessage(
                role=AnalystRole.GPT_QUANT,
                speaker="GPT 퀀트 분석가",
                content=f"⚠️ 분석 중 오류 발생: {str(e)}",
                data={"error": str(e)},
            )

    async def respond_to(
        self,
        symbol: str,
        company_name: str,
        news_title: str,
        previous_messages: list[CouncilMessage],
        other_analysis: str,
        technical_data: Optional[TechnicalAnalysisResult] = None,
    ) -> CouncilMessage:
        """다른 분석가의 의견에 응답"""
        request = f"""펀더멘털 분석가의 의견을 검토하고 응답해주세요:

{other_analysis}

동의하거나 반대 의견이 있다면 근거와 함께 제시하고,
최종 투자 비율에 대한 조정 의견을 제안해주세요."""

        return await self.analyze(
            symbol=symbol,
            company_name=company_name,
            news_title=news_title,
            previous_messages=previous_messages,
            technical_data=technical_data,
            request=request,
        )


    async def generate_independent_signal(
        self,
        symbol: str,
        company_name: str,
        technical_data: TechnicalAnalysisResult,
    ) -> Tuple[bool, str, dict]:
        """
        기술적 지표만으로 독립적인 매매 시그널 생성

        Returns:
            (should_signal, action, signal_data)
            - should_signal: 시그널 생성 여부
            - action: "BUY", "SELL", "HOLD"
            - signal_data: 상세 데이터
        """
        if not technical_data or technical_data.current_price <= 0:
            return False, "HOLD", {"reason": "기술적 데이터 없음"}

        # 1. 규칙 기반 1차 필터링 (API 비용 절감)
        rule_signal, rule_action, rule_data = self._rule_based_signal(technical_data)

        if not rule_signal:
            logger.debug(f"[퀀트독립] {symbol} - 규칙 기반 필터링 통과 안됨")
            return False, "HOLD", rule_data

        # 2. GPT를 통한 2차 검증 (규칙 기반에서 신호가 감지된 경우만)
        self._initialize()

        prompt = f"""기술적 지표 기반으로 매매 신호를 판단해주세요.

[종목 정보]
종목코드: {symbol}
종목명: {company_name}

[기술적 지표]
{technical_data.to_prompt_text()}

[규칙 기반 분석 결과]
1차 신호: {rule_action}
근거: {rule_data.get('reason', '')}

[요청]
위 기술적 지표를 검토하고 매매 신호의 유효성을 평가해주세요.

[응답 형식 - JSON]
{{
    "confirm_signal": true/false,
    "action": "BUY" 또는 "SELL" 또는 "HOLD",
    "confidence": 0.0-1.0 사이 신뢰도,
    "score": 1-10 점수,
    "reason": "판단 근거 (1-2문장)",
    "entry_price": 진입가,
    "stop_loss": 손절가,
    "target_price": 목표가
}}"""

        try:
            response = await self._client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": "당신은 퀀트 분석 전문가입니다. 기술적 지표를 분석하여 매매 신호를 검증합니다."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=2048,
            )

            response_text = response.choices[0].message.content

            # JSON 파싱
            try:
                if "```json" in response_text:
                    json_str = response_text.split("```json")[1].split("```")[0]
                elif "```" in response_text:
                    json_str = response_text.split("```")[1].split("```")[0]
                else:
                    json_str = response_text

                data = json.loads(json_str.strip())

                if data.get("confirm_signal", False):
                    action = data.get("action", "HOLD")
                    logger.info(
                        f"[퀀트독립] {symbol} - GPT 검증 통과: {action} "
                        f"(신뢰도: {data.get('confidence', 0):.0%})"
                    )
                    return True, action, {
                        "source": "quant_independent",
                        "confidence": data.get("confidence", 0.7),
                        "score": data.get("score", 5),
                        "reason": data.get("reason", ""),
                        "entry_price": data.get("entry_price"),
                        "stop_loss": data.get("stop_loss"),
                        "target_price": data.get("target_price"),
                        "rule_based_signal": rule_action,
                    }
                else:
                    logger.debug(f"[퀀트독립] {symbol} - GPT 검증 미통과")
                    return False, "HOLD", {"reason": "GPT 검증 미통과"}

            except json.JSONDecodeError:
                logger.warning(f"[퀀트독립] {symbol} - JSON 파싱 실패")
                return False, "HOLD", {"reason": "응답 파싱 실패"}

        except Exception as e:
            logger.error(f"[퀀트독립] {symbol} - GPT 호출 오류: {e}")
            return False, "HOLD", {"reason": f"오류: {str(e)}"}

    def _rule_based_signal(
        self,
        technical_data: TechnicalAnalysisResult
    ) -> Tuple[bool, str, dict]:
        """
        규칙 기반 매매 신호 1차 필터링 (API 호출 없이 빠르게 판단)

        Returns:
            (should_continue, suggested_action, reason_data)
        """
        signals = []
        buy_signals = 0
        sell_signals = 0

        # 1. RSI 신호
        rsi = technical_data.rsi_14
        if rsi > 0:
            if rsi <= 30:
                buy_signals += 2  # 강한 매수 신호
                signals.append(f"RSI 과매도({rsi:.1f})")
            elif rsi <= 40:
                buy_signals += 1
                signals.append(f"RSI 매수권({rsi:.1f})")
            elif rsi >= 70:
                sell_signals += 2  # 강한 매도 신호
                signals.append(f"RSI 과매수({rsi:.1f})")
            elif rsi >= 60:
                sell_signals += 1
                signals.append(f"RSI 매도권({rsi:.1f})")

        # 2. MACD 신호
        macd = technical_data.macd
        macd_signal = technical_data.macd_signal
        if macd != 0 and macd_signal != 0:
            if macd > macd_signal and macd > 0:
                buy_signals += 1
                signals.append("MACD 골든크로스")
            elif macd < macd_signal and macd < 0:
                sell_signals += 1
                signals.append("MACD 데드크로스")

        # 3. 볼린저밴드 신호
        current_price = technical_data.current_price
        bb_lower = technical_data.bb_lower
        bb_upper = technical_data.bb_upper
        if bb_lower > 0 and bb_upper > 0 and current_price > 0:
            bb_position = (current_price - bb_lower) / (bb_upper - bb_lower) if (bb_upper - bb_lower) > 0 else 0.5
            if bb_position <= 0.1:  # 하단 10% 이내
                buy_signals += 2
                signals.append(f"볼린저밴드 하단 돌파({bb_position:.0%})")
            elif bb_position <= 0.2:
                buy_signals += 1
                signals.append(f"볼린저밴드 하단 근접({bb_position:.0%})")
            elif bb_position >= 0.9:  # 상단 10% 이내
                sell_signals += 2
                signals.append(f"볼린저밴드 상단 돌파({bb_position:.0%})")
            elif bb_position >= 0.8:
                sell_signals += 1
                signals.append(f"볼린저밴드 상단 근접({bb_position:.0%})")

        # 4. 이동평균선 배열
        ma5 = technical_data.ma_5
        ma20 = technical_data.ma_20
        ma60 = technical_data.ma_60
        if ma5 > 0 and ma20 > 0 and current_price > 0:
            if current_price > ma5 > ma20:
                buy_signals += 1
                signals.append("정배열 (가격>MA5>MA20)")
            elif current_price < ma5 < ma20:
                sell_signals += 1
                signals.append("역배열 (가격<MA5<MA20)")

            # 골든크로스/데드크로스
            if ma60 > 0:
                if ma5 > ma20 > ma60:
                    buy_signals += 1
                    signals.append("이동평균선 정배열")
                elif ma5 < ma20 < ma60:
                    sell_signals += 1
                    signals.append("이동평균선 역배열")

        # 5. 거래량 확인 (급등 시 신뢰도 증가)
        volume_ratio = technical_data.volume_ratio
        if volume_ratio >= 2.0:
            if buy_signals > sell_signals:
                buy_signals += 1
                signals.append(f"거래량 급등({volume_ratio:.1f}배)")
            elif sell_signals > buy_signals:
                sell_signals += 1
                signals.append(f"거래량 급등({volume_ratio:.1f}배)")

        # 최종 판단
        # 매수: 최소 3개 이상의 매수 신호, 매도 신호보다 2개 이상 많아야 함
        # 매도: 최소 3개 이상의 매도 신호, 매수 신호보다 2개 이상 많아야 함
        reason_data = {
            "buy_signals": buy_signals,
            "sell_signals": sell_signals,
            "signals": signals,
        }

        if buy_signals >= 3 and buy_signals - sell_signals >= 2:
            reason_data["reason"] = f"매수 신호 우세 ({buy_signals} vs {sell_signals}): " + ", ".join(signals)
            return True, "BUY", reason_data
        elif sell_signals >= 3 and sell_signals - buy_signals >= 2:
            reason_data["reason"] = f"매도 신호 우세 ({sell_signals} vs {buy_signals}): " + ", ".join(signals)
            return True, "SELL", reason_data
        else:
            reason_data["reason"] = f"신호 불충분 (매수:{buy_signals}, 매도:{sell_signals})"
            return False, "HOLD", reason_data

    def quick_technical_score(self, technical_data: TechnicalAnalysisResult) -> int:
        """
        API 호출 없이 빠른 기술적 점수 계산 (1-10)
        비용 절감을 위해 간단한 뉴스에 대해 사용
        """
        if not technical_data or technical_data.current_price <= 0:
            return 5  # 중립

        score = 5  # 기본 점수

        # RSI 기반
        rsi = technical_data.rsi_14
        if 0 < rsi <= 30:
            score += 2
        elif 30 < rsi <= 40:
            score += 1
        elif 60 <= rsi < 70:
            score -= 1
        elif rsi >= 70:
            score -= 2

        # MACD 기반
        if technical_data.macd > technical_data.macd_signal:
            score += 1
        elif technical_data.macd < technical_data.macd_signal:
            score -= 1

        # 이동평균선 기반
        current = technical_data.current_price
        if current > technical_data.ma_20 > 0:
            score += 1
        elif current < technical_data.ma_20 and technical_data.ma_20 > 0:
            score -= 1

        # 볼린저밴드 기반
        if technical_data.bb_lower > 0 and technical_data.bb_upper > 0:
            bb_range = technical_data.bb_upper - technical_data.bb_lower
            if bb_range > 0:
                bb_pos = (current - technical_data.bb_lower) / bb_range
                if bb_pos <= 0.2:
                    score += 1
                elif bb_pos >= 0.8:
                    score -= 1

        return max(1, min(10, score))


# 싱글톤 인스턴스
quant_analyst = QuantAnalyst()

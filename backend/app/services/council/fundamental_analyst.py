"""
Claude 펀더멘털 분석가

기업 가치 분석을 담당하는 Claude 기반 분석가
- 재무제표 분석 (PER, PBR, ROE 등)
- 사업 모델 분석
- 경쟁력 분석
- 성장성 분석

v2: DART API 실제 재무제표 데이터 연동
"""

import logging
from typing import Optional
import json

import anthropic

from app.config import settings
from .models import CouncilMessage, AnalystRole
from app.services.dart_client import FinancialData

logger = logging.getLogger(__name__)


class FundamentalAnalyst:
    """Claude 기반 펀더멘털 분석가"""

    SYSTEM_PROMPT = """당신은 전문 펀더멘털 애널리스트입니다.
기업 가치와 비즈니스 분석을 담당합니다.

분석 영역:
1. 재무 분석: PER, PBR, ROE, 부채비율, 영업이익률
2. 사업 분석: 비즈니스 모델, 경쟁우위, 시장 점유율
3. 성장성: 매출 성장률, 이익 성장률, 신사업 전망
4. 밸류에이션: 적정 주가, 목표 주가

응답 형식:
- 기업 가치 관점에서 분석
- 장기 투자 관점 반영
- 퀀트 분석가의 의견도 고려하여 균형 잡힌 판단
- 한국어로 간결하게 답변"""

    ANALYSIS_PROMPT = """다음 종목에 대한 펀더멘털 분석을 수행해주세요.

[종목 정보]
종목코드: {symbol}
종목명: {company_name}
뉴스: {news_title}

[실제 재무제표 데이터 (DART 전자공시)]
{financial_data}

[이전 대화]
{conversation}

[요청]
{request}

[응답 형식]
다음 JSON 형식으로 응답해주세요:
{{
    "analysis": "펀더멘털 분석 내용 (2-3문장, 위의 실제 재무제표 데이터 기반)",
    "score": 1-10 사이 점수,
    "suggested_percent": 제안 투자 비율 (0-100),
    "reasoning": "투자 비율 산정 근거 (실제 재무지표 인용)",
    "growth_factors": ["성장 요소 1", "성장 요소 2"],
    "valuation_opinion": "현재 밸류에이션에 대한 의견 (PER/PBR 기반)",
    "reply_to_other": "다른 분석가에게 하고 싶은 말 (선택)"
}}"""

    # 재무 데이터 없이 분석할 때 사용
    ANALYSIS_PROMPT_NO_DATA = """다음 종목에 대한 펀더멘털 분석을 수행해주세요.

[종목 정보]
종목코드: {symbol}
종목명: {company_name}
뉴스: {news_title}

[재무제표 데이터]
⚠️ DART에서 재무제표를 조회할 수 없습니다. 일반적인 펀더멘털 관점에서 의견을 제시해주세요.

[이전 대화]
{conversation}

[요청]
{request}

[응답 형식]
다음 JSON 형식으로 응답해주세요:
{{
    "analysis": "펀더멘털 분석 관점의 의견 (2-3문장)",
    "score": 1-10 사이 점수,
    "suggested_percent": 제안 투자 비율 (0-100),
    "reasoning": "투자 비율 산정 근거",
    "growth_factors": ["성장 요소 1", "성장 요소 2"],
    "reply_to_other": "다른 분석가에게 하고 싶은 말 (선택)"
}}"""

    def __init__(self):
        self._client: Optional[anthropic.AsyncAnthropic] = None
        self._initialized = False

    def _initialize(self):
        """Anthropic 클라이언트 초기화"""
        if self._initialized:
            return

        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY가 설정되지 않았습니다")

        self._client = anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            base_url=settings.anthropic_base_url,
        )
        self._initialized = True
        logger.info(f"Claude 펀더멘털 분석가 초기화 (모델: {settings.anthropic_model})")

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
        financial_data: Optional[FinancialData] = None,
        request: str = "펀더멘털 분석을 수행하고 투자 비율을 제안해주세요."
    ) -> CouncilMessage:
        """펀더멘털 분석 수행"""
        self._initialize()

        conversation = self._build_conversation(previous_messages)

        # 재무 데이터 유무에 따라 프롬프트 선택
        if financial_data and financial_data.revenue:
            prompt = self.ANALYSIS_PROMPT.format(
                symbol=symbol,
                company_name=company_name,
                news_title=news_title,
                financial_data=financial_data.to_prompt_text(),
                conversation=conversation,
                request=request,
            )
            logger.info(f"[펀더멘털분석] {symbol} - DART 실제 재무제표 사용")
        else:
            prompt = self.ANALYSIS_PROMPT_NO_DATA.format(
                symbol=symbol,
                company_name=company_name,
                news_title=news_title,
                conversation=conversation,
                request=request,
            )
            logger.warning(f"[펀더멘털분석] {symbol} - 재무제표 없이 분석")

        try:
            response = await self._client.messages.create(
                model=settings.anthropic_model,
                max_tokens=2048,
                system=self.SYSTEM_PROMPT,
                messages=[
                    {"role": "user", "content": prompt},
                ],
            )

            response_text = response.content[0].text

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

                content = f"""📈 **펀더멘털 분석 결과**

{data.get('analysis', '')}

• 기업가치 점수: {data.get('score', 5)}/10
• 제안 투자 비율: {data.get('suggested_percent', 0)}%
• 근거: {data.get('reasoning', '')}

📊 성장 요소:
{chr(10).join(f"- {g}" for g in data.get('growth_factors', []))}"""

                # 밸류에이션 의견 (있는 경우)
                if data.get('valuation_opinion'):
                    content += f"""

💰 밸류에이션 의견:
{data.get('valuation_opinion')}"""

                if data.get('reply_to_other'):
                    content += f"\n\n💬 {data.get('reply_to_other')}"

                # 실제 데이터 사용 여부 표시
                if financial_data and financial_data.revenue:
                    content += f"\n\n📋 *DART 전자공시 재무제표 기반 분석*"

            except json.JSONDecodeError:
                # JSON 파싱 실패 시 원본 텍스트 사용
                content = f"📈 **펀더멘털 분석**\n\n{response_text}"
                data = {"score": 5, "suggested_percent": 0}

            return CouncilMessage(
                role=AnalystRole.CLAUDE_FUNDAMENTAL,
                speaker="Claude 펀더멘털 분석가",
                content=content,
                data=data,
            )

        except Exception as e:
            logger.error(f"Claude 펀더멘털 분석 오류: {e}")
            return CouncilMessage(
                role=AnalystRole.CLAUDE_FUNDAMENTAL,
                speaker="Claude 펀더멘털 분석가",
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
    ) -> CouncilMessage:
        """다른 분석가의 의견에 응답"""
        request = f"""퀀트 분석가의 의견을 검토하고 응답해주세요:

{other_analysis}

동의하거나 반대 의견이 있다면 근거와 함께 제시하고,
최종 투자 비율에 대한 조정 의견을 제안해주세요."""

        return await self.analyze(
            symbol=symbol,
            company_name=company_name,
            news_title=news_title,
            previous_messages=previous_messages,
            request=request,
        )

    CONSENSUS_PROMPT = """지금까지의 논의를 종합하여 최종 투자 결론을 내려주세요.

[종목 정보]
종목코드: {symbol}
종목명: {company_name}
트리거: {news_title}

[이전 대화]
{conversation}

[합의 기준점]
퀀트 분석 제안: {quant_percent}%
펀더멘털 분석 제안: {fundamental_percent}%
평균값: {avg_percent:.1f}%

[요청]
두 분석을 종합하여 최종 투자 비율을 결정해주세요.
이 전략은 단기 스윙 매매입니다. 목표가 미달 시 정해진 기간 후 매도하여 더 좋은 기회에 재투자하므로,
**보유 기한(캘린더 기준 일수)**도 함께 결정해주세요.

[응답 형식]
다음 JSON 형식으로 응답해주세요:
{{
    "analysis": "합의 근거 (2-3문장)",
    "score": 1-10 사이 점수,
    "suggested_percent": 최종 투자 비율 (0-100),
    "reasoning": "투자 비율 산정 근거",
    "holding_days": 보유 기한 일수 (최소 5, 최대 21),
    "holding_rationale": "보유 기한 설정 근거 (1문장)"
}}"""

    async def propose_consensus(
        self,
        symbol: str,
        company_name: str,
        news_title: str,
        previous_messages: list[CouncilMessage],
        quant_percent: float,
        fundamental_percent: float,
    ) -> CouncilMessage:
        """합의안 제안 (최종 투자 비율 + 보유 기한 결정)"""
        self._initialize()

        avg_percent = (quant_percent + fundamental_percent) / 2
        conversation = self._build_conversation(previous_messages)

        prompt = self.CONSENSUS_PROMPT.format(
            symbol=symbol,
            company_name=company_name,
            news_title=news_title,
            conversation=conversation,
            quant_percent=quant_percent,
            fundamental_percent=fundamental_percent,
            avg_percent=avg_percent,
        )

        try:
            response = await self._client.messages.create(
                model=settings.anthropic_model,
                max_tokens=1024,
                system=self.SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )

            response_text = response.content[0].text

            try:
                if "```json" in response_text:
                    json_str = response_text.split("```json")[1].split("```")[0]
                elif "```" in response_text:
                    json_str = response_text.split("```")[1].split("```")[0]
                else:
                    json_str = response_text

                data = json.loads(json_str.strip())
                holding_days = data.get("holding_days", 7)
                holding_days = max(5, min(21, int(holding_days)))  # 5~21일 바운드

                content = f"""⚖️ **최종 합의**

{data.get('analysis', '')}

• 합의 점수: {data.get('score', 5)}/10
• 최종 투자 비율: {data.get('suggested_percent', 0)}%
• 근거: {data.get('reasoning', '')}

⏰ 보유 기한: {holding_days}일 (목표가 미달 시 자동 매도)
• {data.get('holding_rationale', '')}"""

                data["holding_days"] = holding_days

            except json.JSONDecodeError:
                content = f"⚖️ **최종 합의**\n\n{response_text}"
                data = {"score": 5, "suggested_percent": avg_percent, "holding_days": 7}

            return CouncilMessage(
                role=AnalystRole.CLAUDE_FUNDAMENTAL,
                speaker="Claude 합의 도출",
                content=content,
                data=data,
            )

        except Exception as e:
            logger.error(f"합의 도출 오류: {e}")
            return CouncilMessage(
                role=AnalystRole.CLAUDE_FUNDAMENTAL,
                speaker="Claude 합의 도출",
                content=f"⚠️ 합의 도출 중 오류: {str(e)}",
                data={"score": 5, "suggested_percent": avg_percent, "holding_days": 7},
            )


# 싱글톤 인스턴스
fundamental_analyst = FundamentalAnalyst()

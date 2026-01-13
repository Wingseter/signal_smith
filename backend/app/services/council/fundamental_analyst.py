"""
Claude 펀더멘털 분석가

기업 가치 분석을 담당하는 Claude 기반 분석가
- 재무제표 분석 (PER, PBR, ROE 등)
- 사업 모델 분석
- 경쟁력 분석
- 성장성 분석
"""

import logging
from typing import Optional
import json

import anthropic

from app.config import settings
from .models import CouncilMessage, AnalystRole

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

[이전 대화]
{conversation}

[요청]
{request}

[응답 형식]
다음 JSON 형식으로 응답해주세요:
{{
    "analysis": "펀더멘털 분석 내용 (2-3문장)",
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

        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
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
        request: str = "펀더멘털 분석을 수행하고 투자 비율을 제안해주세요."
    ) -> CouncilMessage:
        """펀더멘털 분석 수행"""
        self._initialize()

        conversation = self._build_conversation(previous_messages)

        prompt = self.ANALYSIS_PROMPT.format(
            symbol=symbol,
            company_name=company_name,
            news_title=news_title,
            conversation=conversation,
            request=request,
        )

        try:
            response = await self._client.messages.create(
                model=settings.anthropic_model,
                max_tokens=500,
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

                if data.get('reply_to_other'):
                    content += f"\n\n💬 {data.get('reply_to_other')}"

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

    async def propose_consensus(
        self,
        symbol: str,
        company_name: str,
        news_title: str,
        previous_messages: list[CouncilMessage],
        quant_percent: float,
        fundamental_percent: float,
    ) -> CouncilMessage:
        """합의안 제안"""
        avg_percent = (quant_percent + fundamental_percent) / 2

        request = f"""지금까지의 논의를 종합해주세요.

퀀트 분석 제안: {quant_percent}%
펀더멘털 분석 제안: {fundamental_percent}%

두 분석을 종합하여 최종 투자 비율을 제안하고,
합의 근거를 설명해주세요.

평균값 {avg_percent:.1f}%를 기준으로 조정이 필요하다면 근거와 함께 제시해주세요."""

        return await self.analyze(
            symbol=symbol,
            company_name=company_name,
            news_title=news_title,
            previous_messages=previous_messages,
            request=request,
        )


# 싱글톤 인스턴스
fundamental_analyst = FundamentalAnalyst()

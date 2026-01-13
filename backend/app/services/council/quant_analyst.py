"""
GPT 퀀트 분석가

기술적 분석을 담당하는 GPT 기반 분석가
- RSI, MACD, 볼린저밴드 등 기술적 지표 분석
- 거래량 분석
- 차트 패턴 분석
- 리스크 관리 관점의 투자 비율 제안
"""

import logging
from typing import Optional
import json

from openai import AsyncOpenAI

from app.config import settings
from .models import CouncilMessage, AnalystRole

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
- 분석 결과는 구체적인 수치와 함께 제시
- 투자 비율은 총 자금 대비 %로 제안
- 한국어로 간결하게 답변"""

    ANALYSIS_PROMPT = """다음 종목에 대한 퀀트/기술적 분석을 수행해주세요.

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
    "analysis": "기술적 분석 내용 (2-3문장)",
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

        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
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
        request: str = "기술적 분석을 수행하고 투자 비율을 제안해주세요."
    ) -> CouncilMessage:
        """퀀트 분석 수행"""
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
            response = await self._client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=500,
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

                content = f"""📊 **퀀트 분석 결과**

{data.get('analysis', '')}

• 기술적 점수: {data.get('score', 5)}/10
• 제안 투자 비율: {data.get('suggested_percent', 0)}%
• 근거: {data.get('reasoning', '')}

⚠️ 리스크 요소:
{chr(10).join(f"- {r}" for r in data.get('risk_factors', []))}"""

                if data.get('reply_to_other'):
                    content += f"\n\n💬 {data.get('reply_to_other')}"

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
            request=request,
        )


# 싱글톤 인스턴스
quant_analyst = QuantAnalyst()

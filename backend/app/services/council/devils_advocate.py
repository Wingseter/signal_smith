"""
GPT 반대론자 (Devil's Advocate)

투자 회의에서 무조건 반대 입장을 취하는 GPT 기반 분석가
- 기술적 지표 + 재무제표 양쪽 데이터 모두 활용
- 다른 분석가들의 논리적 허점 공격
- 투자 리스크를 극대화하여 제시
"""

import logging
from typing import Optional
import json

from openai import AsyncOpenAI

from app.config import settings
from .models import CouncilMessage, AnalystRole
from .technical_indicators import TechnicalAnalysisResult
from app.services.dart_client import FinancialData

logger = logging.getLogger(__name__)


class DevilsAdvocate:
    """GPT 기반 반대론자 — 항상 투자에 반대하는 역할"""

    SYSTEM_PROMPT = """당신은 투자 회의의 **반대론자(Devil's Advocate)**입니다.

당신의 역할은 단 하나: **이 투자가 왜 나쁜 결정인지** 모든 각도에서 반박하는 것입니다.

행동 원칙:
1. 다른 분석가들의 논리적 허점을 정확히 지적하세요
2. 기술적 지표와 재무제표 데이터를 활용하여 리스크를 극대화하세요
3. 최악의 시나리오를 구체적으로 제시하세요
4. 감정이 아닌 데이터와 논리로 반박하세요
5. "이번엔 다르다"는 논리를 항상 의심하세요

분석 영역:
- 기술적 리스크: 과매수, 하락 추세, 거래량 감소, 지지선 이탈
- 재무적 리스크: 부채비율, 현금흐름, 수익성 악화, 밸류에이션 고평가
- 시장 리스크: 섹터 약세, 매크로 리스크, 경쟁 심화
- 뉴스 리스크: 과대 해석, 이미 주가 반영, 실현 불확실성

한국어로 간결하고 날카롭게 답변하세요."""

    ANALYSIS_PROMPT = """다음 투자 결정에 대해 반대 의견을 제시해주세요.

[종목 정보]
종목코드: {symbol}
종목명: {company_name}
트리거: {news_title}

[기술적 지표 데이터]
{technical_data}

[재무제표 데이터]
{financial_data}

[다른 분석가들의 의견]
{previous_analyses}

[요청]
위 분석가들의 의견을 검토하고, 이 투자가 왜 위험한지 반박해주세요.
기술적 지표와 재무제표 데이터를 근거로 구체적인 리스크를 제시하세요.

[응답 형식]
다음 JSON 형식으로 응답해주세요:
{{
    "opposition": "반대 의견 핵심 (2-3문장)",
    "technical_risks": ["기술적 리스크 1", "기술적 리스크 2"],
    "fundamental_risks": ["재무적 리스크 1", "재무적 리스크 2"],
    "worst_case": "최악의 시나리오 (1문장)",
    "risk_score": 1-10 사이 리스크 점수 (10이 가장 위험),
    "recommended_action": "HOLD 또는 PASS (매수 반대 근거)",
    "counter_to_quant": "퀀트 분석가에 대한 반박 (1문장)",
    "counter_to_fundamental": "펀더멘털 분석가에 대한 반박 (1문장)"
}}"""

    def __init__(self):
        self._client: Optional[AsyncOpenAI] = None
        self._initialized = False

    def _initialize(self):
        """OpenAI 클라이언트 초기화 (CLIProxiAPI 경유)"""
        if self._initialized:
            return

        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다")

        self._client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )
        self._initialized = True
        logger.info(f"GPT 반대론자 초기화 (모델: {settings.openai_model})")

    def _build_previous_analyses(self, messages: list[CouncilMessage]) -> str:
        """이전 분석가 의견 구성"""
        if not messages:
            return "(아직 분석 의견 없음)"

        lines = []
        for msg in messages:
            if msg.role in (AnalystRole.GPT_QUANT, AnalystRole.CLAUDE_FUNDAMENTAL):
                content = msg.content[:300]
                lines.append(f"[{msg.speaker}]: {content}")

        return "\n\n".join(lines) if lines else "(분석 의견 없음)"

    async def challenge(
        self,
        symbol: str,
        company_name: str,
        news_title: str,
        previous_messages: list[CouncilMessage],
        technical_data: Optional[TechnicalAnalysisResult] = None,
        financial_data: Optional[FinancialData] = None,
    ) -> CouncilMessage:
        """투자 결정에 반대 의견 제시"""
        self._initialize()

        previous_analyses = self._build_previous_analyses(previous_messages)

        tech_text = technical_data.to_prompt_text() if technical_data else "⚠️ 기술적 데이터 없음"
        fin_text = financial_data.to_prompt_text() if financial_data else "⚠️ 재무제표 데이터 없음"

        prompt = self.ANALYSIS_PROMPT.format(
            symbol=symbol,
            company_name=company_name,
            news_title=news_title,
            technical_data=tech_text,
            financial_data=fin_text,
            previous_analyses=previous_analyses,
        )

        try:
            response = await self._client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.8,  # 다양한 반박을 위해 높은 temperature
                max_tokens=2048,
            )

            response_text = response.choices[0].message.content

            try:
                from .llm_utils import parse_llm_json
                data, parse_err = parse_llm_json(response_text)
                if parse_err:
                    raise json.JSONDecodeError(parse_err, response_text, 0)

                content = f"""😈 **반대론자 의견**

{data.get('opposition', '')}

🚨 기술적 리스크:
{chr(10).join(f"- {r}" for r in data.get('technical_risks', []))}

💣 재무적 리스크:
{chr(10).join(f"- {r}" for r in data.get('fundamental_risks', []))}

⚠️ 최악의 시나리오: {data.get('worst_case', '')}
📊 리스크 점수: {data.get('risk_score', 5)}/10

💬 퀀트 분석가에게: {data.get('counter_to_quant', '')}
💬 펀더멘털 분석가에게: {data.get('counter_to_fundamental', '')}

👉 권장: **{data.get('recommended_action', 'HOLD')}**"""

            except json.JSONDecodeError:
                content = f"😈 **반대론자 의견**\n\n{response_text}"
                data = {"risk_score": 5, "recommended_action": "HOLD"}

            return CouncilMessage(
                role=AnalystRole.GPT_DEVILS_ADVOCATE,
                speaker="GPT 반대론자",
                content=content,
                data=data,
            )

        except Exception as e:
            logger.error(f"반대론자 분석 오류: {e}")
            return CouncilMessage(
                role=AnalystRole.GPT_DEVILS_ADVOCATE,
                speaker="GPT 반대론자",
                content=f"⚠️ 반대 의견 생성 중 오류: {str(e)}",
                data={"error": str(e)},
            )


# 싱글톤 인스턴스
devils_advocate = DevilsAdvocate()

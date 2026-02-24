"""
Claude AI Agent for Fundamental Analysis

Responsibilities:
- Analyze financial statements and reports
- Evaluate company fundamentals
- Assess long-term investment potential
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
import json

from app.config import settings


class ClaudeFundamentalAgent:
    """Claude-based agent for fundamental analysis."""

    def __init__(self):
        self.model_name = settings.anthropic_model
        self.api_key = settings.anthropic_api_key
        self._client = None

    def _get_client(self):
        """Lazy initialization of Anthropic client."""
        if self._client is None and self.api_key:
            from anthropic import AsyncAnthropic
            self._client = AsyncAnthropic(api_key=self.api_key, base_url=settings.anthropic_base_url)
        return self._client

    def _format_financial_data(self, data: dict) -> str:
        """Format financial data for the prompt."""
        if not data:
            return "재무 데이터 없음"

        lines = []

        # Income statement
        if "income_statement" in data:
            inc = data["income_statement"]
            lines.append("손익계산서:")
            lines.append(f"  - 매출액: {inc.get('revenue', 'N/A')}")
            lines.append(f"  - 매출원가: {inc.get('cost_of_sales', 'N/A')}")
            lines.append(f"  - 영업이익: {inc.get('operating_profit', 'N/A')}")
            lines.append(f"  - 당기순이익: {inc.get('net_income', 'N/A')}")

        # Balance sheet
        if "balance_sheet" in data:
            bs = data["balance_sheet"]
            lines.append("재무상태표:")
            lines.append(f"  - 총자산: {bs.get('total_assets', 'N/A')}")
            lines.append(f"  - 총부채: {bs.get('total_liabilities', 'N/A')}")
            lines.append(f"  - 자기자본: {bs.get('equity', 'N/A')}")
            lines.append(f"  - 부채비율: {bs.get('debt_ratio', 'N/A')}%")

        # Ratios
        if "ratios" in data:
            ratios = data["ratios"]
            lines.append("주요 비율:")
            lines.append(f"  - PER: {ratios.get('per', 'N/A')}")
            lines.append(f"  - PBR: {ratios.get('pbr', 'N/A')}")
            lines.append(f"  - ROE: {ratios.get('roe', 'N/A')}%")
            lines.append(f"  - ROA: {ratios.get('roa', 'N/A')}%")
            lines.append(f"  - 영업이익률: {ratios.get('operating_margin', 'N/A')}%")
            lines.append(f"  - 순이익률: {ratios.get('net_margin', 'N/A')}%")

        return "\n".join(lines)

    async def analyze(
        self,
        symbol: str,
        financial_data: Optional[dict] = None,
        company_info: Optional[dict] = None,
    ) -> dict:
        """
        Perform fundamental analysis on a stock.

        Args:
            symbol: Stock symbol to analyze
            financial_data: Optional financial statement data
            company_info: Optional company information

        Returns:
            Fundamental analysis result
        """
        client = self._get_client()

        if client is None:
            return {
                "agent": "claude",
                "analysis_type": "fundamental",
                "symbol": symbol,
                "score": None,
                "summary": "Anthropic API not configured",
                "recommendation": None,
                "error": "API key not set",
            }

        try:
            # Format financial data
            financial_context = self._format_financial_data(financial_data) if financial_data else ""

            # Format company info
            company_context = ""
            if company_info:
                company_context = f"""
                회사 정보:
                - 회사명: {company_info.get('name', 'N/A')}
                - 업종: {company_info.get('sector', 'N/A')}
                - 산업: {company_info.get('industry', 'N/A')}
                - 시가총액: {company_info.get('market_cap', 'N/A')}
                - 상장일: {company_info.get('listing_date', 'N/A')}
                """

            prompt = f"""You are a professional fundamental analyst specializing in Korean stocks.
            Perform a thorough fundamental analysis for stock symbol {symbol}.

            {company_context}

            {financial_context}

            Analyze the following aspects thoroughly:

            1. **Financial Health**
               - Revenue growth trends
               - Profit margins (gross, operating, net)
               - Debt levels and interest coverage
               - Cash flow analysis

            2. **Valuation Metrics**
               - P/E ratio vs industry average
               - P/B ratio
               - EV/EBITDA
               - PEG ratio

            3. **Business Quality**
               - Competitive advantages (moat)
               - Market position
               - Management quality
               - Industry outlook

            4. **Risk Assessment**
               - Key business risks
               - Regulatory risks
               - Competition threats
               - Macro-economic sensitivity

            Provide your analysis in the following JSON format:
            {{
                "fundamental_score": <number from -100 to 100>,
                "financial_health_score": <number from 0 to 100>,
                "valuation_score": <number from -100 to 100>,
                "business_quality_score": <number from 0 to 100>,
                "growth_potential": "<high/medium/low>",
                "valuation_assessment": "<undervalued/fairly valued/overvalued>",
                "key_strengths": ["<strength1>", "<strength2>"],
                "key_risks": ["<risk1>", "<risk2>"],
                "summary": "<3-4 sentence fundamental analysis summary>",
                "investment_thesis": "<brief investment thesis>",
                "recommendation": "<buy/hold/sell>",
                "confidence": <number from 0 to 100>,
                "fair_value_estimate": "<your estimate of fair value or 'insufficient data'>"
            }}

            Respond only with valid JSON."""

            message = await client.messages.create(
                model=self.model_name,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )

            import json
            response_text = message.content[0].text

            # Try to extract JSON from response
            try:
                # Find JSON in response
                start = response_text.find("{")
                end = response_text.rfind("}") + 1
                if start >= 0 and end > start:
                    result = json.loads(response_text[start:end])
                else:
                    raise json.JSONDecodeError("No JSON found", response_text, 0)
            except json.JSONDecodeError:
                result = {
                    "fundamental_score": 0,
                    "summary": response_text[:500],
                    "recommendation": "hold",
                    "confidence": 50,
                }

            return {
                "agent": "claude",
                "analysis_type": "fundamental",
                "symbol": symbol,
                "score": result.get("fundamental_score", 0),
                "summary": result.get("summary", ""),
                "recommendation": result.get("recommendation", "hold"),
                "financial_health_score": result.get("financial_health_score"),
                "valuation_score": result.get("valuation_score"),
                "business_quality_score": result.get("business_quality_score"),
                "growth_potential": result.get("growth_potential"),
                "valuation_assessment": result.get("valuation_assessment"),
                "key_strengths": result.get("key_strengths", []),
                "key_risks": result.get("key_risks", []),
                "investment_thesis": result.get("investment_thesis"),
                "confidence": result.get("confidence", 50),
                "fair_value_estimate": result.get("fair_value_estimate"),
                "analyzed_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            return {
                "agent": "claude",
                "analysis_type": "fundamental",
                "symbol": symbol,
                "score": None,
                "summary": f"Analysis failed: {str(e)}",
                "recommendation": None,
                "error": str(e),
                "analyzed_at": datetime.utcnow().isoformat(),
            }

    async def analyze_financial_report(self, report_text: str, symbol: str) -> dict:
        """
        Analyze a specific financial report (e.g., from DART).

        Args:
            report_text: Text content of the financial report
            symbol: Stock symbol

        Returns:
            Detailed analysis of the report
        """
        client = self._get_client()

        if client is None:
            return {"error": "API key not set"}

        try:
            prompt = f"""Analyze the following financial report for {symbol}:

            {report_text[:10000]}  # Limit to first 10k characters

            Extract and analyze:
            1. Key financial metrics and their trends
            2. Notable changes from previous periods
            3. Management discussion highlights
            4. Risk factors mentioned
            5. Future outlook and guidance

            Provide a structured analysis in JSON format:
            {{
                "report_type": "<type of report>",
                "period": "<reporting period>",
                "key_metrics": {{}},
                "notable_changes": [],
                "management_outlook": "<summary>",
                "risk_factors": [],
                "investment_implications": "<analysis>",
                "sentiment": "<positive/neutral/negative>"
            }}
            """

            message = await client.messages.create(
                model=self.model_name,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )

            import json
            response_text = message.content[0].text

            try:
                start = response_text.find("{")
                end = response_text.rfind("}") + 1
                if start >= 0 and end > start:
                    return json.loads(response_text[start:end])
            except json.JSONDecodeError:
                pass

            return {"analysis": response_text}

        except Exception as e:
            return {"error": str(e)}

    async def compare_peers(
        self,
        symbol: str,
        peers: List[dict],
        financial_data: Optional[dict] = None,
    ) -> dict:
        """
        Compare a stock with its peers.

        Args:
            symbol: Target stock symbol
            peers: List of peer company data
            financial_data: Target company's financial data

        Returns:
            Peer comparison analysis
        """
        client = self._get_client()

        if client is None:
            return {"error": "API key not set"}

        try:
            peers_str = "\n".join([
                f"- {p.get('symbol', 'N/A')} ({p.get('name', 'N/A')}): "
                f"PER {p.get('per', 'N/A')}, PBR {p.get('pbr', 'N/A')}, "
                f"ROE {p.get('roe', 'N/A')}%"
                for p in peers
            ])

            target_str = self._format_financial_data(financial_data) if financial_data else "데이터 없음"

            prompt = f"""
            {symbol} 종목을 동종 업체와 비교 분석하세요:

            대상 종목 ({symbol}):
            {target_str}

            동종 업체:
            {peers_str}

            다음 JSON 형식으로 비교 분석을 제공하세요:
            {{
                "relative_valuation": {{
                    "vs_peers": "<premium/inline/discount>",
                    "valuation_gap_pct": <시장 대비 할인/프리미엄 %>
                }},
                "competitive_position": {{
                    "market_share_rank": <순위 또는 "N/A">,
                    "competitive_advantages": ["<강점1>", "<강점2>"],
                    "competitive_weaknesses": ["<약점1>", "<약점2>"]
                }},
                "financial_comparison": {{
                    "profitability_rank": <순위>,
                    "growth_rank": <순위>,
                    "stability_rank": <순위>
                }},
                "peer_vs_analysis": [
                    {{
                        "peer_symbol": "<피어 종목코드>",
                        "comparison": "<비교 분석>",
                        "preference": "<target/peer/neutral>"
                    }}
                ],
                "summary": "<동종 업체 대비 종합 평가 (한글)>",
                "recommendation": "<업종 내 추천 순위 및 이유>"
            }}
            """

            message = await client.messages.create(
                model=self.model_name,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )

            response_text = message.content[0].text

            try:
                start = response_text.find("{")
                end = response_text.rfind("}") + 1
                if start >= 0 and end > start:
                    result = json.loads(response_text[start:end])
                    result["symbol"] = symbol
                    result["compared_at"] = datetime.utcnow().isoformat()
                    return result
            except json.JSONDecodeError:
                pass

            return {
                "symbol": symbol,
                "analysis": response_text,
                "compared_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            return {"error": str(e)}

    async def evaluate_dividend(
        self,
        symbol: str,
        dividend_history: List[dict],
        financial_data: Optional[dict] = None,
    ) -> dict:
        """
        Evaluate dividend policy and sustainability.

        Args:
            symbol: Stock symbol
            dividend_history: Historical dividend data
            financial_data: Financial statement data

        Returns:
            Dividend analysis
        """
        client = self._get_client()

        if client is None:
            return {"error": "API key not set"}

        try:
            dividend_str = "\n".join([
                f"- {d.get('year', 'N/A')}: {d.get('dps', 0):,}원 (배당률 {d.get('yield', 0):.2f}%)"
                for d in dividend_history
            ]) if dividend_history else "배당 데이터 없음"

            financial_str = self._format_financial_data(financial_data) if financial_data else ""

            prompt = f"""
            {symbol} 종목의 배당 정책을 분석하세요:

            배당 이력:
            {dividend_str}

            {financial_str}

            다음 JSON 형식으로 배당 분석을 제공하세요:
            {{
                "dividend_score": <0-100>,
                "current_yield": <현재 배당률 %>,
                "payout_ratio": <배당성향 %>,
                "sustainability": {{
                    "score": <0-100>,
                    "assessment": "<안정적/주의/위험>",
                    "concerns": ["<우려사항1>"]
                }},
                "growth_potential": {{
                    "trend": "<increasing/stable/decreasing>",
                    "expected_growth": "<예상 성장률>"
                }},
                "dividend_history_analysis": "<배당 이력 분석>",
                "vs_sector": "<업종 대비 배당 수준>",
                "recommendation": {{
                    "action": "<buy for income/hold/avoid>",
                    "target_investor": "<적합한 투자자 유형>",
                    "rationale": "<근거>"
                }},
                "summary": "<배당 투자 관점 요약 (한글)>"
            }}
            """

            message = await client.messages.create(
                model=self.model_name,
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}],
            )

            response_text = message.content[0].text

            try:
                start = response_text.find("{")
                end = response_text.rfind("}") + 1
                if start >= 0 and end > start:
                    result = json.loads(response_text[start:end])
                    result["symbol"] = symbol
                    result["analyzed_at"] = datetime.utcnow().isoformat()
                    return result
            except json.JSONDecodeError:
                pass

            return {
                "symbol": symbol,
                "analysis": response_text,
                "analyzed_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            return {"error": str(e)}

    async def assess_esg(
        self,
        symbol: str,
        esg_data: Optional[dict] = None,
        company_info: Optional[dict] = None,
    ) -> dict:
        """
        ESG (Environmental, Social, Governance) assessment.

        Args:
            symbol: Stock symbol
            esg_data: ESG-related data if available
            company_info: Company information

        Returns:
            ESG assessment
        """
        client = self._get_client()

        if client is None:
            return {"error": "API key not set"}

        try:
            context = ""
            if company_info:
                context = f"""
                회사 정보:
                - 회사명: {company_info.get('name', 'N/A')}
                - 업종: {company_info.get('sector', 'N/A')}
                - 산업: {company_info.get('industry', 'N/A')}
                """

            esg_context = ""
            if esg_data:
                esg_context = f"""
                ESG 데이터:
                - 환경 점수: {esg_data.get('environmental_score', 'N/A')}
                - 사회 점수: {esg_data.get('social_score', 'N/A')}
                - 지배구조 점수: {esg_data.get('governance_score', 'N/A')}
                """

            prompt = f"""
            {symbol} 종목의 ESG 평가를 수행하세요:

            {context}
            {esg_context}

            다음 JSON 형식으로 ESG 분석을 제공하세요:
            {{
                "overall_esg_score": <0-100>,
                "environmental": {{
                    "score": <0-100>,
                    "key_factors": ["<요인1>", "<요인2>"],
                    "risks": ["<리스크1>"],
                    "initiatives": ["<이니셔티브1>"]
                }},
                "social": {{
                    "score": <0-100>,
                    "key_factors": ["<요인1>"],
                    "labor_practices": "<평가>",
                    "community_impact": "<평가>"
                }},
                "governance": {{
                    "score": <0-100>,
                    "board_quality": "<평가>",
                    "transparency": "<평가>",
                    "shareholder_rights": "<평가>"
                }},
                "esg_trend": "<improving/stable/declining>",
                "materiality_issues": ["<중요 이슈1>", "<중요 이슈2>"],
                "investment_implication": "<ESG 관점 투자 시사점>",
                "summary": "<ESG 종합 평가 (한글)>"
            }}
            """

            message = await client.messages.create(
                model=self.model_name,
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}],
            )

            response_text = message.content[0].text

            try:
                start = response_text.find("{")
                end = response_text.rfind("}") + 1
                if start >= 0 and end > start:
                    result = json.loads(response_text[start:end])
                    result["symbol"] = symbol
                    result["assessed_at"] = datetime.utcnow().isoformat()
                    return result
            except json.JSONDecodeError:
                pass

            return {
                "symbol": symbol,
                "analysis": response_text,
                "assessed_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            return {"error": str(e)}

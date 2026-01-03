"""
Claude AI Agent for Fundamental Analysis

Responsibilities:
- Analyze financial statements and reports
- Evaluate company fundamentals
- Assess long-term investment potential
"""

from typing import Optional

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
            self._client = AsyncAnthropic(api_key=self.api_key)
        return self._client

    async def analyze(
        self,
        symbol: str,
        financial_data: Optional[dict] = None,
    ) -> dict:
        """
        Perform fundamental analysis on a stock.

        Args:
            symbol: Stock symbol to analyze
            financial_data: Optional financial statement data

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
            prompt = f"""You are a fundamental analyst specializing in Korean stocks.
            Analyze the company with stock symbol {symbol}.

            Perform a thorough fundamental analysis considering:

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

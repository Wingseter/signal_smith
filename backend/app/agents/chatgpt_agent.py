"""
ChatGPT AI Agent for Quantitative Analysis

Responsibilities:
- Perform quantitative analysis on stock data
- Develop and evaluate trading strategies
- Generate buy/sell signals based on quantitative factors
"""

from typing import Optional

from app.config import settings


class ChatGPTQuantAgent:
    """ChatGPT-based agent for quantitative analysis."""

    def __init__(self):
        self.model_name = settings.openai_model
        self.api_key = settings.openai_api_key
        self._client = None

    def _get_client(self):
        """Lazy initialization of OpenAI client."""
        if self._client is None and self.api_key:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(api_key=self.api_key)
        return self._client

    async def analyze(self, symbol: str, price_data: Optional[list] = None) -> dict:
        """
        Perform quantitative analysis on a stock.

        Args:
            symbol: Stock symbol to analyze
            price_data: Optional historical price data

        Returns:
            Quantitative analysis result
        """
        client = self._get_client()

        if client is None:
            return {
                "agent": "chatgpt",
                "analysis_type": "quant",
                "symbol": symbol,
                "score": None,
                "summary": "OpenAI API not configured",
                "recommendation": None,
                "error": "API key not set",
            }

        try:
            system_prompt = """You are a quantitative analyst specializing in Korean stocks.
            Analyze stocks using quantitative factors and provide trading recommendations.
            Always respond in valid JSON format."""

            user_prompt = f"""
            Perform quantitative analysis for stock symbol: {symbol}

            Analyze the following factors and provide your assessment:
            1. Price momentum (short-term and long-term)
            2. Volatility analysis
            3. Volume trends
            4. Relative strength vs market index
            5. Mean reversion potential

            Provide your analysis in this JSON format:
            {{
                "quant_score": <number from -100 to 100>,
                "momentum_score": <number from -100 to 100>,
                "volatility_assessment": "<low/medium/high>",
                "volume_trend": "<increasing/stable/decreasing>",
                "relative_strength": <number from 0 to 100>,
                "summary": "<2-3 sentence quantitative summary>",
                "trading_strategy": "<specific trading recommendation>",
                "recommendation": "<buy/hold/sell>",
                "confidence": <number from 0 to 100>,
                "risk_level": "<low/medium/high>"
            }}
            """

            response = await client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
            )

            import json
            result = json.loads(response.choices[0].message.content)

            return {
                "agent": "chatgpt",
                "analysis_type": "quant",
                "symbol": symbol,
                "score": result.get("quant_score", 0),
                "summary": result.get("summary", ""),
                "recommendation": result.get("recommendation", "hold"),
                "momentum_score": result.get("momentum_score"),
                "volatility": result.get("volatility_assessment"),
                "volume_trend": result.get("volume_trend"),
                "relative_strength": result.get("relative_strength"),
                "trading_strategy": result.get("trading_strategy"),
                "confidence": result.get("confidence", 50),
                "risk_level": result.get("risk_level"),
            }

        except Exception as e:
            return {
                "agent": "chatgpt",
                "analysis_type": "quant",
                "symbol": symbol,
                "score": None,
                "summary": f"Analysis failed: {str(e)}",
                "recommendation": None,
                "error": str(e),
            }

    async def generate_trading_signal(
        self,
        symbol: str,
        current_price: float,
        analysis_results: dict,
    ) -> dict:
        """
        Generate a specific trading signal based on analysis.

        Args:
            symbol: Stock symbol
            current_price: Current stock price
            analysis_results: Combined analysis from all agents

        Returns:
            Trading signal with entry/exit points
        """
        client = self._get_client()

        if client is None:
            return {"error": "API key not set"}

        try:
            prompt = f"""
            Based on the following analysis for {symbol} at current price {current_price}:

            {analysis_results}

            Generate a specific trading signal in JSON format:
            {{
                "action": "<buy/sell/hold>",
                "signal_strength": <number from 0 to 100>,
                "entry_price": <suggested entry price or null>,
                "target_price": <target price for profit taking>,
                "stop_loss": <stop loss price>,
                "position_size_percent": <recommended position size as % of portfolio>,
                "time_horizon": "<short/medium/long>",
                "rationale": "<brief explanation>"
            }}
            """

            response = await client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.2,
            )

            import json
            return json.loads(response.choices[0].message.content)

        except Exception as e:
            return {"error": str(e)}

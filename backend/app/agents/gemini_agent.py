"""
Gemini AI Agent for Real-time News Analysis

Responsibilities:
- Monitor news headlines and breaking news
- Analyze market sentiment from news
- Identify news-driven trading opportunities
"""

from typing import Optional

from app.config import settings


class GeminiNewsAgent:
    """Gemini-based agent for news and sentiment analysis."""

    def __init__(self):
        self.model_name = settings.gemini_model
        self.api_key = settings.google_api_key
        self._client = None

    def _get_client(self):
        """Lazy initialization of Gemini client."""
        if self._client is None and self.api_key:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self._client = genai.GenerativeModel(self.model_name)
        return self._client

    async def analyze(self, symbol: str) -> dict:
        """
        Analyze news sentiment for a stock symbol.

        Args:
            symbol: Stock symbol to analyze

        Returns:
            Analysis result with sentiment score and summary
        """
        client = self._get_client()

        if client is None:
            return {
                "agent": "gemini",
                "analysis_type": "news",
                "symbol": symbol,
                "score": None,
                "summary": "Gemini API not configured",
                "recommendation": None,
                "error": "API key not set",
            }

        try:
            prompt = f"""
            You are a financial news analyst. Analyze the recent news sentiment for the Korean stock with symbol {symbol}.

            Provide your analysis in the following JSON format:
            {{
                "sentiment_score": <number from -100 to 100>,
                "summary": "<2-3 sentence summary of news sentiment>",
                "key_news": ["<headline 1>", "<headline 2>"],
                "recommendation": "<buy/hold/sell based on news sentiment>",
                "confidence": <number from 0 to 100>
            }}

            Consider:
            - Recent company announcements
            - Industry news
            - Market-moving events
            - Analyst opinions

            Respond only with valid JSON.
            """

            response = await client.generate_content_async(prompt)

            # Parse response
            import json
            try:
                result = json.loads(response.text)
            except json.JSONDecodeError:
                result = {
                    "sentiment_score": 0,
                    "summary": response.text[:500],
                    "recommendation": "hold",
                    "confidence": 50,
                }

            return {
                "agent": "gemini",
                "analysis_type": "news",
                "symbol": symbol,
                "score": result.get("sentiment_score", 0),
                "summary": result.get("summary", ""),
                "recommendation": result.get("recommendation", "hold"),
                "key_news": result.get("key_news", []),
                "confidence": result.get("confidence", 50),
            }

        except Exception as e:
            return {
                "agent": "gemini",
                "analysis_type": "news",
                "symbol": symbol,
                "score": None,
                "summary": f"Analysis failed: {str(e)}",
                "recommendation": None,
                "error": str(e),
            }

    async def analyze_breaking_news(self, news_text: str) -> dict:
        """
        Analyze breaking news for potential trading signals.

        Args:
            news_text: News article or headline text

        Returns:
            Quick analysis of news impact
        """
        client = self._get_client()

        if client is None:
            return {"error": "API key not set"}

        try:
            prompt = f"""
            Analyze this breaking news for potential stock market impact:

            "{news_text}"

            Provide a quick analysis in JSON format:
            {{
                "impact_level": "<high/medium/low>",
                "affected_sectors": ["<sector1>", "<sector2>"],
                "sentiment": "<positive/negative/neutral>",
                "urgency": <number from 1 to 10>,
                "brief_analysis": "<one sentence summary>"
            }}
            """

            response = await client.generate_content_async(prompt)

            import json
            try:
                return json.loads(response.text)
            except json.JSONDecodeError:
                return {
                    "impact_level": "medium",
                    "sentiment": "neutral",
                    "brief_analysis": response.text[:200],
                }

        except Exception as e:
            return {"error": str(e)}

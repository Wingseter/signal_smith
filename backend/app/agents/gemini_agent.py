"""
Gemini AI Agent for Real-time News Analysis

Responsibilities:
- Monitor news headlines and breaking news
- Analyze market sentiment from news
- Identify news-driven trading opportunities
"""

from typing import Optional, List
from datetime import datetime
import json

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

    async def analyze(
        self,
        symbol: str,
        news_data: Optional[List[dict]] = None,
        price_context: Optional[dict] = None,
    ) -> dict:
        """
        Analyze news sentiment for a stock symbol.

        Args:
            symbol: Stock symbol to analyze
            news_data: Optional list of news articles
            price_context: Optional current price information

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
            # Build context from provided data
            news_context = ""
            if news_data:
                news_items = []
                for i, news in enumerate(news_data[:10], 1):
                    title = news.get("title", "")
                    content = news.get("content", news.get("description", ""))[:200]
                    source = news.get("source", "Unknown")
                    date = news.get("date", news.get("published_at", ""))
                    news_items.append(f"{i}. [{source}] {title}\n   {content}... ({date})")
                news_context = f"\n\n실제 뉴스 데이터:\n" + "\n".join(news_items)

            price_info = ""
            if price_context:
                price_info = f"""
                현재 시세 정보:
                - 현재가: {price_context.get('current_price', 'N/A'):,}원
                - 전일대비: {price_context.get('change', 'N/A'):,}원 ({price_context.get('change_rate', 0):.2f}%)
                - 거래량: {price_context.get('volume', 'N/A'):,}주
                """

            prompt = f"""
            You are a financial news analyst specializing in Korean stocks.
            Analyze the news sentiment for stock symbol {symbol}.
            {news_context}
            {price_info}

            Provide your analysis in the following JSON format:
            {{
                "sentiment_score": <number from -100 to 100, positive=bullish, negative=bearish>,
                "summary": "<2-3 sentence summary of news sentiment in Korean>",
                "key_news": ["<주요 뉴스 1>", "<주요 뉴스 2>"],
                "positive_factors": ["<긍정 요인 1>", "<긍정 요인 2>"],
                "negative_factors": ["<부정 요인 1>", "<부정 요인 2>"],
                "recommendation": "<buy/hold/sell based on news sentiment>",
                "confidence": <number from 0 to 100>,
                "news_impact": "<high/medium/low>",
                "time_sensitivity": "<urgent/normal/low>"
            }}

            Consider:
            - Company announcements and earnings
            - Industry trends and competition
            - Market-moving events
            - Analyst opinions and ratings
            - Regulatory or policy changes
            - Global market sentiment

            Respond only with valid JSON.
            """

            import google.generativeai as genai
            response = await client.generate_content_async(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.3,
                    max_output_tokens=4096,
                ),
            )

            # Parse response - handle markdown code blocks from Gemini 2.5+
            import json
            try:
                text = response.text
                if "```json" in text:
                    text = text.split("```json")[1].split("```")[0]
                elif "```" in text:
                    text = text.split("```")[1].split("```")[0]
                result = json.loads(text.strip())
            except (json.JSONDecodeError, IndexError):
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
                "positive_factors": result.get("positive_factors", []),
                "negative_factors": result.get("negative_factors", []),
                "confidence": result.get("confidence", 50),
                "news_impact": result.get("news_impact", "medium"),
                "time_sensitivity": result.get("time_sensitivity", "normal"),
                "analyzed_at": datetime.utcnow().isoformat(),
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
                "analyzed_at": datetime.utcnow().isoformat(),
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

            import google.generativeai as genai
            response = await client.generate_content_async(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.3,
                    max_output_tokens=4096,
                ),
            )

            import json
            try:
                text = response.text
                if "```json" in text:
                    text = text.split("```json")[1].split("```")[0]
                elif "```" in text:
                    text = text.split("```")[1].split("```")[0]
                return json.loads(text.strip())
            except (json.JSONDecodeError, IndexError):
                return {
                    "impact_level": "medium",
                    "sentiment": "neutral",
                    "brief_analysis": response.text[:200],
                }

        except Exception as e:
            return {"error": str(e)}

    async def get_market_sentiment(self, market: str = "KOSPI") -> dict:
        """
        Get overall market sentiment.

        Args:
            market: Market to analyze (KOSPI or KOSDAQ)

        Returns:
            Overall market sentiment analysis
        """
        client = self._get_client()

        if client is None:
            return {"error": "API key not set"}

        try:
            prompt = f"""
            Analyze the current overall sentiment for the Korean {market} market.

            Consider:
            - Global market trends (US, China, Japan markets)
            - Korean economic indicators
            - Foreign investor flows
            - Sector rotation trends
            - Key upcoming events

            Provide analysis in JSON format:
            {{
                "market": "{market}",
                "overall_sentiment": "<bullish/neutral/bearish>",
                "sentiment_score": <number from -100 to 100>,
                "key_drivers": ["<driver1>", "<driver2>"],
                "sector_outlook": {{
                    "strong": ["<sector1>", "<sector2>"],
                    "weak": ["<sector1>", "<sector2>"]
                }},
                "risk_factors": ["<risk1>", "<risk2>"],
                "opportunities": ["<opportunity1>", "<opportunity2>"],
                "short_term_view": "<1-2 sentence outlook>",
                "recommendation": "<aggressive/moderate/defensive>"
            }}
            """

            import google.generativeai as genai
            response = await client.generate_content_async(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.3,
                    max_output_tokens=4096,
                ),
            )

            try:
                text = response.text
                # Gemini 2.5+ may wrap JSON in markdown code blocks
                if "```json" in text:
                    text = text.split("```json")[1].split("```")[0]
                elif "```" in text:
                    text = text.split("```")[1].split("```")[0]
                result = json.loads(text.strip())
                result["analyzed_at"] = datetime.utcnow().isoformat()
                return result
            except (json.JSONDecodeError, IndexError):
                return {
                    "market": market,
                    "overall_sentiment": "neutral",
                    "analysis": response.text[:500],
                    "analyzed_at": datetime.utcnow().isoformat(),
                }

        except Exception as e:
            return {"error": str(e)}

    async def analyze_with_context(
        self,
        symbol: str,
        news_data: Optional[List[dict]] = None,
        price_data: Optional[List[dict]] = None,
        financial_data: Optional[dict] = None,
    ) -> dict:
        """
        Comprehensive analysis with full context.

        Args:
            symbol: Stock symbol
            news_data: Recent news articles
            price_data: Price history
            financial_data: Financial statement data

        Returns:
            Comprehensive news-based analysis
        """
        client = self._get_client()

        if client is None:
            return {"error": "API key not set"}

        try:
            # Build comprehensive context
            context_parts = [f"종목 코드: {symbol}"]

            if news_data:
                news_summary = "\n".join([
                    f"- {n.get('title', '')}" for n in news_data[:5]
                ])
                context_parts.append(f"\n최근 뉴스:\n{news_summary}")

            if price_data and len(price_data) > 0:
                latest = price_data[0]
                context_parts.append(f"""
                최근 가격 정보:
                - 현재가: {latest.get('close', 'N/A'):,}원
                - 거래량: {latest.get('volume', 'N/A'):,}
                """)

            if financial_data:
                context_parts.append(f"""
                재무 정보:
                - 매출액: {financial_data.get('revenue', 'N/A')}
                - 영업이익: {financial_data.get('operating_profit', 'N/A')}
                - PER: {financial_data.get('per', 'N/A')}
                """)

            context = "\n".join(context_parts)

            prompt = f"""
            종합적인 뉴스 기반 분석을 수행하세요:

            {context}

            다음 JSON 형식으로 응답하세요:
            {{
                "overall_assessment": "<종합 평가 2-3문장>",
                "news_sentiment": {{
                    "score": <-100 to 100>,
                    "trend": "<improving/stable/declining>"
                }},
                "key_events": [
                    {{"event": "<이벤트>", "impact": "<positive/negative/neutral>", "significance": "<high/medium/low>"}}
                ],
                "market_perception": "<시장의 인식>",
                "catalysts": {{
                    "positive": ["<촉매1>"],
                    "negative": ["<위험요소1>"]
                }},
                "trading_implication": {{
                    "signal": "<buy/hold/sell>",
                    "strength": <0-100>,
                    "timeframe": "<short/medium/long>",
                    "reasoning": "<근거>"
                }}
            }}
            """

            import google.generativeai as genai
            response = await client.generate_content_async(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.3,
                    max_output_tokens=4096,
                ),
            )

            try:
                text = response.text
                if "```json" in text:
                    text = text.split("```json")[1].split("```")[0]
                elif "```" in text:
                    text = text.split("```")[1].split("```")[0]
                result = json.loads(text.strip())
            except (json.JSONDecodeError, IndexError):
                # Fallback: try to extract JSON from response
                text = response.text
                start = text.find("{")
                end = text.rfind("}") + 1
                if start >= 0 and end > start:
                    try:
                        result = json.loads(text[start:end])
                    except json.JSONDecodeError:
                        result = {"analysis": text[:500]}
                else:
                    result = {"analysis": text[:500]}

            result["symbol"] = symbol
            result["agent"] = "gemini"
            result["analyzed_at"] = datetime.utcnow().isoformat()

            return result

        except Exception as e:
            return {
                "symbol": symbol,
                "agent": "gemini",
                "error": str(e),
                "analyzed_at": datetime.utcnow().isoformat(),
            }

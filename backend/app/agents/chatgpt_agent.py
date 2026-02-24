"""
ChatGPT AI Agent for Quantitative Analysis

Responsibilities:
- Perform quantitative analysis on stock data
- Develop and evaluate trading strategies
- Generate buy/sell signals based on quantitative factors
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
import json

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
            self._client = AsyncOpenAI(api_key=self.api_key, base_url=settings.openai_base_url)
        return self._client

    def _calculate_basic_indicators(self, price_data: List[dict]) -> Dict[str, Any]:
        """Calculate basic technical indicators from price data."""
        if not price_data or len(price_data) < 5:
            return {}

        closes = [p.get("close", 0) for p in price_data]
        volumes = [p.get("volume", 0) for p in price_data]

        # Calculate simple metrics
        current = closes[0] if closes else 0
        prev = closes[1] if len(closes) > 1 else current

        # 5-day and 20-day moving averages
        ma5 = sum(closes[:5]) / min(5, len(closes)) if closes else 0
        ma20 = sum(closes[:20]) / min(20, len(closes)) if closes else 0

        # Volume average
        vol_avg = sum(volumes[:20]) / min(20, len(volumes)) if volumes else 0

        # Price change
        change_1d = ((current - prev) / prev * 100) if prev else 0
        change_5d = ((current - closes[4]) / closes[4] * 100) if len(closes) > 4 else 0
        change_20d = ((current - closes[19]) / closes[19] * 100) if len(closes) > 19 else 0

        # Volatility (standard deviation of returns)
        if len(closes) > 1:
            returns = [(closes[i] - closes[i+1]) / closes[i+1] * 100
                      for i in range(min(20, len(closes)-1))]
            volatility = (sum((r - sum(returns)/len(returns))**2 for r in returns) / len(returns)) ** 0.5
        else:
            volatility = 0

        return {
            "current_price": current,
            "ma5": round(ma5, 2),
            "ma20": round(ma20, 2),
            "ma5_signal": "above" if current > ma5 else "below",
            "ma20_signal": "above" if current > ma20 else "below",
            "volume_current": volumes[0] if volumes else 0,
            "volume_avg_20d": round(vol_avg, 0),
            "volume_ratio": round(volumes[0] / vol_avg, 2) if vol_avg > 0 else 0,
            "change_1d": round(change_1d, 2),
            "change_5d": round(change_5d, 2),
            "change_20d": round(change_20d, 2),
            "volatility_20d": round(volatility, 2),
        }

    async def analyze(
        self,
        symbol: str,
        price_data: Optional[List[dict]] = None,
        market_data: Optional[dict] = None,
    ) -> dict:
        """
        Perform quantitative analysis on a stock.

        Args:
            symbol: Stock symbol to analyze
            price_data: Optional historical price data
            market_data: Optional market index data for relative analysis

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
            # Calculate indicators if price data is provided
            indicators = self._calculate_basic_indicators(price_data) if price_data else {}

            # Build data context
            data_context = ""
            if indicators:
                data_context = f"""
                실제 기술적 지표:
                - 현재가: {indicators.get('current_price', 'N/A'):,}원
                - 5일 이동평균: {indicators.get('ma5', 'N/A'):,}원 ({indicators.get('ma5_signal', 'N/A')})
                - 20일 이동평균: {indicators.get('ma20', 'N/A'):,}원 ({indicators.get('ma20_signal', 'N/A')})
                - 1일 변동률: {indicators.get('change_1d', 0):.2f}%
                - 5일 변동률: {indicators.get('change_5d', 0):.2f}%
                - 20일 변동률: {indicators.get('change_20d', 0):.2f}%
                - 거래량 비율 (vs 20일 평균): {indicators.get('volume_ratio', 0):.2f}x
                - 20일 변동성: {indicators.get('volatility_20d', 0):.2f}%
                """

            market_context = ""
            if market_data:
                market_context = f"""
                시장 지수 정보:
                - KOSPI: {market_data.get('kospi', 'N/A')}
                - KOSDAQ: {market_data.get('kosdaq', 'N/A')}
                - 시장 변동률: {market_data.get('market_change', 'N/A')}%
                """

            system_prompt = """You are a professional quantitative analyst specializing in Korean stocks.
            Analyze stocks using quantitative factors and provide actionable trading recommendations.
            Use the provided technical indicators for your analysis.
            Always respond in valid JSON format only. No additional text."""

            user_prompt = f"""
            종목 코드 {symbol}에 대한 퀀트 분석을 수행하세요.
            {data_context}
            {market_context}

            다음 요소들을 분석하세요:
            1. 가격 모멘텀 (단기/중기/장기)
            2. 변동성 분석 및 리스크 평가
            3. 거래량 트렌드 및 이상 징후
            4. 이동평균 기반 추세 분석
            5. 시장 대비 상대 강도 (RS)
            6. 평균회귀 가능성

            다음 JSON 형식으로 응답하세요:
            {{
                "quant_score": <-100 to 100, 양수=매수, 음수=매도>,
                "momentum": {{
                    "short_term": <-100 to 100>,
                    "medium_term": <-100 to 100>,
                    "trend": "<uptrend/sideways/downtrend>"
                }},
                "volatility": {{
                    "level": "<low/medium/high>",
                    "percentile": <0-100>,
                    "risk_adjusted_return": <number>
                }},
                "volume_analysis": {{
                    "trend": "<increasing/stable/decreasing>",
                    "conviction": "<strong/moderate/weak>",
                    "unusual_activity": <true/false>
                }},
                "moving_averages": {{
                    "ma_trend": "<bullish/neutral/bearish>",
                    "golden_cross": <true/false>,
                    "death_cross": <true/false>
                }},
                "relative_strength": <0 to 100>,
                "mean_reversion": {{
                    "probability": <0-100>,
                    "direction": "<up/down/none>"
                }},
                "summary": "<2-3문장 퀀트 분석 요약 (한글)>",
                "trading_strategy": "<구체적인 매매 전략 (한글)>",
                "entry_point": "<진입 가격 또는 조건>",
                "exit_point": "<청산 가격 또는 조건>",
                "recommendation": "<buy/hold/sell>",
                "confidence": <0 to 100>,
                "risk_level": "<low/medium/high>",
                "time_horizon": "<short/medium/long>"
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
                "momentum": result.get("momentum"),
                "volatility": result.get("volatility"),
                "volume_analysis": result.get("volume_analysis"),
                "moving_averages": result.get("moving_averages"),
                "relative_strength": result.get("relative_strength"),
                "mean_reversion": result.get("mean_reversion"),
                "trading_strategy": result.get("trading_strategy"),
                "entry_point": result.get("entry_point"),
                "exit_point": result.get("exit_point"),
                "confidence": result.get("confidence", 50),
                "risk_level": result.get("risk_level"),
                "time_horizon": result.get("time_horizon"),
                "indicators": indicators,
                "analyzed_at": datetime.utcnow().isoformat(),
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
                "analyzed_at": datetime.utcnow().isoformat(),
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

    async def backtest_strategy(
        self,
        symbol: str,
        strategy: str,
        price_data: List[dict],
        initial_capital: int = 10000000,
    ) -> dict:
        """
        Backtest a trading strategy.

        Args:
            symbol: Stock symbol
            strategy: Strategy description or name
            price_data: Historical price data
            initial_capital: Initial capital in KRW

        Returns:
            Backtest results
        """
        client = self._get_client()

        if client is None:
            return {"error": "API key not set"}

        if len(price_data) < 20:
            return {"error": "Insufficient price data for backtesting"}

        try:
            # Prepare price summary
            price_summary = {
                "period_start": price_data[-1].get("date", ""),
                "period_end": price_data[0].get("date", ""),
                "start_price": price_data[-1].get("close", 0),
                "end_price": price_data[0].get("close", 0),
                "high": max(p.get("high", 0) for p in price_data),
                "low": min(p.get("low", 0) for p in price_data),
                "data_points": len(price_data),
            }

            prompt = f"""
            다음 전략을 백테스트하세요:
            종목: {symbol}
            전략: {strategy}
            초기 자본: {initial_capital:,}원

            가격 데이터 요약:
            - 기간: {price_summary['period_start']} ~ {price_summary['period_end']}
            - 시작가: {price_summary['start_price']:,}원
            - 종가: {price_summary['end_price']:,}원
            - 최고가: {price_summary['high']:,}원
            - 최저가: {price_summary['low']:,}원
            - 데이터 포인트: {price_summary['data_points']}개

            백테스트 결과를 JSON 형식으로 제공하세요:
            {{
                "strategy_name": "<전략 이름>",
                "total_return_pct": <총 수익률 %>,
                "annualized_return_pct": <연환산 수익률 %>,
                "max_drawdown_pct": <최대 낙폭 %>,
                "sharpe_ratio": <샤프 비율>,
                "win_rate_pct": <승률 %>,
                "total_trades": <총 거래 수>,
                "profit_factor": <손익비>,
                "avg_trade_return_pct": <평균 거래 수익률>,
                "final_capital": <최종 자본>,
                "buy_hold_return_pct": <단순 보유 수익률>,
                "outperformance_pct": <전략 초과 수익률>,
                "assessment": "<전략 평가 (한글)>",
                "improvements": ["<개선안1>", "<개선안2>"]
            }}
            """

            response = await client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.3,
            )

            result = json.loads(response.choices[0].message.content)
            result["symbol"] = symbol
            result["initial_capital"] = initial_capital
            result["backtested_at"] = datetime.utcnow().isoformat()

            return result

        except Exception as e:
            return {"error": str(e)}

    async def optimize_portfolio(
        self,
        holdings: List[dict],
        risk_tolerance: str = "moderate",
    ) -> dict:
        """
        Optimize portfolio allocation.

        Args:
            holdings: Current portfolio holdings
            risk_tolerance: low/moderate/high

        Returns:
            Portfolio optimization suggestions
        """
        client = self._get_client()

        if client is None:
            return {"error": "API key not set"}

        try:
            holdings_str = "\n".join([
                f"- {h.get('symbol', 'N/A')}: {h.get('weight', 0):.1f}% (평가금액: {h.get('evaluation', 0):,}원)"
                for h in holdings
            ])

            prompt = f"""
            포트폴리오 최적화 분석:

            현재 보유 종목:
            {holdings_str}

            위험 성향: {risk_tolerance}

            다음 JSON 형식으로 최적화 제안을 하세요:
            {{
                "current_analysis": {{
                    "diversification_score": <0-100>,
                    "risk_score": <0-100>,
                    "sector_concentration": "<분석>",
                    "issues": ["<문제점1>", "<문제점2>"]
                }},
                "recommendations": [
                    {{
                        "symbol": "<종목코드>",
                        "action": "<increase/decrease/hold/add/remove>",
                        "target_weight": <목표 비중 %>,
                        "reason": "<이유>"
                    }}
                ],
                "suggested_allocation": {{
                    "<종목코드>": <비중 %>
                }},
                "expected_improvement": {{
                    "risk_reduction": "<예상 리스크 감소>",
                    "return_improvement": "<예상 수익 개선>"
                }},
                "summary": "<포트폴리오 최적화 요약 (한글)>"
            }}
            """

            response = await client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.3,
            )

            result = json.loads(response.choices[0].message.content)
            result["risk_tolerance"] = risk_tolerance
            result["optimized_at"] = datetime.utcnow().isoformat()

            return result

        except Exception as e:
            return {"error": str(e)}

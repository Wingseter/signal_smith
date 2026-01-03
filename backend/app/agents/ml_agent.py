"""
ML Agent for Technical Analysis

Responsibilities:
- Analyze chart patterns
- Evaluate trading volume
- Calculate technical indicators
- Identify support/resistance levels
"""

from typing import Optional
import numpy as np
import pandas as pd


class MLTechnicalAgent:
    """ML-based agent for technical analysis."""

    def __init__(self):
        self.indicators_calculated = False

    async def analyze(
        self,
        symbol: str,
        price_data: Optional[list] = None,
    ) -> dict:
        """
        Perform technical analysis on a stock.

        Args:
            symbol: Stock symbol to analyze
            price_data: Historical OHLCV data

        Returns:
            Technical analysis result
        """
        # If no real price data, return placeholder analysis
        if not price_data:
            return self._generate_placeholder_analysis(symbol)

        try:
            df = pd.DataFrame(price_data)

            # Calculate technical indicators
            indicators = self._calculate_indicators(df)

            # Analyze patterns
            patterns = self._analyze_patterns(df)

            # Calculate overall technical score
            score = self._calculate_technical_score(indicators, patterns)

            # Determine recommendation
            if score > 30:
                recommendation = "buy"
            elif score < -30:
                recommendation = "sell"
            else:
                recommendation = "hold"

            return {
                "agent": "ml",
                "analysis_type": "technical",
                "symbol": symbol,
                "score": score,
                "summary": self._generate_summary(indicators, patterns),
                "recommendation": recommendation,
                "indicators": indicators,
                "patterns": patterns,
                "support_levels": self._find_support_levels(df),
                "resistance_levels": self._find_resistance_levels(df),
                "confidence": 70,
            }

        except Exception as e:
            return {
                "agent": "ml",
                "analysis_type": "technical",
                "symbol": symbol,
                "score": None,
                "summary": f"Analysis failed: {str(e)}",
                "recommendation": None,
                "error": str(e),
            }

    def _calculate_indicators(self, df: pd.DataFrame) -> dict:
        """Calculate technical indicators."""
        close = df["close"].values
        high = df["high"].values if "high" in df else close
        low = df["low"].values if "low" in df else close
        volume = df["volume"].values if "volume" in df else np.ones(len(close))

        indicators = {}

        # Moving Averages
        indicators["sma_5"] = self._sma(close, 5)
        indicators["sma_20"] = self._sma(close, 20)
        indicators["sma_60"] = self._sma(close, 60) if len(close) >= 60 else None

        # EMA
        indicators["ema_12"] = self._ema(close, 12)
        indicators["ema_26"] = self._ema(close, 26) if len(close) >= 26 else None

        # MACD
        if indicators["ema_26"] is not None:
            indicators["macd"] = indicators["ema_12"] - indicators["ema_26"]
            indicators["macd_signal"] = self._ema(
                np.array([indicators["ema_12"] - indicators["ema_26"]] * 9), 9
            )

        # RSI
        indicators["rsi"] = self._rsi(close, 14)

        # Bollinger Bands
        bb_middle = self._sma(close, 20)
        bb_std = np.std(close[-20:]) if len(close) >= 20 else np.std(close)
        indicators["bb_upper"] = bb_middle + 2 * bb_std
        indicators["bb_lower"] = bb_middle - 2 * bb_std
        indicators["bb_middle"] = bb_middle

        # Volume analysis
        indicators["volume_sma"] = self._sma(volume, 20)
        indicators["volume_ratio"] = volume[-1] / indicators["volume_sma"] if indicators["volume_sma"] > 0 else 1

        # Current price position
        indicators["current_price"] = close[-1]
        indicators["price_vs_sma20"] = ((close[-1] / indicators["sma_20"]) - 1) * 100 if indicators["sma_20"] else 0

        return indicators

    def _analyze_patterns(self, df: pd.DataFrame) -> dict:
        """Analyze chart patterns."""
        close = df["close"].values
        patterns = {}

        # Trend analysis
        if len(close) >= 20:
            short_trend = (close[-1] - close[-5]) / close[-5] * 100
            medium_trend = (close[-1] - close[-20]) / close[-20] * 100

            if short_trend > 2:
                patterns["short_term_trend"] = "bullish"
            elif short_trend < -2:
                patterns["short_term_trend"] = "bearish"
            else:
                patterns["short_term_trend"] = "neutral"

            if medium_trend > 5:
                patterns["medium_term_trend"] = "bullish"
            elif medium_trend < -5:
                patterns["medium_term_trend"] = "bearish"
            else:
                patterns["medium_term_trend"] = "neutral"

        # Simple pattern detection
        if len(close) >= 3:
            # Higher highs / higher lows
            if close[-1] > close[-2] > close[-3]:
                patterns["momentum"] = "increasing"
            elif close[-1] < close[-2] < close[-3]:
                patterns["momentum"] = "decreasing"
            else:
                patterns["momentum"] = "mixed"

        return patterns

    def _calculate_technical_score(self, indicators: dict, patterns: dict) -> float:
        """Calculate overall technical score from -100 to 100."""
        score = 0
        weights_used = 0

        # RSI component
        if indicators.get("rsi") is not None:
            rsi = indicators["rsi"]
            if rsi < 30:
                score += 30  # Oversold - bullish
            elif rsi > 70:
                score -= 30  # Overbought - bearish
            else:
                score += (50 - rsi) / 2  # Neutral zone
            weights_used += 1

        # Moving average component
        if indicators.get("price_vs_sma20") is not None:
            pv = indicators["price_vs_sma20"]
            score += min(max(pv * 2, -30), 30)
            weights_used += 1

        # MACD component
        if indicators.get("macd") is not None:
            if indicators["macd"] > 0:
                score += 20
            else:
                score -= 20
            weights_used += 1

        # Volume component
        if indicators.get("volume_ratio") is not None:
            vr = indicators["volume_ratio"]
            if vr > 1.5:
                # High volume - amplify trend
                if patterns.get("short_term_trend") == "bullish":
                    score += 15
                elif patterns.get("short_term_trend") == "bearish":
                    score -= 15
            weights_used += 1

        # Trend component
        if patterns.get("medium_term_trend") == "bullish":
            score += 20
        elif patterns.get("medium_term_trend") == "bearish":
            score -= 20

        return max(min(score, 100), -100)

    def _find_support_levels(self, df: pd.DataFrame) -> list:
        """Find support levels from price data."""
        if len(df) < 20:
            return []

        close = df["close"].values
        low = df["low"].values if "low" in df else close

        # Simple support: recent lows
        supports = []
        for i in range(5, len(low) - 5):
            if low[i] == min(low[i-5:i+5]):
                supports.append(float(low[i]))

        # Return unique levels, sorted
        return sorted(list(set(supports)))[-3:]

    def _find_resistance_levels(self, df: pd.DataFrame) -> list:
        """Find resistance levels from price data."""
        if len(df) < 20:
            return []

        close = df["close"].values
        high = df["high"].values if "high" in df else close

        # Simple resistance: recent highs
        resistances = []
        for i in range(5, len(high) - 5):
            if high[i] == max(high[i-5:i+5]):
                resistances.append(float(high[i]))

        # Return unique levels, sorted
        return sorted(list(set(resistances)))[:3]

    def _generate_summary(self, indicators: dict, patterns: dict) -> str:
        """Generate human-readable summary."""
        parts = []

        if indicators.get("rsi"):
            rsi = indicators["rsi"]
            if rsi < 30:
                parts.append("RSI indicates oversold conditions")
            elif rsi > 70:
                parts.append("RSI indicates overbought conditions")
            else:
                parts.append(f"RSI at {rsi:.1f} shows neutral momentum")

        if patterns.get("medium_term_trend"):
            parts.append(f"Medium-term trend is {patterns['medium_term_trend']}")

        if indicators.get("volume_ratio"):
            vr = indicators["volume_ratio"]
            if vr > 1.5:
                parts.append("Trading volume is above average")
            elif vr < 0.5:
                parts.append("Trading volume is below average")

        return ". ".join(parts) + "." if parts else "Insufficient data for analysis."

    def _generate_placeholder_analysis(self, symbol: str) -> dict:
        """Generate placeholder analysis when no price data available."""
        return {
            "agent": "ml",
            "analysis_type": "technical",
            "symbol": symbol,
            "score": 0,
            "summary": "No price data available for technical analysis. Please ensure price data is collected.",
            "recommendation": "hold",
            "indicators": {},
            "patterns": {},
            "support_levels": [],
            "resistance_levels": [],
            "confidence": 0,
        }

    @staticmethod
    def _sma(data: np.ndarray, period: int) -> float:
        """Calculate Simple Moving Average."""
        if len(data) < period:
            return float(np.mean(data))
        return float(np.mean(data[-period:]))

    @staticmethod
    def _ema(data: np.ndarray, period: int) -> float:
        """Calculate Exponential Moving Average."""
        if len(data) < period:
            return float(np.mean(data))
        multiplier = 2 / (period + 1)
        ema = data[0]
        for price in data[1:]:
            ema = (price - ema) * multiplier + ema
        return float(ema)

    @staticmethod
    def _rsi(data: np.ndarray, period: int = 14) -> float:
        """Calculate Relative Strength Index."""
        if len(data) < period + 1:
            return 50.0

        deltas = np.diff(data)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return float(rsi)

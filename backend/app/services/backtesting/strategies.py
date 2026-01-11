"""
Built-in Trading Strategies for Backtesting
"""

import numpy as np
import pandas as pd

from app.services.backtesting.strategy import (
    Strategy,
    StrategyContext,
    Signal,
    SignalType,
)


class MACrossoverStrategy(Strategy):
    """
    이동평균 교차 전략

    단기 이동평균이 장기 이동평균을 상향 돌파하면 매수,
    하향 돌파하면 매도합니다.
    """

    def __init__(
        self,
        short_period: int = 5,
        long_period: int = 20,
        **kwargs,
    ):
        super().__init__(
            name=f"MA Crossover ({short_period}/{long_period})",
            description="이동평균 교차 전략",
            short_period=short_period,
            long_period=long_period,
            **kwargs,
        )
        self.short_period = short_period
        self.long_period = long_period

    def get_required_history(self) -> int:
        return self.long_period + 5

    def validate_parameters(self) -> bool:
        return self.short_period < self.long_period and self.short_period > 0

    def generate_signal(self, context: StrategyContext) -> Signal:
        df = context.ohlcv
        close = df["close"]

        # Calculate moving averages
        short_ma = close.rolling(self.short_period).mean()
        long_ma = close.rolling(self.long_period).mean()

        current_short = short_ma.iloc[-1]
        current_long = long_ma.iloc[-1]
        prev_short = short_ma.iloc[-2]
        prev_long = long_ma.iloc[-2]

        # Check for crossover
        if prev_short <= prev_long and current_short > current_long:
            # Golden cross - Buy signal
            strength = min((current_short - current_long) / current_long * 100, 1.0)
            return Signal(
                signal_type=SignalType.BUY,
                symbol=context.symbol,
                price=context.current_price,
                timestamp=context.current_date,
                strength=abs(strength),
                reason=f"골든크로스: 단기MA({current_short:.0f}) > 장기MA({current_long:.0f})",
            )

        elif prev_short >= prev_long and current_short < current_long:
            # Death cross - Sell signal (if holding)
            if context.position:
                return Signal(
                    signal_type=SignalType.SELL,
                    symbol=context.symbol,
                    price=context.current_price,
                    timestamp=context.current_date,
                    strength=1.0,
                    reason=f"데드크로스: 단기MA({current_short:.0f}) < 장기MA({current_long:.0f})",
                )

        return Signal(
            signal_type=SignalType.HOLD,
            symbol=context.symbol,
            price=context.current_price,
            timestamp=context.current_date,
        )


class RSIStrategy(Strategy):
    """
    RSI (Relative Strength Index) 전략

    RSI가 과매도 구간(30 이하)에서 상승하면 매수,
    과매수 구간(70 이상)에서 하락하면 매도합니다.
    """

    def __init__(
        self,
        period: int = 14,
        oversold: float = 30.0,
        overbought: float = 70.0,
        **kwargs,
    ):
        super().__init__(
            name=f"RSI ({period}, {oversold}/{overbought})",
            description="RSI 과매수/과매도 전략",
            period=period,
            oversold=oversold,
            overbought=overbought,
            **kwargs,
        )
        self.period = period
        self.oversold = oversold
        self.overbought = overbought

    def get_required_history(self) -> int:
        return self.period + 10

    def validate_parameters(self) -> bool:
        return (
            self.period > 0
            and 0 < self.oversold < self.overbought < 100
        )

    def _calculate_rsi(self, prices: pd.Series) -> pd.Series:
        """Calculate RSI."""
        delta = prices.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)

        avg_gain = gain.rolling(self.period).mean()
        avg_loss = loss.rolling(self.period).mean()

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def generate_signal(self, context: StrategyContext) -> Signal:
        df = context.ohlcv
        rsi = self._calculate_rsi(df["close"])

        current_rsi = rsi.iloc[-1]
        prev_rsi = rsi.iloc[-2]

        # Buy when RSI rises from oversold
        if prev_rsi < self.oversold and current_rsi >= self.oversold:
            strength = (self.oversold - prev_rsi) / self.oversold
            return Signal(
                signal_type=SignalType.BUY,
                symbol=context.symbol,
                price=context.current_price,
                timestamp=context.current_date,
                strength=min(strength, 1.0),
                reason=f"RSI 과매도 탈출: {prev_rsi:.1f} -> {current_rsi:.1f}",
                metadata={"rsi": current_rsi},
            )

        # Sell when RSI falls from overbought (if holding)
        if prev_rsi > self.overbought and current_rsi <= self.overbought:
            if context.position:
                return Signal(
                    signal_type=SignalType.SELL,
                    symbol=context.symbol,
                    price=context.current_price,
                    timestamp=context.current_date,
                    strength=1.0,
                    reason=f"RSI 과매수 탈출: {prev_rsi:.1f} -> {current_rsi:.1f}",
                    metadata={"rsi": current_rsi},
                )

        return Signal(
            signal_type=SignalType.HOLD,
            symbol=context.symbol,
            price=context.current_price,
            timestamp=context.current_date,
            metadata={"rsi": current_rsi},
        )


class BollingerBandStrategy(Strategy):
    """
    볼린저 밴드 전략

    가격이 하단 밴드 아래로 내려갔다가 다시 올라오면 매수,
    상단 밴드 위로 올라갔다가 다시 내려오면 매도합니다.
    """

    def __init__(
        self,
        period: int = 20,
        std_dev: float = 2.0,
        **kwargs,
    ):
        super().__init__(
            name=f"Bollinger Band ({period}, {std_dev}σ)",
            description="볼린저 밴드 평균회귀 전략",
            period=period,
            std_dev=std_dev,
            **kwargs,
        )
        self.period = period
        self.std_dev = std_dev

    def get_required_history(self) -> int:
        return self.period + 5

    def validate_parameters(self) -> bool:
        return self.period > 0 and self.std_dev > 0

    def _calculate_bands(self, prices: pd.Series) -> tuple:
        """Calculate Bollinger Bands."""
        middle = prices.rolling(self.period).mean()
        std = prices.rolling(self.period).std()

        upper = middle + (std * self.std_dev)
        lower = middle - (std * self.std_dev)

        return upper, middle, lower

    def generate_signal(self, context: StrategyContext) -> Signal:
        df = context.ohlcv
        close = df["close"]

        upper, middle, lower = self._calculate_bands(close)

        current_price = context.current_price
        prev_price = close.iloc[-2]

        current_upper = upper.iloc[-1]
        current_lower = lower.iloc[-1]
        current_middle = middle.iloc[-1]

        prev_upper = upper.iloc[-2]
        prev_lower = lower.iloc[-2]

        # Buy when price bounces from lower band
        if prev_price < prev_lower and current_price >= current_lower:
            strength = (prev_lower - prev_price) / prev_lower
            return Signal(
                signal_type=SignalType.BUY,
                symbol=context.symbol,
                price=current_price,
                timestamp=context.current_date,
                strength=min(strength * 10, 1.0),
                reason=f"하단밴드 반등: {current_price:.0f} > {current_lower:.0f}",
                metadata={
                    "upper": current_upper,
                    "middle": current_middle,
                    "lower": current_lower,
                },
            )

        # Sell when price falls from upper band (if holding)
        if prev_price > prev_upper and current_price <= current_upper:
            if context.position:
                return Signal(
                    signal_type=SignalType.SELL,
                    symbol=context.symbol,
                    price=current_price,
                    timestamp=context.current_date,
                    strength=1.0,
                    reason=f"상단밴드 하락: {current_price:.0f} < {current_upper:.0f}",
                    metadata={
                        "upper": current_upper,
                        "middle": current_middle,
                        "lower": current_lower,
                    },
                )

        return Signal(
            signal_type=SignalType.HOLD,
            symbol=context.symbol,
            price=current_price,
            timestamp=context.current_date,
            metadata={
                "upper": current_upper,
                "middle": current_middle,
                "lower": current_lower,
            },
        )


class MACDStrategy(Strategy):
    """
    MACD (Moving Average Convergence Divergence) 전략

    MACD 선이 시그널 선을 상향 돌파하면 매수,
    하향 돌파하면 매도합니다.
    """

    def __init__(
        self,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
        **kwargs,
    ):
        super().__init__(
            name=f"MACD ({fast_period}/{slow_period}/{signal_period})",
            description="MACD 시그널 교차 전략",
            fast_period=fast_period,
            slow_period=slow_period,
            signal_period=signal_period,
            **kwargs,
        )
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period

    def get_required_history(self) -> int:
        return self.slow_period + self.signal_period + 5

    def validate_parameters(self) -> bool:
        return (
            self.fast_period < self.slow_period
            and self.fast_period > 0
            and self.signal_period > 0
        )

    def _calculate_macd(self, prices: pd.Series) -> tuple:
        """Calculate MACD, Signal line, and Histogram."""
        fast_ema = prices.ewm(span=self.fast_period, adjust=False).mean()
        slow_ema = prices.ewm(span=self.slow_period, adjust=False).mean()

        macd = fast_ema - slow_ema
        signal = macd.ewm(span=self.signal_period, adjust=False).mean()
        histogram = macd - signal

        return macd, signal, histogram

    def generate_signal(self, context: StrategyContext) -> Signal:
        df = context.ohlcv
        close = df["close"]

        macd, signal, histogram = self._calculate_macd(close)

        current_macd = macd.iloc[-1]
        current_signal = signal.iloc[-1]
        current_hist = histogram.iloc[-1]

        prev_macd = macd.iloc[-2]
        prev_signal = signal.iloc[-2]
        prev_hist = histogram.iloc[-2]

        # Buy when MACD crosses above signal line
        if prev_macd <= prev_signal and current_macd > current_signal:
            # Stronger signal when histogram is increasing
            strength = min(abs(current_hist) / abs(current_signal) if current_signal != 0 else 0.5, 1.0)
            return Signal(
                signal_type=SignalType.BUY,
                symbol=context.symbol,
                price=context.current_price,
                timestamp=context.current_date,
                strength=strength,
                reason=f"MACD 골든크로스: MACD({current_macd:.2f}) > Signal({current_signal:.2f})",
                metadata={
                    "macd": current_macd,
                    "signal": current_signal,
                    "histogram": current_hist,
                },
            )

        # Sell when MACD crosses below signal line (if holding)
        if prev_macd >= prev_signal and current_macd < current_signal:
            if context.position:
                return Signal(
                    signal_type=SignalType.SELL,
                    symbol=context.symbol,
                    price=context.current_price,
                    timestamp=context.current_date,
                    strength=1.0,
                    reason=f"MACD 데드크로스: MACD({current_macd:.2f}) < Signal({current_signal:.2f})",
                    metadata={
                        "macd": current_macd,
                        "signal": current_signal,
                        "histogram": current_hist,
                    },
                )

        return Signal(
            signal_type=SignalType.HOLD,
            symbol=context.symbol,
            price=context.current_price,
            timestamp=context.current_date,
            metadata={
                "macd": current_macd,
                "signal": current_signal,
                "histogram": current_hist,
            },
        )


class CombinedStrategy(Strategy):
    """
    복합 전략

    여러 지표의 시그널을 조합하여 더 강력한 신호만 거래합니다.
    """

    def __init__(
        self,
        ma_short: int = 5,
        ma_long: int = 20,
        rsi_period: int = 14,
        rsi_oversold: float = 30.0,
        rsi_overbought: float = 70.0,
        min_confirmations: int = 2,
        **kwargs,
    ):
        super().__init__(
            name="Combined Strategy",
            description="MA + RSI 복합 전략",
            ma_short=ma_short,
            ma_long=ma_long,
            rsi_period=rsi_period,
            rsi_oversold=rsi_oversold,
            rsi_overbought=rsi_overbought,
            min_confirmations=min_confirmations,
            **kwargs,
        )
        self.ma_short = ma_short
        self.ma_long = ma_long
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.min_confirmations = min_confirmations

    def get_required_history(self) -> int:
        return max(self.ma_long, self.rsi_period) + 10

    def _calculate_rsi(self, prices: pd.Series) -> pd.Series:
        delta = prices.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.rolling(self.rsi_period).mean()
        avg_loss = loss.rolling(self.rsi_period).mean()
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def generate_signal(self, context: StrategyContext) -> Signal:
        df = context.ohlcv
        close = df["close"]

        # Calculate indicators
        short_ma = close.rolling(self.ma_short).mean()
        long_ma = close.rolling(self.ma_long).mean()
        rsi = self._calculate_rsi(close)

        current_short = short_ma.iloc[-1]
        current_long = long_ma.iloc[-1]
        prev_short = short_ma.iloc[-2]
        prev_long = long_ma.iloc[-2]
        current_rsi = rsi.iloc[-1]

        buy_signals = 0
        sell_signals = 0
        reasons = []

        # MA Crossover check
        if prev_short <= prev_long and current_short > current_long:
            buy_signals += 1
            reasons.append("MA골든크로스")
        elif prev_short >= prev_long and current_short < current_long:
            sell_signals += 1
            reasons.append("MA데드크로스")

        # RSI check
        if current_rsi < self.rsi_oversold:
            buy_signals += 1
            reasons.append(f"RSI과매도({current_rsi:.1f})")
        elif current_rsi > self.rsi_overbought:
            sell_signals += 1
            reasons.append(f"RSI과매수({current_rsi:.1f})")

        # Trend check (price above/below long MA)
        if context.current_price > current_long:
            buy_signals += 1
        else:
            sell_signals += 1

        # Generate signal based on confirmations
        if buy_signals >= self.min_confirmations:
            return Signal(
                signal_type=SignalType.BUY,
                symbol=context.symbol,
                price=context.current_price,
                timestamp=context.current_date,
                strength=min(buy_signals / 3.0, 1.0),
                reason=" + ".join(reasons) if reasons else "복합매수신호",
                metadata={"rsi": current_rsi, "ma_short": current_short, "ma_long": current_long},
            )

        if sell_signals >= self.min_confirmations and context.position:
            return Signal(
                signal_type=SignalType.SELL,
                symbol=context.symbol,
                price=context.current_price,
                timestamp=context.current_date,
                strength=1.0,
                reason=" + ".join(reasons) if reasons else "복합매도신호",
                metadata={"rsi": current_rsi, "ma_short": current_short, "ma_long": current_long},
            )

        return Signal(
            signal_type=SignalType.HOLD,
            symbol=context.symbol,
            price=context.current_price,
            timestamp=context.current_date,
            metadata={"rsi": current_rsi, "ma_short": current_short, "ma_long": current_long},
        )

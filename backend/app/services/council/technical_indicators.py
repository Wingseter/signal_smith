"""
기술적 지표 계산 모듈

키움증권 차트 데이터를 기반으로 기술적 지표를 계산합니다.
- RSI (Relative Strength Index)
- MACD (Moving Average Convergence Divergence)
- 볼린저 밴드 (Bollinger Bands)
- 이동평균선 (MA)
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TechnicalAnalysisResult:
    """기술적 분석 결과"""
    symbol: str
    current_price: int

    # RSI
    rsi_14: Optional[float] = None
    rsi_signal: Optional[str] = None  # 과매수/과매도/중립

    # MACD
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None
    macd_trend: Optional[str] = None  # 상승/하락/교차

    # 볼린저 밴드
    bb_upper: Optional[float] = None
    bb_middle: Optional[float] = None
    bb_lower: Optional[float] = None
    bb_position: Optional[str] = None  # 상단돌파/중앙/하단근접

    # 이동평균
    ma_5: Optional[float] = None
    ma_20: Optional[float] = None
    ma_60: Optional[float] = None
    ma_trend: Optional[str] = None  # 정배열/역배열/혼조

    # 거래량
    volume_avg_20: Optional[int] = None
    volume_ratio: Optional[float] = None  # 최근 거래량 / 평균 거래량

    # 종합 점수 (1-10)
    technical_score: Optional[int] = None

    def to_prompt_text(self) -> str:
        """GPT 프롬프트용 텍스트 생성"""
        lines = [
            f"현재가: {self.current_price:,}원",
            "",
            "【RSI 지표】",
            f"- RSI(14): {self.rsi_14:.1f}" if self.rsi_14 else "- RSI(14): 데이터 부족",
            f"- 신호: {self.rsi_signal}" if self.rsi_signal else "",
            "",
            "【MACD 지표】",
            f"- MACD: {self.macd:.2f}" if self.macd else "- MACD: 데이터 부족",
            f"- Signal: {self.macd_signal:.2f}" if self.macd_signal else "",
            f"- Histogram: {self.macd_histogram:.2f}" if self.macd_histogram else "",
            f"- 추세: {self.macd_trend}" if self.macd_trend else "",
            "",
            "【볼린저 밴드】",
            f"- 상단: {self.bb_upper:,.0f}원" if self.bb_upper else "- 볼린저밴드: 데이터 부족",
            f"- 중앙: {self.bb_middle:,.0f}원" if self.bb_middle else "",
            f"- 하단: {self.bb_lower:,.0f}원" if self.bb_lower else "",
            f"- 위치: {self.bb_position}" if self.bb_position else "",
            "",
            "【이동평균선】",
            f"- MA5: {self.ma_5:,.0f}원" if self.ma_5 else "- 이동평균: 데이터 부족",
            f"- MA20: {self.ma_20:,.0f}원" if self.ma_20 else "",
            f"- MA60: {self.ma_60:,.0f}원" if self.ma_60 else "",
            f"- 배열: {self.ma_trend}" if self.ma_trend else "",
            "",
            "【거래량】",
            f"- 20일 평균: {self.volume_avg_20:,}주" if self.volume_avg_20 else "- 거래량: 데이터 부족",
            f"- 거래량 비율: {self.volume_ratio:.1f}배" if self.volume_ratio else "",
        ]
        return "\n".join(line for line in lines if line or line == "")


class TechnicalIndicatorCalculator:
    """기술적 지표 계산기"""

    def calculate_rsi(self, prices: List[int], period: int = 14) -> Optional[float]:
        """RSI 계산"""
        if len(prices) < period + 1:
            return None

        # 가격 변화량 계산
        changes = [prices[i] - prices[i+1] for i in range(len(prices)-1)]
        changes = changes[:period]  # 최근 period 개만 사용

        gains = [c for c in changes if c > 0]
        losses = [-c for c in changes if c < 0]

        avg_gain = sum(gains) / period if gains else 0
        avg_loss = sum(losses) / period if losses else 0

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return round(rsi, 2)

    def calculate_macd(
        self,
        prices: List[int],
        fast: int = 12,
        slow: int = 26,
        signal: int = 9
    ) -> Dict[str, Optional[float]]:
        """MACD 계산"""
        if len(prices) < slow + signal:
            return {"macd": None, "signal": None, "histogram": None}

        def ema(data: List[float], period: int) -> List[float]:
            """지수이동평균 계산"""
            if len(data) < period:
                return []

            k = 2 / (period + 1)
            ema_values = [sum(data[:period]) / period]  # 첫 EMA는 SMA

            for price in data[period:]:
                ema_values.append(price * k + ema_values[-1] * (1 - k))

            return ema_values

        prices_float = [float(p) for p in prices]

        # EMA 계산 (최신순 → 과거순이므로 뒤집어서 계산)
        prices_asc = list(reversed(prices_float))

        ema_fast = ema(prices_asc, fast)
        ema_slow = ema(prices_asc, slow)

        if not ema_fast or not ema_slow:
            return {"macd": None, "signal": None, "histogram": None}

        # MACD 라인 계산
        min_len = min(len(ema_fast), len(ema_slow))
        macd_line = [ema_fast[-(min_len-i)] - ema_slow[-(min_len-i)] for i in range(min_len)]

        if len(macd_line) < signal:
            return {"macd": None, "signal": None, "histogram": None}

        # Signal 라인 계산
        signal_line = ema(macd_line, signal)

        if not signal_line:
            return {"macd": macd_line[-1], "signal": None, "histogram": None}

        macd_value = macd_line[-1]
        signal_value = signal_line[-1]
        histogram = macd_value - signal_value

        return {
            "macd": round(macd_value, 2),
            "signal": round(signal_value, 2),
            "histogram": round(histogram, 2)
        }

    def calculate_bollinger_bands(
        self,
        prices: List[int],
        period: int = 20,
        std_dev: float = 2.0
    ) -> Dict[str, Optional[float]]:
        """볼린저 밴드 계산"""
        if len(prices) < period:
            return {"upper": None, "middle": None, "lower": None}

        # 최근 period 개의 가격
        recent_prices = prices[:period]

        # 중심선 (SMA)
        middle = sum(recent_prices) / period

        # 표준편차
        variance = sum((p - middle) ** 2 for p in recent_prices) / period
        std = variance ** 0.5

        # 상단/하단 밴드
        upper = middle + (std_dev * std)
        lower = middle - (std_dev * std)

        return {
            "upper": round(upper, 0),
            "middle": round(middle, 0),
            "lower": round(lower, 0)
        }

    def calculate_moving_averages(
        self,
        prices: List[int]
    ) -> Dict[str, Optional[float]]:
        """이동평균선 계산"""
        result = {"ma_5": None, "ma_20": None, "ma_60": None}

        if len(prices) >= 5:
            result["ma_5"] = round(sum(prices[:5]) / 5, 0)

        if len(prices) >= 20:
            result["ma_20"] = round(sum(prices[:20]) / 20, 0)

        if len(prices) >= 60:
            result["ma_60"] = round(sum(prices[:60]) / 60, 0)

        return result

    def calculate_volume_analysis(
        self,
        volumes: List[int],
        period: int = 20
    ) -> Dict[str, Optional[float]]:
        """거래량 분석"""
        if len(volumes) < period:
            return {"avg": None, "ratio": None}

        # 최근 거래량 (오늘)
        current_volume = volumes[0]

        # 20일 평균 거래량
        avg_volume = sum(volumes[1:period+1]) / period

        # 거래량 비율
        ratio = current_volume / avg_volume if avg_volume > 0 else 0

        return {
            "avg": int(avg_volume),
            "ratio": round(ratio, 2)
        }

    def analyze(
        self,
        symbol: str,
        daily_prices: List[Dict[str, Any]]
    ) -> TechnicalAnalysisResult:
        """
        종합 기술적 분석 수행

        Args:
            symbol: 종목코드
            daily_prices: 일봉 데이터 리스트 (최신순)
                [{"date": "20240115", "open": 50000, "high": 51000,
                  "low": 49000, "close": 50500, "volume": 1000000}, ...]
        """
        if not daily_prices:
            logger.warning(f"차트 데이터 없음: {symbol}")
            return TechnicalAnalysisResult(symbol=symbol, current_price=0)

        # 종가 리스트 추출 (최신순)
        close_prices = [d.get("close", 0) for d in daily_prices]
        volumes = [d.get("volume", 0) for d in daily_prices]

        current_price = close_prices[0] if close_prices else 0

        result = TechnicalAnalysisResult(
            symbol=symbol,
            current_price=current_price
        )

        # RSI 계산
        rsi = self.calculate_rsi(close_prices)
        if rsi is not None:
            result.rsi_14 = rsi
            if rsi >= 70:
                result.rsi_signal = "과매수 (매도 신호)"
            elif rsi <= 30:
                result.rsi_signal = "과매도 (매수 신호)"
            else:
                result.rsi_signal = "중립"

        # MACD 계산
        macd_data = self.calculate_macd(close_prices)
        if macd_data["macd"] is not None:
            result.macd = macd_data["macd"]
            result.macd_signal = macd_data["signal"]
            result.macd_histogram = macd_data["histogram"]

            if macd_data["histogram"] and macd_data["histogram"] > 0:
                result.macd_trend = "상승 추세"
            elif macd_data["histogram"] and macd_data["histogram"] < 0:
                result.macd_trend = "하락 추세"
            else:
                result.macd_trend = "추세 전환 중"

        # 볼린저 밴드 계산
        bb_data = self.calculate_bollinger_bands(close_prices)
        if bb_data["middle"] is not None:
            result.bb_upper = bb_data["upper"]
            result.bb_middle = bb_data["middle"]
            result.bb_lower = bb_data["lower"]

            if current_price >= bb_data["upper"]:
                result.bb_position = "상단 돌파 (과매수 주의)"
            elif current_price <= bb_data["lower"]:
                result.bb_position = "하단 근접 (반등 가능)"
            else:
                result.bb_position = "밴드 내 움직임"

        # 이동평균선 계산
        ma_data = self.calculate_moving_averages(close_prices)
        result.ma_5 = ma_data["ma_5"]
        result.ma_20 = ma_data["ma_20"]
        result.ma_60 = ma_data["ma_60"]

        if ma_data["ma_5"] and ma_data["ma_20"] and ma_data["ma_60"]:
            if ma_data["ma_5"] > ma_data["ma_20"] > ma_data["ma_60"]:
                result.ma_trend = "정배열 (상승 추세)"
            elif ma_data["ma_5"] < ma_data["ma_20"] < ma_data["ma_60"]:
                result.ma_trend = "역배열 (하락 추세)"
            else:
                result.ma_trend = "혼조세"

        # 거래량 분석
        vol_data = self.calculate_volume_analysis(volumes)
        result.volume_avg_20 = vol_data["avg"]
        result.volume_ratio = vol_data["ratio"]

        # 종합 점수 계산 (1-10)
        result.technical_score = self._calculate_score(result)

        return result

    def _calculate_score(self, result: TechnicalAnalysisResult) -> int:
        """종합 기술적 점수 계산 (1-10)"""
        score = 5  # 기본 점수

        # RSI 기반 점수 조정
        if result.rsi_14:
            if result.rsi_14 <= 30:
                score += 2  # 과매도 = 매수 기회
            elif result.rsi_14 >= 70:
                score -= 2  # 과매수 = 매도 신호
            elif 40 <= result.rsi_14 <= 60:
                score += 1  # 중립은 약간 긍정

        # MACD 기반 점수 조정
        if result.macd_histogram:
            if result.macd_histogram > 0:
                score += 1
            else:
                score -= 1

        # 볼린저 밴드 기반 점수 조정
        if result.bb_position:
            if "하단" in result.bb_position:
                score += 1
            elif "상단" in result.bb_position:
                score -= 1

        # 이동평균 배열 기반 점수 조정
        if result.ma_trend:
            if "정배열" in result.ma_trend:
                score += 1
            elif "역배열" in result.ma_trend:
                score -= 1

        # 거래량 기반 점수 조정
        if result.volume_ratio:
            if result.volume_ratio >= 2.0:
                score += 1  # 거래량 급증

        # 범위 제한
        return max(1, min(10, score))


# 싱글톤 인스턴스
technical_calculator = TechnicalIndicatorCalculator()

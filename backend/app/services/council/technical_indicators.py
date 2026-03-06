"""
기술적 지표 어댑터 (council용)

signals/indicators.py의 QuantIndicatorCalculator 결과를 council의
TechnicalAnalysisResult로 매핑한다. 계산 로직은 signals 모듈에 단일 소스로 존재.
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from app.services.signals.indicators import quant_calculator

logger = logging.getLogger(__name__)


@dataclass
class TechnicalAnalysisResult:
    """기술적 분석 결과"""
    symbol: str
    current_price: int

    # RSI
    rsi_14: Optional[float] = None
    rsi_signal: Optional[str] = None

    # MACD
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None
    macd_trend: Optional[str] = None

    # 볼린저 밴드
    bb_upper: Optional[float] = None
    bb_middle: Optional[float] = None
    bb_lower: Optional[float] = None
    bb_position: Optional[str] = None

    # 이동평균
    ma_5: Optional[float] = None
    ma_20: Optional[float] = None
    ma_60: Optional[float] = None
    ma_trend: Optional[str] = None

    # 거래량
    volume_avg_20: Optional[int] = None
    volume_ratio: Optional[float] = None

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
    """기술적 지표 계산기 — QuantIndicatorCalculator 결과를 매핑"""

    def analyze(self, symbol: str, daily_prices: List[Dict[str, Any]]) -> TechnicalAnalysisResult:
        """종합 기술적 분석 수행 (signals 모듈에 위임)"""
        if not daily_prices:
            logger.warning(f"차트 데이터 없음: {symbol}")
            return TechnicalAnalysisResult(symbol=symbol, current_price=0)

        ind = quant_calculator.calculate_all(symbol, daily_prices)
        current_price = ind.current_price

        result = TechnicalAnalysisResult(symbol=symbol, current_price=current_price)

        # RSI 매핑
        if ind.rsi_14 is not None:
            result.rsi_14 = ind.rsi_14
            if ind.rsi_14 >= 70:
                result.rsi_signal = "과매수 (매도 신호)"
            elif ind.rsi_14 <= 30:
                result.rsi_signal = "과매도 (매수 신호)"
            else:
                result.rsi_signal = "중립"

        # MACD 매핑
        if ind.macd_line is not None:
            result.macd = ind.macd_line
            result.macd_signal = ind.macd_signal
            result.macd_histogram = ind.macd_histogram
            if ind.macd_histogram and ind.macd_histogram > 0:
                result.macd_trend = "상승 추세"
            elif ind.macd_histogram and ind.macd_histogram < 0:
                result.macd_trend = "하락 추세"
            else:
                result.macd_trend = "추세 전환 중"

        # 볼린저 밴드 매핑
        if ind.bb_middle > 0:
            result.bb_upper = ind.bb_upper
            result.bb_middle = ind.bb_middle
            result.bb_lower = ind.bb_lower
            if current_price >= ind.bb_upper:
                result.bb_position = "상단 돌파 (과매수 주의)"
            elif current_price <= ind.bb_lower:
                result.bb_position = "하단 근접 (반등 가능)"
            else:
                result.bb_position = "밴드 내 움직임"

        # 이동평균 매핑
        result.ma_5 = ind.ma_5 or None
        result.ma_20 = ind.ma_20 or None
        result.ma_60 = ind.ma_60 or None
        if ind.ma_5 and ind.ma_20 and ind.ma_60:
            if ind.ma_5 > ind.ma_20 > ind.ma_60:
                result.ma_trend = "정배열 (상승 추세)"
            elif ind.ma_5 < ind.ma_20 < ind.ma_60:
                result.ma_trend = "역배열 (하락 추세)"
            else:
                result.ma_trend = "혼조세"

        # 거래량 매핑
        if ind.v20 > 0:
            result.volume_avg_20 = int(ind.v20)
            result.volume_ratio = round(ind.volume_shock, 2) if ind.volume_shock else None

        # 종합 점수
        result.technical_score = self._calculate_score(result)

        return result

    def _calculate_score(self, result: TechnicalAnalysisResult) -> int:
        """종합 기술적 점수 계산 (1-10)"""
        score = 5

        if result.rsi_14:
            if result.rsi_14 <= 30:
                score += 2
            elif result.rsi_14 >= 70:
                score -= 2
            elif 40 <= result.rsi_14 <= 60:
                score += 1

        if result.macd_histogram:
            if result.macd_histogram > 0:
                score += 1
            else:
                score -= 1

        if result.bb_position:
            if "하단" in result.bb_position:
                score += 1
            elif "상단" in result.bb_position:
                score -= 1

        if result.ma_trend:
            if "정배열" in result.ma_trend:
                score += 1
            elif "역배열" in result.ma_trend:
                score -= 1

        if result.volume_ratio:
            if result.volume_ratio >= 2.0:
                score += 1

        return max(1, min(10, score))


# 싱글톤 인스턴스
technical_calculator = TechnicalIndicatorCalculator()

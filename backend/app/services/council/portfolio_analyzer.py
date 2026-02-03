"""
포트폴리오 분석 및 SELL 시그널 생성

보유 종목의 기술적/펀더멘털 분석을 통해 SELL 시그널 생성
- 손절/익절 조건 모니터링
- 기술적 지표 악화 감지
- 뉴스 기반 리스크 평가
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class PortfolioPosition:
    """보유 포지션"""
    symbol: str
    company_name: str
    quantity: int
    avg_price: int              # 평균 매입가
    current_price: int          # 현재가
    market_value: int           # 평가금액
    profit_loss: int            # 평가손익
    profit_loss_rate: float     # 수익률 (%)
    holding_days: int           # 보유 일수
    portfolio_weight: float     # 포트폴리오 비중 (%)


@dataclass
class SellSignalReason:
    """매도 시그널 이유"""
    reason_type: str           # stop_loss, take_profit, technical, fundamental, news
    description: str
    urgency: str               # low, medium, high, critical
    confidence: float          # 0-1


@dataclass
class PortfolioSellCandidate:
    """매도 후보 종목"""
    position: PortfolioPosition
    reasons: List[SellSignalReason]
    total_score: float         # 종합 점수 (높을수록 매도 권장)
    suggested_action: str      # SELL, PARTIAL_SELL, HOLD, WATCH


class PortfolioAnalyzer:
    """포트폴리오 분석기"""

    # 기본 설정
    STOP_LOSS_THRESHOLD = -5.0      # 손절 기준 (-5%)
    TAKE_PROFIT_THRESHOLD = 20.0    # 익절 기준 (+20%)
    TRAILING_STOP_RATE = 0.7        # 트레일링 스탑 (고점 대비 30% 하락)

    MAX_HOLDING_DAYS = 90           # 최대 보유 기간 (일)
    MAX_PORTFOLIO_WEIGHT = 30.0     # 최대 포트폴리오 비중 (%)

    def __init__(self):
        self._highest_prices: Dict[str, int] = {}  # 종목별 최고가 기록

    def update_highest_price(self, symbol: str, price: int):
        """최고가 업데이트"""
        current_highest = self._highest_prices.get(symbol, 0)
        if price > current_highest:
            self._highest_prices[symbol] = price
            logger.debug(f"[{symbol}] 최고가 갱신: {price:,}원")

    def check_stop_loss(self, position: PortfolioPosition) -> Optional[SellSignalReason]:
        """손절 조건 체크"""
        if position.profit_loss_rate <= self.STOP_LOSS_THRESHOLD:
            return SellSignalReason(
                reason_type="stop_loss",
                description=f"손절선 도달 (수익률: {position.profit_loss_rate:.1f}%)",
                urgency="critical",
                confidence=0.95,
            )
        return None

    def check_take_profit(self, position: PortfolioPosition) -> Optional[SellSignalReason]:
        """익절 조건 체크"""
        if position.profit_loss_rate >= self.TAKE_PROFIT_THRESHOLD:
            return SellSignalReason(
                reason_type="take_profit",
                description=f"익절 목표 도달 (수익률: {position.profit_loss_rate:.1f}%)",
                urgency="medium",
                confidence=0.85,
            )
        return None

    def check_trailing_stop(self, position: PortfolioPosition) -> Optional[SellSignalReason]:
        """트레일링 스탑 체크"""
        highest = self._highest_prices.get(position.symbol, position.avg_price)

        if highest > position.avg_price:  # 수익 구간에서만
            drop_from_high = (highest - position.current_price) / highest * 100

            if drop_from_high >= (1 - self.TRAILING_STOP_RATE) * 100:
                return SellSignalReason(
                    reason_type="trailing_stop",
                    description=f"고점 대비 {drop_from_high:.1f}% 하락 (고점: {highest:,}원)",
                    urgency="high",
                    confidence=0.80,
                )
        return None

    def check_holding_period(self, position: PortfolioPosition) -> Optional[SellSignalReason]:
        """보유 기간 체크"""
        if position.holding_days >= self.MAX_HOLDING_DAYS:
            return SellSignalReason(
                reason_type="holding_period",
                description=f"장기 보유 ({position.holding_days}일) - 재검토 필요",
                urgency="low",
                confidence=0.50,
            )
        return None

    def check_overweight(self, position: PortfolioPosition) -> Optional[SellSignalReason]:
        """과대 비중 체크"""
        if position.portfolio_weight >= self.MAX_PORTFOLIO_WEIGHT:
            return SellSignalReason(
                reason_type="overweight",
                description=f"포트폴리오 비중 과다 ({position.portfolio_weight:.1f}%)",
                urgency="medium",
                confidence=0.70,
            )
        return None

    async def check_technical_deterioration(
        self,
        position: PortfolioPosition,
        technical_data: Optional[dict] = None
    ) -> Optional[SellSignalReason]:
        """기술적 지표 악화 체크"""
        if not technical_data:
            return None

        reasons = []

        # RSI 과매수 이후 하락 전환
        rsi = technical_data.get("rsi_14")
        if rsi and rsi < 30 and position.profit_loss_rate < 0:
            reasons.append(f"RSI 과매도 진입({rsi:.1f})")

        # MACD 데드크로스
        macd = technical_data.get("macd")
        macd_signal = technical_data.get("macd_signal")
        if macd and macd_signal and macd < macd_signal:
            if macd < 0:  # 음의 영역에서 데드크로스
                reasons.append("MACD 데드크로스 (음의 영역)")

        # 볼린저밴드 하단 돌파
        bb_lower = technical_data.get("bb_lower")
        if bb_lower and position.current_price < bb_lower:
            reasons.append(f"볼린저밴드 하단 돌파 (하단: {bb_lower:,}원)")

        # 이동평균선 하향 이탈
        ma_20 = technical_data.get("ma_20")
        ma_60 = technical_data.get("ma_60")
        if ma_20 and ma_60:
            if position.current_price < ma_20 < ma_60:
                reasons.append("20일선 < 60일선 (하락 추세)")

        if reasons:
            return SellSignalReason(
                reason_type="technical",
                description=", ".join(reasons),
                urgency="medium",
                confidence=0.65,
            )
        return None

    def analyze_position(
        self,
        position: PortfolioPosition,
        technical_data: Optional[dict] = None,
        news_sentiment: Optional[float] = None
    ) -> PortfolioSellCandidate:
        """개별 포지션 분석"""

        # 최고가 업데이트
        self.update_highest_price(position.symbol, position.current_price)

        reasons: List[SellSignalReason] = []

        # 각종 체크
        stop_loss = self.check_stop_loss(position)
        if stop_loss:
            reasons.append(stop_loss)

        take_profit = self.check_take_profit(position)
        if take_profit:
            reasons.append(take_profit)

        trailing_stop = self.check_trailing_stop(position)
        if trailing_stop:
            reasons.append(trailing_stop)

        holding_period = self.check_holding_period(position)
        if holding_period:
            reasons.append(holding_period)

        overweight = self.check_overweight(position)
        if overweight:
            reasons.append(overweight)

        # 뉴스 감성 체크
        if news_sentiment is not None and news_sentiment < 0.3:  # 부정적
            reasons.append(SellSignalReason(
                reason_type="news",
                description=f"부정적 뉴스 감성 (점수: {news_sentiment:.1%})",
                urgency="medium",
                confidence=0.60,
            ))

        # 종합 점수 계산
        total_score = self._calculate_sell_score(reasons)

        # 행동 결정
        if total_score >= 8.0:
            action = "SELL"
        elif total_score >= 5.0:
            action = "PARTIAL_SELL"
        elif total_score >= 3.0:
            action = "WATCH"
        else:
            action = "HOLD"

        return PortfolioSellCandidate(
            position=position,
            reasons=reasons,
            total_score=total_score,
            suggested_action=action,
        )

    def _calculate_sell_score(self, reasons: List[SellSignalReason]) -> float:
        """매도 점수 계산 (0-10)"""
        if not reasons:
            return 0.0

        urgency_weights = {
            "critical": 3.0,
            "high": 2.0,
            "medium": 1.0,
            "low": 0.5,
        }

        total_score = 0.0
        for reason in reasons:
            weight = urgency_weights.get(reason.urgency, 1.0)
            total_score += weight * reason.confidence * 2  # 스케일링

        return min(10.0, total_score)

    async def analyze_portfolio(
        self,
        positions: List[PortfolioPosition],
        technical_data_map: Optional[Dict[str, dict]] = None,
        news_sentiment_map: Optional[Dict[str, float]] = None,
    ) -> List[PortfolioSellCandidate]:
        """전체 포트폴리오 분석"""
        technical_data_map = technical_data_map or {}
        news_sentiment_map = news_sentiment_map or {}

        candidates = []
        for position in positions:
            technical_data = technical_data_map.get(position.symbol)
            news_sentiment = news_sentiment_map.get(position.symbol)

            candidate = self.analyze_position(
                position=position,
                technical_data=technical_data,
                news_sentiment=news_sentiment,
            )

            # HOLD가 아닌 것만 추가
            if candidate.suggested_action != "HOLD":
                candidates.append(candidate)

        # 점수 순 정렬
        candidates.sort(key=lambda x: x.total_score, reverse=True)

        return candidates

    def get_sell_recommendations(
        self,
        candidates: List[PortfolioSellCandidate],
        max_recommendations: int = 5
    ) -> List[dict]:
        """매도 추천 목록 생성"""
        recommendations = []

        for candidate in candidates[:max_recommendations]:
            if candidate.suggested_action in ["SELL", "PARTIAL_SELL"]:
                recommendations.append({
                    "symbol": candidate.position.symbol,
                    "company_name": candidate.position.company_name,
                    "action": candidate.suggested_action,
                    "score": candidate.total_score,
                    "current_price": candidate.position.current_price,
                    "profit_loss_rate": candidate.position.profit_loss_rate,
                    "reasons": [
                        {
                            "type": r.reason_type,
                            "description": r.description,
                            "urgency": r.urgency,
                        }
                        for r in candidate.reasons
                    ],
                })

        return recommendations


# 싱글톤 인스턴스
portfolio_analyzer = PortfolioAnalyzer()

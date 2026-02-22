"""
퀀트 시그널 데이터 모델

주랭 채널 분석 기반 42개 트리거, 50+ 지표 데이터 구조
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
import uuid


class SignalAction(str, Enum):
    """시그널 행동"""
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    HOLD = "hold"
    SELL = "sell"
    STRONG_SELL = "strong_sell"


class SignalStrength(str, Enum):
    """시그널 강도"""
    VERY_STRONG = "very_strong"
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    NONE = "none"


class TriggerSignal(str, Enum):
    """트리거 시그널 방향"""
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


@dataclass
class IndicatorData:
    """종목별 퀀트 지표 결과"""
    symbol: str
    current_price: int = 0
    data_count: int = 0  # 일봉 데이터 수

    # 거래대금 비율 (Trading Value)
    tv5: float = 0.0           # 5일 평균 거래대금
    tv20: float = 0.0          # 20일 평균 거래대금
    tv5_20_ratio: float = 0.0  # TV5/TV20
    tv_spike: float = 0.0      # 당일거래대금 / 20일평균거래대금
    today_trading_value: float = 0.0  # 당일 거래대금

    # 거래량 비율 (Volume)
    v5: float = 0.0            # 5일 평균 거래량
    v20: float = 0.0           # 20일 평균 거래량
    v5_20_ratio: float = 0.0   # V5/V20
    volume_shock: float = 0.0  # 당일거래량 / 20일평균거래량
    today_volume: int = 0

    # OBV (On Balance Volume)
    obv_5: float = 0.0
    obv_10: float = 0.0
    obv_23: float = 0.0
    obv_56: float = 0.0

    # AVWAP (Anchored VWAP)
    avwap_20: float = 0.0
    avwap_60: float = 0.0
    avwap_20_pct: float = 0.0   # 현재가 대비 AVWAP20 괴리율(%)
    avwap_60_pct: float = 0.0   # 현재가 대비 AVWAP60 괴리율(%)

    # CMF / CLV
    cmf_20: float = 0.0         # Chaikin Money Flow (20일)
    clv: float = 0.0            # Close Location Value

    # ADX / DI
    adx: float = 0.0
    plus_di: float = 0.0
    minus_di: float = 0.0

    # 볼린저 밴드 / BBWP / TTM Squeeze
    bb_upper: float = 0.0
    bb_middle: float = 0.0
    bb_lower: float = 0.0
    bb_width: float = 0.0       # 볼린저 밴드 폭
    bbwp: float = 0.0           # 볼린저 밴드 폭 백분위 (0~100)
    keltner_upper: float = 0.0
    keltner_lower: float = 0.0
    ttm_squeeze: bool = False   # 볼린저 < 켈트너 여부

    # ATR / MFI
    atr: float = 0.0
    atr_pct: float = 0.0        # ATR / 현재가 (%)
    mfi_14: float = 0.0         # Money Flow Index

    # UDVR / RVOL
    udvr_60: float = 0.0        # 상승일거래량/하락일거래량 (60일)
    rvol_20: float = 0.0        # 당일거래량 / 20일평균
    rvol_50: float = 0.0        # 당일거래량 / 50일평균

    # 52주 위치
    high_52w: int = 0
    low_52w: int = 0
    position_52w: float = 0.0   # (현재가 - 52주저가) / (52주고가 - 52주저가) * 100

    # 이동평균
    ma_5: float = 0.0
    ma_20: float = 0.0
    ma_60: float = 0.0
    ma_120: float = 0.0

    # 추가 메타
    calculated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "current_price": self.current_price,
            "data_count": self.data_count,
            "trading_value": {
                "tv5": round(self.tv5, 0),
                "tv20": round(self.tv20, 0),
                "tv5_20_ratio": round(self.tv5_20_ratio, 2),
                "tv_spike": round(self.tv_spike, 2),
                "today": round(self.today_trading_value, 0),
            },
            "volume": {
                "v5": round(self.v5, 0),
                "v20": round(self.v20, 0),
                "v5_20_ratio": round(self.v5_20_ratio, 2),
                "volume_shock": round(self.volume_shock, 2),
                "today": self.today_volume,
            },
            "obv": {
                "obv_5": round(self.obv_5, 0),
                "obv_10": round(self.obv_10, 0),
                "obv_23": round(self.obv_23, 0),
                "obv_56": round(self.obv_56, 0),
            },
            "avwap": {
                "avwap_20": round(self.avwap_20, 0),
                "avwap_60": round(self.avwap_60, 0),
                "avwap_20_pct": round(self.avwap_20_pct, 2),
                "avwap_60_pct": round(self.avwap_60_pct, 2),
            },
            "money_flow": {
                "cmf_20": round(self.cmf_20, 4),
                "clv": round(self.clv, 4),
                "mfi_14": round(self.mfi_14, 2),
            },
            "trend": {
                "adx": round(self.adx, 2),
                "plus_di": round(self.plus_di, 2),
                "minus_di": round(self.minus_di, 2),
            },
            "volatility": {
                "bb_upper": round(self.bb_upper, 0),
                "bb_middle": round(self.bb_middle, 0),
                "bb_lower": round(self.bb_lower, 0),
                "bb_width": round(self.bb_width, 4),
                "bbwp": round(self.bbwp, 2),
                "ttm_squeeze": self.ttm_squeeze,
                "atr": round(self.atr, 0),
                "atr_pct": round(self.atr_pct, 2),
            },
            "supply_demand": {
                "udvr_60": round(self.udvr_60, 2),
                "rvol_20": round(self.rvol_20, 2),
                "rvol_50": round(self.rvol_50, 2),
            },
            "position": {
                "high_52w": self.high_52w,
                "low_52w": self.low_52w,
                "position_52w": round(self.position_52w, 2),
            },
            "moving_averages": {
                "ma_5": round(self.ma_5, 0),
                "ma_20": round(self.ma_20, 0),
                "ma_60": round(self.ma_60, 0),
                "ma_120": round(self.ma_120, 0),
            },
            "calculated_at": self.calculated_at.isoformat(),
        }


@dataclass
class TriggerResult:
    """개별 트리거 평가 결과"""
    trigger_id: str            # T-01 ~ T-42
    name: str                  # 트리거명
    signal: TriggerSignal = TriggerSignal.NEUTRAL
    strength: SignalStrength = SignalStrength.NONE
    score: int = 0             # 0~10 점수
    details: str = ""          # 판정 근거
    values: Optional[Dict[str, Any]] = None  # 참고 수치

    def to_dict(self) -> dict:
        return {
            "trigger_id": self.trigger_id,
            "name": self.name,
            "signal": self.signal.value,
            "strength": self.strength.value,
            "score": self.score,
            "details": self.details,
            "values": self.values,
        }


@dataclass
class SignalResult:
    """종목별 종합 시그널"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    symbol: str = ""
    company_name: str = ""

    # 지표 데이터
    indicators: Optional[IndicatorData] = None

    # 트리거 결과
    triggers: List[TriggerResult] = field(default_factory=list)

    # 종합 판정
    composite_score: int = 0     # 1-100 종합 점수
    bullish_count: int = 0       # 매수 트리거 수
    bearish_count: int = 0       # 매도 트리거 수
    neutral_count: int = 0       # 중립 트리거 수
    action: SignalAction = SignalAction.HOLD

    # 메타
    scanned_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "symbol": self.symbol,
            "company_name": self.company_name,
            "indicators": self.indicators.to_dict() if self.indicators else None,
            "triggers": [t.to_dict() for t in self.triggers],
            "composite_score": self.composite_score,
            "bullish_count": self.bullish_count,
            "bearish_count": self.bearish_count,
            "neutral_count": self.neutral_count,
            "action": self.action.value,
            "scanned_at": self.scanned_at.isoformat(),
        }

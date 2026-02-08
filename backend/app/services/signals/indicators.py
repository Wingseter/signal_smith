"""
퀀트 지표 계산기

주랭 채널 분석 기반 50+ 지표 계산
입력: 키움 일봉 데이터 List[Dict] (date, open, high, low, close, volume)
"""

import logging
from typing import List, Dict, Any, Optional

from .models import IndicatorData

logger = logging.getLogger(__name__)


class QuantIndicatorCalculator:
    """퀀트 지표 계산기"""

    def calculate_all(self, symbol: str, daily_prices: List[Dict[str, Any]]) -> IndicatorData:
        """전체 지표 계산

        Args:
            symbol: 종목코드
            daily_prices: 일봉 데이터 (최신순 정렬)

        Returns:
            IndicatorData: 전체 지표 계산 결과
        """
        if not daily_prices:
            logger.warning(f"[{symbol}] 일봉 데이터 없음")
            return IndicatorData(symbol=symbol)

        # 오래된순 정렬 (계산 편의)
        prices = list(reversed(daily_prices))
        data = IndicatorData(symbol=symbol, data_count=len(prices))

        if not prices:
            return data

        # 현재가 설정
        latest = prices[-1]
        data.current_price = latest.get("close", 0)
        data.today_volume = latest.get("volume", 0)

        # 거래대금 계산 (close * volume 근사)
        trading_values = [
            p.get("close", 0) * p.get("volume", 0) for p in prices
        ]
        data.today_trading_value = trading_values[-1] if trading_values else 0

        closes = [p.get("close", 0) for p in prices]
        highs = [p.get("high", 0) for p in prices]
        lows = [p.get("low", 0) for p in prices]
        volumes = [p.get("volume", 0) for p in prices]

        # 각 지표 계산
        self._calc_trading_value_ratios(data, trading_values)
        self._calc_volume_ratios(data, volumes)
        self._calc_obv(data, closes, volumes)
        self._calc_avwap(data, prices)
        self._calc_cmf_clv(data, prices)
        self._calc_adx(data, highs, lows, closes)
        self._calc_bollinger_bbwp_ttm(data, closes)
        self._calc_atr(data, highs, lows, closes)
        self._calc_mfi(data, highs, lows, closes, volumes)
        self._calc_udvr(data, closes, volumes)
        self._calc_rvol(data, volumes)
        self._calc_52w_position(data, highs, lows, closes)
        self._calc_moving_averages(data, closes)

        return data

    # ========================
    # 거래대금 비율
    # ========================

    def _calc_trading_value_ratios(self, data: IndicatorData, tvs: List[float]):
        """TV5/20, TV Spike 계산"""
        n = len(tvs)
        if n < 5:
            return

        data.tv5 = sum(tvs[-5:]) / 5

        if n >= 20:
            data.tv20 = sum(tvs[-20:]) / 20
            if data.tv20 > 0:
                data.tv5_20_ratio = data.tv5 / data.tv20
                data.tv_spike = tvs[-1] / data.tv20 if data.tv20 > 0 else 0
        else:
            data.tv20 = sum(tvs) / n
            if data.tv20 > 0:
                data.tv5_20_ratio = data.tv5 / data.tv20
                data.tv_spike = tvs[-1] / data.tv20

    # ========================
    # 거래량 비율
    # ========================

    def _calc_volume_ratios(self, data: IndicatorData, volumes: List[int]):
        """V5/20, Volume Shock 계산"""
        n = len(volumes)
        if n < 5:
            return

        data.v5 = sum(volumes[-5:]) / 5

        if n >= 20:
            data.v20 = sum(volumes[-20:]) / 20
            if data.v20 > 0:
                data.v5_20_ratio = data.v5 / data.v20
                data.volume_shock = volumes[-1] / data.v20
        else:
            data.v20 = sum(volumes) / n
            if data.v20 > 0:
                data.v5_20_ratio = data.v5 / data.v20
                data.volume_shock = volumes[-1] / data.v20

    # ========================
    # OBV (On Balance Volume)
    # ========================

    def _calc_obv(self, data: IndicatorData, closes: List[float], volumes: List[int]):
        """OBV 5/10/23/56 계산"""
        n = len(closes)
        if n < 2:
            return

        # 전체 OBV 시리즈 계산
        obv_series = [0.0]
        for i in range(1, n):
            if closes[i] > closes[i - 1]:
                obv_series.append(obv_series[-1] + volumes[i])
            elif closes[i] < closes[i - 1]:
                obv_series.append(obv_series[-1] - volumes[i])
            else:
                obv_series.append(obv_series[-1])

        # 기간별 OBV (기간 내 누적)
        def period_obv(period: int) -> float:
            if n < period + 1:
                return 0.0
            obv = 0.0
            start = n - period
            for i in range(start, n):
                if closes[i] > closes[i - 1]:
                    obv += volumes[i]
                elif closes[i] < closes[i - 1]:
                    obv -= volumes[i]
            return obv

        data.obv_5 = period_obv(5)
        data.obv_10 = period_obv(10)
        data.obv_23 = period_obv(23) if n >= 24 else 0.0
        data.obv_56 = period_obv(56) if n >= 57 else 0.0

    # ========================
    # AVWAP (Anchored VWAP)
    # ========================

    def _calc_avwap(self, data: IndicatorData, prices: List[Dict[str, Any]]):
        """AVWAP 20/60 계산"""
        n = len(prices)

        def calc_vwap(period: int) -> float:
            if n < period:
                return 0.0
            subset = prices[-period:]
            total_pv = 0.0
            total_v = 0.0
            for p in subset:
                typical = (p.get("high", 0) + p.get("low", 0) + p.get("close", 0)) / 3
                vol = p.get("volume", 0)
                total_pv += typical * vol
                total_v += vol
            return total_pv / total_v if total_v > 0 else 0.0

        data.avwap_20 = calc_vwap(20)
        data.avwap_60 = calc_vwap(60) if n >= 60 else calc_vwap(n)

        # 현재가 대비 괴리율
        if data.current_price > 0:
            if data.avwap_20 > 0:
                data.avwap_20_pct = ((data.current_price - data.avwap_20) / data.avwap_20) * 100
            if data.avwap_60 > 0:
                data.avwap_60_pct = ((data.current_price - data.avwap_60) / data.avwap_60) * 100

    # ========================
    # CMF / CLV
    # ========================

    def _calc_cmf_clv(self, data: IndicatorData, prices: List[Dict[str, Any]]):
        """Chaikin Money Flow (20일) 및 CLV 계산"""
        n = len(prices)
        if n < 1:
            return

        # CLV 계산 (Close Location Value)
        latest = prices[-1]
        h = latest.get("high", 0)
        l = latest.get("low", 0)
        c = latest.get("close", 0)
        if h != l:
            data.clv = ((c - l) - (h - c)) / (h - l)
        else:
            data.clv = 0.0

        # CMF 20 계산
        period = min(20, n)
        subset = prices[-period:]
        mfv_sum = 0.0
        vol_sum = 0.0
        for p in subset:
            h = p.get("high", 0)
            l = p.get("low", 0)
            c = p.get("close", 0)
            v = p.get("volume", 0)
            if h != l:
                mfm = ((c - l) - (h - c)) / (h - l)
            else:
                mfm = 0.0
            mfv_sum += mfm * v
            vol_sum += v

        data.cmf_20 = mfv_sum / vol_sum if vol_sum > 0 else 0.0

    # ========================
    # ADX / +DI / -DI
    # ========================

    def _calc_adx(self, data: IndicatorData, highs: List[float], lows: List[float], closes: List[float]):
        """ADX, +DI, -DI 계산 (14일)"""
        n = len(closes)
        period = 14
        if n < period + 1:
            return

        # True Range, +DM, -DM 계산
        tr_list = []
        plus_dm_list = []
        minus_dm_list = []

        for i in range(1, n):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1])
            )
            tr_list.append(tr)

            up_move = highs[i] - highs[i - 1]
            down_move = lows[i - 1] - lows[i]

            plus_dm = up_move if (up_move > down_move and up_move > 0) else 0
            minus_dm = down_move if (down_move > up_move and down_move > 0) else 0

            plus_dm_list.append(plus_dm)
            minus_dm_list.append(minus_dm)

        # Wilder's Smoothing
        def wilder_smooth(values: List[float], p: int) -> List[float]:
            if len(values) < p:
                return []
            smoothed = [sum(values[:p])]
            for i in range(p, len(values)):
                smoothed.append(smoothed[-1] - smoothed[-1] / p + values[i])
            return smoothed

        atr_smoothed = wilder_smooth(tr_list, period)
        plus_dm_smoothed = wilder_smooth(plus_dm_list, period)
        minus_dm_smoothed = wilder_smooth(minus_dm_list, period)

        if not atr_smoothed or not plus_dm_smoothed or not minus_dm_smoothed:
            return

        # +DI, -DI
        plus_di_list = []
        minus_di_list = []
        dx_list = []

        for i in range(len(atr_smoothed)):
            atr_val = atr_smoothed[i]
            if atr_val > 0:
                pdi = (plus_dm_smoothed[i] / atr_val) * 100
                mdi = (minus_dm_smoothed[i] / atr_val) * 100
            else:
                pdi = 0.0
                mdi = 0.0
            plus_di_list.append(pdi)
            minus_di_list.append(mdi)

            di_sum = pdi + mdi
            if di_sum > 0:
                dx_list.append(abs(pdi - mdi) / di_sum * 100)
            else:
                dx_list.append(0.0)

        # ADX = DX의 Wilder 이동평균
        adx_smoothed = wilder_smooth(dx_list, period)

        if adx_smoothed:
            data.adx = adx_smoothed[-1]
        if plus_di_list:
            data.plus_di = plus_di_list[-1]
        if minus_di_list:
            data.minus_di = minus_di_list[-1]

    # ========================
    # 볼린저밴드, BBWP, TTM Squeeze
    # ========================

    def _calc_bollinger_bbwp_ttm(self, data: IndicatorData, closes: List[float]):
        """볼린저밴드, BBWP(폭 백분위), TTM Squeeze 계산"""
        n = len(closes)
        bb_period = 20
        bb_std_mult = 2.0

        if n < bb_period:
            return

        # 볼린저 밴드 계산
        recent = closes[-bb_period:]
        sma = sum(recent) / bb_period
        variance = sum((x - sma) ** 2 for x in recent) / bb_period
        std = variance ** 0.5

        data.bb_middle = sma
        data.bb_upper = sma + bb_std_mult * std
        data.bb_lower = sma - bb_std_mult * std
        data.bb_width = (data.bb_upper - data.bb_lower) / data.bb_middle if data.bb_middle > 0 else 0

        # BBWP 계산: 현재 BB 폭이 과거 252일(1년) BB 폭 중 몇 % 위치인지
        lookback = min(252, n - bb_period)
        if lookback > 0:
            bb_widths = []
            for i in range(n - lookback, n + 1):
                if i >= bb_period:
                    window = closes[i - bb_period:i]
                    w_sma = sum(window) / bb_period
                    w_var = sum((x - w_sma) ** 2 for x in window) / bb_period
                    w_std = w_var ** 0.5
                    w_upper = w_sma + bb_std_mult * w_std
                    w_lower = w_sma - bb_std_mult * w_std
                    w_width = (w_upper - w_lower) / w_sma if w_sma > 0 else 0
                    bb_widths.append(w_width)

            if bb_widths:
                current_width = bb_widths[-1]
                below_count = sum(1 for w in bb_widths if w < current_width)
                data.bbwp = (below_count / len(bb_widths)) * 100

        # TTM Squeeze: 볼린저 밴드가 켈트너 채널 안에 들어왔는지
        # 켈트너 채널 = 20 EMA +/- 1.5 * ATR(10)
        if n >= bb_period:
            ema_20 = self._ema(closes, 20)
            if ema_20 is not None:
                # 간단한 ATR(10) 계산
                atr_10 = data.atr  # ATR은 이미 14일로 계산됨, 근사 사용
                if atr_10 == 0 and n > 1:
                    # ATR이 아직 계산 안 됐으면 직접 계산
                    trs = []
                    for i in range(max(1, n - 10), n):
                        tr = closes[i] - closes[i - 1]  # 간단 근사
                        trs.append(abs(tr))
                    atr_10 = sum(trs) / len(trs) if trs else 0

                keltner_mult = 1.5
                data.keltner_upper = ema_20 + keltner_mult * atr_10
                data.keltner_lower = ema_20 - keltner_mult * atr_10

                # Squeeze: BB가 Keltner 안에 있으면 True
                data.ttm_squeeze = (
                    data.bb_lower > data.keltner_lower and
                    data.bb_upper < data.keltner_upper
                )

    # ========================
    # ATR (Average True Range)
    # ========================

    def _calc_atr(self, data: IndicatorData, highs: List[float], lows: List[float], closes: List[float]):
        """ATR(14) 계산"""
        n = len(closes)
        period = 14
        if n < period + 1:
            return

        tr_list = []
        for i in range(1, n):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1])
            )
            tr_list.append(tr)

        # Wilder's Moving Average
        atr = sum(tr_list[:period]) / period
        for i in range(period, len(tr_list)):
            atr = (atr * (period - 1) + tr_list[i]) / period

        data.atr = atr
        data.atr_pct = (atr / data.current_price * 100) if data.current_price > 0 else 0

    # ========================
    # MFI (Money Flow Index)
    # ========================

    def _calc_mfi(self, data: IndicatorData, highs: List[float], lows: List[float],
                  closes: List[float], volumes: List[int]):
        """MFI(14) 계산"""
        n = len(closes)
        period = 14
        if n < period + 1:
            return

        typical_prices = [(highs[i] + lows[i] + closes[i]) / 3 for i in range(n)]

        pos_flow = 0.0
        neg_flow = 0.0

        start = max(1, n - period)
        for i in range(start, n):
            raw_flow = typical_prices[i] * volumes[i]
            if typical_prices[i] > typical_prices[i - 1]:
                pos_flow += raw_flow
            elif typical_prices[i] < typical_prices[i - 1]:
                neg_flow += raw_flow

        if neg_flow > 0:
            mfi_ratio = pos_flow / neg_flow
            data.mfi_14 = 100 - (100 / (1 + mfi_ratio))
        elif pos_flow > 0:
            data.mfi_14 = 100.0
        else:
            data.mfi_14 = 50.0

    # ========================
    # UDVR (Up/Down Volume Ratio)
    # ========================

    def _calc_udvr(self, data: IndicatorData, closes: List[float], volumes: List[int]):
        """상승일거래량/하락일거래량 비율 (60일)"""
        n = len(closes)
        period = min(60, n - 1)
        if period < 1:
            return

        up_vol = 0
        down_vol = 0

        start = n - period
        for i in range(start, n):
            if closes[i] > closes[i - 1]:
                up_vol += volumes[i]
            elif closes[i] < closes[i - 1]:
                down_vol += volumes[i]

        data.udvr_60 = up_vol / down_vol if down_vol > 0 else (10.0 if up_vol > 0 else 1.0)

    # ========================
    # RVOL (Relative Volume)
    # ========================

    def _calc_rvol(self, data: IndicatorData, volumes: List[int]):
        """상대 거래량 20/50"""
        n = len(volumes)
        if n >= 20:
            avg_20 = sum(volumes[-20:]) / 20
            data.rvol_20 = volumes[-1] / avg_20 if avg_20 > 0 else 0
        if n >= 50:
            avg_50 = sum(volumes[-50:]) / 50
            data.rvol_50 = volumes[-1] / avg_50 if avg_50 > 0 else 0

    # ========================
    # 52주 위치
    # ========================

    def _calc_52w_position(self, data: IndicatorData, highs: List[float], lows: List[float],
                           closes: List[float]):
        """52주 고가/저가 대비 현재 위치"""
        n = len(closes)
        period = min(252, n)  # 약 1년 거래일

        recent_highs = highs[-period:]
        recent_lows = lows[-period:]

        data.high_52w = int(max(recent_highs)) if recent_highs else 0
        data.low_52w = int(min(l for l in recent_lows if l > 0)) if recent_lows else 0

        price_range = data.high_52w - data.low_52w
        if price_range > 0:
            data.position_52w = ((data.current_price - data.low_52w) / price_range) * 100

    # ========================
    # 이동평균
    # ========================

    def _calc_moving_averages(self, data: IndicatorData, closes: List[float]):
        """이동평균선 5/20/60/120"""
        n = len(closes)
        if n >= 5:
            data.ma_5 = sum(closes[-5:]) / 5
        if n >= 20:
            data.ma_20 = sum(closes[-20:]) / 20
        if n >= 60:
            data.ma_60 = sum(closes[-60:]) / 60
        if n >= 120:
            data.ma_120 = sum(closes[-120:]) / 120

    # ========================
    # 유틸리티
    # ========================

    def _ema(self, values: List[float], period: int) -> Optional[float]:
        """지수이동평균 계산"""
        n = len(values)
        if n < period:
            return None

        multiplier = 2 / (period + 1)
        ema = sum(values[:period]) / period

        for i in range(period, n):
            ema = (values[i] - ema) * multiplier + ema

        return ema


# 싱글톤 인스턴스
quant_calculator = QuantIndicatorCalculator()

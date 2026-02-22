"""
퀀트 트리거 평가기

주랭 채널 분석 기반 42개 트리거 평가
IndicatorData를 입력받아 트리거 판정
"""

import logging
from typing import List

from .models import (
    IndicatorData, TriggerResult,
    TriggerSignal, SignalStrength, SignalAction,
)

logger = logging.getLogger(__name__)


class TriggerEvaluator:
    """트리거 평가기"""

    def evaluate_all(self, ind: IndicatorData) -> List[TriggerResult]:
        """전체 트리거 평가

        Args:
            ind: 지표 데이터

        Returns:
            트리거 결과 리스트
        """
        results = []

        # ★★★★★ 1차 핵심 트리거 (6개)
        results.append(self._t01_tv_accumulation(ind))
        results.append(self._t02_tv_spike(ind))
        results.append(self._t03_kosdaq_tv_breakout(ind))
        results.append(self._t09_obv_alignment(ind))
        results.append(self._t14_avwap_position(ind))
        results.append(self._t20_bbwp_ttm_squeeze(ind))

        # ★★★★☆ 2차 트리거 (16개)
        results.append(self._t04_tv_trend(ind))
        results.append(self._t05_volume_surge(ind))
        results.append(self._t06_volume_breakout(ind))
        results.append(self._t07_volume_dry(ind))
        results.append(self._t08_volume_divergence(ind))
        results.append(self._t10_obv_divergence(ind))
        results.append(self._t11_obv_breakout(ind))
        results.append(self._t12_cmf_signal(ind))
        results.append(self._t13_clv_signal(ind))
        results.append(self._t15_avwap_cross(ind))
        results.append(self._t16_cmf_trend(ind))
        results.append(self._t17_mfi_signal(ind))
        results.append(self._t18_adx_trend(ind))
        results.append(self._t19_di_cross(ind))
        results.append(self._t21_bb_squeeze_release(ind))
        results.append(self._t22_accumulation_pattern(ind))

        # ★★★☆☆ 3차 트리거 (20개)
        results.append(self._t23_udvr_signal(ind))
        results.append(self._t24_rvol_signal(ind))
        results.append(self._t25_52w_position(ind))
        results.append(self._t26_ma_alignment(ind))
        results.append(self._t27_ma_cross(ind))
        results.append(self._t28_price_momentum(ind))
        results.append(self._t29_volatility_contraction(ind))
        results.append(self._t30_breakout_readiness(ind))
        results.append(self._t31_risk_reward(ind))
        results.append(self._t32_trend_strength(ind))
        results.append(self._t33_money_flow_combo(ind))
        results.append(self._t34_supply_demand_balance(ind))
        results.append(self._t35_entry_timing(ind))
        results.append(self._t36_exit_warning(ind))
        results.append(self._t37_consolidation_phase(ind))
        results.append(self._t38_trend_reversal(ind))
        results.append(self._t39_volume_price_confirm(ind))
        results.append(self._t40_institutional_flow(ind))
        results.append(self._t41_composite_buy(ind))
        results.append(self._t42_composite_sell(ind))

        return results

    def calculate_composite_score(self, triggers: List[TriggerResult]) -> int:
        """종합 점수 계산 (1-100)"""
        if not triggers:
            return 50

        total_score = 0
        total_weight = 0

        for t in triggers:
            # 핵심 트리거 가중치 높게
            tier = int(t.trigger_id.split("-")[1])
            if tier <= 3 or tier == 9 or tier == 14 or tier == 20:
                weight = 3  # 1차 핵심
            elif tier <= 22:
                weight = 2  # 2차
            else:
                weight = 1  # 3차

            if t.signal == TriggerSignal.BULLISH:
                total_score += t.score * weight
            elif t.signal == TriggerSignal.BEARISH:
                total_score -= t.score * weight

            total_weight += 10 * weight  # 최대 점수 기준

        if total_weight == 0:
            return 50

        # -100 ~ +100 → 1 ~ 100 변환
        raw = (total_score / total_weight) * 100
        normalized = max(1, min(100, int(50 + raw / 2)))
        return normalized

    def determine_action(self, score: int, triggers: List[TriggerResult]) -> SignalAction:
        """종합 점수로 행동 결정"""
        if score >= 80:
            return SignalAction.STRONG_BUY
        elif score >= 65:
            return SignalAction.BUY
        elif score >= 40:
            return SignalAction.HOLD
        elif score >= 25:
            return SignalAction.SELL
        else:
            return SignalAction.STRONG_SELL

    # ============================================================
    # ★★★★★ 1차 핵심 트리거 (6개)
    # ============================================================

    def _t01_tv_accumulation(self, ind: IndicatorData) -> TriggerResult:
        """T-01: TV5/20 매집 감지 (ratio 1.0~3.5 구간 판정)"""
        ratio = ind.tv5_20_ratio

        if 1.5 <= ratio <= 3.5:
            signal = TriggerSignal.BULLISH
            if ratio >= 2.5:
                strength = SignalStrength.VERY_STRONG
                score = 9
                details = f"강한 매집 신호 (TV5/20={ratio:.2f})"
            elif ratio >= 2.0:
                strength = SignalStrength.STRONG
                score = 7
                details = f"매집 진행 중 (TV5/20={ratio:.2f})"
            else:
                strength = SignalStrength.MODERATE
                score = 5
                details = f"초기 매집 감지 (TV5/20={ratio:.2f})"
        elif ratio > 3.5:
            signal = TriggerSignal.BEARISH
            strength = SignalStrength.MODERATE
            score = 4
            details = f"과열 주의 (TV5/20={ratio:.2f})"
        elif ratio >= 1.0:
            signal = TriggerSignal.NEUTRAL
            strength = SignalStrength.WEAK
            score = 3
            details = f"거래대금 보통 (TV5/20={ratio:.2f})"
        else:
            signal = TriggerSignal.NEUTRAL
            strength = SignalStrength.NONE
            score = 0
            details = f"거래대금 부족 (TV5/20={ratio:.2f})"

        return TriggerResult(
            trigger_id="T-01", name="TV5/20 매집 감지",
            signal=signal, strength=strength, score=score, details=details,
            values={"tv5_20_ratio": round(ratio, 2)},
        )

    def _t02_tv_spike(self, ind: IndicatorData) -> TriggerResult:
        """T-02: 거래대금 스파이크 (5x/10x/50x 단계)"""
        spike = ind.tv_spike

        if spike >= 50:
            signal, strength, score = TriggerSignal.BULLISH, SignalStrength.VERY_STRONG, 10
            details = f"극단적 거래대금 폭발 ({spike:.1f}x)"
        elif spike >= 10:
            signal, strength, score = TriggerSignal.BULLISH, SignalStrength.VERY_STRONG, 9
            details = f"거래대금 대폭발 ({spike:.1f}x)"
        elif spike >= 5:
            signal, strength, score = TriggerSignal.BULLISH, SignalStrength.STRONG, 7
            details = f"거래대금 급증 ({spike:.1f}x)"
        elif spike >= 3:
            signal, strength, score = TriggerSignal.BULLISH, SignalStrength.MODERATE, 5
            details = f"거래대금 증가 ({spike:.1f}x)"
        elif spike >= 1.5:
            signal, strength, score = TriggerSignal.NEUTRAL, SignalStrength.WEAK, 3
            details = f"거래대금 소폭 증가 ({spike:.1f}x)"
        else:
            signal, strength, score = TriggerSignal.NEUTRAL, SignalStrength.NONE, 0
            details = f"거래대금 평이 ({spike:.1f}x)"

        return TriggerResult(
            trigger_id="T-02", name="거래대금 스파이크",
            signal=signal, strength=strength, score=score, details=details,
            values={"tv_spike": round(spike, 2)},
        )

    def _t03_kosdaq_tv_breakout(self, ind: IndicatorData) -> TriggerResult:
        """T-03: 거래대금 1000억 돌파"""
        tv = ind.today_trading_value
        tv_억 = tv / 1_0000_0000  # 억원 단위

        if tv_억 >= 1000:
            signal, strength, score = TriggerSignal.BULLISH, SignalStrength.VERY_STRONG, 9
            details = f"거래대금 {tv_억:.0f}억원 (1000억 돌파)"
        elif tv_억 >= 500:
            signal, strength, score = TriggerSignal.BULLISH, SignalStrength.STRONG, 7
            details = f"거래대금 {tv_억:.0f}억원 (500억 이상)"
        elif tv_억 >= 200:
            signal, strength, score = TriggerSignal.BULLISH, SignalStrength.MODERATE, 5
            details = f"거래대금 {tv_억:.0f}억원 (200억 이상)"
        elif tv_억 >= 50:
            signal, strength, score = TriggerSignal.NEUTRAL, SignalStrength.WEAK, 2
            details = f"거래대금 {tv_억:.0f}억원"
        else:
            signal, strength, score = TriggerSignal.NEUTRAL, SignalStrength.NONE, 0
            details = f"거래대금 {tv_억:.0f}억원 (유동성 부족)"

        return TriggerResult(
            trigger_id="T-03", name="거래대금 돌파",
            signal=signal, strength=strength, score=score, details=details,
            values={"today_tv_억": round(tv_억, 1)},
        )

    def _t09_obv_alignment(self, ind: IndicatorData) -> TriggerResult:
        """T-09: OBV 다중 타임프레임 양수 정렬"""
        obv_values = [ind.obv_5, ind.obv_10, ind.obv_23, ind.obv_56]
        positive_count = sum(1 for v in obv_values if v > 0)

        if positive_count == 4:
            signal, strength, score = TriggerSignal.BULLISH, SignalStrength.VERY_STRONG, 9
            details = "OBV 전 구간 양수 정렬 (ALL POSITIVE)"
        elif positive_count == 3:
            signal, strength, score = TriggerSignal.BULLISH, SignalStrength.STRONG, 7
            details = f"OBV 양수 정렬 ({positive_count}/4)"
        elif positive_count == 2:
            signal, strength, score = TriggerSignal.NEUTRAL, SignalStrength.MODERATE, 4
            details = f"OBV 혼조 ({positive_count}/4)"
        elif positive_count == 1:
            signal, strength, score = TriggerSignal.BEARISH, SignalStrength.MODERATE, 3
            details = f"OBV 음수 우세 ({positive_count}/4)"
        else:
            signal, strength, score = TriggerSignal.BEARISH, SignalStrength.STRONG, 2
            details = "OBV 전 구간 음수 (NEGATIVE)"

        return TriggerResult(
            trigger_id="T-09", name="OBV 다중 타임프레임 정렬",
            signal=signal, strength=strength, score=score, details=details,
            values={"obv_5": ind.obv_5, "obv_10": ind.obv_10,
                    "obv_23": ind.obv_23, "obv_56": ind.obv_56,
                    "positive_count": positive_count},
        )

    def _t14_avwap_position(self, ind: IndicatorData) -> TriggerResult:
        """T-14: AVWAP 매수 위치 판단 (-10%~+10% 구간)"""
        pct_60 = ind.avwap_60_pct

        if -5 <= pct_60 <= 0:
            signal, strength, score = TriggerSignal.BULLISH, SignalStrength.VERY_STRONG, 9
            details = f"AVWAP60 근처 매수 적기 ({pct_60:+.1f}%)"
        elif -10 <= pct_60 < -5:
            signal, strength, score = TriggerSignal.BULLISH, SignalStrength.STRONG, 7
            details = f"AVWAP60 하방 할인 구간 ({pct_60:+.1f}%)"
        elif 0 < pct_60 <= 5:
            signal, strength, score = TriggerSignal.BULLISH, SignalStrength.MODERATE, 5
            details = f"AVWAP60 소폭 상방 ({pct_60:+.1f}%)"
        elif 5 < pct_60 <= 10:
            signal, strength, score = TriggerSignal.NEUTRAL, SignalStrength.WEAK, 3
            details = f"AVWAP60 상방 이탈 주의 ({pct_60:+.1f}%)"
        elif pct_60 > 10:
            signal, strength, score = TriggerSignal.BEARISH, SignalStrength.MODERATE, 4
            details = f"AVWAP60 과이격 ({pct_60:+.1f}%)"
        else:
            signal, strength, score = TriggerSignal.BEARISH, SignalStrength.STRONG, 3
            details = f"AVWAP60 대폭 하방 ({pct_60:+.1f}%)"

        return TriggerResult(
            trigger_id="T-14", name="AVWAP 매수 위치",
            signal=signal, strength=strength, score=score, details=details,
            values={"avwap_60_pct": round(pct_60, 2), "avwap_20_pct": round(ind.avwap_20_pct, 2)},
        )

    def _t20_bbwp_ttm_squeeze(self, ind: IndicatorData) -> TriggerResult:
        """T-20: BBWP + TTM Squeeze 압축 폭발"""
        bbwp = ind.bbwp
        squeeze = ind.ttm_squeeze

        if squeeze and bbwp <= 20:
            signal, strength, score = TriggerSignal.BULLISH, SignalStrength.VERY_STRONG, 10
            details = f"극도 압축 + TTM 스퀴즈 (BBWP={bbwp:.0f}%)"
        elif squeeze and bbwp <= 40:
            signal, strength, score = TriggerSignal.BULLISH, SignalStrength.STRONG, 8
            details = f"TTM 스퀴즈 진행 중 (BBWP={bbwp:.0f}%)"
        elif bbwp <= 20:
            signal, strength, score = TriggerSignal.BULLISH, SignalStrength.STRONG, 7
            details = f"변동성 극도 압축 (BBWP={bbwp:.0f}%)"
        elif bbwp <= 40:
            signal, strength, score = TriggerSignal.NEUTRAL, SignalStrength.MODERATE, 4
            details = f"변동성 낮은 편 (BBWP={bbwp:.0f}%)"
        elif bbwp >= 80:
            signal, strength, score = TriggerSignal.BEARISH, SignalStrength.MODERATE, 3
            details = f"변동성 과대 (BBWP={bbwp:.0f}%)"
        else:
            signal, strength, score = TriggerSignal.NEUTRAL, SignalStrength.NONE, 2
            details = f"변동성 보통 (BBWP={bbwp:.0f}%)"

        return TriggerResult(
            trigger_id="T-20", name="BBWP+TTM 압축 폭발",
            signal=signal, strength=strength, score=score, details=details,
            values={"bbwp": round(bbwp, 1), "ttm_squeeze": squeeze},
        )

    # ============================================================
    # ★★★★☆ 2차 트리거 (16개)
    # ============================================================

    def _t04_tv_trend(self, ind: IndicatorData) -> TriggerResult:
        """T-04: 거래대금 추세"""
        ratio = ind.tv5_20_ratio
        if ratio >= 1.5:
            return TriggerResult("T-04", "거래대금 추세", TriggerSignal.BULLISH,
                                 SignalStrength.MODERATE, 6, f"거래대금 증가 추세 ({ratio:.2f}x)",
                                 {"tv5_20_ratio": round(ratio, 2)})
        elif ratio <= 0.5:
            return TriggerResult("T-04", "거래대금 추세", TriggerSignal.BEARISH,
                                 SignalStrength.MODERATE, 4, f"거래대금 감소 추세 ({ratio:.2f}x)",
                                 {"tv5_20_ratio": round(ratio, 2)})
        return TriggerResult("T-04", "거래대금 추세", TriggerSignal.NEUTRAL,
                             SignalStrength.WEAK, 3, f"거래대금 보합 ({ratio:.2f}x)",
                             {"tv5_20_ratio": round(ratio, 2)})

    def _t05_volume_surge(self, ind: IndicatorData) -> TriggerResult:
        """T-05: 거래량 급증"""
        shock = ind.volume_shock
        if shock >= 5:
            return TriggerResult("T-05", "거래량 급증", TriggerSignal.BULLISH,
                                 SignalStrength.VERY_STRONG, 8, f"거래량 폭발 ({shock:.1f}x)",
                                 {"volume_shock": round(shock, 2)})
        elif shock >= 3:
            return TriggerResult("T-05", "거래량 급증", TriggerSignal.BULLISH,
                                 SignalStrength.STRONG, 6, f"거래량 급증 ({shock:.1f}x)",
                                 {"volume_shock": round(shock, 2)})
        elif shock >= 2:
            return TriggerResult("T-05", "거래량 급증", TriggerSignal.BULLISH,
                                 SignalStrength.MODERATE, 5, f"거래량 증가 ({shock:.1f}x)",
                                 {"volume_shock": round(shock, 2)})
        return TriggerResult("T-05", "거래량 급증", TriggerSignal.NEUTRAL,
                             SignalStrength.NONE, 2, f"거래량 보통 ({shock:.1f}x)",
                             {"volume_shock": round(shock, 2)})

    def _t06_volume_breakout(self, ind: IndicatorData) -> TriggerResult:
        """T-06: 거래량 돌파"""
        v_ratio = ind.v5_20_ratio
        if v_ratio >= 2.0:
            return TriggerResult("T-06", "거래량 돌파", TriggerSignal.BULLISH,
                                 SignalStrength.STRONG, 7, f"5일평균 거래량 > 20일평균 2배 ({v_ratio:.2f}x)",
                                 {"v5_20_ratio": round(v_ratio, 2)})
        elif v_ratio >= 1.5:
            return TriggerResult("T-06", "거래량 돌파", TriggerSignal.BULLISH,
                                 SignalStrength.MODERATE, 5, f"거래량 점진 증가 ({v_ratio:.2f}x)",
                                 {"v5_20_ratio": round(v_ratio, 2)})
        return TriggerResult("T-06", "거래량 돌파", TriggerSignal.NEUTRAL,
                             SignalStrength.NONE, 2, f"거래량 보합 ({v_ratio:.2f}x)",
                             {"v5_20_ratio": round(v_ratio, 2)})

    def _t07_volume_dry(self, ind: IndicatorData) -> TriggerResult:
        """T-07: 거래량 고갈 (매집 전 조용한 구간)"""
        v_ratio = ind.v5_20_ratio
        shock = ind.volume_shock
        if v_ratio <= 0.5 and shock <= 0.5:
            return TriggerResult("T-07", "거래량 고갈", TriggerSignal.BULLISH,
                                 SignalStrength.MODERATE, 5,
                                 f"거래 고갈 → 매집 가능 (V5/20={v_ratio:.2f}, Shock={shock:.2f})",
                                 {"v5_20_ratio": round(v_ratio, 2), "volume_shock": round(shock, 2)})
        elif v_ratio <= 0.7:
            return TriggerResult("T-07", "거래량 고갈", TriggerSignal.NEUTRAL,
                                 SignalStrength.WEAK, 3, f"거래 감소 (V5/20={v_ratio:.2f})",
                                 {"v5_20_ratio": round(v_ratio, 2)})
        return TriggerResult("T-07", "거래량 고갈", TriggerSignal.NEUTRAL,
                             SignalStrength.NONE, 2, f"거래량 충분 (V5/20={v_ratio:.2f})",
                             {"v5_20_ratio": round(v_ratio, 2)})

    def _t08_volume_divergence(self, ind: IndicatorData) -> TriggerResult:
        """T-08: 가격-거래량 다이버전스"""
        # 가격 상승 + 거래량 감소 = bearish divergence
        # 가격 하락 + 거래량 증가 = bullish divergence (잠재적 반전)
        v_ratio = ind.v5_20_ratio
        if v_ratio >= 2.0 and ind.position_52w <= 30:
            return TriggerResult("T-08", "가격-거래량 다이버전스", TriggerSignal.BULLISH,
                                 SignalStrength.STRONG, 7, "저점 + 거래량 급증 (반전 가능)",
                                 {"v5_20_ratio": round(v_ratio, 2), "position_52w": round(ind.position_52w, 1)})
        elif v_ratio <= 0.5 and ind.position_52w >= 80:
            return TriggerResult("T-08", "가격-거래량 다이버전스", TriggerSignal.BEARISH,
                                 SignalStrength.MODERATE, 4, "고점 + 거래량 감소 (약세 다이버전스)",
                                 {"v5_20_ratio": round(v_ratio, 2), "position_52w": round(ind.position_52w, 1)})
        return TriggerResult("T-08", "가격-거래량 다이버전스", TriggerSignal.NEUTRAL,
                             SignalStrength.NONE, 2, "다이버전스 없음")

    def _t10_obv_divergence(self, ind: IndicatorData) -> TriggerResult:
        """T-10: OBV 다이버전스"""
        # 단기 OBV 양수 + 장기 음수 = 매집 초기 단계
        if ind.obv_5 > 0 and ind.obv_10 > 0 and ind.obv_56 < 0:
            return TriggerResult("T-10", "OBV 다이버전스", TriggerSignal.BULLISH,
                                 SignalStrength.STRONG, 7, "단기 OBV 양수 전환 (매집 초기)",
                                 {"obv_5": ind.obv_5, "obv_56": ind.obv_56})
        elif ind.obv_5 < 0 and ind.obv_56 > 0:
            return TriggerResult("T-10", "OBV 다이버전스", TriggerSignal.BEARISH,
                                 SignalStrength.MODERATE, 4, "단기 OBV 음수 전환 (유출 시작)",
                                 {"obv_5": ind.obv_5, "obv_56": ind.obv_56})
        return TriggerResult("T-10", "OBV 다이버전스", TriggerSignal.NEUTRAL,
                             SignalStrength.NONE, 2, "OBV 다이버전스 없음")

    def _t11_obv_breakout(self, ind: IndicatorData) -> TriggerResult:
        """T-11: OBV 돌파"""
        if ind.obv_5 > 0 and ind.obv_10 > 0 and ind.obv_23 > 0:
            return TriggerResult("T-11", "OBV 돌파", TriggerSignal.BULLISH,
                                 SignalStrength.STRONG, 7, "OBV 단중기 모두 양수",
                                 {"obv_5": ind.obv_5, "obv_10": ind.obv_10, "obv_23": ind.obv_23})
        return TriggerResult("T-11", "OBV 돌파", TriggerSignal.NEUTRAL,
                             SignalStrength.NONE, 2, "OBV 돌파 미확인")

    def _t12_cmf_signal(self, ind: IndicatorData) -> TriggerResult:
        """T-12: CMF 시그널"""
        cmf = ind.cmf_20
        if cmf >= 0.15:
            return TriggerResult("T-12", "CMF 시그널", TriggerSignal.BULLISH,
                                 SignalStrength.STRONG, 7, f"강한 자금 유입 (CMF={cmf:.3f})",
                                 {"cmf_20": round(cmf, 4)})
        elif cmf >= 0.05:
            return TriggerResult("T-12", "CMF 시그널", TriggerSignal.BULLISH,
                                 SignalStrength.MODERATE, 5, f"자금 유입 (CMF={cmf:.3f})",
                                 {"cmf_20": round(cmf, 4)})
        elif cmf <= -0.15:
            return TriggerResult("T-12", "CMF 시그널", TriggerSignal.BEARISH,
                                 SignalStrength.STRONG, 3, f"강한 자금 유출 (CMF={cmf:.3f})",
                                 {"cmf_20": round(cmf, 4)})
        elif cmf <= -0.05:
            return TriggerResult("T-12", "CMF 시그널", TriggerSignal.BEARISH,
                                 SignalStrength.MODERATE, 4, f"자금 유출 (CMF={cmf:.3f})",
                                 {"cmf_20": round(cmf, 4)})
        return TriggerResult("T-12", "CMF 시그널", TriggerSignal.NEUTRAL,
                             SignalStrength.WEAK, 3, f"CMF 중립 ({cmf:.3f})",
                             {"cmf_20": round(cmf, 4)})

    def _t13_clv_signal(self, ind: IndicatorData) -> TriggerResult:
        """T-13: CLV 시그널"""
        clv = ind.clv
        if clv >= 0.5:
            return TriggerResult("T-13", "CLV 시그널", TriggerSignal.BULLISH,
                                 SignalStrength.STRONG, 7, f"종가 고점 근처 (CLV={clv:.2f})",
                                 {"clv": round(clv, 4)})
        elif clv >= 0:
            return TriggerResult("T-13", "CLV 시그널", TriggerSignal.BULLISH,
                                 SignalStrength.WEAK, 4, f"종가 중앙 상방 (CLV={clv:.2f})",
                                 {"clv": round(clv, 4)})
        elif clv <= -0.5:
            return TriggerResult("T-13", "CLV 시그널", TriggerSignal.BEARISH,
                                 SignalStrength.STRONG, 3, f"종가 저점 근처 (CLV={clv:.2f})",
                                 {"clv": round(clv, 4)})
        return TriggerResult("T-13", "CLV 시그널", TriggerSignal.BEARISH,
                             SignalStrength.WEAK, 4, f"종가 중앙 하방 (CLV={clv:.2f})",
                             {"clv": round(clv, 4)})

    def _t15_avwap_cross(self, ind: IndicatorData) -> TriggerResult:
        """T-15: AVWAP 교차"""
        pct_20 = ind.avwap_20_pct
        pct_60 = ind.avwap_60_pct
        if pct_20 > 0 and pct_60 > 0 and ind.current_price > 0:
            return TriggerResult("T-15", "AVWAP 교차", TriggerSignal.BULLISH,
                                 SignalStrength.MODERATE, 6, f"AVWAP 20/60 모두 상방 돌파",
                                 {"avwap_20_pct": round(pct_20, 2), "avwap_60_pct": round(pct_60, 2)})
        elif pct_20 < 0 and pct_60 < 0:
            return TriggerResult("T-15", "AVWAP 교차", TriggerSignal.BEARISH,
                                 SignalStrength.MODERATE, 4, f"AVWAP 20/60 모두 하방",
                                 {"avwap_20_pct": round(pct_20, 2), "avwap_60_pct": round(pct_60, 2)})
        return TriggerResult("T-15", "AVWAP 교차", TriggerSignal.NEUTRAL,
                             SignalStrength.WEAK, 3, "AVWAP 혼조")

    def _t16_cmf_trend(self, ind: IndicatorData) -> TriggerResult:
        """T-16: CMF 추세"""
        cmf = ind.cmf_20
        if cmf > 0.1:
            return TriggerResult("T-16", "CMF 추세", TriggerSignal.BULLISH,
                                 SignalStrength.MODERATE, 6, f"지속적 자금 유입 (CMF={cmf:.3f})",
                                 {"cmf_20": round(cmf, 4)})
        elif cmf < -0.1:
            return TriggerResult("T-16", "CMF 추세", TriggerSignal.BEARISH,
                                 SignalStrength.MODERATE, 4, f"지속적 자금 유출 (CMF={cmf:.3f})",
                                 {"cmf_20": round(cmf, 4)})
        return TriggerResult("T-16", "CMF 추세", TriggerSignal.NEUTRAL,
                             SignalStrength.NONE, 2, f"CMF 추세 약함 ({cmf:.3f})")

    def _t17_mfi_signal(self, ind: IndicatorData) -> TriggerResult:
        """T-17: MFI 시그널"""
        mfi = ind.mfi_14
        if mfi >= 80:
            return TriggerResult("T-17", "MFI 시그널", TriggerSignal.BEARISH,
                                 SignalStrength.MODERATE, 4, f"MFI 과매수 ({mfi:.0f})",
                                 {"mfi_14": round(mfi, 2)})
        elif mfi <= 20:
            return TriggerResult("T-17", "MFI 시그널", TriggerSignal.BULLISH,
                                 SignalStrength.STRONG, 7, f"MFI 과매도 ({mfi:.0f})",
                                 {"mfi_14": round(mfi, 2)})
        elif mfi <= 40:
            return TriggerResult("T-17", "MFI 시그널", TriggerSignal.BULLISH,
                                 SignalStrength.MODERATE, 5, f"MFI 저점 접근 ({mfi:.0f})",
                                 {"mfi_14": round(mfi, 2)})
        return TriggerResult("T-17", "MFI 시그널", TriggerSignal.NEUTRAL,
                             SignalStrength.NONE, 3, f"MFI 보통 ({mfi:.0f})",
                             {"mfi_14": round(mfi, 2)})

    def _t18_adx_trend(self, ind: IndicatorData) -> TriggerResult:
        """T-18: ADX 추세 강도"""
        adx = ind.adx
        if adx >= 40:
            signal = TriggerSignal.BULLISH if ind.plus_di > ind.minus_di else TriggerSignal.BEARISH
            return TriggerResult("T-18", "ADX 추세 강도", signal,
                                 SignalStrength.VERY_STRONG, 8 if signal == TriggerSignal.BULLISH else 3,
                                 f"강한 추세 (ADX={adx:.0f}, +DI={ind.plus_di:.0f}, -DI={ind.minus_di:.0f})",
                                 {"adx": round(adx, 2), "plus_di": round(ind.plus_di, 2), "minus_di": round(ind.minus_di, 2)})
        elif adx >= 25:
            signal = TriggerSignal.BULLISH if ind.plus_di > ind.minus_di else TriggerSignal.BEARISH
            return TriggerResult("T-18", "ADX 추세 강도", signal,
                                 SignalStrength.MODERATE, 5 if signal == TriggerSignal.BULLISH else 4,
                                 f"추세 발달 (ADX={adx:.0f})",
                                 {"adx": round(adx, 2)})
        return TriggerResult("T-18", "ADX 추세 강도", TriggerSignal.NEUTRAL,
                             SignalStrength.WEAK, 3, f"추세 약함/횡보 (ADX={adx:.0f})",
                             {"adx": round(adx, 2)})

    def _t19_di_cross(self, ind: IndicatorData) -> TriggerResult:
        """T-19: +DI/-DI 교차"""
        diff = ind.plus_di - ind.minus_di
        if diff > 15:
            return TriggerResult("T-19", "DI 교차", TriggerSignal.BULLISH,
                                 SignalStrength.STRONG, 7, f"+DI 우위 (+DI-(-DI)={diff:.0f})",
                                 {"plus_di": round(ind.plus_di, 2), "minus_di": round(ind.minus_di, 2)})
        elif diff > 5:
            return TriggerResult("T-19", "DI 교차", TriggerSignal.BULLISH,
                                 SignalStrength.MODERATE, 5, f"+DI 소폭 우위 ({diff:.0f})",
                                 {"plus_di": round(ind.plus_di, 2), "minus_di": round(ind.minus_di, 2)})
        elif diff < -15:
            return TriggerResult("T-19", "DI 교차", TriggerSignal.BEARISH,
                                 SignalStrength.STRONG, 3, f"-DI 우위 ({diff:.0f})",
                                 {"plus_di": round(ind.plus_di, 2), "minus_di": round(ind.minus_di, 2)})
        elif diff < -5:
            return TriggerResult("T-19", "DI 교차", TriggerSignal.BEARISH,
                                 SignalStrength.MODERATE, 4, f"-DI 소폭 우위 ({diff:.0f})")
        return TriggerResult("T-19", "DI 교차", TriggerSignal.NEUTRAL,
                             SignalStrength.NONE, 3, "DI 균형")

    def _t21_bb_squeeze_release(self, ind: IndicatorData) -> TriggerResult:
        """T-21: 볼린저 밴드 스퀴즈 해제"""
        bbwp = ind.bbwp
        squeeze = ind.ttm_squeeze
        if not squeeze and bbwp <= 30:
            return TriggerResult("T-21", "BB 스퀴즈 해제", TriggerSignal.BULLISH,
                                 SignalStrength.STRONG, 7, f"스퀴즈 해제 직후 (BBWP={bbwp:.0f}%)",
                                 {"bbwp": round(bbwp, 1), "ttm_squeeze": squeeze})
        elif not squeeze and bbwp >= 70:
            return TriggerResult("T-21", "BB 스퀴즈 해제", TriggerSignal.NEUTRAL,
                                 SignalStrength.WEAK, 3, f"변동성 확대 중 (BBWP={bbwp:.0f}%)",
                                 {"bbwp": round(bbwp, 1)})
        return TriggerResult("T-21", "BB 스퀴즈 해제", TriggerSignal.NEUTRAL,
                             SignalStrength.NONE, 2, "스퀴즈 해제 미확인")

    def _t22_accumulation_pattern(self, ind: IndicatorData) -> TriggerResult:
        """T-22: 종합 매집 패턴 (TV + OBV + CMF)"""
        score_count = 0
        if 1.5 <= ind.tv5_20_ratio <= 3.5:
            score_count += 1
        if ind.obv_5 > 0 and ind.obv_10 > 0:
            score_count += 1
        if ind.cmf_20 > 0.05:
            score_count += 1

        if score_count >= 3:
            return TriggerResult("T-22", "종합 매집 패턴", TriggerSignal.BULLISH,
                                 SignalStrength.VERY_STRONG, 9,
                                 f"TV+OBV+CMF 동시 매집 확인 ({score_count}/3)")
        elif score_count == 2:
            return TriggerResult("T-22", "종합 매집 패턴", TriggerSignal.BULLISH,
                                 SignalStrength.STRONG, 6, f"매집 패턴 부분 확인 ({score_count}/3)")
        return TriggerResult("T-22", "종합 매집 패턴", TriggerSignal.NEUTRAL,
                             SignalStrength.NONE, 2, f"매집 패턴 미확인 ({score_count}/3)")

    # ============================================================
    # ★★★☆☆ 3차 트리거 (20개)
    # ============================================================

    def _t23_udvr_signal(self, ind: IndicatorData) -> TriggerResult:
        """T-23: UDVR 수급 시그널"""
        udvr = ind.udvr_60
        if udvr >= 2.0:
            return TriggerResult("T-23", "UDVR 수급", TriggerSignal.BULLISH,
                                 SignalStrength.STRONG, 7, f"상승일 거래량 압도 (UDVR={udvr:.1f})",
                                 {"udvr_60": round(udvr, 2)})
        elif udvr >= 1.3:
            return TriggerResult("T-23", "UDVR 수급", TriggerSignal.BULLISH,
                                 SignalStrength.MODERATE, 5, f"상승일 거래량 우세 ({udvr:.1f})",
                                 {"udvr_60": round(udvr, 2)})
        elif udvr <= 0.5:
            return TriggerResult("T-23", "UDVR 수급", TriggerSignal.BEARISH,
                                 SignalStrength.STRONG, 3, f"하락일 거래량 압도 ({udvr:.1f})",
                                 {"udvr_60": round(udvr, 2)})
        return TriggerResult("T-23", "UDVR 수급", TriggerSignal.NEUTRAL,
                             SignalStrength.NONE, 3, f"UDVR 균형 ({udvr:.1f})")

    def _t24_rvol_signal(self, ind: IndicatorData) -> TriggerResult:
        """T-24: 상대 거래량"""
        rvol = ind.rvol_20
        if rvol >= 3:
            return TriggerResult("T-24", "상대 거래량", TriggerSignal.BULLISH,
                                 SignalStrength.STRONG, 7, f"RVOL {rvol:.1f}x (주목)",
                                 {"rvol_20": round(rvol, 2)})
        elif rvol >= 1.5:
            return TriggerResult("T-24", "상대 거래량", TriggerSignal.BULLISH,
                                 SignalStrength.MODERATE, 5, f"RVOL {rvol:.1f}x",
                                 {"rvol_20": round(rvol, 2)})
        return TriggerResult("T-24", "상대 거래량", TriggerSignal.NEUTRAL,
                             SignalStrength.NONE, 2, f"RVOL {rvol:.1f}x (보통)",
                             {"rvol_20": round(rvol, 2)})

    def _t25_52w_position(self, ind: IndicatorData) -> TriggerResult:
        """T-25: 52주 위치"""
        pos = ind.position_52w
        if pos <= 20:
            return TriggerResult("T-25", "52주 위치", TriggerSignal.BULLISH,
                                 SignalStrength.STRONG, 7, f"52주 저점 구간 ({pos:.0f}%)",
                                 {"position_52w": round(pos, 1)})
        elif pos <= 40:
            return TriggerResult("T-25", "52주 위치", TriggerSignal.BULLISH,
                                 SignalStrength.MODERATE, 5, f"52주 하단 ({pos:.0f}%)",
                                 {"position_52w": round(pos, 1)})
        elif pos >= 90:
            return TriggerResult("T-25", "52주 위치", TriggerSignal.BEARISH,
                                 SignalStrength.MODERATE, 3, f"52주 고점 근처 ({pos:.0f}%)",
                                 {"position_52w": round(pos, 1)})
        return TriggerResult("T-25", "52주 위치", TriggerSignal.NEUTRAL,
                             SignalStrength.NONE, 3, f"52주 중간 ({pos:.0f}%)",
                             {"position_52w": round(pos, 1)})

    def _t26_ma_alignment(self, ind: IndicatorData) -> TriggerResult:
        """T-26: 이동평균 정배열/역배열"""
        ma5, ma20, ma60 = ind.ma_5, ind.ma_20, ind.ma_60
        if ma5 > 0 and ma20 > 0 and ma60 > 0:
            if ma5 > ma20 > ma60:
                return TriggerResult("T-26", "이동평균 배열", TriggerSignal.BULLISH,
                                     SignalStrength.STRONG, 7, "정배열 (5>20>60)")
            elif ma5 < ma20 < ma60:
                return TriggerResult("T-26", "이동평균 배열", TriggerSignal.BEARISH,
                                     SignalStrength.STRONG, 3, "역배열 (5<20<60)")
        return TriggerResult("T-26", "이동평균 배열", TriggerSignal.NEUTRAL,
                             SignalStrength.NONE, 3, "이동평균 혼조")

    def _t27_ma_cross(self, ind: IndicatorData) -> TriggerResult:
        """T-27: 이동평균 교차"""
        price = ind.current_price
        ma20 = ind.ma_20
        if price > 0 and ma20 > 0:
            pct = ((price - ma20) / ma20) * 100
            if 0 <= pct <= 3:
                return TriggerResult("T-27", "이동평균 교차", TriggerSignal.BULLISH,
                                     SignalStrength.MODERATE, 6, f"20MA 상향 돌파 ({pct:+.1f}%)",
                                     {"price_vs_ma20_pct": round(pct, 2)})
            elif -3 <= pct < 0:
                return TriggerResult("T-27", "이동평균 교차", TriggerSignal.BEARISH,
                                     SignalStrength.MODERATE, 4, f"20MA 하향 이탈 ({pct:+.1f}%)",
                                     {"price_vs_ma20_pct": round(pct, 2)})
        return TriggerResult("T-27", "이동평균 교차", TriggerSignal.NEUTRAL,
                             SignalStrength.NONE, 3, "MA 교차 없음")

    def _t28_price_momentum(self, ind: IndicatorData) -> TriggerResult:
        """T-28: 가격 모멘텀"""
        if ind.ma_5 > 0 and ind.ma_20 > 0:
            momentum = ((ind.ma_5 - ind.ma_20) / ind.ma_20) * 100
            if momentum > 5:
                return TriggerResult("T-28", "가격 모멘텀", TriggerSignal.BULLISH,
                                     SignalStrength.STRONG, 7, f"강한 상승 모멘텀 ({momentum:+.1f}%)")
            elif momentum > 0:
                return TriggerResult("T-28", "가격 모멘텀", TriggerSignal.BULLISH,
                                     SignalStrength.WEAK, 4, f"상승 모멘텀 ({momentum:+.1f}%)")
            elif momentum < -5:
                return TriggerResult("T-28", "가격 모멘텀", TriggerSignal.BEARISH,
                                     SignalStrength.STRONG, 3, f"강한 하락 모멘텀 ({momentum:+.1f}%)")
        return TriggerResult("T-28", "가격 모멘텀", TriggerSignal.NEUTRAL,
                             SignalStrength.NONE, 3, "모멘텀 보통")

    def _t29_volatility_contraction(self, ind: IndicatorData) -> TriggerResult:
        """T-29: 변동성 수축"""
        atr_pct = ind.atr_pct
        bbwp = ind.bbwp
        if atr_pct > 0 and atr_pct <= 2 and bbwp <= 30:
            return TriggerResult("T-29", "변동성 수축", TriggerSignal.BULLISH,
                                 SignalStrength.STRONG, 7, f"ATR+BBWP 수축 (ATR%={atr_pct:.1f}, BBWP={bbwp:.0f})")
        elif atr_pct <= 3 and bbwp <= 40:
            return TriggerResult("T-29", "변동성 수축", TriggerSignal.BULLISH,
                                 SignalStrength.MODERATE, 5, f"변동성 낮음 (ATR%={atr_pct:.1f})")
        return TriggerResult("T-29", "변동성 수축", TriggerSignal.NEUTRAL,
                             SignalStrength.NONE, 3, f"변동성 보통 (ATR%={atr_pct:.1f})")

    def _t30_breakout_readiness(self, ind: IndicatorData) -> TriggerResult:
        """T-30: 돌파 준비 상태"""
        # 볼린저 스퀴즈 + 거래대금 증가 + OBV 양수 = 돌파 임박
        ready = 0
        if ind.ttm_squeeze:
            ready += 1
        if ind.tv5_20_ratio >= 1.5:
            ready += 1
        if ind.obv_5 > 0 and ind.obv_10 > 0:
            ready += 1
        if ind.adx < 20:  # 횡보 구간
            ready += 1

        if ready >= 3:
            return TriggerResult("T-30", "돌파 준비", TriggerSignal.BULLISH,
                                 SignalStrength.STRONG, 8, f"돌파 임박 ({ready}/4 조건 충족)")
        elif ready == 2:
            return TriggerResult("T-30", "돌파 준비", TriggerSignal.BULLISH,
                                 SignalStrength.MODERATE, 5, f"돌파 준비 ({ready}/4)")
        return TriggerResult("T-30", "돌파 준비", TriggerSignal.NEUTRAL,
                             SignalStrength.NONE, 2, f"돌파 준비 미흡 ({ready}/4)")

    def _t31_risk_reward(self, ind: IndicatorData) -> TriggerResult:
        """T-31: 리스크/리워드"""
        if ind.atr > 0 and ind.current_price > 0:
            risk_pct = ind.atr_pct
            # AVWAP60 기준 잠재 수익
            reward_pct = abs(ind.avwap_60_pct) if ind.avwap_60_pct < 0 else ind.avwap_60_pct
            if risk_pct > 0:
                rr_ratio = reward_pct / risk_pct
                if rr_ratio >= 3:
                    return TriggerResult("T-31", "리스크/리워드", TriggerSignal.BULLISH,
                                         SignalStrength.STRONG, 7, f"R:R={rr_ratio:.1f} (유리)")
                elif rr_ratio >= 2:
                    return TriggerResult("T-31", "리스크/리워드", TriggerSignal.BULLISH,
                                         SignalStrength.MODERATE, 5, f"R:R={rr_ratio:.1f}")
        return TriggerResult("T-31", "리스크/리워드", TriggerSignal.NEUTRAL,
                             SignalStrength.NONE, 3, "R:R 계산 불가/보통")

    def _t32_trend_strength(self, ind: IndicatorData) -> TriggerResult:
        """T-32: 종합 추세 강도"""
        strength = 0
        if ind.adx >= 25:
            strength += 1
        if ind.plus_di > ind.minus_di:
            strength += 1
        if ind.ma_5 > ind.ma_20:
            strength += 1
        if ind.current_price > ind.ma_60:
            strength += 1

        if strength >= 4:
            return TriggerResult("T-32", "추세 강도", TriggerSignal.BULLISH,
                                 SignalStrength.VERY_STRONG, 8, f"강한 상승 추세 ({strength}/4)")
        elif strength >= 3:
            return TriggerResult("T-32", "추세 강도", TriggerSignal.BULLISH,
                                 SignalStrength.MODERATE, 6, f"상승 추세 ({strength}/4)")
        elif strength <= 1:
            return TriggerResult("T-32", "추세 강도", TriggerSignal.BEARISH,
                                 SignalStrength.MODERATE, 4, f"하락 추세 ({strength}/4)")
        return TriggerResult("T-32", "추세 강도", TriggerSignal.NEUTRAL,
                             SignalStrength.NONE, 3, f"추세 혼조 ({strength}/4)")

    def _t33_money_flow_combo(self, ind: IndicatorData) -> TriggerResult:
        """T-33: 자금 흐름 종합"""
        bullish = 0
        if ind.cmf_20 > 0.05:
            bullish += 1
        if ind.mfi_14 < 50:
            bullish += 1
        if ind.clv > 0:
            bullish += 1

        if bullish >= 3:
            return TriggerResult("T-33", "자금흐름 종합", TriggerSignal.BULLISH,
                                 SignalStrength.STRONG, 7, f"자금 유입 종합 확인 ({bullish}/3)")
        elif bullish >= 2:
            return TriggerResult("T-33", "자금흐름 종합", TriggerSignal.BULLISH,
                                 SignalStrength.MODERATE, 5, f"자금 유입 경향 ({bullish}/3)")
        elif bullish == 0:
            return TriggerResult("T-33", "자금흐름 종합", TriggerSignal.BEARISH,
                                 SignalStrength.MODERATE, 4, "자금 유출 종합")
        return TriggerResult("T-33", "자금흐름 종합", TriggerSignal.NEUTRAL,
                             SignalStrength.NONE, 3, "자금흐름 혼조")

    def _t34_supply_demand_balance(self, ind: IndicatorData) -> TriggerResult:
        """T-34: 수급 밸런스"""
        balance = 0
        if ind.obv_10 > 0:
            balance += 1
        if ind.udvr_60 > 1.2:
            balance += 1
        if ind.cmf_20 > 0:
            balance += 1

        if balance >= 3:
            return TriggerResult("T-34", "수급 밸런스", TriggerSignal.BULLISH,
                                 SignalStrength.STRONG, 7, f"매수 수급 우위 ({balance}/3)")
        elif balance == 0:
            return TriggerResult("T-34", "수급 밸런스", TriggerSignal.BEARISH,
                                 SignalStrength.MODERATE, 4, "매도 수급 우위")
        return TriggerResult("T-34", "수급 밸런스", TriggerSignal.NEUTRAL,
                             SignalStrength.NONE, 3, f"수급 균형 ({balance}/3)")

    def _t35_entry_timing(self, ind: IndicatorData) -> TriggerResult:
        """T-35: 진입 타이밍"""
        good = 0
        if -5 <= ind.avwap_60_pct <= 5:
            good += 1
        if ind.bbwp <= 40:
            good += 1
        if ind.mfi_14 <= 50:
            good += 1
        if ind.clv >= 0:
            good += 1

        if good >= 4:
            return TriggerResult("T-35", "진입 타이밍", TriggerSignal.BULLISH,
                                 SignalStrength.VERY_STRONG, 9, f"최적 진입 타이밍 ({good}/4)")
        elif good >= 3:
            return TriggerResult("T-35", "진입 타이밍", TriggerSignal.BULLISH,
                                 SignalStrength.STRONG, 7, f"양호한 진입 ({good}/4)")
        elif good >= 2:
            return TriggerResult("T-35", "진입 타이밍", TriggerSignal.NEUTRAL,
                                 SignalStrength.MODERATE, 4, f"보통 ({good}/4)")
        return TriggerResult("T-35", "진입 타이밍", TriggerSignal.BEARISH,
                             SignalStrength.WEAK, 3, f"진입 비적합 ({good}/4)")

    def _t36_exit_warning(self, ind: IndicatorData) -> TriggerResult:
        """T-36: 이탈 경고"""
        warning = 0
        if ind.mfi_14 >= 80:
            warning += 1
        if ind.bbwp >= 80:
            warning += 1
        if ind.position_52w >= 90:
            warning += 1
        if ind.cmf_20 < -0.1:
            warning += 1

        if warning >= 3:
            return TriggerResult("T-36", "이탈 경고", TriggerSignal.BEARISH,
                                 SignalStrength.VERY_STRONG, 2, f"강한 이탈 경고 ({warning}/4)")
        elif warning >= 2:
            return TriggerResult("T-36", "이탈 경고", TriggerSignal.BEARISH,
                                 SignalStrength.MODERATE, 4, f"이탈 주의 ({warning}/4)")
        return TriggerResult("T-36", "이탈 경고", TriggerSignal.NEUTRAL,
                             SignalStrength.NONE, 5, f"이탈 경고 없음 ({warning}/4)")

    def _t37_consolidation_phase(self, ind: IndicatorData) -> TriggerResult:
        """T-37: 횡보 구간"""
        if ind.adx < 20 and ind.bbwp <= 30:
            return TriggerResult("T-37", "횡보 구간", TriggerSignal.BULLISH,
                                 SignalStrength.MODERATE, 6, "횡보 압축 (잠재적 돌파)")
        elif ind.adx < 20:
            return TriggerResult("T-37", "횡보 구간", TriggerSignal.NEUTRAL,
                                 SignalStrength.WEAK, 3, "횡보 중")
        return TriggerResult("T-37", "횡보 구간", TriggerSignal.NEUTRAL,
                             SignalStrength.NONE, 3, "횡보 아님")

    def _t38_trend_reversal(self, ind: IndicatorData) -> TriggerResult:
        """T-38: 추세 반전 신호"""
        reversal = 0
        if ind.position_52w <= 25 and ind.obv_5 > 0:
            reversal += 1
        if ind.mfi_14 <= 30 and ind.cmf_20 > 0:
            reversal += 1
        if ind.volume_shock >= 2 and ind.clv >= 0.3:
            reversal += 1

        if reversal >= 2:
            return TriggerResult("T-38", "추세 반전", TriggerSignal.BULLISH,
                                 SignalStrength.STRONG, 7, f"바닥 반전 신호 ({reversal}/3)")
        elif reversal == 1:
            return TriggerResult("T-38", "추세 반전", TriggerSignal.BULLISH,
                                 SignalStrength.WEAK, 4, f"반전 초기 ({reversal}/3)")
        return TriggerResult("T-38", "추세 반전", TriggerSignal.NEUTRAL,
                             SignalStrength.NONE, 3, "반전 신호 없음")

    def _t39_volume_price_confirm(self, ind: IndicatorData) -> TriggerResult:
        """T-39: 거래량-가격 확인"""
        confirmed = 0
        if ind.volume_shock >= 1.5 and ind.clv >= 0.3:
            confirmed += 1
        if ind.v5_20_ratio >= 1.3 and ind.current_price > ind.ma_20:
            confirmed += 1

        if confirmed >= 2:
            return TriggerResult("T-39", "거래량-가격 확인", TriggerSignal.BULLISH,
                                 SignalStrength.STRONG, 7, "거래량+가격 상승 확인")
        elif confirmed == 1:
            return TriggerResult("T-39", "거래량-가격 확인", TriggerSignal.BULLISH,
                                 SignalStrength.WEAK, 4, "부분 확인")
        return TriggerResult("T-39", "거래량-가격 확인", TriggerSignal.NEUTRAL,
                             SignalStrength.NONE, 3, "미확인")

    def _t40_institutional_flow(self, ind: IndicatorData) -> TriggerResult:
        """T-40: 기관 수급 추정 (TV+OBV 복합)"""
        # 거래대금 증가 + OBV 양수 + 변동성 낮음 = 기관 매집 추정
        inst = 0
        if 1.5 <= ind.tv5_20_ratio <= 3.0:
            inst += 1
        if ind.obv_23 > 0:
            inst += 1
        if ind.atr_pct <= 3:
            inst += 1

        if inst >= 3:
            return TriggerResult("T-40", "기관수급 추정", TriggerSignal.BULLISH,
                                 SignalStrength.STRONG, 7, f"기관 매집 패턴 ({inst}/3)")
        elif inst == 2:
            return TriggerResult("T-40", "기관수급 추정", TriggerSignal.BULLISH,
                                 SignalStrength.MODERATE, 5, f"기관 관심 추정 ({inst}/3)")
        return TriggerResult("T-40", "기관수급 추정", TriggerSignal.NEUTRAL,
                             SignalStrength.NONE, 3, "기관 매집 미확인")

    def _t41_composite_buy(self, ind: IndicatorData) -> TriggerResult:
        """T-41: 종합 매수 판정"""
        buy_signals = 0
        if ind.tv5_20_ratio >= 1.5:
            buy_signals += 1
        if ind.obv_5 > 0 and ind.obv_10 > 0:
            buy_signals += 1
        if -5 <= ind.avwap_60_pct <= 5:
            buy_signals += 1
        if ind.cmf_20 > 0:
            buy_signals += 1
        if ind.bbwp <= 40:
            buy_signals += 1

        if buy_signals >= 4:
            return TriggerResult("T-41", "종합 매수 판정", TriggerSignal.BULLISH,
                                 SignalStrength.VERY_STRONG, 9, f"강력 매수 ({buy_signals}/5)")
        elif buy_signals >= 3:
            return TriggerResult("T-41", "종합 매수 판정", TriggerSignal.BULLISH,
                                 SignalStrength.STRONG, 7, f"매수 유리 ({buy_signals}/5)")
        elif buy_signals >= 2:
            return TriggerResult("T-41", "종합 매수 판정", TriggerSignal.NEUTRAL,
                                 SignalStrength.MODERATE, 4, f"매수 보류 ({buy_signals}/5)")
        return TriggerResult("T-41", "종합 매수 판정", TriggerSignal.BEARISH,
                             SignalStrength.WEAK, 3, f"매수 부적합 ({buy_signals}/5)")

    def _t42_composite_sell(self, ind: IndicatorData) -> TriggerResult:
        """T-42: 종합 매도 판정"""
        sell_signals = 0
        if ind.mfi_14 >= 80:
            sell_signals += 1
        if ind.bbwp >= 80:
            sell_signals += 1
        if ind.position_52w >= 85:
            sell_signals += 1
        if ind.cmf_20 < -0.05:
            sell_signals += 1
        if ind.obv_5 < 0 and ind.obv_10 < 0:
            sell_signals += 1

        if sell_signals >= 4:
            return TriggerResult("T-42", "종합 매도 판정", TriggerSignal.BEARISH,
                                 SignalStrength.VERY_STRONG, 1, f"강력 매도 ({sell_signals}/5)")
        elif sell_signals >= 3:
            return TriggerResult("T-42", "종합 매도 판정", TriggerSignal.BEARISH,
                                 SignalStrength.STRONG, 3, f"매도 경고 ({sell_signals}/5)")
        elif sell_signals >= 2:
            return TriggerResult("T-42", "종합 매도 판정", TriggerSignal.NEUTRAL,
                                 SignalStrength.MODERATE, 4, f"매도 주의 ({sell_signals}/5)")
        return TriggerResult("T-42", "종합 매도 판정", TriggerSignal.BULLISH,
                             SignalStrength.WEAK, 6, f"매도 신호 없음 ({sell_signals}/5)")


# 싱글톤 인스턴스
trigger_evaluator = TriggerEvaluator()

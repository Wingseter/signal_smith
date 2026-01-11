"""
Sector & Theme Analysis Service
섹터 로테이션, 테마별 종목 그룹핑
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

import logging

logger = logging.getLogger(__name__)


class MarketCycle(Enum):
    """Economic cycle phases."""
    EARLY_EXPANSION = "early_expansion"  # 초기 확장
    MID_EXPANSION = "mid_expansion"  # 중기 확장
    LATE_EXPANSION = "late_expansion"  # 후기 확장
    EARLY_RECESSION = "early_recession"  # 초기 침체
    MID_RECESSION = "mid_recession"  # 중기 침체
    LATE_RECESSION = "late_recession"  # 후기 침체


class SectorStrength(Enum):
    """Sector relative strength."""
    STRONG_OUTPERFORM = "strong_outperform"
    OUTPERFORM = "outperform"
    NEUTRAL = "neutral"
    UNDERPERFORM = "underperform"
    STRONG_UNDERPERFORM = "strong_underperform"


# Korean market sectors
KOREAN_SECTORS = {
    "IT": {
        "name": "정보기술",
        "description": "반도체, 소프트웨어, IT서비스",
        "cycle_preference": [MarketCycle.EARLY_EXPANSION, MarketCycle.MID_EXPANSION],
        "symbols": ["005930", "000660", "035420", "035720", "036570"],
    },
    "금융": {
        "name": "금융",
        "description": "은행, 증권, 보험",
        "cycle_preference": [MarketCycle.LATE_EXPANSION, MarketCycle.EARLY_EXPANSION],
        "symbols": ["105560", "055550", "086790", "316140", "024110"],
    },
    "바이오": {
        "name": "헬스케어/바이오",
        "description": "제약, 바이오, 의료기기",
        "cycle_preference": [MarketCycle.MID_RECESSION, MarketCycle.LATE_RECESSION],
        "symbols": ["207940", "068270", "091990", "326030", "145020"],
    },
    "자동차": {
        "name": "자동차",
        "description": "완성차, 부품",
        "cycle_preference": [MarketCycle.EARLY_EXPANSION, MarketCycle.MID_EXPANSION],
        "symbols": ["005380", "000270", "012330", "011210", "018880"],
    },
    "화학": {
        "name": "화학/소재",
        "description": "화학, 철강, 비철금속",
        "cycle_preference": [MarketCycle.MID_EXPANSION, MarketCycle.LATE_EXPANSION],
        "symbols": ["051910", "010130", "006400", "005490", "011170"],
    },
    "에너지": {
        "name": "에너지/유틸리티",
        "description": "정유, 가스, 전력",
        "cycle_preference": [MarketCycle.LATE_EXPANSION],
        "symbols": ["096770", "017670", "010950", "015760", "036460"],
    },
    "소비재": {
        "name": "필수소비재",
        "description": "음식료, 생활용품",
        "cycle_preference": [MarketCycle.MID_RECESSION, MarketCycle.LATE_RECESSION],
        "symbols": ["051900", "004370", "097950", "280360", "003230"],
    },
    "경기소비재": {
        "name": "경기소비재",
        "description": "유통, 항공, 호텔",
        "cycle_preference": [MarketCycle.EARLY_EXPANSION, MarketCycle.MID_EXPANSION],
        "symbols": ["004170", "069960", "032640", "008770", "003490"],
    },
    "건설": {
        "name": "건설/부동산",
        "description": "건설, 부동산",
        "cycle_preference": [MarketCycle.LATE_RECESSION, MarketCycle.EARLY_EXPANSION],
        "symbols": ["000720", "047040", "006360", "009540", "034730"],
    },
    "통신": {
        "name": "통신서비스",
        "description": "통신, 미디어",
        "cycle_preference": [MarketCycle.MID_RECESSION, MarketCycle.LATE_RECESSION],
        "symbols": ["017670", "030200", "032640", "034220", "036570"],
    },
}

# Investment themes
INVESTMENT_THEMES = {
    "AI_반도체": {
        "name": "AI/반도체",
        "description": "인공지능 및 반도체 관련주",
        "keywords": ["AI", "반도체", "HBM", "GPU", "NPU"],
        "symbols": ["005930", "000660", "042700", "403870", "058470"],
        "hot": True,
    },
    "2차전지": {
        "name": "2차전지/전기차",
        "description": "배터리, 전기차 관련주",
        "keywords": ["배터리", "리튬", "전기차", "양극재", "음극재"],
        "symbols": ["006400", "051910", "373220", "247540", "086520"],
        "hot": True,
    },
    "바이오신약": {
        "name": "바이오/신약",
        "description": "신약개발, 바이오시밀러",
        "keywords": ["신약", "임상", "FDA", "바이오시밀러", "CAR-T"],
        "symbols": ["207940", "068270", "091990", "326030", "141080"],
        "hot": True,
    },
    "방산": {
        "name": "방위산업",
        "description": "방산, 우주항공",
        "keywords": ["방산", "우주", "위성", "미사일", "드론"],
        "symbols": ["012450", "047810", "298040", "082660", "014970"],
        "hot": False,
    },
    "로봇": {
        "name": "로봇/자동화",
        "description": "로봇, 공장자동화",
        "keywords": ["로봇", "자동화", "협동로봇", "서비스로봇"],
        "symbols": ["099320", "108320", "090460", "267260", "298040"],
        "hot": True,
    },
    "수소경제": {
        "name": "수소/친환경",
        "description": "수소, 신재생에너지",
        "keywords": ["수소", "연료전지", "태양광", "풍력", "ESS"],
        "symbols": ["336260", "009830", "003490", "095660", "281740"],
        "hot": False,
    },
    "메타버스": {
        "name": "메타버스/게임",
        "description": "메타버스, 게임, 콘텐츠",
        "keywords": ["메타버스", "VR", "AR", "게임", "NFT"],
        "symbols": ["035720", "251270", "263750", "293490", "041510"],
        "hot": False,
    },
    "고배당": {
        "name": "고배당주",
        "description": "배당수익률 상위 종목",
        "keywords": ["배당", "배당성장", "우선주"],
        "symbols": ["017670", "015760", "000270", "086790", "005940"],
        "hot": False,
    },
}


@dataclass
class SectorPerformance:
    """Sector performance metrics."""
    sector_id: str
    name: str
    return_1d: float = 0.0
    return_1w: float = 0.0
    return_1m: float = 0.0
    return_3m: float = 0.0
    return_ytd: float = 0.0
    relative_strength: float = 0.0
    strength_rank: int = 0
    strength_level: SectorStrength = SectorStrength.NEUTRAL
    volume_change: float = 0.0
    momentum_score: float = 0.0
    top_gainers: List[Dict[str, Any]] = field(default_factory=list)
    top_losers: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ThemePerformance:
    """Theme performance metrics."""
    theme_id: str
    name: str
    description: str
    is_hot: bool
    return_1d: float = 0.0
    return_1w: float = 0.0
    return_1m: float = 0.0
    momentum_score: float = 0.0
    stock_count: int = 0
    avg_volume_change: float = 0.0
    top_stocks: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class SectorRotationSignal:
    """Sector rotation recommendation."""
    date: datetime
    from_sectors: List[str]
    to_sectors: List[str]
    confidence: float
    cycle_phase: MarketCycle
    rationale: str


class SectorAnalyzer:
    """
    Sector and theme analysis service.

    Provides:
    - Sector performance tracking
    - Sector rotation signals
    - Theme-based stock grouping
    - Relative strength analysis
    """

    def __init__(self):
        self.sectors = KOREAN_SECTORS
        self.themes = INVESTMENT_THEMES

    def analyze_sectors(
        self,
        price_data: Dict[str, pd.DataFrame],
        benchmark_data: Optional[pd.DataFrame] = None,
    ) -> List[SectorPerformance]:
        """
        Analyze all sectors' performance.

        Args:
            price_data: Dictionary of symbol -> price DataFrame
            benchmark_data: Benchmark (KOSPI) price data

        Returns:
            List of SectorPerformance sorted by relative strength
        """
        sector_performances = []

        for sector_id, sector_info in self.sectors.items():
            performance = self._calculate_sector_performance(
                sector_id, sector_info, price_data, benchmark_data
            )
            sector_performances.append(performance)

        # Rank by relative strength
        sector_performances.sort(key=lambda x: x.relative_strength, reverse=True)
        for rank, perf in enumerate(sector_performances, 1):
            perf.strength_rank = rank
            perf.strength_level = self._get_strength_level(
                rank, len(sector_performances)
            )

        return sector_performances

    def analyze_themes(
        self,
        price_data: Dict[str, pd.DataFrame],
    ) -> List[ThemePerformance]:
        """
        Analyze all investment themes' performance.

        Args:
            price_data: Dictionary of symbol -> price DataFrame

        Returns:
            List of ThemePerformance sorted by momentum
        """
        theme_performances = []

        for theme_id, theme_info in self.themes.items():
            performance = self._calculate_theme_performance(
                theme_id, theme_info, price_data
            )
            theme_performances.append(performance)

        # Sort by momentum score
        theme_performances.sort(key=lambda x: x.momentum_score, reverse=True)

        return theme_performances

    def detect_rotation(
        self,
        sector_history: List[List[SectorPerformance]],
        lookback_periods: int = 4,
    ) -> Optional[SectorRotationSignal]:
        """
        Detect sector rotation signals.

        Args:
            sector_history: Historical sector performances (newest first)
            lookback_periods: Number of periods to analyze

        Returns:
            SectorRotationSignal if rotation detected
        """
        if len(sector_history) < lookback_periods:
            return None

        # Analyze rank changes
        current_ranks = {p.sector_id: p.strength_rank for p in sector_history[0]}
        past_ranks = {p.sector_id: p.strength_rank for p in sector_history[-1]}

        # Find improving sectors (rank decreased = improved)
        improving = []
        declining = []

        for sector_id in current_ranks:
            current = current_ranks.get(sector_id, 5)
            past = past_ranks.get(sector_id, 5)
            change = past - current  # Positive = improved

            if change >= 2:
                improving.append((sector_id, change))
            elif change <= -2:
                declining.append((sector_id, change))

        if not improving or not declining:
            return None

        # Determine cycle phase
        cycle = self._estimate_cycle_phase(sector_history[0])

        # Calculate confidence
        avg_improvement = np.mean([c for _, c in improving])
        confidence = min(avg_improvement / 3.0, 1.0)

        return SectorRotationSignal(
            date=datetime.now(),
            from_sectors=[s for s, _ in declining],
            to_sectors=[s for s, _ in improving],
            confidence=confidence,
            cycle_phase=cycle,
            rationale=self._generate_rotation_rationale(
                improving, declining, cycle
            ),
        )

    def get_sector_stocks(self, sector_id: str) -> List[str]:
        """Get stock symbols for a sector."""
        if sector_id in self.sectors:
            return self.sectors[sector_id].get("symbols", [])
        return []

    def get_theme_stocks(self, theme_id: str) -> List[str]:
        """Get stock symbols for a theme."""
        if theme_id in self.themes:
            return self.themes[theme_id].get("symbols", [])
        return []

    def find_stocks_by_keyword(self, keyword: str) -> List[Dict[str, Any]]:
        """Find themes and stocks matching a keyword."""
        results = []

        for theme_id, theme_info in self.themes.items():
            keywords = theme_info.get("keywords", [])
            if any(keyword.lower() in k.lower() for k in keywords):
                results.append({
                    "type": "theme",
                    "id": theme_id,
                    "name": theme_info["name"],
                    "description": theme_info["description"],
                    "symbols": theme_info["symbols"],
                })

        return results

    def get_recommended_sectors(
        self,
        cycle_phase: MarketCycle,
    ) -> List[Dict[str, Any]]:
        """Get recommended sectors for a market cycle phase."""
        recommendations = []

        for sector_id, sector_info in self.sectors.items():
            preferences = sector_info.get("cycle_preference", [])
            if cycle_phase in preferences:
                recommendations.append({
                    "sector_id": sector_id,
                    "name": sector_info["name"],
                    "description": sector_info["description"],
                    "symbols": sector_info["symbols"][:5],
                    "fit_score": 1.0 if preferences[0] == cycle_phase else 0.7,
                })

        recommendations.sort(key=lambda x: x["fit_score"], reverse=True)
        return recommendations

    def calculate_sector_correlation(
        self,
        price_data: Dict[str, pd.DataFrame],
        period_days: int = 60,
    ) -> pd.DataFrame:
        """Calculate correlation matrix between sectors."""
        sector_returns = {}

        for sector_id, sector_info in self.sectors.items():
            symbols = sector_info.get("symbols", [])
            returns_list = []

            for symbol in symbols:
                if symbol in price_data:
                    df = price_data[symbol].tail(period_days)
                    if len(df) > 0:
                        returns = df["close"].pct_change().dropna()
                        returns_list.append(returns)

            if returns_list:
                # Average returns across sector stocks
                avg_returns = pd.concat(returns_list, axis=1).mean(axis=1)
                sector_returns[sector_id] = avg_returns

        if sector_returns:
            returns_df = pd.DataFrame(sector_returns)
            return returns_df.corr()

        return pd.DataFrame()

    def _calculate_sector_performance(
        self,
        sector_id: str,
        sector_info: Dict,
        price_data: Dict[str, pd.DataFrame],
        benchmark_data: Optional[pd.DataFrame],
    ) -> SectorPerformance:
        """Calculate performance metrics for a sector."""
        symbols = sector_info.get("symbols", [])
        returns_1d = []
        returns_1w = []
        returns_1m = []
        returns_3m = []
        returns_ytd = []
        volume_changes = []
        stock_performances = []

        for symbol in symbols:
            if symbol not in price_data:
                continue

            df = price_data[symbol]
            if len(df) < 5:
                continue

            current_price = df["close"].iloc[-1]

            # Calculate returns for different periods
            if len(df) >= 2:
                ret_1d = (current_price / df["close"].iloc[-2] - 1) * 100
                returns_1d.append(ret_1d)

            if len(df) >= 5:
                ret_1w = (current_price / df["close"].iloc[-5] - 1) * 100
                returns_1w.append(ret_1w)

            if len(df) >= 20:
                ret_1m = (current_price / df["close"].iloc[-20] - 1) * 100
                returns_1m.append(ret_1m)

            if len(df) >= 60:
                ret_3m = (current_price / df["close"].iloc[-60] - 1) * 100
                returns_3m.append(ret_3m)

            # YTD return
            current_year = datetime.now().year
            ytd_data = df[df.index >= f"{current_year}-01-01"]
            if len(ytd_data) > 0:
                ret_ytd = (current_price / ytd_data["close"].iloc[0] - 1) * 100
                returns_ytd.append(ret_ytd)

            # Volume change
            if "volume" in df.columns and len(df) >= 20:
                recent_vol = df["volume"].tail(5).mean()
                avg_vol = df["volume"].tail(20).mean()
                if avg_vol > 0:
                    volume_changes.append((recent_vol / avg_vol - 1) * 100)

            stock_performances.append({
                "symbol": symbol,
                "return_1d": ret_1d if len(df) >= 2 else 0,
                "return_1w": ret_1w if len(df) >= 5 else 0,
            })

        # Calculate averages
        avg_return_1d = np.mean(returns_1d) if returns_1d else 0
        avg_return_1w = np.mean(returns_1w) if returns_1w else 0
        avg_return_1m = np.mean(returns_1m) if returns_1m else 0
        avg_return_3m = np.mean(returns_3m) if returns_3m else 0
        avg_return_ytd = np.mean(returns_ytd) if returns_ytd else 0
        avg_volume_change = np.mean(volume_changes) if volume_changes else 0

        # Calculate relative strength vs benchmark
        relative_strength = avg_return_1m
        if benchmark_data is not None and len(benchmark_data) >= 20:
            benchmark_return = (
                benchmark_data["close"].iloc[-1] / benchmark_data["close"].iloc[-20] - 1
            ) * 100
            relative_strength = avg_return_1m - benchmark_return

        # Momentum score (weighted average of returns)
        momentum_score = (
            avg_return_1d * 0.1 +
            avg_return_1w * 0.2 +
            avg_return_1m * 0.4 +
            avg_return_3m * 0.3
        )

        # Get top gainers and losers
        stock_performances.sort(key=lambda x: x["return_1d"], reverse=True)
        top_gainers = stock_performances[:3]
        top_losers = stock_performances[-3:][::-1]

        return SectorPerformance(
            sector_id=sector_id,
            name=sector_info["name"],
            return_1d=round(avg_return_1d, 2),
            return_1w=round(avg_return_1w, 2),
            return_1m=round(avg_return_1m, 2),
            return_3m=round(avg_return_3m, 2),
            return_ytd=round(avg_return_ytd, 2),
            relative_strength=round(relative_strength, 2),
            volume_change=round(avg_volume_change, 2),
            momentum_score=round(momentum_score, 2),
            top_gainers=top_gainers,
            top_losers=top_losers,
        )

    def _calculate_theme_performance(
        self,
        theme_id: str,
        theme_info: Dict,
        price_data: Dict[str, pd.DataFrame],
    ) -> ThemePerformance:
        """Calculate performance metrics for a theme."""
        symbols = theme_info.get("symbols", [])
        returns_1d = []
        returns_1w = []
        returns_1m = []
        volume_changes = []
        stock_performances = []

        for symbol in symbols:
            if symbol not in price_data:
                continue

            df = price_data[symbol]
            if len(df) < 5:
                continue

            current_price = df["close"].iloc[-1]

            # Calculate returns
            ret_1d = (current_price / df["close"].iloc[-2] - 1) * 100 if len(df) >= 2 else 0
            ret_1w = (current_price / df["close"].iloc[-5] - 1) * 100 if len(df) >= 5 else 0
            ret_1m = (current_price / df["close"].iloc[-20] - 1) * 100 if len(df) >= 20 else 0

            returns_1d.append(ret_1d)
            returns_1w.append(ret_1w)
            returns_1m.append(ret_1m)

            # Volume change
            if "volume" in df.columns and len(df) >= 20:
                recent_vol = df["volume"].tail(5).mean()
                avg_vol = df["volume"].tail(20).mean()
                if avg_vol > 0:
                    volume_changes.append((recent_vol / avg_vol - 1) * 100)

            stock_performances.append({
                "symbol": symbol,
                "return_1d": round(ret_1d, 2),
                "return_1w": round(ret_1w, 2),
                "return_1m": round(ret_1m, 2),
            })

        avg_return_1d = np.mean(returns_1d) if returns_1d else 0
        avg_return_1w = np.mean(returns_1w) if returns_1w else 0
        avg_return_1m = np.mean(returns_1m) if returns_1m else 0
        avg_volume_change = np.mean(volume_changes) if volume_changes else 0

        momentum_score = (
            avg_return_1d * 0.2 +
            avg_return_1w * 0.3 +
            avg_return_1m * 0.5
        )

        stock_performances.sort(key=lambda x: x["return_1w"], reverse=True)

        return ThemePerformance(
            theme_id=theme_id,
            name=theme_info["name"],
            description=theme_info["description"],
            is_hot=theme_info.get("hot", False),
            return_1d=round(avg_return_1d, 2),
            return_1w=round(avg_return_1w, 2),
            return_1m=round(avg_return_1m, 2),
            momentum_score=round(momentum_score, 2),
            stock_count=len(symbols),
            avg_volume_change=round(avg_volume_change, 2),
            top_stocks=stock_performances[:5],
        )

    def _get_strength_level(self, rank: int, total: int) -> SectorStrength:
        """Convert rank to strength level."""
        percentile = rank / total
        if percentile <= 0.2:
            return SectorStrength.STRONG_OUTPERFORM
        elif percentile <= 0.4:
            return SectorStrength.OUTPERFORM
        elif percentile <= 0.6:
            return SectorStrength.NEUTRAL
        elif percentile <= 0.8:
            return SectorStrength.UNDERPERFORM
        else:
            return SectorStrength.STRONG_UNDERPERFORM

    def _estimate_cycle_phase(
        self,
        sector_performances: List[SectorPerformance],
    ) -> MarketCycle:
        """Estimate current market cycle phase based on sector leadership."""
        # Map sector strengths
        sector_ranks = {p.sector_id: p.strength_rank for p in sector_performances}

        # Early expansion: IT, Consumer discretionary lead
        # Late expansion: Energy, Materials lead
        # Recession: Healthcare, Consumer staples lead

        it_rank = sector_ranks.get("IT", 5)
        finance_rank = sector_ranks.get("금융", 5)
        bio_rank = sector_ranks.get("바이오", 5)
        energy_rank = sector_ranks.get("에너지", 5)

        if it_rank <= 2 and finance_rank <= 4:
            return MarketCycle.EARLY_EXPANSION
        elif energy_rank <= 2:
            return MarketCycle.LATE_EXPANSION
        elif bio_rank <= 2:
            return MarketCycle.MID_RECESSION
        else:
            return MarketCycle.MID_EXPANSION

    def _generate_rotation_rationale(
        self,
        improving: List[Tuple[str, int]],
        declining: List[Tuple[str, int]],
        cycle: MarketCycle,
    ) -> str:
        """Generate rationale for sector rotation."""
        improving_names = [
            self.sectors[s]["name"] for s, _ in improving if s in self.sectors
        ]
        declining_names = [
            self.sectors[s]["name"] for s, _ in declining if s in self.sectors
        ]

        cycle_names = {
            MarketCycle.EARLY_EXPANSION: "초기 확장",
            MarketCycle.MID_EXPANSION: "중기 확장",
            MarketCycle.LATE_EXPANSION: "후기 확장",
            MarketCycle.EARLY_RECESSION: "초기 침체",
            MarketCycle.MID_RECESSION: "중기 침체",
            MarketCycle.LATE_RECESSION: "후기 침체",
        }

        return (
            f"경기 사이클 '{cycle_names[cycle]}' 단계에서 "
            f"{', '.join(improving_names)} 섹터가 강세를 보이고 있습니다. "
            f"{', '.join(declining_names)} 섹터에서 자금 이동이 감지됩니다."
        )

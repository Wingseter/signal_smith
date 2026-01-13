"""뉴스 관련 데이터 모델"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List


class NewsSentiment(str, Enum):
    """뉴스 감성 분류"""
    VERY_POSITIVE = "very_positive"  # 8-10점
    POSITIVE = "positive"            # 6-7점
    NEUTRAL = "neutral"              # 4-5점
    NEGATIVE = "negative"            # 2-3점
    VERY_NEGATIVE = "very_negative"  # 1점


class NewsCategory(str, Enum):
    """뉴스 카테고리"""
    CONTRACT = "contract"           # 계약체결
    BONUS_STOCK = "bonus_stock"     # 무상증자
    EARNINGS = "earnings"           # 실적발표
    MANAGEMENT = "management"       # 경영권, M&A
    REGULATION = "regulation"       # 규제, 정책
    MARKET = "market"               # 시장동향
    OTHER = "other"                 # 기타


@dataclass
class NewsArticle:
    """뉴스 기사"""
    title: str
    url: str
    source: str
    published_at: datetime
    symbol: Optional[str] = None          # 관련 종목코드
    company_name: Optional[str] = None    # 관련 회사명
    content: Optional[str] = None         # 본문 (크롤링 시)
    summary: Optional[str] = None         # 요약
    category: NewsCategory = NewsCategory.OTHER
    keywords: List[str] = field(default_factory=list)


@dataclass
class NewsAnalysisResult:
    """뉴스 분석 결과"""
    article: NewsArticle
    score: int                            # 1-10점
    sentiment: NewsSentiment
    confidence: float                     # 분석 신뢰도 0-1
    analysis_reason: str                  # 분석 근거
    trading_signal: Optional[str] = None  # BUY, SELL, HOLD
    analyzed_at: datetime = field(default_factory=datetime.now)
    analyzer: str = "gemini"              # gemini or tavily


@dataclass
class DeepAnalysisResult:
    """심층 분석 결과 (Tavily)"""
    symbol: str
    company_name: str
    news_summary: str                     # 종합 뉴스 요약
    sentiment_score: int                  # 1-10점
    key_findings: List[str]               # 주요 발견사항
    risk_factors: List[str]               # 위험 요소
    opportunity_factors: List[str]        # 기회 요소
    recommendation: str                   # 투자 권고
    sources: List[str]                    # 참고 출처
    analyzed_at: datetime = field(default_factory=datetime.now)


# 트리거 키워드 설정
TRIGGER_KEYWORDS = {
    NewsCategory.CONTRACT: [
        "계약", "수주", "공급계약", "납품", "MOU", "협약",
        "대형계약", "신규계약", "계약체결"
    ],
    NewsCategory.BONUS_STOCK: [
        "무상증자", "주식배당", "액면분할", "주식분할"
    ],
    NewsCategory.EARNINGS: [
        "실적", "매출", "영업이익", "순이익", "흑자전환",
        "적자전환", "어닝서프라이즈", "실적발표", "분기실적"
    ],
    NewsCategory.MANAGEMENT: [
        "인수", "합병", "M&A", "경영권", "지분", "대주주",
        "최대주주", "경영참여"
    ],
    NewsCategory.REGULATION: [
        "규제", "허가", "승인", "인허가", "FDA", "식약처",
        "정책", "법안"
    ],
    NewsCategory.MARKET: [
        # 시장 동향 키워드 추가 - 주가 움직임 관련
        "급등", "급락", "상승", "하락", "돌파", "신고가", "신저가",
        "상한가", "하한가", "폭등", "폭락", "랠리", "조정",
        # 투자 관련
        "매수", "매도", "외국인", "기관", "개인", "공매도",
        # 시장 지표
        "코스피", "코스닥", "나스닥", "다우", "증시",
    ],
}

# 긍정/부정 키워드
POSITIVE_KEYWORDS = [
    "급등", "상승", "호재", "흑자", "성장", "신고가",
    "대박", "수혜", "호황", "상한가", "돌파"
]

NEGATIVE_KEYWORDS = [
    "급락", "하락", "악재", "적자", "감소", "신저가",
    "폭락", "하한가", "손실", "부진", "위기"
]

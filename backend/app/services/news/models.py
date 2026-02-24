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


# 한국 주요 종목 매핑 (회사명 → 종목코드)
# Gemini가 회사명만 추출해도 종목코드를 찾을 수 있도록
KOREAN_STOCK_MAP = {
    # 대형주 (KOSPI 시가총액 상위)
    "삼성전자": "005930",
    "SK하이닉스": "000660",
    "LG에너지솔루션": "373220",
    "삼성바이오로직스": "207940",
    "삼성SDI": "006400",
    "현대차": "005380",
    "현대자동차": "005380",
    "기아": "000270",
    "기아차": "000270",
    "셀트리온": "068270",
    "KB금융": "105560",
    "신한지주": "055550",
    "POSCO홀딩스": "005490",
    "포스코홀딩스": "005490",
    "NAVER": "035420",
    "네이버": "035420",
    "카카오": "035720",
    "LG화학": "051910",
    "현대모비스": "012330",
    "삼성물산": "028260",
    "삼성생명": "032830",
    "하나금융지주": "086790",
    "삼성화재": "000810",
    "LG전자": "066570",
    "SK이노베이션": "096770",
    "SK텔레콤": "017670",
    "SK": "034730",
    "KT": "030200",
    "KT&G": "033780",
    "삼성전기": "009150",
    "한국전력": "015760",
    "한전": "015760",
    "두산에너빌리티": "034020",
    "SK바이오팜": "326030",
    "크래프톤": "259960",
    "삼성에스디에스": "018260",
    "삼성SDS": "018260",
    "LG디스플레이": "034220",
    "고려아연": "010130",
    "HMM": "011200",
    "HD현대중공업": "329180",
    "현대중공업": "329180",
    "HD한국조선해양": "009540",
    "한국조선해양": "009540",
    "대한항공": "003490",
    "아모레퍼시픽": "090430",
    "LG생활건강": "051900",
    "엔씨소프트": "036570",
    "넷마블": "251270",
    "카카오뱅크": "323410",
    "카카오페이": "377300",
    "SK스퀘어": "402340",
    "에코프로비엠": "247540",
    "에코프로": "086520",
    "포스코퓨처엠": "003670",
    "LG이노텍": "011070",
    "SK아이이테크놀로지": "361610",
    "SK IE Technology": "361610",
    "한화솔루션": "009830",
    "한화에어로스페이스": "012450",
    "한화": "000880",
    "롯데케미칼": "011170",
    "CJ제일제당": "097950",
    "현대건설": "000720",
    "GS건설": "006360",
    "두산밥캣": "241560",
    "OCI": "010060",
    "삼성중공업": "010140",
    "한미약품": "128940",
    "유한양행": "000100",
    "녹십자": "006280",
    "셀트리온헬스케어": "091990",
    "삼성바이오에피스": "207940",  # 삼성바이오로직스 자회사
    "SK케미칼": "285130",
    "CJ ENM": "035760",
    "스튜디오드래곤": "253450",
    "하이브": "352820",
    "JYP엔터테인먼트": "035900",
    "JYP": "035900",
    "SM엔터테인먼트": "041510",
    "SM": "041510",
    "와이지엔터테인먼트": "122870",
    "YG": "122870",

    # 화장품/생활용품
    "코스맥스": "044820",
    "한국콜마": "161890",
    "아모레퍼시픽": "090430",
    "LG생활건강": "051900",

    # KOSDAQ 인기 종목
    "펄어비스": "263750",
    "CJ ENM": "035760",
    "카카오게임즈": "293490",
    "HLB": "028300",
    "알테오젠": "196170",
    "리노공업": "058470",
    "솔브레인": "357780",
    "원익IPS": "240810",
    "파크시스템스": "140860",
    "클래시스": "214150",
    "케이엠더블유": "032500",
    "씨젠": "096530",
    "메드팩토": "235980",
    "셀리버리": "268600",
    "엘앤에프": "066970",
    "레인보우로보틱스": "277810",
    "로보티즈": "108490",
    "두산로보틱스": "454910",

    # 2차전지/반도체 테마
    "LG에너지솔루션": "373220",
    "에코프로비엠": "247540",
    "포스코퓨처엠": "003670",
    "삼성SDI": "006400",
    "SK온": "373220",  # LG에너지솔루션과 동일 (예시)
    "CSLG": "003610",  # 천보 (2차전지 소재)
    "천보": "278280",
    "코스모신소재": "005070",
    "일진머티리얼즈": "020150",
    "솔루스첨단소재": "336370",
    "SK넥실리스": "000670",
    "후성": "093370",

    # 바이오/제약
    "삼성바이오로직스": "207940",
    "셀트리온": "068270",
    "SK바이오사이언스": "302440",
    "유한양행": "000100",
    "녹십자": "006280",
    "종근당": "185750",
    "대웅제약": "069620",
    "한미약품": "128940",
    "GC녹십자": "006280",

    # 조선/해운
    "HD현대중공업": "329180",
    "삼성중공업": "010140",
    "한화오션": "042660",
    "HMM": "011200",
    "팬오션": "028670",

    # 자동차/부품
    "현대차": "005380",
    "기아": "000270",
    "현대모비스": "012330",
    "현대위아": "011210",
    "만도": "204320",
    "한온시스템": "018880",
    "현대오토에버": "307950",
    "HL만도": "204320",

    # 금융
    "KB금융": "105560",
    "신한지주": "055550",
    "하나금융지주": "086790",
    "우리금융지주": "316140",
    "삼성생명": "032830",
    "삼성화재": "000810",
    "DB손해보험": "005830",
    "미래에셋증권": "006800",
    "NH투자증권": "005940",
    "키움증권": "039490",

    # 건설/인프라
    "삼성물산": "028260",
    "현대건설": "000720",
    "GS건설": "006360",
    "대우건설": "047040",
    "DL이앤씨": "375500",
    "HDC현대산업개발": "294870",

    # IT/플랫폼
    "네이버": "035420",
    "카카오": "035720",
    "쿠팡": "CPNG",  # 미국상장
    "배달의민족": "N/A",  # 비상장
    "토스": "N/A",  # 비상장
    "야놀자": "N/A",  # 비상장
}


def lookup_stock_code(company_name: str) -> str | None:
    """회사명으로 종목코드 조회"""
    if not company_name:
        return None

    # 정확한 매칭
    if company_name in KOREAN_STOCK_MAP:
        code = KOREAN_STOCK_MAP[company_name]
        return code if code != "N/A" else None

    # 부분 매칭 (회사명이 포함된 경우)
    for name, code in KOREAN_STOCK_MAP.items():
        if name in company_name or company_name in name:
            return code if code != "N/A" else None

    return None


# 역방향 매핑 (종목코드 → 회사명) - 자동 생성
_REVERSE_STOCK_MAP: dict[str, str] = {}
for _name, _code in KOREAN_STOCK_MAP.items():
    if _code != "N/A" and _code not in _REVERSE_STOCK_MAP:
        _REVERSE_STOCK_MAP[_code] = _name


def lookup_company_name(symbol: str) -> str | None:
    """종목코드로 회사명 조회"""
    if not symbol:
        return None
    return _REVERSE_STOCK_MAP.get(symbol)

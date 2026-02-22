"""Application-wide constants.

Centralizes magic numbers previously scattered across task modules
and service code.
"""

# ── Council defaults ──
DEFAULT_MIN_CONFIDENCE = 0.6
DEFAULT_COUNCIL_THRESHOLD = 7
DEFAULT_SELL_THRESHOLD = 3
DEFAULT_MAX_POSITION_PER_STOCK = 500_000

# ── Signal scanning ──
SCAN_UNIVERSE_LIMIT = 500
MAX_CONCURRENT_SCANS = 5

# ── Sell monitoring ──
SELL_COOLDOWN_SECONDS = 1800  # 30 minutes
STOP_LOSS_DEFAULT_PERCENT = 5.0
TAKE_PROFIT_DEFAULT_PERCENT = 20.0

# ── Fallback blue-chip symbols ──
FALLBACK_SYMBOLS = [
    "005930",  # 삼성전자
    "000660",  # SK하이닉스
    "035420",  # NAVER
    "035720",  # 카카오
    "051910",  # LG화학
    "006400",  # 삼성SDI
    "005380",  # 현대자동차
    "068270",  # 셀트리온
    "028260",  # 삼성물산
    "207940",  # 삼성바이오로직스
]

# ── API analysis limits ──
ANALYST_TIMEOUT_SECONDS = 15
MAX_WATCHLIST_ANALYSIS = 10
NEWS_SENTIMENT_CACHE_TTL = 300  # 5 minutes
STOCK_UNIVERSE_CACHE_TTL = 86400  # 24 hours

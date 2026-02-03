"""
AI 투자 회의 시스템

멀티 AI가 협력하여 투자 결정을 내리는 회의 시스템
- Gemini: 뉴스 판단 및 회의 소집
- GPT: 퀀트/기술적 분석
- Claude: 펀더멘털 분석

v2: 자동 매매, SELL 시그널, 거래 시간 체크 추가
"""

from .models import (
    CouncilMeeting,
    CouncilMessage,
    InvestmentSignal,
    SignalStatus,
)
from .quant_analyst import QuantAnalyst, quant_analyst
from .fundamental_analyst import FundamentalAnalyst, fundamental_analyst
from .orchestrator import CouncilOrchestrator, council_orchestrator
from .trading_hours import TradingHoursChecker, trading_hours, MarketSession
from .cost_manager import CostManager, cost_manager, AnalysisDepth
from .portfolio_analyzer import PortfolioAnalyzer, portfolio_analyzer

__all__ = [
    "CouncilMeeting",
    "CouncilMessage",
    "InvestmentSignal",
    "SignalStatus",
    "QuantAnalyst",
    "quant_analyst",
    "FundamentalAnalyst",
    "fundamental_analyst",
    "CouncilOrchestrator",
    "council_orchestrator",
    "TradingHoursChecker",
    "trading_hours",
    "MarketSession",
    "CostManager",
    "cost_manager",
    "AnalysisDepth",
    "PortfolioAnalyzer",
    "portfolio_analyzer",
]

"""
AI 투자 회의 시스템

멀티 AI가 협력하여 투자 결정을 내리는 회의 시스템
- Sonnet: 뉴스 분석 및 트리거
- GPT: 퀀트/기술적 분석 + 반대론자
- Claude Opus: 펀더멘털 분석 + 최종 판결

v3: 반대론자 추가, Gemini→Sonnet 전환
"""

from .models import (
    CouncilMeeting,
    CouncilMessage,
    InvestmentSignal,
    SignalStatus,
)
from .quant_analyst import QuantAnalyst, quant_analyst
from .fundamental_analyst import FundamentalAnalyst, fundamental_analyst
from .devils_advocate import DevilsAdvocate, devils_advocate
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
    "DevilsAdvocate",
    "devils_advocate",
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

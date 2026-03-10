"""AI 투자 회의 데이터 모델"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List
import uuid


class SignalStatus(str, Enum):
    """시그널 상태"""
    PENDING = "pending"          # 승인 대기
    APPROVED = "approved"        # 승인됨
    REJECTED = "rejected"        # 거부됨
    EXECUTED = "executed"        # 체결됨
    EXPIRED = "expired"          # 만료됨
    AUTO_EXECUTED = "auto_executed"  # 자동 체결됨
    QUEUED = "queued"            # 자동매매 구매 대기 (거래시간 외)


class AnalystRole(str, Enum):
    """분석가 역할"""
    GEMINI_JUDGE = "gemini_judge"       # 뉴스 트리거 (레거시 명칭 유지)
    GPT_QUANT = "gpt_quant"             # GPT: 퀀트 분석
    CLAUDE_FUNDAMENTAL = "claude_fundamental"  # Claude: 펀더멘털 분석
    GPT_DEVILS_ADVOCATE = "gpt_devils_advocate"  # GPT: 반대론자
    MODERATOR = "moderator"             # 중재자 (합의 도출)


@dataclass
class CouncilMessage:
    """회의 메시지"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    role: AnalystRole = AnalystRole.MODERATOR
    speaker: str = ""                    # 발언자 이름
    content: str = ""                    # 발언 내용
    data: Optional[dict] = None          # 분석 데이터 (차트, 지표 등)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "role": self.role.value,
            "speaker": self.speaker,
            "content": self.content,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class InvestmentSignal:
    """투자 시그널"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    symbol: str = ""                     # 종목코드
    company_name: str = ""               # 회사명
    action: str = "BUY"                  # BUY, SELL, HOLD

    # 투자 비율 및 금액
    allocation_percent: float = 0.0      # 총 자금 대비 비율 (%)
    suggested_amount: int = 0            # 제안 금액
    suggested_quantity: int = 0          # 제안 수량
    target_price: Optional[int] = None   # 목표가
    stop_loss_price: Optional[int] = None  # 손절가

    # 분석 요약
    quant_summary: str = ""              # 퀀트 분석 요약
    fundamental_summary: str = ""        # 펀더멘털 분석 요약
    consensus_reason: str = ""           # 합의 근거

    # 신뢰도
    confidence: float = 0.0              # 0-1
    quant_score: int = 0                 # 1-10
    fundamental_score: int = 0           # 1-10

    # 상태
    status: SignalStatus = SignalStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    executed_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "symbol": self.symbol,
            "company_name": self.company_name,
            "action": self.action,
            "allocation_percent": self.allocation_percent,
            "suggested_amount": self.suggested_amount,
            "suggested_quantity": self.suggested_quantity,
            "target_price": self.target_price,
            "stop_loss_price": self.stop_loss_price,
            "quant_summary": self.quant_summary,
            "fundamental_summary": self.fundamental_summary,
            "consensus_reason": self.consensus_reason,
            "confidence": self.confidence,
            "quant_score": self.quant_score,
            "fundamental_score": self.fundamental_score,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
        }


@dataclass
class CouncilMeeting:
    """AI 투자 회의"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    # 회의 대상
    symbol: str = ""
    company_name: str = ""
    news_title: str = ""                 # 트리거 뉴스/퀀트 설명
    news_score: int = 0                  # Gemini 뉴스 점수
    trigger_source: str = "news"         # 트리거 소스: "news" | "quant"

    # 회의 진행
    messages: List[CouncilMessage] = field(default_factory=list)
    current_round: int = 0               # 현재 라운드 (최대 3라운드)
    max_rounds: int = 3

    # 결과
    signal: Optional[InvestmentSignal] = None
    consensus_reached: bool = False

    # 메타
    started_at: datetime = field(default_factory=datetime.now)
    ended_at: Optional[datetime] = None

    def add_message(self, message: CouncilMessage):
        """메시지 추가"""
        self.messages.append(message)

    def get_transcript(self) -> str:
        """회의록 텍스트 생성"""
        lines = [
            f"═══════════════════════════════════════════",
            f"📋 AI 투자 회의록",
            f"═══════════════════════════════════════════",
            f"회의 ID: {self.id}",
            f"종목: {self.company_name} ({self.symbol})",
            f"트리거 뉴스: {self.news_title}",
            f"뉴스 점수: {self.news_score}/10",
            f"시작 시간: {self.started_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"───────────────────────────────────────────",
            "",
        ]

        for msg in self.messages:
            emoji = {
                AnalystRole.GEMINI_JUDGE: "🔔",
                AnalystRole.GPT_QUANT: "📊",
                AnalystRole.CLAUDE_FUNDAMENTAL: "📈",
                AnalystRole.GPT_DEVILS_ADVOCATE: "😈",
                AnalystRole.MODERATOR: "⚖️",
            }.get(msg.role, "💬")

            lines.append(f"{emoji} [{msg.speaker}]")
            lines.append(msg.content)
            lines.append("")

        if self.signal:
            lines.extend([
                f"───────────────────────────────────────────",
                f"📌 최종 결론",
                f"───────────────────────────────────────────",
                f"행동: {self.signal.action}",
                f"투자 비율: {self.signal.allocation_percent}%",
                f"제안 금액: {self.signal.suggested_amount:,}원",
                f"신뢰도: {self.signal.confidence:.0%}",
                f"",
                f"퀀트 분석: {self.signal.quant_summary}",
                f"펀더멘털 분석: {self.signal.fundamental_summary}",
                f"합의 근거: {self.signal.consensus_reason}",
            ])

        if self.ended_at:
            lines.append(f"")
            lines.append(f"종료 시간: {self.ended_at.strftime('%Y-%m-%d %H:%M:%S')}")

        lines.append(f"═══════════════════════════════════════════")

        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "symbol": self.symbol,
            "company_name": self.company_name,
            "news_title": self.news_title,
            "news_score": self.news_score,
            "trigger_source": self.trigger_source,
            "messages": [m.to_dict() for m in self.messages],
            "current_round": self.current_round,
            "max_rounds": self.max_rounds,
            "signal": self.signal.to_dict() if self.signal else None,
            "consensus_reached": self.consensus_reached,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "transcript": self.get_transcript(),
        }

import { useState, useEffect, useRef, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { councilApi, councilWebSocket } from '../../services/api';

interface CouncilMessage {
  id: string;
  role: string;
  speaker: string;
  content: string;
  data: Record<string, unknown> | null;
  timestamp: string;
}

interface InvestmentSignal {
  id: string;
  symbol: string;
  company_name: string;
  action: string;
  allocation_percent: number;
  suggested_amount: number;
  suggested_quantity: number;
  target_price: number | null;
  stop_loss_price: number | null;
  quant_summary: string;
  fundamental_summary: string;
  consensus_reason: string;
  confidence: number;
  quant_score: number;
  fundamental_score: number;
  status: string;
  created_at: string;
  executed_at: string | null;
}

interface CouncilMeeting {
  id: string;
  symbol: string;
  company_name: string;
  news_title: string;
  news_score: number;
  messages: CouncilMessage[];
  current_round: number;
  max_rounds: number;
  signal: InvestmentSignal | null;
  consensus_reached: boolean;
  started_at: string;
  ended_at: string | null;
  transcript: string;
}

interface TradingStatus {
  session: string;
  can_trade: boolean;
  reason: string;
  status_message: string;
  queued_count: number;
  auto_execute: boolean;
  respect_trading_hours: boolean;
}

interface CostStats {
  daily_cost: number;
  monthly_cost: number;
  daily_remaining: number;
  monthly_remaining: number;
  daily_limit: number;
  monthly_limit: number;
}

interface CouncilStatus {
  running: boolean;
  auto_execute: boolean;
  council_threshold: number;
  pending_signals: number;
  total_meetings: number;
  daily_trades: number;
  monitor_running: boolean;
  trading?: TradingStatus;
  cost?: CostStats;
}

interface CouncilConfig {
  council_threshold: number;
  sell_threshold: number;
  auto_execute: boolean;
  max_position_per_stock: number;
  poll_interval: number;
}

// AI 분석가 정보 - 각 AI의 역할과 분석 방법론 설명
const AI_ANALYSTS = {
  gemini_judge: {
    name: 'Gemini',
    role: '뉴스/심리 분석가',
    icon: '🔔',
    color: 'blue',
    bgColor: 'bg-blue-50',
    borderColor: 'border-blue-200',
    textColor: 'text-blue-700',
    gradientFrom: 'from-blue-500',
    gradientTo: 'to-blue-600',
    description: '실시간 뉴스와 시장 심리를 분석하여 투자 기회를 발굴합니다.',
    methodology: [
      '뉴스 헤드라인 감성 분석',
      '소셜 미디어 트렌드 모니터링',
      '시장 심리 지표 (VIX, Put/Call Ratio) 분석',
      '이벤트 드리븐 투자 기회 포착'
    ],
    strengths: ['빠른 뉴스 대응', '시장 심리 파악', '이벤트 분석'],
    avatar: '🤖'
  },
  gpt_quant: {
    name: 'GPT',
    role: '퀀트/기술적 분석가',
    icon: '📊',
    color: 'green',
    bgColor: 'bg-green-50',
    borderColor: 'border-green-200',
    textColor: 'text-green-700',
    gradientFrom: 'from-green-500',
    gradientTo: 'to-green-600',
    description: '기술적 지표와 수학적 모델로 매매 타이밍을 분석합니다.',
    methodology: [
      'RSI, MACD, Bollinger Bands 등 기술적 지표',
      '이동평균선 교차 분석',
      '거래량 패턴 및 가격 모멘텀 분석',
      '통계적 아비트라지 기회 탐색'
    ],
    strengths: ['정밀한 진입/청산 타이밍', '리스크 수치화', '패턴 인식'],
    avatar: '🧮'
  },
  claude_fundamental: {
    name: 'Claude',
    role: '펀더멘털 분석가',
    icon: '📈',
    color: 'purple',
    bgColor: 'bg-purple-50',
    borderColor: 'border-purple-200',
    textColor: 'text-purple-700',
    gradientFrom: 'from-purple-500',
    gradientTo: 'to-purple-600',
    description: '기업의 재무제표와 내재가치를 분석하여 장기 투자 가치를 평가합니다.',
    methodology: [
      'PER, PBR, ROE 등 가치평가 지표 분석',
      '재무제표 심층 분석 (수익성, 안정성, 성장성)',
      '산업 경쟁력 및 해자(Moat) 분석',
      'DCF 및 상대가치 평가 모델'
    ],
    strengths: ['기업 내재가치 평가', '장기 투자 관점', '리스크 분석'],
    avatar: '📚'
  },
  moderator: {
    name: '조정자',
    role: '회의 진행자',
    icon: '⚖️',
    color: 'yellow',
    bgColor: 'bg-yellow-50',
    borderColor: 'border-yellow-200',
    textColor: 'text-yellow-700',
    gradientFrom: 'from-yellow-500',
    gradientTo: 'to-yellow-600',
    description: '3개 AI의 의견을 종합하여 최종 투자 결정을 조율합니다.',
    methodology: [
      '다수결 및 가중 투표 시스템',
      '의견 충돌 시 중재 및 조정',
      '리스크/리턴 균형 최적화',
      '최종 합의 도출 및 시그널 생성'
    ],
    strengths: ['균형 잡힌 결정', '리스크 관리', '합의 도출'],
    avatar: '👨‍⚖️'
  }
};

// AI 분석가 소개 카드 컴포넌트
function AIAnalystCard({
  analyst,
  isExpanded,
  onToggle
}: {
  analyst: typeof AI_ANALYSTS.gemini_judge;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  return (
    <div
      className={`rounded-xl border-2 ${analyst.borderColor} overflow-hidden transition-all duration-300 ${
        isExpanded ? 'shadow-lg' : 'shadow-sm hover:shadow-md'
      }`}
    >
      <div
        className={`bg-gradient-to-r ${analyst.gradientFrom} ${analyst.gradientTo} p-4 cursor-pointer`}
        onClick={onToggle}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <span className="text-3xl">{analyst.avatar}</span>
            <div>
              <h3 className="font-bold text-white text-lg">{analyst.name}</h3>
              <p className="text-white/80 text-sm">{analyst.role}</p>
            </div>
          </div>
          <span className="text-white text-xl">
            {isExpanded ? '▲' : '▼'}
          </span>
        </div>
      </div>

      {isExpanded && (
        <div className={`${analyst.bgColor} p-4 space-y-4`}>
          <p className="text-gray-700 text-sm">{analyst.description}</p>

          <div>
            <h4 className="font-semibold text-gray-800 text-sm mb-2">📋 분석 방법론</h4>
            <ul className="space-y-1">
              {analyst.methodology.map((method, idx) => (
                <li key={idx} className="text-xs text-gray-600 flex items-start">
                  <span className="text-gray-400 mr-2">•</span>
                  {method}
                </li>
              ))}
            </ul>
          </div>

          <div>
            <h4 className="font-semibold text-gray-800 text-sm mb-2">💪 강점</h4>
            <div className="flex flex-wrap gap-2">
              {analyst.strengths.map((strength, idx) => (
                <span
                  key={idx}
                  className={`px-2 py-1 rounded-full text-xs font-medium ${analyst.bgColor} ${analyst.textColor} border ${analyst.borderColor}`}
                >
                  {strength}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// AI 팀 소개 섹션
function AITeamIntroduction() {
  const [expandedAnalyst, setExpandedAnalyst] = useState<string | null>(null);
  const [showGuide, setShowGuide] = useState(false);

  return (
    <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
      <div
        className="p-4 bg-gradient-to-r from-indigo-600 to-purple-600 cursor-pointer"
        onClick={() => setShowGuide(!showGuide)}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <span className="text-2xl">🤖</span>
            <div>
              <h2 className="font-bold text-white text-lg">AI 투자 위원회 소개</h2>
              <p className="text-white/80 text-sm">3개의 전문 AI가 협력하여 최적의 투자 결정을 내립니다</p>
            </div>
          </div>
          <span className="text-white">{showGuide ? '▲ 접기' : '▼ 펼치기'}</span>
        </div>
      </div>

      {showGuide && (
        <div className="p-6 space-y-6">
          {/* 투자 결정 프로세스 설명 */}
          <div className="bg-gray-50 rounded-lg p-4">
            <h3 className="font-bold text-gray-800 mb-3">🔄 AI 투자 결정 프로세스</h3>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="text-center">
                <div className="w-12 h-12 mx-auto bg-blue-100 rounded-full flex items-center justify-center mb-2">
                  <span className="text-xl">📰</span>
                </div>
                <p className="text-sm font-medium text-gray-800">1. 뉴스 감지</p>
                <p className="text-xs text-gray-500">Gemini가 중요 뉴스 발굴</p>
              </div>
              <div className="text-center">
                <div className="w-12 h-12 mx-auto bg-green-100 rounded-full flex items-center justify-center mb-2">
                  <span className="text-xl">📊</span>
                </div>
                <p className="text-sm font-medium text-gray-800">2. 기술적 분석</p>
                <p className="text-xs text-gray-500">GPT가 차트/지표 분석</p>
              </div>
              <div className="text-center">
                <div className="w-12 h-12 mx-auto bg-purple-100 rounded-full flex items-center justify-center mb-2">
                  <span className="text-xl">📈</span>
                </div>
                <p className="text-sm font-medium text-gray-800">3. 가치 평가</p>
                <p className="text-xs text-gray-500">Claude가 기업가치 분석</p>
              </div>
              <div className="text-center">
                <div className="w-12 h-12 mx-auto bg-yellow-100 rounded-full flex items-center justify-center mb-2">
                  <span className="text-xl">⚖️</span>
                </div>
                <p className="text-sm font-medium text-gray-800">4. 합의 도출</p>
                <p className="text-xs text-gray-500">최종 투자 시그널 생성</p>
              </div>
            </div>
          </div>

          {/* AI 분석가 카드들 */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {Object.entries(AI_ANALYSTS).map(([key, analyst]) => (
              <AIAnalystCard
                key={key}
                analyst={analyst}
                isExpanded={expandedAnalyst === key}
                onToggle={() => setExpandedAnalyst(expandedAnalyst === key ? null : key)}
              />
            ))}
          </div>

          {/* 신뢰도 지표 설명 */}
          <div className="bg-gradient-to-r from-gray-50 to-gray-100 rounded-lg p-4">
            <h3 className="font-bold text-gray-800 mb-3">📊 신뢰도 지표 이해하기</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
              <div className="bg-white rounded-lg p-3 border">
                <div className="flex items-center space-x-2 mb-2">
                  <span className="text-green-600 font-bold">퀀트 점수</span>
                  <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded">GPT</span>
                </div>
                <p className="text-gray-600 text-xs">기술적 지표 기반 점수입니다. RSI, MACD 등의 신호 강도를 0-100으로 수치화합니다.</p>
              </div>
              <div className="bg-white rounded-lg p-3 border">
                <div className="flex items-center space-x-2 mb-2">
                  <span className="text-purple-600 font-bold">펀더멘털 점수</span>
                  <span className="text-xs bg-purple-100 text-purple-700 px-2 py-0.5 rounded">Claude</span>
                </div>
                <p className="text-gray-600 text-xs">재무제표 기반 가치평가 점수입니다. PER, ROE 등을 종합하여 0-100으로 평가합니다.</p>
              </div>
              <div className="bg-white rounded-lg p-3 border">
                <div className="flex items-center space-x-2 mb-2">
                  <span className="text-indigo-600 font-bold">종합 신뢰도</span>
                  <span className="text-xs bg-indigo-100 text-indigo-700 px-2 py-0.5 rounded">합의</span>
                </div>
                <p className="text-gray-600 text-xs">3개 AI의 의견 일치도입니다. 60% 이상이면 자동 체결이 가능합니다.</p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// 개선된 메시지 버블 - AI별 특색 강화
function MessageBubble({ message }: { message: CouncilMessage }) {
  const analyst = AI_ANALYSTS[message.role as keyof typeof AI_ANALYSTS] || {
    name: message.speaker,
    bgColor: 'bg-gray-50',
    borderColor: 'border-gray-200',
    textColor: 'text-gray-700',
    icon: '💬',
    avatar: '🤖'
  };

  return (
    <div className={`p-4 rounded-xl border-2 ${analyst.borderColor} ${analyst.bgColor} mb-4 transition-all hover:shadow-md`}>
      <div className="flex items-start space-x-3">
        <div className={`w-10 h-10 rounded-full bg-gradient-to-br ${analyst.gradientFrom || 'from-gray-400'} ${analyst.gradientTo || 'to-gray-500'} flex items-center justify-center flex-shrink-0`}>
          <span className="text-lg">{analyst.avatar || analyst.icon}</span>
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center space-x-2">
              <span className={`font-bold ${analyst.textColor}`}>{analyst.name || message.speaker}</span>
              {analyst.role && (
                <span className={`text-xs px-2 py-0.5 rounded-full ${analyst.bgColor} ${analyst.textColor} border ${analyst.borderColor}`}>
                  {analyst.role}
                </span>
              )}
            </div>
            <span className="text-xs text-gray-400">
              {new Date(message.timestamp).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })}
            </span>
          </div>
          <div className="text-gray-700 whitespace-pre-wrap text-sm leading-relaxed">
            {message.content}
          </div>
        </div>
      </div>
    </div>
  );
}

// 개선된 시그널 카드 - 더 상세한 정보와 시각화
function SignalCard({
  signal,
  onApprove,
  onReject,
  onExecute,
  isLoading
}: {
  signal: InvestmentSignal;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
  onExecute: (id: string) => void;
  isLoading: boolean;
}) {
  const [showDetail, setShowDetail] = useState(false);

  const statusConfig: Record<string, { bg: string; text: string; label: string; icon: string }> = {
    pending: { bg: 'bg-yellow-100', text: 'text-yellow-800', label: '승인 대기', icon: '⏳' },
    queued: { bg: 'bg-orange-100', text: 'text-orange-800', label: '구매 대기', icon: '🕐' },
    approved: { bg: 'bg-blue-100', text: 'text-blue-800', label: '승인됨', icon: '✅' },
    rejected: { bg: 'bg-red-100', text: 'text-red-800', label: '거부됨', icon: '❌' },
    executed: { bg: 'bg-green-100', text: 'text-green-800', label: '체결됨', icon: '💰' },
    auto_executed: { bg: 'bg-green-100', text: 'text-green-800', label: '자동 체결', icon: '🤖' },
  };

  const status = statusConfig[signal.status] || { bg: 'bg-gray-100', text: 'text-gray-800', label: signal.status, icon: '📋' };

  // 신뢰도에 따른 색상
  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.8) return 'text-green-600 bg-green-50';
    if (confidence >= 0.6) return 'text-blue-600 bg-blue-50';
    if (confidence >= 0.4) return 'text-yellow-600 bg-yellow-50';
    return 'text-red-600 bg-red-50';
  };

  return (
    <div className="bg-white rounded-xl border-2 shadow-sm hover:shadow-lg transition-all overflow-hidden">
      {/* 헤더 */}
      <div className={`p-4 ${signal.action === 'BUY' ? 'bg-gradient-to-r from-green-500 to-emerald-600' : signal.action === 'SELL' ? 'bg-gradient-to-r from-red-500 to-rose-600' : 'bg-gradient-to-r from-gray-500 to-gray-600'}`}>
        <div className="flex justify-between items-start">
          <div className="text-white">
            <div className="flex items-center space-x-2">
              <span className="text-2xl font-bold">
                {signal.action === 'BUY' ? '📈 매수' : signal.action === 'SELL' ? '📉 매도' : '📊 보유'}
              </span>
            </div>
            <h3 className="text-xl font-bold mt-1">{signal.company_name}</h3>
            <span className="text-white/80 text-sm">{signal.symbol}</span>
          </div>
          <span className={`px-3 py-1 rounded-full text-xs font-bold ${status.bg} ${status.text}`}>
            {status.icon} {status.label}
          </span>
        </div>
      </div>

      {/* 주요 지표 */}
      <div className="p-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
          <div className="text-center p-3 bg-gray-50 rounded-lg">
            <p className="text-xs text-gray-500 mb-1">투자 비율</p>
            <p className="text-xl font-bold text-gray-800">{signal.allocation_percent.toFixed(1)}%</p>
          </div>
          <div className="text-center p-3 bg-gray-50 rounded-lg">
            <p className="text-xs text-gray-500 mb-1">제안 금액</p>
            <p className="text-xl font-bold text-gray-800">{(signal.suggested_amount / 10000).toFixed(0)}만원</p>
          </div>
          <div className={`text-center p-3 rounded-lg ${getConfidenceColor(signal.confidence)}`}>
            <p className="text-xs opacity-70 mb-1">종합 신뢰도</p>
            <p className="text-xl font-bold">{(signal.confidence * 100).toFixed(0)}%</p>
          </div>
          <div className="text-center p-3 bg-gray-50 rounded-lg">
            <p className="text-xs text-gray-500 mb-1">AI 점수</p>
            <div className="flex items-center justify-center space-x-1">
              <span className="text-green-600 font-bold">{signal.quant_score}</span>
              <span className="text-gray-400">/</span>
              <span className="text-purple-600 font-bold">{signal.fundamental_score}</span>
            </div>
          </div>
        </div>

        {/* AI 점수 시각화 바 */}
        <div className="space-y-2 mb-4">
          <div>
            <div className="flex justify-between items-center mb-1">
              <span className="text-xs text-green-600 font-medium">📊 퀀트 분석 (GPT)</span>
              <span className="text-xs text-gray-500">{signal.quant_score}/100</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className="bg-gradient-to-r from-green-400 to-green-600 h-2 rounded-full transition-all"
                style={{ width: `${signal.quant_score}%` }}
              />
            </div>
          </div>
          <div>
            <div className="flex justify-between items-center mb-1">
              <span className="text-xs text-purple-600 font-medium">📈 펀더멘털 분석 (Claude)</span>
              <span className="text-xs text-gray-500">{signal.fundamental_score}/100</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className="bg-gradient-to-r from-purple-400 to-purple-600 h-2 rounded-full transition-all"
                style={{ width: `${signal.fundamental_score}%` }}
              />
            </div>
          </div>
        </div>

        {/* 합의 이유 */}
        <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-3 mb-4">
          <p className="text-xs text-indigo-600 font-semibold mb-1">💡 AI 합의 이유</p>
          <p className="text-sm text-indigo-800">{signal.consensus_reason}</p>
        </div>

        {/* 상세 정보 토글 */}
        <button
          onClick={() => setShowDetail(!showDetail)}
          className="w-full text-center text-sm text-gray-500 hover:text-gray-700 py-2"
        >
          {showDetail ? '▲ 상세 정보 접기' : '▼ 상세 정보 보기'}
        </button>

        {showDetail && (
          <div className="mt-4 space-y-3 pt-4 border-t">
            {signal.quant_summary && (
              <div className="bg-green-50 rounded-lg p-3">
                <p className="text-xs text-green-600 font-semibold mb-1">📊 GPT 퀀트 분석 요약</p>
                <p className="text-sm text-green-800">{signal.quant_summary}</p>
              </div>
            )}
            {signal.fundamental_summary && (
              <div className="bg-purple-50 rounded-lg p-3">
                <p className="text-xs text-purple-600 font-semibold mb-1">📈 Claude 펀더멘털 분석 요약</p>
                <p className="text-sm text-purple-800">{signal.fundamental_summary}</p>
              </div>
            )}
            <div className="grid grid-cols-2 gap-3 text-sm">
              {signal.target_price && (
                <div className="bg-gray-50 rounded-lg p-2">
                  <span className="text-gray-500 text-xs">목표가</span>
                  <p className="font-bold text-gray-800">{signal.target_price.toLocaleString()}원</p>
                </div>
              )}
              {signal.stop_loss_price && (
                <div className="bg-gray-50 rounded-lg p-2">
                  <span className="text-gray-500 text-xs">손절가</span>
                  <p className="font-bold text-red-600">{signal.stop_loss_price.toLocaleString()}원</p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* 액션 버튼 */}
        {signal.status === 'pending' && (
          <div className="flex space-x-3 mt-4">
            <button
              onClick={() => onApprove(signal.id)}
              disabled={isLoading}
              className="flex-1 px-4 py-3 bg-gradient-to-r from-blue-500 to-blue-600 text-white rounded-xl text-sm font-bold hover:from-blue-600 hover:to-blue-700 disabled:opacity-50 transition-all shadow-md hover:shadow-lg"
            >
              ✅ 승인하기
            </button>
            <button
              onClick={() => onReject(signal.id)}
              disabled={isLoading}
              className="flex-1 px-4 py-3 bg-gray-100 text-gray-700 rounded-xl text-sm font-bold hover:bg-gray-200 disabled:opacity-50 transition-all"
            >
              ❌ 거부하기
            </button>
          </div>
        )}

        {signal.status === 'queued' && (
          <div className="mt-4 px-4 py-3 bg-orange-50 border border-orange-200 rounded-xl text-center">
            <p className="text-sm font-bold text-orange-700">🕐 장 개시 후 자동 체결 예정</p>
            <p className="text-xs text-orange-500 mt-1">거래 시간에 자동으로 주문이 실행됩니다</p>
          </div>
        )}

        {signal.status === 'approved' && (
          <button
            onClick={() => onExecute(signal.id)}
            disabled={isLoading}
            className="w-full mt-4 px-4 py-3 bg-gradient-to-r from-green-500 to-emerald-600 text-white rounded-xl text-sm font-bold hover:from-green-600 hover:to-emerald-700 disabled:opacity-50 transition-all shadow-md hover:shadow-lg"
          >
            💰 지금 체결하기
          </button>
        )}
      </div>
    </div>
  );
}

// 개선된 회의 뷰어
function MeetingViewer({
  meeting,
  onApproveSignal,
  onRejectSignal,
  onExecuteSignal,
  isLoading
}: {
  meeting: CouncilMeeting;
  onApproveSignal?: (signalId: string) => void;
  onRejectSignal?: (signalId: string) => void;
  onExecuteSignal?: (signalId: string) => void;
  isLoading?: boolean;
}) {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [meeting.messages]);

  // AI별 발언 횟수 계산
  const speakerStats = meeting.messages.reduce((acc, msg) => {
    acc[msg.role] = (acc[msg.role] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  return (
    <div className="bg-white rounded-xl border-2 shadow-lg overflow-hidden">
      {/* 회의 헤더 */}
      <div className="bg-gradient-to-r from-indigo-600 to-purple-600 p-5">
        <div className="flex justify-between items-start">
          <div className="text-white">
            <div className="flex items-center space-x-2">
              <span className="text-2xl">🏛️</span>
              <h3 className="font-bold text-xl">{meeting.company_name}</h3>
              <span className="text-white/70">({meeting.symbol})</span>
            </div>
            <p className="text-white/80 text-sm mt-2 max-w-lg">{meeting.news_title}</p>
          </div>
          <div className="text-right">
            <span className={`px-3 py-1 rounded-full text-sm font-bold ${
              meeting.consensus_reached
                ? 'bg-green-100 text-green-800'
                : 'bg-yellow-100 text-yellow-800'
            }`}>
              {meeting.consensus_reached ? '✅ 합의 완료' : `🔄 라운드 ${meeting.current_round}/${meeting.max_rounds}`}
            </span>
            <p className="text-white/70 text-xs mt-2">
              뉴스 중요도: {'⭐'.repeat(Math.round(meeting.news_score / 2))} ({meeting.news_score}/10)
            </p>
          </div>
        </div>

        {/* AI 참여 현황 */}
        <div className="flex items-center space-x-4 mt-4 pt-4 border-t border-white/20">
          {Object.entries(AI_ANALYSTS).map(([key, analyst]) => {
            const count = speakerStats[key] || 0;
            if (count === 0) return null;
            return (
              <div key={key} className="flex items-center space-x-2 text-white/90 text-sm">
                <span>{analyst.avatar}</span>
                <span>{analyst.name}</span>
                <span className="bg-white/20 px-2 py-0.5 rounded-full text-xs">{count}회</span>
              </div>
            );
          })}
        </div>
      </div>

      {/* 회의 내용 */}
      <div className="p-5 max-h-[600px] overflow-y-auto bg-gray-50">
        {meeting.messages.length === 0 ? (
          <div className="text-center py-10 text-gray-500">
            <span className="text-4xl mb-3 block">💬</span>
            <p>아직 발언이 없습니다</p>
            <p className="text-sm">회의가 시작되면 AI들의 토론이 여기에 표시됩니다</p>
          </div>
        ) : (
          <>
            {meeting.messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}
            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      {/* 시그널 요약 */}
      {meeting.signal && (
        <div className="p-5 bg-gradient-to-r from-indigo-50 to-purple-50 border-t-2 border-indigo-200">
          <h4 className="font-bold text-indigo-800 mb-3 flex items-center">
            <span className="text-xl mr-2">📌</span>
            최종 투자 시그널
          </h4>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <div className="bg-white rounded-lg p-3 text-center border">
              <span className="text-xs text-gray-500">행동</span>
              <p className={`font-bold text-lg ${
                meeting.signal.action === 'BUY' ? 'text-green-600' :
                meeting.signal.action === 'SELL' ? 'text-red-600' : 'text-gray-600'
              }`}>
                {meeting.signal.action === 'BUY' ? '📈 매수' :
                 meeting.signal.action === 'SELL' ? '📉 매도' : '📊 보유'}
              </p>
            </div>
            <div className="bg-white rounded-lg p-3 text-center border">
              <span className="text-xs text-gray-500">투자 비율</span>
              <p className="font-bold text-lg text-gray-800">{meeting.signal.allocation_percent.toFixed(1)}%</p>
            </div>
            <div className="bg-white rounded-lg p-3 text-center border">
              <span className="text-xs text-gray-500">제안 금액</span>
              <p className="font-bold text-lg text-gray-800">{(meeting.signal.suggested_amount / 10000).toFixed(0)}만원</p>
            </div>
            <div className="bg-white rounded-lg p-3 text-center border">
              <span className="text-xs text-gray-500">신뢰도</span>
              <p className="font-bold text-lg text-indigo-600">{(meeting.signal.confidence * 100).toFixed(0)}%</p>
            </div>
            <div className="bg-white rounded-lg p-3 text-center border">
              <span className="text-xs text-gray-500">AI 점수</span>
              <p className="font-bold text-lg">
                <span className="text-green-600">{meeting.signal.quant_score}</span>
                <span className="text-gray-400 mx-1">/</span>
                <span className="text-purple-600">{meeting.signal.fundamental_score}</span>
              </p>
            </div>
          </div>
          <div className="mt-3 bg-white rounded-lg p-3 border">
            <p className="text-sm text-gray-700">{meeting.signal.consensus_reason}</p>
          </div>

          {/* 시그널 액션 버튼 - 회의 뷰어에서도 승인/거부/체결 가능 */}
          {meeting.signal.status === 'pending' && onApproveSignal && onRejectSignal && (
            <div className="mt-4 flex space-x-3">
              <button
                onClick={() => onApproveSignal(meeting.signal!.id)}
                disabled={isLoading}
                className="flex-1 px-4 py-3 bg-gradient-to-r from-blue-500 to-blue-600 text-white rounded-xl text-sm font-bold hover:from-blue-600 hover:to-blue-700 disabled:opacity-50 transition-all shadow-md hover:shadow-lg"
              >
                ✅ 승인하기
              </button>
              <button
                onClick={() => onRejectSignal(meeting.signal!.id)}
                disabled={isLoading}
                className="flex-1 px-4 py-3 bg-gray-100 text-gray-700 rounded-xl text-sm font-bold hover:bg-gray-200 disabled:opacity-50 transition-all"
              >
                ❌ 거부하기
              </button>
            </div>
          )}

          {meeting.signal.status === 'queued' && (
            <div className="mt-4 px-4 py-3 bg-orange-50 border border-orange-200 rounded-xl text-center">
              <p className="text-sm font-bold text-orange-700">🕐 장 개시 후 자동 체결 예정</p>
              <p className="text-xs text-orange-500 mt-1">거래 시간에 자동으로 주문이 실행됩니다</p>
            </div>
          )}

          {meeting.signal.status === 'approved' && onExecuteSignal && (
            <button
              onClick={() => onExecuteSignal(meeting.signal!.id)}
              disabled={isLoading}
              className="mt-4 w-full px-4 py-3 bg-gradient-to-r from-green-500 to-emerald-600 text-white rounded-xl text-sm font-bold hover:from-green-600 hover:to-emerald-700 disabled:opacity-50 transition-all shadow-md hover:shadow-lg"
            >
              💰 지금 체결하기
            </button>
          )}

          {(meeting.signal.status === 'executed' || meeting.signal.status === 'auto_executed') && (
            <div className="mt-4 p-3 bg-green-100 border border-green-300 rounded-xl text-center">
              <span className="text-green-700 font-bold">✅ 체결 완료</span>
            </div>
          )}

          {meeting.signal.status === 'rejected' && (
            <div className="mt-4 p-3 bg-red-100 border border-red-300 rounded-xl text-center">
              <span className="text-red-700 font-bold">❌ 거부됨</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// 설정 패널
function ConfigPanel({
  config,
  onUpdate,
  isLoading
}: {
  config: CouncilConfig;
  onUpdate: (config: CouncilConfig) => void;
  isLoading: boolean;
}) {
  const [localConfig, setLocalConfig] = useState(config);

  useEffect(() => {
    setLocalConfig(config);
  }, [config]);

  return (
    <div className="bg-white rounded-xl border-2 shadow-lg overflow-hidden">
      <div className="bg-gradient-to-r from-gray-700 to-gray-800 p-4">
        <h3 className="font-bold text-white flex items-center">
          <span className="mr-2">⚙️</span>
          AI 회의 설정
        </h3>
        <p className="text-gray-300 text-sm mt-1">투자 회의의 민감도와 자동화 수준을 조정합니다</p>
      </div>
      <div className="p-5">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              📰 뉴스 중요도 기준 (1-10)
            </label>
            <input
              type="range"
              min={1}
              max={10}
              value={localConfig.council_threshold}
              onChange={(e) => setLocalConfig({ ...localConfig, council_threshold: parseInt(e.target.value) })}
              className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
            />
            <div className="flex justify-between text-xs text-gray-500 mt-1">
              <span>민감 (1)</span>
              <span className="font-bold text-indigo-600">{localConfig.council_threshold}</span>
              <span>엄격 (10)</span>
            </div>
            <p className="text-xs text-gray-400 mt-1">낮을수록 더 많은 뉴스에 대해 회의가 소집됩니다</p>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              📉 매도 기준 점수 (1-10)
            </label>
            <input
              type="range"
              min={1}
              max={10}
              value={localConfig.sell_threshold}
              onChange={(e) => setLocalConfig({ ...localConfig, sell_threshold: parseInt(e.target.value) })}
              className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
            />
            <div className="flex justify-between text-xs text-gray-500 mt-1">
              <span>민감 (1)</span>
              <span className="font-bold text-red-600">{localConfig.sell_threshold}</span>
              <span>엄격 (10)</span>
            </div>
            <p className="text-xs text-gray-400 mt-1">낮을수록 매도 신호가 더 자주 발생합니다</p>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              💰 종목당 최대 투자금
            </label>
            <input
              type="number"
              value={localConfig.max_position_per_stock}
              onChange={(e) => setLocalConfig({ ...localConfig, max_position_per_stock: parseInt(e.target.value) })}
              className="w-full px-4 py-2 border-2 rounded-lg text-sm focus:border-indigo-500 focus:outline-none"
            />
            <p className="text-xs text-gray-400 mt-1">단일 종목에 투자할 최대 금액 (원)</p>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              ⏰ 뉴스 체크 주기 (초)
            </label>
            <input
              type="number"
              min={30}
              value={localConfig.poll_interval}
              onChange={(e) => setLocalConfig({ ...localConfig, poll_interval: parseInt(e.target.value) })}
              className="w-full px-4 py-2 border-2 rounded-lg text-sm focus:border-indigo-500 focus:outline-none"
            />
            <p className="text-xs text-gray-400 mt-1">새로운 뉴스를 확인하는 간격</p>
          </div>
        </div>

        <div className="mt-5 p-4 bg-yellow-50 border-2 border-yellow-200 rounded-xl">
          <label className="flex items-start space-x-3 cursor-pointer">
            <input
              type="checkbox"
              checked={localConfig.auto_execute}
              onChange={(e) => setLocalConfig({ ...localConfig, auto_execute: e.target.checked })}
              className="w-5 h-5 rounded border-2 border-yellow-400 text-yellow-600 focus:ring-yellow-500 mt-0.5"
            />
            <div>
              <span className="font-bold text-yellow-800">🤖 자동 체결 활성화</span>
              <p className="text-sm text-yellow-700 mt-1">
                활성화 시 신뢰도 60% 이상의 시그널이 자동으로 체결됩니다.
                <br/>
                <span className="text-yellow-600 font-medium">⚠️ 주의: 실제 주문이 자동으로 실행됩니다.</span>
              </p>
            </div>
          </label>
        </div>

        <button
          onClick={() => onUpdate(localConfig)}
          disabled={isLoading}
          className="mt-5 w-full px-6 py-3 bg-gradient-to-r from-indigo-500 to-purple-600 text-white rounded-xl font-bold hover:from-indigo-600 hover:to-purple-700 disabled:opacity-50 transition-all shadow-md hover:shadow-lg"
        >
          {isLoading ? '저장 중...' : '💾 설정 저장'}
        </button>
      </div>
    </div>
  );
}

// 계좌 잔고 & 보유종목 인터페이스
interface AccountBalance {
  total_deposit: number;
  available_amount: number;
  total_purchase: number;
  total_evaluation: number;
  total_profit_loss: number;
  profit_rate: number;
  [key: string]: unknown;
}

interface Holding {
  symbol: string;
  name: string;
  quantity: number;
  avg_price: number;
  current_price: number;
  evaluation: number;
  profit_loss: number;
  profit_rate: number;
  [key: string]: unknown;
}

// 보유종목 패널 컴포넌트
interface AccountSummary {
  balance: AccountBalance;
  holdings: Holding[];
  count: number;
}

function AccountHoldingsPanel() {
  const queryClient = useQueryClient();

  const { data: summary, isLoading, isError } = useQuery<AccountSummary>({
    queryKey: ['council', 'account', 'summary'],
    queryFn: councilApi.getAccountSummary,
    refetchInterval: 30000,
    retry: 3,
    retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 10000),
    staleTime: 15000,
  });

  const balance = summary?.balance;
  const holdingsData = summary ? { holdings: summary.holdings, count: summary.count } : undefined;

  const handleRetry = () => {
    queryClient.invalidateQueries({ queryKey: ['council', 'account'] });
  };

  return (
    <div className="bg-white rounded-xl border-2 shadow-lg overflow-hidden">
      <div className="bg-gradient-to-r from-emerald-600 to-teal-600 p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <span className="text-2xl">💼</span>
            <div>
              <h2 className="font-bold text-white text-lg">키움 계좌 현황</h2>
              <p className="text-white/80 text-sm">실시간 보유종목 및 잔고 (30초 갱신)</p>
            </div>
          </div>
          <div className="flex items-center space-x-2">
            {isLoading && (
              <span className="text-white/60 text-sm animate-pulse">갱신 중...</span>
            )}
            {isError && !isLoading && (
              <button
                onClick={handleRetry}
                className="px-3 py-1 bg-white/20 hover:bg-white/30 text-white text-sm rounded-full transition-all"
              >
                다시 시도
              </button>
            )}
          </div>
        </div>
      </div>

      {/* 로딩 스켈레톤 */}
      {isLoading && !balance && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="bg-gray-100 rounded-lg p-3 text-center animate-pulse">
              <div className="h-3 bg-gray-200 rounded w-12 mx-auto mb-2" />
              <div className="h-6 bg-gray-200 rounded w-20 mx-auto" />
            </div>
          ))}
        </div>
      )}

      {/* 에러 상태 */}
      {isError && !balance && !isLoading && (
        <div className="p-6 text-center">
          <span className="text-3xl mb-2 block">⚠️</span>
          <p className="text-gray-500 font-medium">계좌 정보를 불러올 수 없습니다</p>
          <button
            onClick={handleRetry}
            className="mt-3 px-4 py-2 bg-emerald-500 text-white text-sm rounded-lg hover:bg-emerald-600 transition-all"
          >
            다시 시도
          </button>
        </div>
      )}

      {/* 계좌 잔고 카드 */}
      {balance && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-4">
          <div className="bg-gray-50 rounded-lg p-3 text-center">
            <p className="text-xs text-gray-500 mb-1">예수금</p>
            <p className="text-lg font-bold text-gray-800">
              {(balance.available_amount / 10000).toLocaleString()}만원
            </p>
          </div>
          <div className="bg-gray-50 rounded-lg p-3 text-center">
            <p className="text-xs text-gray-500 mb-1">총평가금액</p>
            <p className="text-lg font-bold text-gray-800">
              {(balance.total_evaluation / 10000).toLocaleString()}만원
            </p>
          </div>
          <div className={`rounded-lg p-3 text-center ${
            balance.total_profit_loss >= 0 ? 'bg-red-50' : 'bg-blue-50'
          }`}>
            <p className="text-xs text-gray-500 mb-1">총손익</p>
            <p className={`text-lg font-bold ${
              balance.total_profit_loss >= 0 ? 'text-red-600' : 'text-blue-600'
            }`}>
              {balance.total_profit_loss >= 0 ? '+' : ''}{balance.total_profit_loss.toLocaleString()}원
            </p>
          </div>
          <div className={`rounded-lg p-3 text-center ${
            balance.profit_rate >= 0 ? 'bg-red-50' : 'bg-blue-50'
          }`}>
            <p className="text-xs text-gray-500 mb-1">수익률</p>
            <p className={`text-lg font-bold ${
              balance.profit_rate >= 0 ? 'text-red-600' : 'text-blue-600'
            }`}>
              {balance.profit_rate >= 0 ? '+' : ''}{balance.profit_rate.toFixed(2)}%
            </p>
          </div>
        </div>
      )}

      {/* 보유종목 테이블 */}
      <div className="px-4 pb-4">
        {isLoading && !holdingsData ? (
          <div className="space-y-2 py-4">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-10 bg-gray-100 rounded animate-pulse" />
            ))}
          </div>
        ) : holdingsData && holdingsData.holdings.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b-2 border-gray-200">
                  <th className="text-left py-2 px-2 text-gray-600 font-semibold">종목명</th>
                  <th className="text-right py-2 px-2 text-gray-600 font-semibold">수량</th>
                  <th className="text-right py-2 px-2 text-gray-600 font-semibold">평균단가</th>
                  <th className="text-right py-2 px-2 text-gray-600 font-semibold">현재가</th>
                  <th className="text-right py-2 px-2 text-gray-600 font-semibold">평가금액</th>
                  <th className="text-right py-2 px-2 text-gray-600 font-semibold">손익</th>
                  <th className="text-right py-2 px-2 text-gray-600 font-semibold">수익률</th>
                </tr>
              </thead>
              <tbody>
                {holdingsData.holdings.map((holding) => (
                  <tr key={holding.symbol} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="py-2 px-2">
                      <div>
                        <span className="font-medium text-gray-800">{holding.name}</span>
                        <span className="text-gray-400 text-xs ml-1">({holding.symbol})</span>
                      </div>
                    </td>
                    <td className="text-right py-2 px-2 text-gray-700">{holding.quantity.toLocaleString()}</td>
                    <td className="text-right py-2 px-2 text-gray-700">{holding.avg_price.toLocaleString()}</td>
                    <td className="text-right py-2 px-2 text-gray-700">{holding.current_price.toLocaleString()}</td>
                    <td className="text-right py-2 px-2 font-medium text-gray-800">
                      {holding.evaluation.toLocaleString()}
                    </td>
                    <td className={`text-right py-2 px-2 font-medium ${
                      holding.profit_loss >= 0 ? 'text-red-600' : 'text-blue-600'
                    }`}>
                      {holding.profit_loss >= 0 ? '+' : ''}{holding.profit_loss.toLocaleString()}
                    </td>
                    <td className={`text-right py-2 px-2 font-bold ${
                      holding.profit_rate >= 0 ? 'text-red-600' : 'text-blue-600'
                    }`}>
                      {holding.profit_rate >= 0 ? '+' : ''}{holding.profit_rate.toFixed(2)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : holdingsData ? (
          <div className="text-center py-8 text-gray-500">
            <span className="text-3xl mb-2 block">📭</span>
            <p className="font-medium">보유종목 없음</p>
            <p className="text-xs text-gray-400 mt-1">AI 위원회가 매수 결정을 내리면 여기에 표시됩니다</p>
          </div>
        ) : null}
      </div>
    </div>
  );
}

// 메인 컴포넌트
export default function AICouncil() {
  const queryClient = useQueryClient();
  const [wsConnected, setWsConnected] = useState(false);
  const [selectedMeeting, setSelectedMeeting] = useState<CouncilMeeting | null>(null);
  const [showConfig, setShowConfig] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  // Fetch status
  const { data: status } = useQuery<CouncilStatus>({
    queryKey: ['council', 'status'],
    queryFn: councilApi.getStatus,
    refetchInterval: 10000,
  });

  // Fetch pending signals
  const { data: pendingSignals } = useQuery<{ signals: InvestmentSignal[]; total: number }>({
    queryKey: ['council', 'signals', 'pending'],
    queryFn: councilApi.getPendingSignals,
  });

  // Fetch meetings
  const { data: meetings } = useQuery<{ meetings: CouncilMeeting[]; total: number }>({
    queryKey: ['council', 'meetings'],
    queryFn: () => councilApi.getMeetings(10),
  });

  // Mutations
  const startMutation = useMutation({
    mutationFn: councilApi.start,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['council'] }),
  });

  const stopMutation = useMutation({
    mutationFn: councilApi.stop,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['council'] }),
  });

  const configMutation = useMutation({
    mutationFn: councilApi.updateConfig,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['council'] });
      setShowConfig(false);
    },
  });

  const approveMutation = useMutation({
    mutationFn: councilApi.approveSignal,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['council', 'signals'] }),
  });

  const rejectMutation = useMutation({
    mutationFn: councilApi.rejectSignal,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['council', 'signals'] }),
  });

  const executeMutation = useMutation({
    mutationFn: councilApi.executeSignal,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['council', 'signals'] }),
  });

  // Test mutations
  const [testResult, setTestResult] = useState<Record<string, unknown> | null>(null);
  const [testLoading, setTestLoading] = useState(false);

  const handleTestAnalyze = async () => {
    setTestLoading(true);
    try {
      const result = await councilApi.testAnalyzeNews();
      setTestResult(result);
    } catch (error) {
      setTestResult({ error: String(error) });
    } finally {
      setTestLoading(false);
    }
  };

  const handleForceCouncil = async () => {
    setTestLoading(true);
    try {
      const result = await councilApi.testForceCouncil();
      setTestResult(result);
      queryClient.invalidateQueries({ queryKey: ['council'] });
    } catch (error) {
      setTestResult({ error: String(error) });
    } finally {
      setTestLoading(false);
    }
  };

  const handleMockCouncil = async () => {
    setTestLoading(true);
    try {
      // 삼성전자로 테스트 회의 소집
      const result = await councilApi.testMockCouncil('005930', '삼성전자');
      setTestResult(result);
      queryClient.invalidateQueries({ queryKey: ['council'] });
    } catch (error) {
      setTestResult({ error: String(error) });
    } finally {
      setTestLoading(false);
    }
  };

  // WebSocket connection
  const connectWebSocket = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = councilWebSocket.connect();
    wsRef.current = ws;

    ws.onopen = () => setWsConnected(true);

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      if (data.type === 'meeting_update') {
        if (selectedMeeting?.id === data.meeting.id) {
          setSelectedMeeting(data.meeting);
        }
        queryClient.invalidateQueries({ queryKey: ['council', 'meetings'] });
      } else if (['signal_created', 'signal_approved', 'signal_rejected', 'signal_executed'].includes(data.type)) {
        queryClient.invalidateQueries({ queryKey: ['council', 'signals'] });
      } else if (data.type === 'connected') {
        queryClient.invalidateQueries({ queryKey: ['council'] });
      }
    };

    ws.onclose = () => {
      setWsConnected(false);
      setTimeout(connectWebSocket, 3000);
    };

    ws.onerror = () => setWsConnected(false);
  }, [queryClient, selectedMeeting?.id]);

  useEffect(() => {
    connectWebSocket();

    const pingInterval = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        councilWebSocket.ping(wsRef.current);
      }
    }, 30000);

    return () => {
      clearInterval(pingInterval);
      wsRef.current?.close();
    };
  }, [connectWebSocket]);

  // 페이지 진입 시 모니터링 자동 시작
  const autoStarted = useRef(false);
  useEffect(() => {
    if (status && !status.running && !autoStarted.current && !startMutation.isPending) {
      autoStarted.current = true;
      startMutation.mutate(undefined);
    }
  }, [status]);

  const defaultConfig: CouncilConfig = {
    council_threshold: status?.council_threshold || 7,
    sell_threshold: 3,
    auto_execute: status?.auto_execute ?? true,
    max_position_per_stock: 500000,
    poll_interval: 60,
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-500 rounded-2xl p-6 text-white shadow-xl">
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-3xl font-bold flex items-center">
              <span className="mr-3">🏛️</span>
              AI 투자 위원회
            </h1>
            <p className="text-white/80 mt-2 max-w-xl">
              Gemini, GPT, Claude 3개의 전문 AI가 실시간으로 협력하여
              최적의 투자 결정을 도출합니다.
            </p>
          </div>
          <div className="flex items-center space-x-3">
            <span className={`flex items-center px-4 py-2 rounded-full text-sm font-medium ${
              wsConnected
                ? 'bg-green-500/20 text-green-100 border border-green-400/50'
                : 'bg-red-500/20 text-red-100 border border-red-400/50'
            }`}>
              <span className={`w-2 h-2 rounded-full mr-2 ${
                wsConnected ? 'bg-green-400 animate-pulse' : 'bg-red-400'
              }`} />
              {wsConnected ? '실시간 연결됨' : '연결 끊김'}
            </span>
            <button
              onClick={() => setShowConfig(!showConfig)}
              className="px-4 py-2 bg-white/20 hover:bg-white/30 rounded-full text-sm font-medium transition-all"
            >
              ⚙️ 설정
            </button>
          </div>
        </div>
      </div>

      {/* AI 팀 소개 */}
      <AITeamIntroduction />

      {/* Trading Status Card */}
      {status?.trading && (
        <div className={`rounded-xl shadow-lg p-5 ${
          status.trading.can_trade
            ? 'bg-gradient-to-r from-green-50 to-emerald-50 border-2 border-green-300'
            : 'bg-gradient-to-r from-gray-50 to-slate-50 border-2 border-gray-300'
        }`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <div className={`w-14 h-14 rounded-full flex items-center justify-center ${
                status.trading.can_trade
                  ? 'bg-green-500'
                  : 'bg-gray-400'
              }`}>
                <span className="text-2xl">
                  {status.trading.session === 'regular' ? '📈' :
                   status.trading.session === 'pre_market' ? '🌅' :
                   status.trading.session === 'post_market' ? '🌆' :
                   status.trading.session === 'closed' ? '🌙' : '⏰'}
                </span>
              </div>
              <div>
                <h3 className={`text-lg font-bold ${
                  status.trading.can_trade ? 'text-green-800' : 'text-gray-700'
                }`}>
                  {status.trading.status_message}
                </h3>
                <p className="text-sm text-gray-500">{status.trading.reason}</p>
              </div>
            </div>
            <div className="flex items-center space-x-4">
              {status.trading.queued_count > 0 && (
                <div className="bg-orange-100 border border-orange-300 rounded-lg px-4 py-2 text-center">
                  <p className="text-xs text-orange-600">대기 주문</p>
                  <p className="text-xl font-bold text-orange-700">{status.trading.queued_count}건</p>
                </div>
              )}
              <div className={`px-4 py-2 rounded-lg text-center ${
                status.trading.auto_execute
                  ? 'bg-purple-100 border border-purple-300'
                  : 'bg-gray-100 border border-gray-300'
              }`}>
                <p className="text-xs text-gray-600">자동매매</p>
                <p className={`text-sm font-bold ${
                  status.trading.auto_execute ? 'text-purple-700' : 'text-gray-500'
                }`}>
                  {status.trading.auto_execute ? '🤖 ON' : '⏸️ OFF'}
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 계좌 보유종목 현황 */}
      <AccountHoldingsPanel />

      {/* Status Cards */}
      <div className="grid grid-cols-2 md:grid-cols-6 gap-4">
        <div className="bg-white rounded-xl shadow-md p-5 border-l-4 border-indigo-500">
          <p className="text-sm text-gray-500 mb-1">운영 상태</p>
          <p className={`text-xl font-bold ${status?.running ? 'text-green-600' : 'text-gray-400'}`}>
            {status?.running ? '🟢 실행 중' : '⭕ 중지됨'}
          </p>
        </div>
        <div className="bg-white rounded-xl shadow-md p-5 border-l-4 border-yellow-500">
          <p className="text-sm text-gray-500 mb-1">대기 시그널</p>
          <p className="text-3xl font-bold text-yellow-600">{status?.pending_signals || 0}</p>
        </div>
        <div className="bg-white rounded-xl shadow-md p-5 border-l-4 border-blue-500">
          <p className="text-sm text-gray-500 mb-1">총 회의</p>
          <p className="text-3xl font-bold text-blue-600">{status?.total_meetings || 0}</p>
        </div>
        <div className="bg-white rounded-xl shadow-md p-5 border-l-4 border-green-500">
          <p className="text-sm text-gray-500 mb-1">오늘 거래</p>
          <p className="text-3xl font-bold text-green-600">{status?.daily_trades || 0}</p>
        </div>
        <div className="bg-white rounded-xl shadow-md p-5 border-l-4 border-purple-500">
          <p className="text-sm text-gray-500 mb-1">자동 체결</p>
          <p className={`text-xl font-bold ${status?.auto_execute ? 'text-purple-600' : 'text-gray-400'}`}>
            {status?.auto_execute ? '🤖 활성화' : '⏸️ 비활성화'}
          </p>
        </div>
        {/* AI 비용 통계 카드 */}
        <div className="bg-white rounded-xl shadow-md p-5 border-l-4 border-orange-500">
          <p className="text-sm text-gray-500 mb-1">AI 비용 (일/월)</p>
          {status?.cost ? (
            <div>
              <p className="text-lg font-bold text-orange-600">
                ${status.cost.daily_cost.toFixed(2)} / ${status.cost.monthly_cost.toFixed(2)}
              </p>
              <div className="mt-1">
                <div className="w-full bg-gray-200 rounded-full h-1.5">
                  <div
                    className={`h-1.5 rounded-full transition-all ${
                      (status.cost.daily_cost / status.cost.daily_limit) > 0.8
                        ? 'bg-red-500'
                        : (status.cost.daily_cost / status.cost.daily_limit) > 0.5
                          ? 'bg-yellow-500'
                          : 'bg-green-500'
                    }`}
                    style={{ width: `${Math.min(100, (status.cost.daily_cost / status.cost.daily_limit) * 100)}%` }}
                  />
                </div>
                <p className="text-xs text-gray-400 mt-0.5">
                  일일 한도: ${status.cost.daily_limit} (${status.cost.daily_remaining.toFixed(2)} 남음)
                </p>
              </div>
            </div>
          ) : (
            <p className="text-lg font-bold text-gray-400">-</p>
          )}
        </div>
      </div>

      {/* Control Buttons */}
      <div className="flex flex-wrap gap-3">
        {!status?.running ? (
          <button
            onClick={() => startMutation.mutate(undefined)}
            disabled={startMutation.isPending}
            className="px-8 py-4 bg-gradient-to-r from-green-500 to-emerald-600 text-white rounded-xl font-bold text-lg hover:from-green-600 hover:to-emerald-700 disabled:opacity-50 transition-all shadow-lg hover:shadow-xl"
          >
            {startMutation.isPending ? '⏳ 시작 중...' : '🚀 AI 모니터링 시작'}
          </button>
        ) : (
          <button
            onClick={() => stopMutation.mutate()}
            disabled={stopMutation.isPending}
            className="px-8 py-4 bg-gradient-to-r from-red-500 to-rose-600 text-white rounded-xl font-bold text-lg hover:from-red-600 hover:to-rose-700 disabled:opacity-50 transition-all shadow-lg hover:shadow-xl"
          >
            {stopMutation.isPending ? '⏳ 중지 중...' : '⏹️ 모니터링 중지'}
          </button>
        )}

        {/* 테스트 버튼들 */}
        <button
          onClick={handleTestAnalyze}
          disabled={testLoading}
          className="px-6 py-4 bg-gradient-to-r from-blue-500 to-cyan-600 text-white rounded-xl font-bold hover:from-blue-600 hover:to-cyan-700 disabled:opacity-50 transition-all shadow-lg"
        >
          {testLoading ? '⏳ 분석 중...' : '🔍 뉴스 분석 테스트'}
        </button>
        <button
          onClick={handleForceCouncil}
          disabled={testLoading}
          className="px-6 py-4 bg-gradient-to-r from-purple-500 to-pink-600 text-white rounded-xl font-bold hover:from-purple-600 hover:to-pink-700 disabled:opacity-50 transition-all shadow-lg"
        >
          {testLoading ? '⏳ 회의 소집 중...' : '🏛️ 실제 뉴스로 회의'}
        </button>
        <button
          onClick={handleMockCouncil}
          disabled={testLoading}
          className="px-6 py-4 bg-gradient-to-r from-amber-500 to-orange-600 text-white rounded-xl font-bold hover:from-amber-600 hover:to-orange-700 disabled:opacity-50 transition-all shadow-lg"
        >
          {testLoading ? '⏳ 회의 소집 중...' : '🧪 삼성전자 테스트 회의'}
        </button>
      </div>

      {/* 테스트 결과 표시 */}
      {testResult && (
        <div className={`rounded-xl p-4 shadow-lg ${testResult.error ? 'bg-red-900' : 'bg-gray-900'}`}>
          <div className="flex justify-between items-center mb-3">
            <h3 className="text-white font-bold flex items-center">
              <span className="mr-2">{testResult.error ? '❌' : testResult.status === 'council_started' ? '✅' : '🧪'}</span>
              {testResult.error ? '오류 발생' : testResult.status === 'council_started' ? '회의 시작됨!' : '테스트 결과'}
            </h3>
            <button
              onClick={() => setTestResult(null)}
              className="text-gray-400 hover:text-white text-sm"
            >
              ✕ 닫기
            </button>
          </div>
          {/* 요약 정보 표시 */}
          {'article' in testResult && testResult.article ? (
            <div className="bg-gray-800 rounded-lg p-3 mb-3">
              <p className="text-white font-medium">{String((testResult.article as Record<string, unknown>).title)}</p>
              <p className="text-gray-400 text-sm mt-1">
                종목: {String((testResult.article as Record<string, unknown>).company_name)} ({String((testResult.article as Record<string, unknown>).symbol)})
              </p>
            </div>
          ) : null}
          {'analysis_result' in testResult && testResult.analysis_result ? (
            <div className="grid grid-cols-2 gap-2 mb-3">
              <div className="bg-gray-800 rounded-lg p-2 text-center">
                <p className="text-gray-400 text-xs">점수</p>
                <p className="text-2xl font-bold text-white">{Number((testResult.analysis_result as Record<string, unknown>).score)}/10</p>
              </div>
              <div className="bg-gray-800 rounded-lg p-2 text-center">
                <p className="text-gray-400 text-xs">신뢰도</p>
                <p className="text-2xl font-bold text-white">{Math.round(Number((testResult.analysis_result as Record<string, unknown>).confidence) * 100)}%</p>
              </div>
            </div>
          ) : null}
          {testResult.should_trigger_council !== undefined && (
            <div className={`rounded-lg p-3 mb-3 ${testResult.should_trigger_council ? 'bg-green-800' : 'bg-yellow-800'}`}>
              <p className="text-white font-medium">
                {testResult.should_trigger_council
                  ? '✅ 회의 소집 조건 충족!'
                  : `⚠️ 회의 소집 조건 미충족 (threshold: ${testResult.council_threshold})`}
              </p>
            </div>
          )}
          <details className="mt-2">
            <summary className="text-gray-400 text-sm cursor-pointer hover:text-white">📋 상세 JSON 보기</summary>
            <pre className={`text-sm overflow-auto max-h-64 whitespace-pre-wrap mt-2 ${testResult.error ? 'text-red-400' : 'text-green-400'}`}>
              {JSON.stringify(testResult, null, 2)}
            </pre>
          </details>
        </div>
      )}

      {/* Config Panel */}
      {showConfig && (
        <ConfigPanel
          config={defaultConfig}
          onUpdate={(config) => configMutation.mutate(config)}
          isLoading={configMutation.isPending}
        />
      )}

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Pending Signals */}
        <div>
          <h2 className="text-xl font-bold text-gray-800 mb-4 flex items-center">
            <span className="mr-2">📋</span>
            대기 중인 투자 시그널
          </h2>
          {pendingSignals?.signals && pendingSignals.signals.length > 0 ? (
            <div className="space-y-4">
              {pendingSignals.signals.map((signal) => (
                <SignalCard
                  key={signal.id}
                  signal={signal}
                  onApprove={(id) => approveMutation.mutate(id)}
                  onReject={(id) => rejectMutation.mutate(id)}
                  onExecute={(id) => executeMutation.mutate(id)}
                  isLoading={approveMutation.isPending || rejectMutation.isPending || executeMutation.isPending}
                />
              ))}
            </div>
          ) : (
            <div className="bg-white rounded-xl border-2 border-dashed border-gray-300 p-10 text-center">
              <span className="text-5xl mb-4 block">📭</span>
              <p className="text-gray-500 font-medium">대기 중인 시그널이 없습니다</p>
              <p className="text-sm text-gray-400 mt-2">
                AI 회의에서 새로운 투자 시그널이 생성되면 여기에 표시됩니다
              </p>
            </div>
          )}
        </div>

        {/* Recent Meetings */}
        <div>
          <h2 className="text-xl font-bold text-gray-800 mb-4 flex items-center">
            <span className="mr-2">🏛️</span>
            최근 AI 회의
          </h2>
          {meetings?.meetings && meetings.meetings.length > 0 ? (
            <div className="space-y-3">
              {meetings.meetings.map((meeting) => (
                <div
                  key={meeting.id}
                  onClick={() => setSelectedMeeting(meeting)}
                  className={`bg-white rounded-xl border-2 p-4 cursor-pointer transition-all hover:shadow-lg ${
                    selectedMeeting?.id === meeting.id
                      ? 'ring-2 ring-indigo-500 border-indigo-300'
                      : 'border-gray-200 hover:border-indigo-300'
                  }`}
                >
                  <div className="flex justify-between items-start">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center space-x-2">
                        <h4 className="font-bold text-gray-900">{meeting.company_name}</h4>
                        <span className="text-gray-400 text-sm">({meeting.symbol})</span>
                      </div>
                      <p className="text-sm text-gray-500 truncate mt-1">{meeting.news_title}</p>
                    </div>
                    <span className={`px-3 py-1 rounded-full text-xs font-bold ${
                      meeting.consensus_reached
                        ? 'bg-green-100 text-green-700'
                        : 'bg-yellow-100 text-yellow-700'
                    }`}>
                      {meeting.consensus_reached ? '✅ 완료' : '🔄 진행 중'}
                    </span>
                  </div>
                  <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-100">
                    <div className="flex items-center space-x-3 text-xs text-gray-500">
                      <span>⭐ {meeting.news_score}/10</span>
                      <span>💬 {meeting.messages.length}개 발언</span>
                    </div>
                    <span className="text-xs text-gray-400">
                      {new Date(meeting.started_at).toLocaleString('ko-KR', {
                        month: 'short',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit'
                      })}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="bg-white rounded-xl border-2 border-dashed border-gray-300 p-10 text-center">
              <span className="text-5xl mb-4 block">🏛️</span>
              <p className="text-gray-500 font-medium">아직 회의가 없습니다</p>
              <p className="text-sm text-gray-400 mt-2">
                모니터링을 시작하면 AI 회의가 자동으로 소집됩니다
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Selected Meeting Detail */}
      {selectedMeeting && (
        <div>
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-bold text-gray-800 flex items-center">
              <span className="mr-2">📝</span>
              회의 상세 내용
            </h2>
            <button
              onClick={() => setSelectedMeeting(null)}
              className="px-4 py-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-all"
            >
              ✕ 닫기
            </button>
          </div>
          <MeetingViewer
            meeting={selectedMeeting}
            onApproveSignal={(id) => approveMutation.mutate(id)}
            onRejectSignal={(id) => rejectMutation.mutate(id)}
            onExecuteSignal={(id) => executeMutation.mutate(id)}
            isLoading={approveMutation.isPending || rejectMutation.isPending || executeMutation.isPending}
          />
        </div>
      )}

      {/* 투자 유의사항 */}
      <div className="bg-gradient-to-r from-amber-50 to-orange-50 border-2 border-amber-200 rounded-xl p-5">
        <div className="flex items-start space-x-3">
          <span className="text-2xl">⚠️</span>
          <div>
            <h4 className="font-bold text-amber-800">투자 유의사항</h4>
            <p className="text-sm text-amber-700 mt-1">
              AI 투자 위원회의 결정은 참고용이며, 최종 투자 결정은 사용자 본인의 판단에 따라 이루어져야 합니다.
              투자에는 원금 손실의 위험이 있으며, 과거의 성과가 미래 수익을 보장하지 않습니다.
              자동 체결 기능 사용 시 실제 주문이 실행되므로 신중하게 설정해 주세요.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

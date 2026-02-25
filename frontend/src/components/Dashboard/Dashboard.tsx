import { useState, useCallback, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { tradingApi, analysisApi, stocksApi, councilApi } from '../../services/api';
import { useMarketWebSocket, useTradingWebSocket } from '../../hooks';
import { useCouncilStore } from '../../store/councilStore';
import StockChart from '../Charts/StockChart';
import { RealizedPnlPanel } from '../Council/RealizedPnlPanel';
import { AccountHoldingsPanel } from '../Council/AccountHoldingsPanel';

interface Signal {
  id: number;
  symbol: string;
  signal_type: 'buy' | 'sell' | 'hold';
  strength: number;
  source_agent: string;
  reason: string;
  confidence: number;
  created_at: string;
}

interface Agent {
  name: string;
  role: string;
  status: string;
  model?: string;
  last_analysis?: string;
}

interface MarketData {
  symbol: string;
  price: number;
  change: number;
  change_percent: number;
  volume: number;
  timestamp: string;
}

interface AccountBalance {
  total_deposit: number;
  available_amount: number;
  total_purchase: number;
  total_evaluation: number;
  total_profit_loss: number;
  profit_rate: number;
}

interface SignalStats {
  total: number;
  pending: number;
  executed: number;
  by_type: { buy: number; sell: number; hold: number };
  success_rate: number;
  avg_return: number;
}

interface CouncilStatus {
  running: boolean;
  auto_execute: boolean;
  council_threshold: number;
  pending_signals: number;
  total_meetings: number;
  daily_trades: number;
  monitor_running: boolean;
}

interface CouncilMeeting {
  id: string;
  symbol: string;
  company_name: string;
  news_title: string;
  news_score: number;
  current_round: number;
  max_rounds: number;
  consensus_reached: boolean;
  started_at: string;
  messages: Array<{ id: string; speaker: string; content: string }>;
}

// AI 투자 위원회 실시간 상태 컴포넌트
function AICouncilLiveStatus({ councilStatus, latestMeeting }: {
  councilStatus: CouncilStatus | undefined;
  latestMeeting: CouncilMeeting | undefined;
}) {
  const { triggers, unreadCount } = useCouncilStore();

  return (
    <div className="bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-500 rounded-2xl shadow-xl p-6 text-white">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-3">
          <span className="text-3xl">🏛️</span>
          <div>
            <h2 className="text-xl font-bold">AI 투자 위원회</h2>
            <p className="text-white/70 text-sm">Gemini · GPT · Claude 실시간 협업</p>
          </div>
        </div>
        <div className="flex items-center space-x-3">
          <div className={`px-4 py-2 rounded-full text-sm font-bold ${
            councilStatus?.running
              ? 'bg-green-400/20 text-green-100 border border-green-400/50'
              : 'bg-gray-400/20 text-gray-200 border border-gray-400/50'
          }`}>
            <span className={`inline-block w-2 h-2 rounded-full mr-2 ${
              councilStatus?.running ? 'bg-green-400 animate-pulse' : 'bg-gray-400'
            }`} />
            {councilStatus?.running ? '회의 진행 중' : '대기 중'}
          </div>
          {unreadCount > 0 && (
            <span className="px-3 py-1 bg-red-500 rounded-full text-sm font-bold animate-bounce">
              {unreadCount} 새 알림
            </span>
          )}
        </div>
      </div>

      {/* 실시간 회의 현황 */}
      {latestMeeting && !latestMeeting.consensus_reached ? (
        <div className="bg-white/10 backdrop-blur rounded-xl p-4 mb-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center space-x-2">
              <span className="w-3 h-3 bg-red-500 rounded-full animate-pulse" />
              <span className="font-semibold">실시간 회의 진행 중</span>
            </div>
            <span className="text-sm text-white/70">
              라운드 {latestMeeting.current_round}/{latestMeeting.max_rounds}
            </span>
          </div>
          <div className="flex items-center space-x-3 mb-2">
            <span className="text-2xl font-bold">{latestMeeting.company_name}</span>
            <span className="text-white/60">({latestMeeting.symbol})</span>
            <span className="text-yellow-300">{'⭐'.repeat(Math.round(latestMeeting.news_score / 2))}</span>
          </div>
          <p className="text-white/80 text-sm line-clamp-1 mb-3">{latestMeeting.news_title}</p>
          <Link
            to="/council"
            className="inline-flex items-center px-4 py-2 bg-white text-indigo-600 rounded-lg font-bold text-sm hover:bg-indigo-50 transition-all"
          >
            🎙️ 실시간 토론 참관하기 →
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-4 gap-4 mb-4">
          <div className="bg-white/10 backdrop-blur rounded-lg p-3 text-center">
            <p className="text-3xl font-bold">{councilStatus?.total_meetings || 0}</p>
            <p className="text-xs text-white/70 mt-1">오늘 회의</p>
          </div>
          <div className="bg-white/10 backdrop-blur rounded-lg p-3 text-center">
            <p className="text-3xl font-bold">{councilStatus?.pending_signals || 0}</p>
            <p className="text-xs text-white/70 mt-1">대기 시그널</p>
          </div>
          <div className="bg-white/10 backdrop-blur rounded-lg p-3 text-center">
            <p className="text-3xl font-bold">{councilStatus?.daily_trades || 0}</p>
            <p className="text-xs text-white/70 mt-1">오늘 체결</p>
          </div>
          <div className="bg-white/10 backdrop-blur rounded-lg p-3 text-center">
            <p className="text-3xl font-bold">{triggers.length}</p>
            <p className="text-xs text-white/70 mt-1">트리거 감지</p>
          </div>
        </div>
      )}

      {/* 최근 트리거 알림 */}
      {triggers.length > 0 && (
        <div className="space-y-2">
          <p className="text-sm font-semibold text-white/80">📢 최근 트리거</p>
          <div className="flex space-x-2 overflow-x-auto pb-2">
            {triggers.slice(0, 3).map((trigger) => (
              <Link
                key={trigger.id}
                to="/council"
                className="flex-shrink-0 bg-white/10 backdrop-blur rounded-lg px-3 py-2 hover:bg-white/20 transition-all"
              >
                <div className="flex items-center space-x-2">
                  <span>{trigger.type === 'news_trigger' ? '📰' : trigger.type === 'meeting_started' ? '🏛️' : '📡'}</span>
                  <div>
                    <p className="text-sm font-medium">{trigger.company_name}</p>
                    <p className="text-xs text-white/60">{trigger.symbol} · ⭐{trigger.news_score}/10</p>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}

      <div className="flex items-center justify-between mt-4 pt-4 border-t border-white/20">
        <div className="flex items-center space-x-2 text-sm text-white/70">
          <span>자동 체결:</span>
          <span className={councilStatus?.auto_execute ? 'text-green-300' : 'text-gray-300'}>
            {councilStatus?.auto_execute ? '✅ 활성화' : '⏸️ 비활성화'}
          </span>
        </div>
        <Link
          to="/council"
          className="text-sm text-white/90 hover:text-white font-medium"
        >
          AI 회의실로 이동 →
        </Link>
      </div>
    </div>
  );
}

// 오늘의 투자 전략 가이드 (AI 기반)
function TodayInvestmentStrategy({
  marketSentiment,
  signalStats,
  councilStatus
}: {
  marketSentiment: { sentiment_score: number; sentiment: string } | undefined;
  signalStats: SignalStats | undefined;
  councilStatus: CouncilStatus | undefined;
}) {
  const strategy = useMemo(() => {
    const sentimentScore = marketSentiment?.sentiment_score || 0;
    const successRate = signalStats?.success_rate || 0;
    const pendingSignals = councilStatus?.pending_signals || 0;

    // 대기 중인 시그널이 많으면 즉각 행동 필요
    const urgentAction = pendingSignals >= 3;

    if (sentimentScore >= 50 && successRate >= 70) {
      return {
        level: 'aggressive',
        title: '🚀 적극 매수 전략',
        description: '시장 심리가 긍정적이고 AI 시그널 성공률이 높습니다.',
        color: 'from-green-500 to-emerald-600',
        bgColor: 'bg-green-50',
        borderColor: 'border-green-200',
        textColor: 'text-green-800',
        urgentAction,
        pendingSignals,
        actions: [
          { icon: '🏛️', text: 'AI 회의 시그널 즉시 확인', link: '/council' },
          { icon: '📊', text: '고신뢰 종목 분석 실행', link: '/analysis' },
          { icon: '💰', text: '분할 매수 주문 설정', link: '/trading' },
        ],
        tips: [
          '신뢰도 70% 이상 시그널에 집중',
          '3개 AI 모두 동의한 종목 우선',
          '목표가 도달 시 부분 익절 고려'
        ]
      };
    } else if (sentimentScore >= 20 && successRate >= 50) {
      return {
        level: 'selective',
        title: '📊 선별 매수 전략',
        description: '시장이 조심스럽지만 기회는 있습니다. 엄선된 종목에만 투자하세요.',
        color: 'from-blue-500 to-indigo-600',
        bgColor: 'bg-blue-50',
        borderColor: 'border-blue-200',
        textColor: 'text-blue-800',
        urgentAction,
        pendingSignals,
        actions: [
          { icon: '🔍', text: '섹터별 강세 종목 탐색', link: '/sectors' },
          { icon: '📈', text: '펀더멘털 우량주 분석', link: '/analysis' },
          { icon: '⏱️', text: '백테스트로 전략 검증', link: '/backtest' },
        ],
        tips: [
          '손절 라인 5% 이내로 설정',
          '분할 매수로 평균단가 관리',
          '급등주 추격 매수 자제'
        ]
      };
    } else if (sentimentScore < 0) {
      return {
        level: 'defensive',
        title: '🛡️ 방어적 운용 전략',
        description: '시장 심리가 부정적입니다. 현금 비중을 높이고 리스크를 관리하세요.',
        color: 'from-red-500 to-rose-600',
        bgColor: 'bg-red-50',
        borderColor: 'border-red-200',
        textColor: 'text-red-800',
        urgentAction,
        pendingSignals,
        actions: [
          { icon: '💼', text: '포트폴리오 리스크 점검', link: '/portfolio' },
          { icon: '📉', text: '손절 라인 재검토', link: '/trading' },
          { icon: '📄', text: '성과 보고서 확인', link: '/reports' },
        ],
        tips: [
          '현금 비중 30% 이상 유지',
          '고베타 종목 비중 축소',
          '배당주/방어주 위주 검토'
        ]
      };
    } else {
      return {
        level: 'neutral',
        title: '⏳ 중립 관망 전략',
        description: '뚜렷한 방향성이 없습니다. 신규 매수보다 기존 포지션 관리에 집중하세요.',
        color: 'from-yellow-500 to-amber-600',
        bgColor: 'bg-yellow-50',
        borderColor: 'border-yellow-200',
        textColor: 'text-yellow-800',
        urgentAction,
        pendingSignals,
        actions: [
          { icon: '📰', text: '뉴스 모니터링 강화', link: '/news-monitor' },
          { icon: '🏛️', text: 'AI 회의 대기 현황', link: '/council' },
          { icon: '📊', text: '관심 종목 분석 저장', link: '/analysis' },
        ],
        tips: [
          '급등주 추격 매수 자제',
          '기존 보유 종목 점검',
          'AI 트리거 알림 대기'
        ]
      };
    }
  }, [marketSentiment, signalStats, councilStatus]);

  return (
    <div className={`rounded-2xl border-2 ${strategy.borderColor} overflow-hidden`}>
      <div className={`bg-gradient-to-r ${strategy.color} p-5 text-white`}>
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold">{strategy.title}</h2>
            <p className="text-white/80 text-sm mt-1">{strategy.description}</p>
          </div>
          <div className="text-right">
            <p className="text-xs text-white/70">시장 심리</p>
            <p className="text-2xl font-bold">{marketSentiment?.sentiment || '분석 중'}</p>
          </div>
        </div>
      </div>

      {/* 긴급 알림 배너 */}
      {strategy.urgentAction && strategy.pendingSignals > 0 && (
        <Link
          to="/council"
          className="block bg-gradient-to-r from-red-500 to-orange-500 px-5 py-3 text-white animate-pulse"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center">
              <span className="text-2xl mr-3">🚨</span>
              <div>
                <p className="font-bold">즉각 행동 필요!</p>
                <p className="text-sm text-white/90">대기 중인 AI 시그널 {strategy.pendingSignals}개 - 지금 확인하세요</p>
              </div>
            </div>
            <span className="text-white/80">→</span>
          </div>
        </Link>
      )}

      <div className={`p-5 ${strategy.bgColor}`}>
        {/* 추천 액션 */}
        <div className="mb-4">
          <p className={`text-sm font-bold ${strategy.textColor} mb-3`}>🎯 지금 해야 할 일</p>
          <div className="grid grid-cols-3 gap-3">
            {strategy.actions.map((action, idx) => (
              <Link
                key={idx}
                to={action.link}
                className="bg-white rounded-xl p-3 text-center hover:shadow-md transition-all border border-gray-100"
              >
                <span className="text-2xl block mb-1">{action.icon}</span>
                <span className="text-xs text-gray-700 font-medium">{action.text}</span>
              </Link>
            ))}
          </div>
        </div>

        {/* 투자 팁 */}
        <div>
          <p className={`text-sm font-bold ${strategy.textColor} mb-2`}>💡 투자 팁</p>
          <ul className="space-y-1">
            {strategy.tips.map((tip, idx) => (
              <li key={idx} className={`text-sm ${strategy.textColor} flex items-center`}>
                <span className="w-1.5 h-1.5 rounded-full bg-current mr-2" />
                {tip}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}

// AI 분석가 소개 카드
function AIAnalystShowcase() {
  const analysts = [
    {
      name: 'Gemini',
      role: '뉴스/심리 분석가',
      icon: '📰',
      color: 'from-blue-500 to-blue-600',
      description: '실시간 뉴스와 시장 심리를 분석하여 투자 기회를 발굴합니다.',
      expertise: ['뉴스 감성 분석', '시장 심리 지표', '이벤트 드리븐 투자'],
    },
    {
      name: 'GPT',
      role: '퀀트/기술적 분석가',
      icon: '📊',
      color: 'from-green-500 to-green-600',
      description: '기술적 지표와 수학적 모델로 최적의 매매 타이밍을 분석합니다.',
      expertise: ['RSI/MACD 분석', '패턴 인식', '가격 모멘텀'],
    },
    {
      name: 'Claude',
      role: '펀더멘털 분석가',
      icon: '📈',
      color: 'from-orange-500 to-orange-600',
      description: '기업의 재무제표와 내재가치를 분석하여 장기 투자 가치를 평가합니다.',
      expertise: ['PER/PBR 분석', 'ROE 평가', 'DCF 모델'],
    },
  ];

  return (
    <div className="bg-white rounded-2xl shadow-sm border overflow-hidden">
      <div className="p-5 border-b bg-gradient-to-r from-gray-50 to-white">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <span className="text-2xl">🤖</span>
            <div>
              <h3 className="font-bold text-gray-900">AI 투자 분석가 팀</h3>
              <p className="text-xs text-gray-500">3개의 전문 AI가 협력하여 최적의 투자 결정을 내립니다</p>
            </div>
          </div>
          <Link to="/council" className="text-sm text-indigo-600 hover:text-indigo-700 font-medium">
            토론 참관 →
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-3 divide-x">
        {analysts.map((analyst) => (
          <div key={analyst.name} className="p-4 hover:bg-gray-50 transition-colors">
            <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${analyst.color} flex items-center justify-center text-2xl mb-3`}>
              {analyst.icon}
            </div>
            <h4 className="font-bold text-gray-900">{analyst.name}</h4>
            <p className="text-xs text-gray-500 mb-2">{analyst.role}</p>
            <p className="text-xs text-gray-600 line-clamp-2">{analyst.description}</p>
            <div className="flex flex-wrap gap-1 mt-2">
              {analyst.expertise.map((exp, idx) => (
                <span key={idx} className="text-xs px-2 py-0.5 bg-gray-100 text-gray-600 rounded">
                  {exp}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// 핵심 지표 빠른 가이드
function QuickMetricsGuide() {
  const [expanded, setExpanded] = useState(false);

  const metrics = [
    { name: 'RSI', range: '0-100', signal: '30↓ 매수 | 70↑ 매도', icon: '📈' },
    { name: 'MACD', range: '상향/하향', signal: '상향돌파 매수 | 하향돌파 매도', icon: '📊' },
    { name: 'PER', range: '업종별 상이', signal: '낮을수록 저평가 가능성', icon: '💰' },
    { name: 'PBR', range: '0~', signal: '1 미만이면 자산대비 저평가', icon: '🏦' },
    { name: 'ROE', range: '%', signal: '높을수록 효율적 경영', icon: '📋' },
    { name: '볼린저밴드', range: '상/중/하단', signal: '하단터치 매수 | 상단터치 매도', icon: '📉' },
  ];

  return (
    <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-5 py-4 flex items-center justify-between hover:bg-gray-50 transition-colors"
      >
        <div className="flex items-center space-x-2">
          <span className="text-xl">📚</span>
          <span className="font-semibold text-gray-900">투자 지표 빠른 가이드</span>
          <span className="text-xs px-2 py-0.5 bg-indigo-100 text-indigo-700 rounded-full">초보자 필독</span>
        </div>
        <span className={`transform transition-transform ${expanded ? 'rotate-180' : ''}`}>▼</span>
      </button>

      {expanded && (
        <div className="px-5 pb-5">
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
            {metrics.map((m) => (
              <div key={m.name} className="p-3 bg-gray-50 rounded-lg text-center">
                <span className="text-xl">{m.icon}</span>
                <p className="font-bold text-sm text-gray-900 mt-1">{m.name}</p>
                <p className="text-xs text-gray-500 mt-1">{m.signal}</p>
              </div>
            ))}
          </div>
          <p className="text-xs text-gray-400 mt-3 text-center">
            💡 AI가 이 지표들을 종합적으로 분석하여 매매 시그널을 생성합니다
          </p>
        </div>
      )}
    </div>
  );
}

export default function Dashboard() {
  const [watchlistSymbols] = useState(['005930', '000660', '035420', '035720']);
  const [marketPrices, setMarketPrices] = useState<Record<string, MarketData>>({});

  // WebSocket for real-time market data
  const handlePriceUpdate = useCallback((data: MarketData) => {
    setMarketPrices((prev) => ({
      ...prev,
      [data.symbol]: data,
    }));
  }, []);

  const { status: wsStatus } = useMarketWebSocket({
    symbols: watchlistSymbols,
    onPriceUpdate: handlePriceUpdate,
  });

  // Trading WebSocket
  useTradingWebSocket();

  // Fetch pending signals
  const { data: pendingSignals } = useQuery<Signal[]>({
    queryKey: ['signals', 'pending'],
    queryFn: () => tradingApi.getPendingSignals(5),
    refetchInterval: 30000,
  });

  // Fetch agents status
  const { data: agentsStatus } = useQuery<{ agents: Agent[] }>({
    queryKey: ['agentsStatus'],
    queryFn: analysisApi.getAgentsStatus,
    refetchInterval: 60000,
  });

  // Fetch account balance
  const { data: accountBalance } = useQuery<AccountBalance>({
    queryKey: ['account', 'balance'],
    queryFn: tradingApi.getAccountBalance,
  });

  // Fetch signal stats
  const { data: signalStats } = useQuery<SignalStats>({
    queryKey: ['signals', 'stats'],
    queryFn: analysisApi.getSignalsStats,
  });

  // Fetch market sentiment
  const { data: marketSentiment } = useQuery({
    queryKey: ['market', 'sentiment', 'KOSPI'],
    queryFn: () => analysisApi.getMarketSentiment('KOSPI'),
  });

  // Fetch AI Council status
  const { data: councilStatus } = useQuery<CouncilStatus>({
    queryKey: ['council', 'status'],
    queryFn: councilApi.getStatus,
    refetchInterval: 10000,
  });

  // Fetch latest meetings
  const { data: meetingsData } = useQuery<{ meetings: CouncilMeeting[] }>({
    queryKey: ['council', 'meetings'],
    queryFn: () => councilApi.getMeetings(1),
    refetchInterval: 10000,
  });

  // Fetch watchlist
  const { data: _watchlist } = useQuery({
    queryKey: ['watchlist'],
    queryFn: stocksApi.getWatchlist,
  });
  void _watchlist;

  const latestMeeting = meetingsData?.meetings?.[0];

  const getAgentColor = (agent: string) => {
    switch (agent.toLowerCase()) {
      case 'gemini': return 'bg-blue-100 text-blue-700';
      case 'chatgpt': return 'bg-green-100 text-green-700';
      case 'claude': return 'bg-orange-100 text-orange-700';
      case 'ml': return 'bg-purple-100 text-purple-700';
      default: return 'bg-gray-100 text-gray-700';
    }
  };

  const getSignalStrengthBar = (strength: number) => {
    let color = 'bg-gray-300';
    if (strength >= 70) color = 'bg-green-500';
    else if (strength >= 50) color = 'bg-yellow-500';
    else if (strength >= 30) color = 'bg-orange-500';
    else color = 'bg-red-500';

    return (
      <div className="w-full bg-gray-200 rounded-full h-1.5">
        <div className={`${color} h-1.5 rounded-full transition-all`} style={{ width: `${strength}%` }} />
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">AI 투자 대시보드</h1>
          <p className="text-sm text-gray-500 mt-1">
            3개의 AI가 실시간 토론을 통해 최적의 투자 결정을 내립니다
          </p>
        </div>
        <div className="flex items-center space-x-4">
          <span className={`flex items-center text-sm ${wsStatus === 'connected' ? 'text-green-600' : 'text-gray-400'}`}>
            <span className={`w-2 h-2 rounded-full mr-2 ${wsStatus === 'connected' ? 'bg-green-500 animate-pulse' : 'bg-gray-400'}`} />
            {wsStatus === 'connected' ? '실시간 연결' : '연결 중...'}
          </span>
        </div>
      </div>

      {/* AI Council 실시간 상태 - 가장 중요! */}
      <AICouncilLiveStatus councilStatus={councilStatus} latestMeeting={latestMeeting} />

      {/* 오늘의 투자 전략 */}
      <TodayInvestmentStrategy
        marketSentiment={marketSentiment}
        signalStats={signalStats}
        councilStatus={councilStatus}
      />

      {/* Account Overview */}
      {accountBalance && (
        <div className="bg-gradient-to-r from-slate-700 to-slate-900 rounded-2xl shadow-lg p-6 text-white">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold flex items-center">
              <span className="mr-2">💰</span> 내 계좌 현황
            </h2>
            <Link to="/portfolio" className="text-sm text-slate-300 hover:text-white">
              상세보기 →
            </Link>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <div>
              <p className="text-slate-400 text-sm">예수금</p>
              <p className="text-2xl font-bold">{(accountBalance.total_deposit ?? 0).toLocaleString()}원</p>
            </div>
            <div>
              <p className="text-slate-400 text-sm">주문가능</p>
              <p className="text-2xl font-bold">{(accountBalance.available_amount ?? 0).toLocaleString()}원</p>
            </div>
            <div>
              <p className="text-slate-400 text-sm">매입금액</p>
              <p className="text-2xl font-bold">{(accountBalance.total_purchase ?? 0).toLocaleString()}원</p>
            </div>
            <div>
              <p className="text-slate-400 text-sm">평가손익</p>
              <p className={`text-2xl font-bold ${(accountBalance.total_profit_loss ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {(accountBalance.total_profit_loss ?? 0) >= 0 ? '+' : ''}{(accountBalance.total_profit_loss ?? 0).toLocaleString()}원
              </p>
            </div>
            <div>
              <p className="text-slate-400 text-sm">수익률</p>
              <p className={`text-2xl font-bold ${(accountBalance.profit_rate ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {(accountBalance.profit_rate ?? 0) >= 0 ? '+' : ''}{(accountBalance.profit_rate ?? 0).toFixed(2)}%
              </p>
            </div>
          </div>
        </div>
      )}

      {/* 보유 종목 현황 */}
      <AccountHoldingsPanel />

      {/* 실현 수익 */}
      <RealizedPnlPanel />

      {/* AI 분석가 소개 */}
      <AIAnalystShowcase />

      {/* 핵심 지표 가이드 */}
      <QuickMetricsGuide />

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Chart Section */}
        <div className="lg:col-span-2 bg-white rounded-xl shadow-sm border p-6">
          <div className="flex justify-between items-center mb-4">
            <div>
              <h2 className="text-lg font-semibold text-gray-900">시장 차트</h2>
              <p className="text-xs text-gray-500">실시간 지수 현황</p>
            </div>
            <div className="flex space-x-2">
              <button className="px-3 py-1 text-sm bg-indigo-100 text-indigo-700 rounded-md font-medium">
                KOSPI
              </button>
              <button className="px-3 py-1 text-sm text-gray-600 hover:bg-gray-100 rounded-md">
                KOSDAQ
              </button>
            </div>
          </div>
          <StockChart symbol="KOSPI" />
        </div>

        {/* Pending Signals */}
        <div className="bg-white rounded-xl shadow-sm border p-6">
          <div className="flex justify-between items-center mb-4">
            <div>
              <h2 className="text-lg font-semibold text-gray-900">AI 시그널</h2>
              <p className="text-xs text-gray-500">실행 대기 중인 매매 신호</p>
            </div>
            <Link to="/signals" className="text-sm text-indigo-600 hover:text-indigo-700 font-medium">
              전체 보기
            </Link>
          </div>
          {pendingSignals && pendingSignals.length > 0 ? (
            <div className="space-y-3">
              {pendingSignals.map((signal) => (
                <div
                  key={signal.id}
                  className="p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors border"
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center space-x-2">
                      <span
                        className={`px-2 py-1 rounded text-xs font-bold ${
                          signal.signal_type === 'buy'
                            ? 'bg-green-100 text-green-800'
                            : signal.signal_type === 'sell'
                            ? 'bg-red-100 text-red-800'
                            : 'bg-gray-100 text-gray-800'
                        }`}
                      >
                        {signal.signal_type === 'buy' ? '매수' : signal.signal_type === 'sell' ? '매도' : '보유'}
                      </span>
                      <span className="font-bold text-gray-900">{signal.symbol}</span>
                    </div>
                    <span className={`px-2 py-0.5 rounded text-xs ${getAgentColor(signal.source_agent)}`}>
                      {signal.source_agent}
                    </span>
                  </div>
                  <p className="text-sm text-gray-600 line-clamp-2 mb-2">{signal.reason}</p>

                  <div className="space-y-1">
                    <div className="flex justify-between text-xs text-gray-500">
                      <span>신뢰도</span>
                      <span className="font-medium">{signal.confidence}%</span>
                    </div>
                    {getSignalStrengthBar(signal.strength)}
                  </div>

                  <Link
                    to={`/stocks/${signal.symbol}`}
                    className="block text-xs text-indigo-600 hover:text-indigo-700 mt-2 text-right"
                  >
                    상세 분석 →
                  </Link>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-gray-500">
              <div className="text-4xl mb-3">🔍</div>
              <p className="font-medium">대기 중인 시그널이 없습니다</p>
              <p className="text-sm mt-1">AI가 새로운 기회를 찾고 있습니다</p>
              <Link
                to="/council"
                className="inline-block mt-4 px-4 py-2 bg-indigo-100 text-indigo-700 rounded-lg text-sm font-medium hover:bg-indigo-200"
              >
                AI 회의실 확인하기
              </Link>
            </div>
          )}
        </div>
      </div>

      {/* Watchlist */}
      <div className="bg-white rounded-xl shadow-sm border p-6">
        <div className="flex justify-between items-center mb-4">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">관심 종목</h2>
            <p className="text-xs text-gray-500">실시간 시세 · 클릭하여 AI 분석 보기</p>
          </div>
          <Link to="/stocks" className="text-sm text-indigo-600 hover:text-indigo-700 font-medium">
            종목 검색 →
          </Link>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {watchlistSymbols.map((symbol) => {
            const priceData = marketPrices[symbol];
            const changePercent = priceData?.change_percent || 0;
            const companyName = symbol === '005930' ? '삼성전자' :
              symbol === '000660' ? 'SK하이닉스' :
              symbol === '035420' ? 'NAVER' :
              symbol === '035720' ? '카카오' : '';

            return (
              <Link
                key={symbol}
                to={`/stocks/${symbol}`}
                className="p-4 bg-gray-50 rounded-xl hover:bg-gray-100 transition-all border hover:shadow-md"
              >
                <div className="flex justify-between items-start mb-2">
                  <div>
                    <p className="font-bold text-gray-900">{symbol}</p>
                    <p className="text-xs text-gray-500">{companyName}</p>
                  </div>
                  {priceData && (
                    <span
                      className={`px-2 py-1 rounded text-sm font-bold ${
                        changePercent >= 0
                          ? 'bg-red-100 text-red-700'
                          : 'bg-blue-100 text-blue-700'
                      }`}
                    >
                      {changePercent >= 0 ? '▲' : '▼'} {Math.abs(changePercent).toFixed(2)}%
                    </span>
                  )}
                </div>
                <p className="text-xl font-bold text-gray-900">
                  {priceData?.price?.toLocaleString() || '-'}원
                </p>
                <p className="text-xs text-indigo-600 mt-2">AI 분석 보기 →</p>
              </Link>
            );
          })}
        </div>
      </div>

      {/* AI Agents Status */}
      {agentsStatus?.agents && (
        <div className="bg-white rounded-xl shadow-sm border p-6">
          <div className="flex justify-between items-center mb-4">
            <div>
              <h2 className="text-lg font-semibold text-gray-900">AI 에이전트 상태</h2>
              <p className="text-xs text-gray-500">각 AI의 현재 상태와 역할</p>
            </div>
            <Link to="/agents" className="text-sm text-indigo-600 hover:text-indigo-700 font-medium">
              상세 보기 →
            </Link>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {agentsStatus.agents.map((agent) => {
              const agentInfo: Record<string, { icon: string; color: string }> = {
                gemini: { icon: '📰', color: 'from-blue-500 to-blue-600' },
                chatgpt: { icon: '📊', color: 'from-green-500 to-green-600' },
                claude: { icon: '📈', color: 'from-orange-500 to-orange-600' },
                ml: { icon: '🤖', color: 'from-purple-500 to-purple-600' },
              };
              const info = agentInfo[agent.name.toLowerCase()] || { icon: '❓', color: 'from-gray-500 to-gray-600' };

              return (
                <div key={agent.name} className="p-4 bg-gray-50 rounded-xl border">
                  <div className="flex items-center space-x-3 mb-2">
                    <div className={`w-10 h-10 rounded-lg bg-gradient-to-br ${info.color} flex items-center justify-center text-lg`}>
                      {info.icon}
                    </div>
                    <div>
                      <span className="font-semibold capitalize text-gray-900">{agent.name}</span>
                      <span
                        className={`ml-2 w-2 h-2 rounded-full inline-block ${
                          agent.status === 'active' ? 'bg-green-500' : 'bg-gray-400'
                        }`}
                      />
                    </div>
                  </div>
                  <p className="text-xs text-gray-500">{agent.role}</p>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Quick Actions */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Link
          to="/council"
          className="p-5 bg-gradient-to-br from-indigo-50 to-purple-100 rounded-xl hover:from-indigo-100 hover:to-purple-200 transition-all group border border-indigo-200"
        >
          <span className="text-3xl mb-2 block group-hover:scale-110 transition-transform">🏛️</span>
          <span className="font-semibold text-indigo-800">AI 회의실</span>
          <p className="text-xs text-indigo-600 mt-1">실시간 토론 참관</p>
        </Link>
        <Link
          to="/analysis"
          className="p-5 bg-gradient-to-br from-blue-50 to-blue-100 rounded-xl hover:from-blue-100 hover:to-blue-200 transition-all group border border-blue-200"
        >
          <span className="text-3xl mb-2 block group-hover:scale-110 transition-transform">🔍</span>
          <span className="font-semibold text-blue-800">종목 분석</span>
          <p className="text-xs text-blue-600 mt-1">AI 심층 분석</p>
        </Link>
        <Link
          to="/trading"
          className="p-5 bg-gradient-to-br from-green-50 to-green-100 rounded-xl hover:from-green-100 hover:to-green-200 transition-all group border border-green-200"
        >
          <span className="text-3xl mb-2 block group-hover:scale-110 transition-transform">💹</span>
          <span className="font-semibold text-green-800">주문 관리</span>
          <p className="text-xs text-green-600 mt-1">매수/매도 실행</p>
        </Link>
        <Link
          to="/portfolio"
          className="p-5 bg-gradient-to-br from-orange-50 to-orange-100 rounded-xl hover:from-orange-100 hover:to-orange-200 transition-all group border border-orange-200"
        >
          <span className="text-3xl mb-2 block group-hover:scale-110 transition-transform">📁</span>
          <span className="font-semibold text-orange-800">포트폴리오</span>
          <p className="text-xs text-orange-600 mt-1">보유 현황</p>
        </Link>
      </div>

      {/* 투자 위험 경고 */}
      <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-amber-800">
        <div className="flex items-start space-x-3">
          <span className="text-xl">⚠️</span>
          <div>
            <p className="font-semibold">투자 유의사항</p>
            <p className="text-sm mt-1">
              AI 분석은 참고 자료일 뿐, 투자의 최종 결정과 책임은 투자자 본인에게 있습니다.
              분산 투자와 손절 라인 설정으로 리스크를 관리하세요.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

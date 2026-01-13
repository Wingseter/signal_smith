import { useState, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { tradingApi, analysisApi, stocksApi } from '../../services/api';
import { useMarketWebSocket, useTradingWebSocket } from '../../hooks';
import StockChart from '../Charts/StockChart';

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

  // Fetch coordinator status
  const { data: coordinatorStatus } = useQuery({
    queryKey: ['coordinatorStatus'],
    queryFn: analysisApi.getCoordinatorStatus,
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

  // Fetch watchlist
  const { data: watchlist } = useQuery({
    queryKey: ['watchlist'],
    queryFn: stocksApi.getWatchlist,
  });

  const getAgentColor = (agent: string) => {
    switch (agent.toLowerCase()) {
      case 'gemini': return 'bg-purple-100 text-purple-700';
      case 'chatgpt': return 'bg-green-100 text-green-700';
      case 'claude': return 'bg-orange-100 text-orange-700';
      case 'ml': return 'bg-blue-100 text-blue-700';
      default: return 'bg-gray-100 text-gray-700';
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-sm text-gray-500 mt-1">Signal Smith - AI 주식 자동 분석 시스템</p>
        </div>
        <div className="flex items-center space-x-4">
          <span className={`flex items-center text-sm ${wsStatus === 'connected' ? 'text-green-600' : 'text-gray-400'}`}>
            <span className={`w-2 h-2 rounded-full mr-2 ${wsStatus === 'connected' ? 'bg-green-500 animate-pulse' : 'bg-gray-400'}`} />
            {wsStatus === 'connected' ? '실시간 연결' : '연결 중...'}
          </span>
        </div>
      </div>

      {/* Account Overview */}
      {accountBalance && (
        <div className="bg-gradient-to-r from-primary-600 to-primary-800 rounded-xl shadow-lg p-6 text-white">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <div>
              <p className="text-primary-200 text-sm">예수금</p>
              <p className="text-2xl font-bold">{(accountBalance.total_deposit ?? 0).toLocaleString()}원</p>
            </div>
            <div>
              <p className="text-primary-200 text-sm">주문가능</p>
              <p className="text-2xl font-bold">{(accountBalance.available_amount ?? 0).toLocaleString()}원</p>
            </div>
            <div>
              <p className="text-primary-200 text-sm">매입금액</p>
              <p className="text-2xl font-bold">{(accountBalance.total_purchase ?? 0).toLocaleString()}원</p>
            </div>
            <div>
              <p className="text-primary-200 text-sm">평가손익</p>
              <p className={`text-2xl font-bold ${(accountBalance.total_profit_loss ?? 0) >= 0 ? 'text-green-300' : 'text-red-300'}`}>
                {(accountBalance.total_profit_loss ?? 0) >= 0 ? '+' : ''}{(accountBalance.total_profit_loss ?? 0).toLocaleString()}원
              </p>
            </div>
            <div>
              <p className="text-primary-200 text-sm">수익률</p>
              <p className={`text-2xl font-bold ${(accountBalance.profit_rate ?? 0) >= 0 ? 'text-green-300' : 'text-red-300'}`}>
                {(accountBalance.profit_rate ?? 0) >= 0 ? '+' : ''}{(accountBalance.profit_rate ?? 0).toFixed(2)}%
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Quick Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {/* Market Sentiment */}
        <div className="bg-white rounded-lg shadow p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">시장 심리</p>
              <p className={`text-2xl font-bold ${
                (marketSentiment?.sentiment_score || 0) >= 0 ? 'text-green-600' : 'text-red-600'
              }`}>
                {marketSentiment?.sentiment || '분석 중'}
              </p>
            </div>
            <div className={`w-12 h-12 rounded-full flex items-center justify-center ${
              (marketSentiment?.sentiment_score || 0) >= 50 ? 'bg-green-100' :
              (marketSentiment?.sentiment_score || 0) >= 0 ? 'bg-yellow-100' : 'bg-red-100'
            }`}>
              <span className="text-lg">
                {(marketSentiment?.sentiment_score || 0) >= 50 ? '📈' :
                 (marketSentiment?.sentiment_score || 0) >= 0 ? '➡️' : '📉'}
              </span>
            </div>
          </div>
        </div>

        {/* Pending Signals */}
        <div className="bg-white rounded-lg shadow p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">대기 시그널</p>
              <p className="text-2xl font-bold text-yellow-600">{signalStats?.pending || 0}</p>
            </div>
            <Link
              to="/signals"
              className="text-sm text-primary-600 hover:text-primary-700 font-medium"
            >
              보기 →
            </Link>
          </div>
        </div>

        {/* Success Rate */}
        <div className="bg-white rounded-lg shadow p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">시그널 성공률</p>
              <p className="text-2xl font-bold text-green-600">
                {signalStats?.success_rate?.toFixed(1) || 0}%
              </p>
            </div>
            <div className="w-12 h-12">
              <svg viewBox="0 0 36 36" className="transform -rotate-90">
                <circle
                  cx="18" cy="18" r="16"
                  fill="none"
                  stroke="#e5e7eb"
                  strokeWidth="3"
                />
                <circle
                  cx="18" cy="18" r="16"
                  fill="none"
                  stroke="#10b981"
                  strokeWidth="3"
                  strokeDasharray={`${(signalStats?.success_rate || 0)} 100`}
                  strokeLinecap="round"
                />
              </svg>
            </div>
          </div>
        </div>

        {/* Active Agents */}
        <div className="bg-white rounded-lg shadow p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">활성 에이전트</p>
              <p className="text-2xl font-bold text-blue-600">
                {agentsStatus?.agents?.filter((a) => a.status === 'active').length || 0}/4
              </p>
            </div>
            <Link
              to="/agents"
              className="text-sm text-primary-600 hover:text-primary-700 font-medium"
            >
              관리 →
            </Link>
          </div>
        </div>
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Chart Section */}
        <div className="lg:col-span-2 bg-white rounded-lg shadow p-6">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-lg font-semibold text-gray-900">시장 차트</h2>
            <div className="flex space-x-2">
              <button className="px-3 py-1 text-sm bg-primary-100 text-primary-700 rounded-md">
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
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-lg font-semibold text-gray-900">대기 중인 시그널</h2>
            <Link
              to="/signals"
              className="text-sm text-primary-600 hover:text-primary-700 font-medium"
            >
              전체 보기
            </Link>
          </div>
          {pendingSignals && pendingSignals.length > 0 ? (
            <div className="space-y-3">
              {pendingSignals.map((signal) => (
                <div
                  key={signal.id}
                  className="p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-3">
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
                      <span className="font-medium">{signal.symbol}</span>
                    </div>
                    <span className={`px-2 py-0.5 rounded text-xs ${getAgentColor(signal.source_agent)}`}>
                      {signal.source_agent}
                    </span>
                  </div>
                  <p className="text-sm text-gray-600 mt-2 line-clamp-1">{signal.reason}</p>
                  <div className="flex justify-between items-center mt-2 text-xs text-gray-500">
                    <span>강도: {signal.strength}%</span>
                    <span>신뢰도: {signal.confidence}%</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-gray-500">
              <p>대기 중인 시그널이 없습니다</p>
              <Link
                to="/analysis"
                className="text-primary-600 hover:text-primary-700 text-sm mt-2 inline-block"
              >
                분석 시작하기 →
              </Link>
            </div>
          )}
        </div>
      </div>

      {/* Watchlist */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-lg font-semibold text-gray-900">관심 종목</h2>
          <Link
            to="/stocks"
            className="text-sm text-primary-600 hover:text-primary-700 font-medium"
          >
            종목 검색
          </Link>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {watchlistSymbols.map((symbol) => {
            const priceData = marketPrices[symbol];
            return (
              <Link
                key={symbol}
                to={`/stocks/${symbol}`}
                className="p-4 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
              >
                <div className="flex justify-between items-start">
                  <div>
                    <p className="font-bold text-gray-900">{symbol}</p>
                    <p className="text-lg font-semibold mt-1">
                      {priceData?.price?.toLocaleString() || '-'}원
                    </p>
                  </div>
                  {priceData && (
                    <span
                      className={`px-2 py-1 rounded text-sm font-medium ${
                        priceData.change_percent >= 0
                          ? 'bg-red-100 text-red-700'
                          : 'bg-blue-100 text-blue-700'
                      }`}
                    >
                      {priceData.change_percent >= 0 ? '+' : ''}
                      {priceData.change_percent?.toFixed(2)}%
                    </span>
                  )}
                </div>
              </Link>
            );
          })}
        </div>
      </div>

      {/* AI Agents Status */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-lg font-semibold text-gray-900">AI 에이전트 상태</h2>
          <Link
            to="/agents"
            className="text-sm text-primary-600 hover:text-primary-700 font-medium"
          >
            상세 보기
          </Link>
        </div>
        {agentsStatus?.agents ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {agentsStatus.agents.map((agent) => (
              <div key={agent.name} className="p-4 bg-gray-50 rounded-lg">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center space-x-2">
                    <span className={`w-8 h-8 rounded-full flex items-center justify-center ${getAgentColor(agent.name)}`}>
                      <span className="text-xs font-bold">
                        {agent.name.charAt(0).toUpperCase()}
                      </span>
                    </span>
                    <span className="font-medium capitalize">{agent.name}</span>
                  </div>
                  <span
                    className={`w-2.5 h-2.5 rounded-full ${
                      agent.status === 'active' ? 'bg-green-500' : 'bg-gray-400'
                    }`}
                  />
                </div>
                <p className="text-sm text-gray-600">{agent.role}</p>
                {agent.model && (
                  <p className="text-xs text-gray-400 mt-1">{agent.model}</p>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-8 text-gray-500">
            <p>에이전트 상태를 불러오는 중...</p>
          </div>
        )}
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Link
          to="/analysis"
          className="p-4 bg-primary-50 rounded-lg hover:bg-primary-100 transition-colors text-center"
        >
          <span className="text-2xl mb-2 block">🔍</span>
          <span className="font-medium text-primary-700">종목 분석</span>
        </Link>
        <Link
          to="/signals"
          className="p-4 bg-green-50 rounded-lg hover:bg-green-100 transition-colors text-center"
        >
          <span className="text-2xl mb-2 block">📊</span>
          <span className="font-medium text-green-700">시그널 관리</span>
        </Link>
        <Link
          to="/trading"
          className="p-4 bg-blue-50 rounded-lg hover:bg-blue-100 transition-colors text-center"
        >
          <span className="text-2xl mb-2 block">💹</span>
          <span className="font-medium text-blue-700">주문 관리</span>
        </Link>
        <Link
          to="/portfolio"
          className="p-4 bg-purple-50 rounded-lg hover:bg-purple-100 transition-colors text-center"
        >
          <span className="text-2xl mb-2 block">📁</span>
          <span className="font-medium text-purple-700">포트폴리오</span>
        </Link>
      </div>
    </div>
  );
}

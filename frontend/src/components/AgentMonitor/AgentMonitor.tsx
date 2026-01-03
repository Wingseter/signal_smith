import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { analysisApi } from '../../services/api';

interface Agent {
  name: string;
  role: string;
  status: string;
  last_run: string | null;
  success_rate: number | null;
}

interface CoordinatorStatus {
  status: string;
  workflow: string;
  agents: string[];
  weights: Record<string, number>;
  features: string[];
}

interface SignalsStats {
  total_signals: number;
  pending_signals: number;
  executed_signals: number;
  buy_signals: number;
  sell_signals: number;
  buy_ratio: number;
}

interface MarketSentiment {
  market: string;
  overall_sentiment: string;
  sentiment_score: number;
  key_drivers: string[];
  sector_outlook: {
    strong: string[];
    weak: string[];
  };
  analyzed_at: string;
}

export default function AgentMonitor() {
  const queryClient = useQueryClient();
  const [selectedMarket, setSelectedMarket] = useState('KOSPI');
  const [analysisSymbol, setAnalysisSymbol] = useState('');

  const { data: agents, isLoading: agentsLoading } = useQuery<Agent[]>({
    queryKey: ['agentsStatus'],
    queryFn: analysisApi.getAgentsStatus,
    refetchInterval: 10000,
  });

  const { data: coordinator } = useQuery<CoordinatorStatus>({
    queryKey: ['coordinatorStatus'],
    queryFn: analysisApi.getCoordinatorStatus,
    refetchInterval: 30000,
  });

  const { data: signalsStats } = useQuery<SignalsStats>({
    queryKey: ['signalsStats'],
    queryFn: analysisApi.getSignalsStats,
    refetchInterval: 30000,
  });

  const { data: marketSentiment, isLoading: sentimentLoading } = useQuery<MarketSentiment>({
    queryKey: ['marketSentiment', selectedMarket],
    queryFn: () => analysisApi.getMarketSentiment(selectedMarket),
    staleTime: 60000,
  });

  const quickAnalysisMutation = useMutation({
    mutationFn: (symbol: string) => analysisApi.runQuickAnalysis(symbol),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['signalsStats'] });
    },
  });

  const fullAnalysisMutation = useMutation({
    mutationFn: (symbol: string) => analysisApi.runFullAnalysis(symbol),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['signalsStats'] });
    },
  });

  const getAgentIcon = (name: string) => {
    switch (name) {
      case 'gemini': return '🔮';
      case 'chatgpt': return '🤖';
      case 'claude': return '🧠';
      case 'ml': return '📊';
      default: return '⚙️';
    }
  };

  const getAgentColor = (name: string) => {
    switch (name) {
      case 'gemini': return 'bg-blue-500';
      case 'chatgpt': return 'bg-green-500';
      case 'claude': return 'bg-orange-500';
      case 'ml': return 'bg-purple-500';
      default: return 'bg-gray-500';
    }
  };

  const getSentimentColor = (sentiment: string) => {
    switch (sentiment) {
      case 'bullish': return 'text-green-600 bg-green-100';
      case 'bearish': return 'text-red-600 bg-red-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  const handleRunAnalysis = (type: 'quick' | 'full') => {
    if (!analysisSymbol.trim()) return;
    if (type === 'quick') {
      quickAnalysisMutation.mutate(analysisSymbol.toUpperCase());
    } else {
      fullAnalysisMutation.mutate(analysisSymbol.toUpperCase());
    }
  };

  if (agentsLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-900">AI 에이전트 모니터</h1>
        <div className="flex items-center space-x-2">
          <span className="flex h-3 w-3">
            <span className="animate-ping absolute inline-flex h-3 w-3 rounded-full bg-green-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-3 w-3 bg-green-500"></span>
          </span>
          <span className="text-sm text-gray-600">실시간 모니터링 중</span>
        </div>
      </div>

      {/* Quick Analysis Panel */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">분석 실행</h2>
        <div className="flex space-x-4">
          <input
            type="text"
            value={analysisSymbol}
            onChange={(e) => setAnalysisSymbol(e.target.value)}
            placeholder="종목 코드 (예: 005930)"
            className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
          <button
            onClick={() => handleRunAnalysis('quick')}
            disabled={quickAnalysisMutation.isPending || !analysisSymbol}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {quickAnalysisMutation.isPending ? '분석 중...' : '빠른 분석'}
          </button>
          <button
            onClick={() => handleRunAnalysis('full')}
            disabled={fullAnalysisMutation.isPending || !analysisSymbol}
            className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {fullAnalysisMutation.isPending ? '분석 중...' : '전체 분석'}
          </button>
        </div>
        {(quickAnalysisMutation.isSuccess || fullAnalysisMutation.isSuccess) && (
          <div className="mt-4 p-4 bg-green-50 border border-green-200 rounded-lg">
            <p className="text-green-800">
              분석이 완료되었습니다. 결과는 대시보드에서 확인하세요.
            </p>
          </div>
        )}
        {(quickAnalysisMutation.isError || fullAnalysisMutation.isError) && (
          <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg">
            <p className="text-red-800">분석 중 오류가 발생했습니다.</p>
          </div>
        )}
      </div>

      {/* Coordinator & Stats Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Coordinator Status */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">코디네이터 상태</h2>
          <div className="flex items-center space-x-4 mb-4">
            <div className={`w-4 h-4 rounded-full ${coordinator?.status === 'active' ? 'bg-green-500 animate-pulse' : 'bg-gray-400'}`} />
            <div>
              <p className="font-medium">LangGraph 오케스트레이터</p>
              <p className="text-sm text-gray-500">워크플로우: {coordinator?.workflow}</p>
            </div>
          </div>
          {coordinator?.weights && (
            <div className="mt-4">
              <p className="text-sm font-medium text-gray-700 mb-2">에이전트 가중치</p>
              <div className="space-y-2">
                {Object.entries(coordinator.weights).map(([agent, weight]) => (
                  <div key={agent} className="flex items-center">
                    <span className="w-24 text-sm capitalize">{agent}</span>
                    <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
                      <div
                        className={`h-full ${getAgentColor(agent === 'news' ? 'gemini' : agent === 'quant' ? 'chatgpt' : agent === 'fundamental' ? 'claude' : 'ml')}`}
                        style={{ width: `${weight * 100}%` }}
                      />
                    </div>
                    <span className="ml-2 text-sm text-gray-600">{(weight * 100).toFixed(0)}%</span>
                  </div>
                ))}
              </div>
            </div>
          )}
          {coordinator?.features && (
            <div className="mt-4 flex flex-wrap gap-2">
              {coordinator.features.map((feature) => (
                <span key={feature} className="px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded-full">
                  {feature.replace(/_/g, ' ')}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Signals Stats */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">시그널 통계</h2>
          <div className="grid grid-cols-2 gap-4">
            <div className="text-center p-4 bg-gray-50 rounded-lg">
              <p className="text-3xl font-bold text-gray-900">{signalsStats?.total_signals || 0}</p>
              <p className="text-sm text-gray-500">전체 시그널</p>
            </div>
            <div className="text-center p-4 bg-yellow-50 rounded-lg">
              <p className="text-3xl font-bold text-yellow-600">{signalsStats?.pending_signals || 0}</p>
              <p className="text-sm text-gray-500">대기 중</p>
            </div>
            <div className="text-center p-4 bg-green-50 rounded-lg">
              <p className="text-3xl font-bold text-green-600">{signalsStats?.buy_signals || 0}</p>
              <p className="text-sm text-gray-500">매수 시그널</p>
            </div>
            <div className="text-center p-4 bg-red-50 rounded-lg">
              <p className="text-3xl font-bold text-red-600">{signalsStats?.sell_signals || 0}</p>
              <p className="text-sm text-gray-500">매도 시그널</p>
            </div>
          </div>
          {signalsStats && signalsStats.total_signals > 0 && (
            <div className="mt-4">
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-500">매수/매도 비율</span>
                <span className="font-medium">{signalsStats.buy_ratio.toFixed(1)}% 매수</span>
              </div>
              <div className="mt-2 h-2 bg-gray-200 rounded-full overflow-hidden flex">
                <div className="bg-green-500" style={{ width: `${signalsStats.buy_ratio}%` }} />
                <div className="bg-red-500" style={{ width: `${100 - signalsStats.buy_ratio}%` }} />
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Market Sentiment */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-lg font-semibold text-gray-900">시장 센티먼트</h2>
          <div className="flex space-x-2">
            {['KOSPI', 'KOSDAQ'].map((market) => (
              <button
                key={market}
                onClick={() => setSelectedMarket(market)}
                className={`px-3 py-1 rounded-lg text-sm ${
                  selectedMarket === market
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                {market}
              </button>
            ))}
          </div>
        </div>
        {sentimentLoading ? (
          <div className="flex justify-center py-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          </div>
        ) : marketSentiment ? (
          <div className="space-y-4">
            <div className="flex items-center space-x-4">
              <span className={`px-4 py-2 rounded-full font-medium ${getSentimentColor(marketSentiment.overall_sentiment)}`}>
                {marketSentiment.overall_sentiment.toUpperCase()}
              </span>
              <div className="flex-1">
                <div className="flex items-center">
                  <span className="text-2xl font-bold">
                    {marketSentiment.sentiment_score > 0 ? '+' : ''}{marketSentiment.sentiment_score}
                  </span>
                  <span className="ml-2 text-gray-500">/ 100</span>
                </div>
              </div>
            </div>
            {marketSentiment.key_drivers && marketSentiment.key_drivers.length > 0 && (
              <div>
                <p className="text-sm font-medium text-gray-700 mb-2">주요 동인</p>
                <div className="flex flex-wrap gap-2">
                  {marketSentiment.key_drivers.map((driver, i) => (
                    <span key={i} className="px-2 py-1 bg-gray-100 text-gray-700 text-sm rounded">
                      {driver}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {marketSentiment.sector_outlook && (
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-sm font-medium text-green-700 mb-2">강세 섹터</p>
                  <div className="space-y-1">
                    {marketSentiment.sector_outlook.strong?.map((sector, i) => (
                      <span key={i} className="block text-sm text-gray-600">• {sector}</span>
                    ))}
                  </div>
                </div>
                <div>
                  <p className="text-sm font-medium text-red-700 mb-2">약세 섹터</p>
                  <div className="space-y-1">
                    {marketSentiment.sector_outlook.weak?.map((sector, i) => (
                      <span key={i} className="block text-sm text-gray-600">• {sector}</span>
                    ))}
                  </div>
                </div>
              </div>
            )}
            <p className="text-xs text-gray-400">
              분석 시간: {new Date(marketSentiment.analyzed_at).toLocaleString()}
            </p>
          </div>
        ) : (
          <p className="text-gray-500 text-center py-4">센티먼트 데이터를 불러올 수 없습니다.</p>
        )}
      </div>

      {/* Agent Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {agents?.map((agent) => (
          <div key={agent.name} className="bg-white rounded-lg shadow p-6 hover:shadow-lg transition-shadow">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center space-x-3">
                <div className={`w-12 h-12 rounded-full ${getAgentColor(agent.name)} bg-opacity-20 flex items-center justify-center`}>
                  <span className="text-2xl">{getAgentIcon(agent.name)}</span>
                </div>
                <div>
                  <h3 className="font-semibold capitalize">{agent.name}</h3>
                  <p className="text-xs text-gray-500">{agent.role}</p>
                </div>
              </div>
              <span className={`w-3 h-3 rounded-full ${agent.status === 'active' ? 'bg-green-500 animate-pulse' : 'bg-gray-400'}`} />
            </div>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-500">상태</span>
                <span className={`font-medium ${agent.status === 'active' ? 'text-green-600' : 'text-gray-600'}`}>
                  {agent.status === 'active' ? '활성' : '비활성'}
                </span>
              </div>
              {agent.success_rate !== null && (
                <div className="flex justify-between">
                  <span className="text-gray-500">성공률</span>
                  <span className="font-medium">{agent.success_rate.toFixed(1)}%</span>
                </div>
              )}
              <div className="flex justify-between">
                <span className="text-gray-500">마지막 실행</span>
                <span className="text-gray-900">
                  {agent.last_run ? new Date(agent.last_run).toLocaleTimeString() : '-'}
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Agent Workflow Visualization */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-6">에이전트 협업 워크플로우</h2>
        <div className="flex flex-col items-center">
          {/* Input */}
          <div className="flex items-center space-x-4 mb-4">
            <div className="w-20 h-20 bg-gradient-to-br from-blue-400 to-blue-600 rounded-2xl flex items-center justify-center text-white text-3xl shadow-lg">
              📥
            </div>
            <div className="text-left">
              <p className="font-medium">데이터 입력</p>
              <p className="text-sm text-gray-500">가격, 뉴스, 재무 데이터</p>
            </div>
          </div>

          <div className="w-px h-8 bg-gray-300"></div>
          <div className="text-gray-400">▼</div>
          <div className="w-px h-8 bg-gray-300"></div>

          {/* Coordinator */}
          <div className="w-full max-w-md bg-gradient-to-r from-purple-500 to-purple-700 rounded-2xl p-4 text-white text-center shadow-lg mb-4">
            <p className="text-lg font-bold">🔄 LangGraph 코디네이터</p>
            <p className="text-sm opacity-80">병렬 실행 & 가중 평균 스코어링</p>
          </div>

          <div className="flex justify-center space-x-4 mb-4">
            {['gemini', 'chatgpt', 'claude', 'ml'].map((name, index) => (
              <div key={name} className="relative">
                {index > 0 && <div className="absolute -left-2 top-1/2 w-4 h-px bg-gray-300"></div>}
                <div className="w-px h-4 bg-gray-300 mx-auto"></div>
                <div className="text-gray-400 text-center">▼</div>
              </div>
            ))}
          </div>

          {/* Agents */}
          <div className="grid grid-cols-4 gap-4 mb-4">
            {[
              { name: 'gemini', label: '뉴스', color: 'from-blue-400 to-blue-600' },
              { name: 'chatgpt', label: '퀀트', color: 'from-green-400 to-green-600' },
              { name: 'claude', label: '펀더멘털', color: 'from-orange-400 to-orange-600' },
              { name: 'ml', label: '기술적', color: 'from-purple-400 to-purple-600' },
            ].map((agent) => (
              <div key={agent.name} className="text-center">
                <div className={`w-16 h-16 mx-auto bg-gradient-to-br ${agent.color} rounded-xl flex items-center justify-center text-2xl shadow-md`}>
                  {getAgentIcon(agent.name)}
                </div>
                <p className="mt-2 text-sm font-medium">{agent.label}</p>
              </div>
            ))}
          </div>

          <div className="flex justify-center">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="w-px h-8 bg-gray-300 mx-8"></div>
            ))}
          </div>
          <div className="text-gray-400">▼</div>

          {/* Synthesis */}
          <div className="w-full max-w-md bg-gradient-to-r from-yellow-500 to-yellow-600 rounded-2xl p-4 text-white text-center shadow-lg my-4">
            <p className="text-lg font-bold">📊 결과 종합</p>
            <p className="text-sm opacity-80">가중 평균 점수 & 추천 생성</p>
          </div>

          <div className="w-px h-8 bg-gray-300"></div>
          <div className="text-gray-400">▼</div>

          {/* Signal */}
          <div className="w-20 h-20 bg-gradient-to-br from-red-500 to-pink-600 rounded-2xl flex items-center justify-center text-white text-3xl shadow-lg">
            💹
          </div>
          <p className="mt-2 font-medium">트레이딩 시그널</p>
        </div>
      </div>
    </div>
  );
}

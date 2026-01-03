import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { analysisApi, stocksApi, analysisWebSocket } from '../../services/api';

interface AnalysisResult {
  agent: string;
  analysis_type: string;
  symbol: string;
  score: number | null;
  summary: string;
  recommendation: 'buy' | 'hold' | 'sell' | null;
  confidence: number;
  analyzed_at: string;
  details?: Record<string, unknown>;
}

interface ConsolidatedAnalysis {
  symbol: string;
  final_score: number;
  recommendation: string;
  confidence: number;
  signal_generated: boolean;
  agent_results: {
    news?: AnalysisResult;
    quant?: AnalysisResult;
    fundamental?: AnalysisResult;
    technical?: AnalysisResult;
  };
  summary: string;
  analyzed_at: string;
}

interface AnalysisHistory {
  id: number;
  symbol: string;
  analysis_type: string;
  agent_name: string;
  score: number | null;
  summary: string;
  recommendation: string | null;
  created_at: string;
}

interface TaskStatus {
  task_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  result?: ConsolidatedAnalysis;
  error?: string;
}

interface PriceData {
  close: number;
  change_percent: number;
}

export default function AnalysisPanel() {
  const queryClient = useQueryClient();
  const [selectedSymbol, setSelectedSymbol] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [activeTab, setActiveTab] = useState<'result' | 'history'>('result');
  const [taskId, setTaskId] = useState<string | null>(null);
  const [wsConnected, setWsConnected] = useState(false);

  // Search stocks
  const { data: searchResults } = useQuery({
    queryKey: ['stocks', 'search', searchInput],
    queryFn: () => stocksApi.list({ limit: 10 }),
    enabled: searchInput.length >= 2,
  });

  // Fetch consolidated analysis for selected symbol
  const { data: consolidatedAnalysis, isLoading: analysisLoading, refetch: refetchAnalysis } = useQuery<ConsolidatedAnalysis>({
    queryKey: ['analysis', 'consolidated', selectedSymbol],
    queryFn: () => analysisApi.getConsolidated(selectedSymbol),
    enabled: !!selectedSymbol,
  });

  // Fetch analysis history
  const { data: analysisHistory } = useQuery<AnalysisHistory[]>({
    queryKey: ['analysis', 'history', selectedSymbol],
    queryFn: () => analysisApi.getHistory(selectedSymbol, undefined, 20),
    enabled: !!selectedSymbol && activeTab === 'history',
  });

  // Fetch current price
  const { data: currentPrice } = useQuery<PriceData>({
    queryKey: ['price', selectedSymbol],
    queryFn: () => stocksApi.getRealtimePrice(selectedSymbol),
    enabled: !!selectedSymbol,
    refetchInterval: 10000,
  });

  // Poll task status
  const { data: taskStatus, isLoading: taskLoading } = useQuery<TaskStatus>({
    queryKey: ['analysis', 'task', taskId],
    queryFn: () => analysisApi.getTaskStatus(taskId!),
    enabled: !!taskId,
    refetchInterval: (query) => {
      const data = query.state.data as TaskStatus | undefined;
      if (data?.status === 'completed' || data?.status === 'failed') {
        return false;
      }
      return 2000;
    },
  });

  // Run quick analysis mutation
  const quickAnalysisMutation = useMutation({
    mutationFn: (symbol: string) => analysisApi.runQuickAnalysis(symbol),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['analysis', 'consolidated', selectedSymbol] });
      queryClient.invalidateQueries({ queryKey: ['analysis', 'history', selectedSymbol] });
    },
  });

  // Request background analysis mutation
  const backgroundAnalysisMutation = useMutation({
    mutationFn: (symbol: string) => analysisApi.requestBackgroundAnalysis(symbol),
    onSuccess: (data) => {
      setTaskId(data.task_id);
    },
  });

  // Run full analysis mutation
  const fullAnalysisMutation = useMutation({
    mutationFn: (symbol: string) => analysisApi.runFullAnalysis(symbol, {
      analysis_types: ['news', 'quant', 'fundamental', 'technical'],
      save_to_db: true,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['analysis', 'consolidated', selectedSymbol] });
      queryClient.invalidateQueries({ queryKey: ['analysis', 'history', selectedSymbol] });
    },
  });

  // Handle task completion
  useEffect(() => {
    if (taskStatus?.status === 'completed') {
      queryClient.invalidateQueries({ queryKey: ['analysis', 'consolidated', selectedSymbol] });
      queryClient.invalidateQueries({ queryKey: ['analysis', 'history', selectedSymbol] });
      setTaskId(null);
    }
  }, [taskStatus, selectedSymbol, queryClient]);

  // WebSocket connection
  useEffect(() => {
    if (!selectedSymbol) return;

    const ws = analysisWebSocket.connect();

    ws.onopen = () => {
      setWsConnected(true);
      analysisWebSocket.subscribeSymbol(ws, selectedSymbol);
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'analysis_update' && data.symbol === selectedSymbol) {
        refetchAnalysis();
      }
    };

    ws.onclose = () => setWsConnected(false);
    ws.onerror = () => setWsConnected(false);

    const pingInterval = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        analysisWebSocket.ping(ws);
      }
    }, 30000);

    return () => {
      clearInterval(pingInterval);
      ws.close();
    };
  }, [selectedSymbol, refetchAnalysis]);

  const handleSymbolSelect = (symbol: string) => {
    setSelectedSymbol(symbol);
    setSearchInput('');
  };

  const getScoreColor = (score: number | null) => {
    if (score === null) return 'text-gray-500';
    if (score >= 50) return 'text-green-600';
    if (score >= 20) return 'text-green-500';
    if (score >= -20) return 'text-gray-600';
    if (score >= -50) return 'text-red-500';
    return 'text-red-600';
  };

  const getScoreBgColor = (score: number | null) => {
    if (score === null) return 'bg-gray-100';
    if (score >= 50) return 'bg-green-100';
    if (score >= 20) return 'bg-green-50';
    if (score >= -20) return 'bg-gray-50';
    if (score >= -50) return 'bg-red-50';
    return 'bg-red-100';
  };

  const getRecommendationBadge = (rec: string | null) => {
    switch (rec) {
      case 'buy':
        return <span className="px-3 py-1 bg-green-100 text-green-800 rounded-full font-bold">매수</span>;
      case 'sell':
        return <span className="px-3 py-1 bg-red-100 text-red-800 rounded-full font-bold">매도</span>;
      case 'hold':
        return <span className="px-3 py-1 bg-yellow-100 text-yellow-800 rounded-full font-bold">보유</span>;
      default:
        return <span className="px-3 py-1 bg-gray-100 text-gray-800 rounded-full">-</span>;
    }
  };

  const getAgentIcon = (agent: string) => {
    switch (agent) {
      case 'gemini':
        return (
          <div className="w-8 h-8 rounded-full bg-purple-100 flex items-center justify-center">
            <span className="text-purple-600 font-bold text-xs">G</span>
          </div>
        );
      case 'chatgpt':
        return (
          <div className="w-8 h-8 rounded-full bg-green-100 flex items-center justify-center">
            <span className="text-green-600 font-bold text-xs">C</span>
          </div>
        );
      case 'claude':
        return (
          <div className="w-8 h-8 rounded-full bg-orange-100 flex items-center justify-center">
            <span className="text-orange-600 font-bold text-xs">CL</span>
          </div>
        );
      case 'ml':
        return (
          <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center">
            <span className="text-blue-600 font-bold text-xs">ML</span>
          </div>
        );
      default:
        return (
          <div className="w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center">
            <span className="text-gray-600 font-bold text-xs">?</span>
          </div>
        );
    }
  };

  const isAnalyzing = quickAnalysisMutation.isPending ||
    backgroundAnalysisMutation.isPending ||
    fullAnalysisMutation.isPending ||
    (taskId && taskStatus?.status !== 'completed' && taskStatus?.status !== 'failed');

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">AI 종목 분석</h1>
          <p className="text-sm text-gray-500 mt-1">
            4개의 AI 에이전트가 종합 분석을 수행합니다
          </p>
        </div>
        <span className={`flex items-center text-sm ${wsConnected ? 'text-green-600' : 'text-gray-400'}`}>
          <span className={`w-2 h-2 rounded-full mr-2 ${wsConnected ? 'bg-green-500 animate-pulse' : 'bg-gray-400'}`} />
          {wsConnected ? '실시간' : '오프라인'}
        </span>
      </div>

      {/* Search */}
      <div className="relative">
        <div className="flex space-x-3">
          <div className="flex-1 relative">
            <input
              type="text"
              value={searchInput || selectedSymbol}
              onChange={(e) => {
                setSearchInput(e.target.value.toUpperCase());
                if (e.target.value === '') setSelectedSymbol('');
              }}
              placeholder="종목 코드를 입력하세요 (예: 005930)"
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            />
            {searchInput && searchResults && (
              <div className="absolute z-10 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-60 overflow-auto">
                {searchResults.map((stock: { symbol: string; name: string; market: string }) => (
                  <button
                    key={stock.symbol}
                    onClick={() => handleSymbolSelect(stock.symbol)}
                    className="w-full px-4 py-2 text-left hover:bg-gray-50 flex justify-between items-center"
                  >
                    <span className="font-medium">{stock.symbol}</span>
                    <span className="text-sm text-gray-500">{stock.name}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Analysis Buttons */}
          <button
            onClick={() => quickAnalysisMutation.mutate(selectedSymbol)}
            disabled={!selectedSymbol || isAnalyzing}
            className="px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed font-medium"
          >
            빠른 분석
          </button>
          <button
            onClick={() => fullAnalysisMutation.mutate(selectedSymbol)}
            disabled={!selectedSymbol || isAnalyzing}
            className="px-4 py-3 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:bg-gray-300 disabled:cursor-not-allowed font-medium"
          >
            전체 분석
          </button>
          <button
            onClick={() => backgroundAnalysisMutation.mutate(selectedSymbol)}
            disabled={!selectedSymbol || isAnalyzing}
            className="px-4 py-3 bg-gray-600 text-white rounded-lg hover:bg-gray-700 disabled:bg-gray-300 disabled:cursor-not-allowed font-medium"
          >
            백그라운드
          </button>
        </div>
      </div>

      {/* Current Price */}
      {selectedSymbol && currentPrice && (
        <div className="bg-white rounded-lg shadow p-4 flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <div>
              <h2 className="text-xl font-bold text-gray-900">{selectedSymbol}</h2>
              <p className="text-sm text-gray-500">실시간 시세</p>
            </div>
          </div>
          <div className="text-right">
            <p className="text-2xl font-bold text-gray-900">
              {currentPrice.close?.toLocaleString()}원
            </p>
            <p className={`text-sm font-medium ${currentPrice.change_percent >= 0 ? 'text-red-600' : 'text-blue-600'}`}>
              {currentPrice.change_percent >= 0 ? '+' : ''}{currentPrice.change_percent?.toFixed(2)}%
            </p>
          </div>
        </div>
      )}

      {/* Loading / Task Status */}
      {isAnalyzing && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <div className="flex items-center">
            <svg className="animate-spin h-5 w-5 text-blue-600 mr-3" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
            </svg>
            <div>
              <p className="text-blue-800 font-medium">
                {taskId ? `분석 진행 중... (${taskStatus?.status || 'pending'})` : '분석 실행 중...'}
              </p>
              <p className="text-blue-600 text-sm">
                AI 에이전트가 {selectedSymbol} 종목을 분석하고 있습니다
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Tabs */}
      {selectedSymbol && (
        <div className="flex space-x-4 border-b">
          <button
            onClick={() => setActiveTab('result')}
            className={`pb-2 px-1 font-medium border-b-2 transition-colors ${
              activeTab === 'result'
                ? 'border-primary-600 text-primary-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            분석 결과
          </button>
          <button
            onClick={() => setActiveTab('history')}
            className={`pb-2 px-1 font-medium border-b-2 transition-colors ${
              activeTab === 'history'
                ? 'border-primary-600 text-primary-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            분석 히스토리
          </button>
        </div>
      )}

      {/* Analysis Result */}
      {activeTab === 'result' && consolidatedAnalysis && (
        <div className="space-y-6">
          {/* Final Score Card */}
          <div className={`rounded-lg shadow-lg p-6 ${getScoreBgColor(consolidatedAnalysis.final_score)}`}>
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-medium text-gray-700">종합 점수</h3>
                <p className={`text-5xl font-bold ${getScoreColor(consolidatedAnalysis.final_score)}`}>
                  {consolidatedAnalysis.final_score >= 0 ? '+' : ''}{consolidatedAnalysis.final_score?.toFixed(1)}
                </p>
              </div>
              <div className="text-right">
                <div className="mb-2">
                  {getRecommendationBadge(consolidatedAnalysis.recommendation)}
                </div>
                <p className="text-sm text-gray-500">
                  신뢰도: {consolidatedAnalysis.confidence?.toFixed(0)}%
                </p>
                {consolidatedAnalysis.signal_generated && (
                  <span className="inline-block mt-2 px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs font-medium">
                    시그널 생성됨
                  </span>
                )}
              </div>
            </div>
            <p className="mt-4 text-gray-700">{consolidatedAnalysis.summary}</p>
            <p className="mt-2 text-xs text-gray-500">
              분석 시간: {new Date(consolidatedAnalysis.analyzed_at).toLocaleString()}
            </p>
          </div>

          {/* Agent Results Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {(['news', 'quant', 'fundamental', 'technical'] as const).map((type) => {
              const result = consolidatedAnalysis.agent_results[type];
              if (!result) return null;

              return (
                <div key={type} className="bg-white rounded-lg shadow p-4">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center space-x-3">
                      {getAgentIcon(result.agent)}
                      <div>
                        <h4 className="font-medium text-gray-900">
                          {type === 'news' ? '뉴스 분석' :
                           type === 'quant' ? '퀀트 분석' :
                           type === 'fundamental' ? '펀더멘털 분석' :
                           '기술적 분석'}
                        </h4>
                        <p className="text-xs text-gray-500">{result.agent}</p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className={`text-xl font-bold ${getScoreColor(result.score)}`}>
                        {result.score !== null ? (result.score >= 0 ? '+' : '') + result.score.toFixed(0) : '-'}
                      </p>
                      {getRecommendationBadge(result.recommendation)}
                    </div>
                  </div>
                  <p className="text-sm text-gray-600 line-clamp-3">{result.summary}</p>
                  <div className="mt-2 flex justify-between items-center text-xs text-gray-500">
                    <span>신뢰도: {result.confidence?.toFixed(0)}%</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Analysis History */}
      {activeTab === 'history' && (
        <div className="bg-white rounded-lg shadow">
          {analysisHistory && analysisHistory.length > 0 ? (
            <div className="divide-y">
              {analysisHistory.map((item) => (
                <div key={item.id} className="p-4 hover:bg-gray-50">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center space-x-3">
                      {getAgentIcon(item.agent_name)}
                      <div>
                        <div className="flex items-center space-x-2">
                          <span className="font-medium text-gray-900">{item.analysis_type}</span>
                          <span className="text-xs px-2 py-0.5 bg-gray-100 text-gray-600 rounded">
                            {item.agent_name}
                          </span>
                        </div>
                        <p className="text-sm text-gray-600 mt-1 line-clamp-2">{item.summary}</p>
                        <p className="text-xs text-gray-400 mt-1">
                          {new Date(item.created_at).toLocaleString()}
                        </p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className={`text-lg font-bold ${getScoreColor(item.score)}`}>
                        {item.score !== null ? (item.score >= 0 ? '+' : '') + item.score : '-'}
                      </p>
                      {getRecommendationBadge(item.recommendation)}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-12 text-gray-500">
              <svg className="w-12 h-12 mx-auto mb-4 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <p>분석 히스토리가 없습니다</p>
            </div>
          )}
        </div>
      )}

      {/* Empty State */}
      {!selectedSymbol && (
        <div className="bg-white rounded-lg shadow p-12 text-center">
          <svg className="w-16 h-16 mx-auto mb-4 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <h3 className="text-lg font-medium text-gray-900 mb-2">종목을 선택하세요</h3>
          <p className="text-gray-500">
            분석할 종목 코드를 입력하면 AI 에이전트가 종합 분석을 수행합니다
          </p>
          <div className="mt-6 flex justify-center space-x-4">
            {['005930', '000660', '035420', '035720'].map((symbol) => (
              <button
                key={symbol}
                onClick={() => handleSymbolSelect(symbol)}
                className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 text-sm font-medium"
              >
                {symbol}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

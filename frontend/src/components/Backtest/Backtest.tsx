import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { backtestApi } from '../../services/api';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  AreaChart,
  Area,
} from 'recharts';
import clsx from 'clsx';

interface StrategyParam {
  type: string;
  min: number;
  max: number;
  default: number;
}

interface Strategy {
  name: string;
  description: string;
  parameters: Record<string, StrategyParam>;
}

interface Trade {
  symbol: string;
  entry_date: string;
  entry_price: number;
  exit_date: string;
  exit_price: number;
  quantity: number;
  pnl: number;
  pnl_pct: number;
  holding_days: number;
  exit_reason: string;
}

interface BacktestResult {
  success: boolean;
  id?: number;
  strategy_name: string;
  start_date: string;
  end_date: string;
  initial_capital: number;
  final_value: number;
  total_return_pct: number;
  num_trades: number;
  metrics: {
    returns: Record<string, number>;
    risk: Record<string, number>;
    risk_adjusted: Record<string, number>;
    trading: Record<string, number>;
  };
  trades: Trade[];
  equity_curve: Array<{ date: string; equity: number }>;
  errors: string[];
}

interface BacktestHistoryItem {
  id: number;
  strategy_name: string;
  strategy_display_name: string | null;
  symbols: string[];
  start_date: string;
  end_date: string;
  initial_capital: number;
  final_value: number;
  total_return_pct: number;
  total_trades: number;
  sharpe_ratio: number | null;
  max_drawdown: number | null;
  win_rate: number | null;
  is_favorite: boolean;
  tags: string[] | null;
  notes: string | null;
  created_at: string;
}

const KOREAN_STOCKS = [
  { symbol: '005930', name: '삼성전자' },
  { symbol: '000660', name: 'SK하이닉스' },
  { symbol: '035420', name: 'NAVER' },
  { symbol: '035720', name: '카카오' },
  { symbol: '051910', name: 'LG화학' },
  { symbol: '006400', name: '삼성SDI' },
  { symbol: '068270', name: '셀트리온' },
  { symbol: '105560', name: 'KB금융' },
  { symbol: '055550', name: '신한지주' },
  { symbol: '003550', name: 'LG' },
];

export default function Backtest() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<'run' | 'history'>('run');
  const [selectedStrategy, setSelectedStrategy] = useState<string>('');
  const [selectedSymbols, setSelectedSymbols] = useState<string[]>([]);
  const [startDate, setStartDate] = useState<string>(() => {
    const date = new Date();
    date.setFullYear(date.getFullYear() - 1);
    return date.toISOString().split('T')[0];
  });
  const [endDate, setEndDate] = useState<string>(() => {
    return new Date().toISOString().split('T')[0];
  });
  const [initialCapital, setInitialCapital] = useState<number>(10000000);
  const [params, setParams] = useState<Record<string, number>>({});
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [historyFilter, setHistoryFilter] = useState<{ strategy?: string; favorites_only: boolean }>({
    favorites_only: false,
  });
  const [selectedHistoryId, setSelectedHistoryId] = useState<number | null>(null);

  // Fetch strategies
  const { data: strategiesData } = useQuery({
    queryKey: ['backtest', 'strategies'],
    queryFn: backtestApi.getStrategies,
  });

  // Fetch history
  const { data: historyData, isLoading: historyLoading } = useQuery({
    queryKey: ['backtest', 'history', historyFilter],
    queryFn: () => backtestApi.getHistory({ limit: 50, ...historyFilter }),
    enabled: activeTab === 'history',
  });

  // Fetch selected history detail
  const { data: historyDetail } = useQuery({
    queryKey: ['backtest', 'detail', selectedHistoryId],
    queryFn: () => backtestApi.getDetail(selectedHistoryId!),
    enabled: selectedHistoryId !== null,
  });

  const strategies: Strategy[] = strategiesData?.strategies || [];
  const history: BacktestHistoryItem[] = historyData?.history || [];

  const currentStrategy = useMemo(
    () => strategies.find((s) => s.name === selectedStrategy),
    [strategies, selectedStrategy]
  );

  // Run backtest mutation
  const runBacktest = useMutation({
    mutationFn: backtestApi.run,
    onSuccess: (data) => {
      setResult(data);
      queryClient.invalidateQueries({ queryKey: ['backtest', 'history'] });
    },
  });

  // Toggle favorite mutation
  const toggleFavorite = useMutation({
    mutationFn: ({ id, is_favorite }: { id: number; is_favorite: boolean }) =>
      backtestApi.updateBacktest(id, { is_favorite }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['backtest', 'history'] });
    },
  });

  // Delete backtest mutation
  const deleteBacktest = useMutation({
    mutationFn: backtestApi.deleteBacktest,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['backtest', 'history'] });
      setSelectedHistoryId(null);
    },
  });

  const handleStrategyChange = (strategyName: string) => {
    setSelectedStrategy(strategyName);
    const strategy = strategies.find((s) => s.name === strategyName);
    if (strategy) {
      const defaultParams: Record<string, number> = {};
      Object.entries(strategy.parameters).forEach(([key, param]) => {
        defaultParams[key] = param.default;
      });
      setParams(defaultParams);
    }
  };

  const handleSymbolToggle = (symbol: string) => {
    setSelectedSymbols((prev) =>
      prev.includes(symbol)
        ? prev.filter((s) => s !== symbol)
        : [...prev, symbol]
    );
  };

  const handleRun = () => {
    if (!selectedStrategy || selectedSymbols.length === 0) return;

    runBacktest.mutate({
      strategy: selectedStrategy,
      symbols: selectedSymbols,
      start_date: startDate,
      end_date: endDate,
      initial_capital: initialCapital,
      parameters: params,
    });
  };

  const formatNumber = (num: number) => num.toLocaleString('ko-KR');
  const formatPercent = (num: number) => `${num >= 0 ? '+' : ''}${num.toFixed(2)}%`;
  const formatCurrency = (num: number) => `${formatNumber(Math.round(num))}원`;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">백테스팅</h1>
          <p className="text-sm text-gray-500 mt-1">
            과거 데이터로 전략의 성과를 검증하세요
          </p>
        </div>
        {/* Tabs */}
        <div className="flex gap-2">
          <button
            onClick={() => setActiveTab('run')}
            className={clsx(
              'px-4 py-2 rounded-lg font-medium transition-colors',
              activeTab === 'run'
                ? 'bg-primary-600 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            )}
          >
            백테스트 실행
          </button>
          <button
            onClick={() => setActiveTab('history')}
            className={clsx(
              'px-4 py-2 rounded-lg font-medium transition-colors',
              activeTab === 'history'
                ? 'bg-primary-600 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            )}
          >
            히스토리
          </button>
        </div>
      </div>

      {/* History Tab */}
      {activeTab === 'history' && (
        <div className="space-y-4">
          {/* Filters */}
          <div className="bg-white rounded-lg shadow p-4 flex gap-4 items-center">
            <select
              value={historyFilter.strategy || ''}
              onChange={(e) => setHistoryFilter({ ...historyFilter, strategy: e.target.value || undefined })}
              className="px-3 py-2 border border-gray-300 rounded-md text-sm"
            >
              <option value="">모든 전략</option>
              {strategies.map((s) => (
                <option key={s.name} value={s.name}>{s.description}</option>
              ))}
            </select>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={historyFilter.favorites_only}
                onChange={(e) => setHistoryFilter({ ...historyFilter, favorites_only: e.target.checked })}
                className="rounded border-gray-300 text-primary-600"
              />
              즐겨찾기만
            </label>
          </div>

          {/* History List */}
          {historyLoading ? (
            <div className="text-center py-8 text-gray-500">로딩 중...</div>
          ) : history.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              백테스트 히스토리가 없습니다. 백테스트를 실행해보세요!
            </div>
          ) : (
            <div className="bg-white rounded-lg shadow overflow-hidden">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">전략</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">종목</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">기간</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">수익률</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">샤프</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">MDD</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">거래</th>
                    <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">액션</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {history.map((item) => (
                    <tr
                      key={item.id}
                      className={clsx(
                        'hover:bg-gray-50 cursor-pointer',
                        selectedHistoryId === item.id && 'bg-primary-50'
                      )}
                      onClick={() => setSelectedHistoryId(item.id)}
                    >
                      <td className="px-4 py-3 text-sm font-medium text-gray-900">
                        {item.strategy_display_name || item.strategy_name}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-500">
                        {item.symbols.slice(0, 2).join(', ')}
                        {item.symbols.length > 2 && ` +${item.symbols.length - 2}`}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-500">
                        {item.start_date} ~ {item.end_date}
                      </td>
                      <td className={clsx(
                        'px-4 py-3 text-sm text-right font-medium',
                        item.total_return_pct >= 0 ? 'text-green-600' : 'text-red-600'
                      )}>
                        {item.total_return_pct >= 0 ? '+' : ''}{item.total_return_pct.toFixed(2)}%
                      </td>
                      <td className="px-4 py-3 text-sm text-right text-gray-900">
                        {item.sharpe_ratio?.toFixed(2) || '-'}
                      </td>
                      <td className="px-4 py-3 text-sm text-right text-red-600">
                        {item.max_drawdown?.toFixed(2) || '-'}%
                      </td>
                      <td className="px-4 py-3 text-sm text-right text-gray-900">
                        {item.total_trades}
                      </td>
                      <td className="px-4 py-3 text-center">
                        <div className="flex justify-center gap-2">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              toggleFavorite.mutate({ id: item.id, is_favorite: !item.is_favorite });
                            }}
                            className={clsx(
                              'text-lg',
                              item.is_favorite ? 'text-yellow-500' : 'text-gray-300 hover:text-yellow-500'
                            )}
                          >
                            {item.is_favorite ? '★' : '☆'}
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              if (confirm('삭제하시겠습니까?')) {
                                deleteBacktest.mutate(item.id);
                              }
                            }}
                            className="text-gray-400 hover:text-red-500"
                          >
                            ✕
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* History Detail */}
          {historyDetail && (
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold mb-4">
                {historyDetail.strategy_display_name || historyDetail.strategy_name} 상세
              </h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                <div>
                  <p className="text-sm text-gray-500">초기 자본</p>
                  <p className="font-medium">{formatCurrency(historyDetail.initial_capital)}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">최종 자산</p>
                  <p className="font-medium">{formatCurrency(historyDetail.final_value)}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">승률</p>
                  <p className="font-medium">
                    {historyDetail.winning_trades}/{historyDetail.total_trades} (
                    {((historyDetail.winning_trades / historyDetail.total_trades) * 100 || 0).toFixed(1)}%)
                  </p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">실행일</p>
                  <p className="font-medium">{new Date(historyDetail.created_at).toLocaleString('ko-KR')}</p>
                </div>
              </div>
              {historyDetail.equity_curve && historyDetail.equity_curve.length > 0 && (
                <ResponsiveContainer width="100%" height={200}>
                  <AreaChart data={historyDetail.equity_curve}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis
                      dataKey="date"
                      tickFormatter={(date) => new Date(date).toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' })}
                    />
                    <YAxis tickFormatter={(value) => `${(value / 1000000).toFixed(0)}M`} />
                    <Tooltip
                      labelFormatter={(date) => new Date(date).toLocaleDateString('ko-KR')}
                      formatter={(value: number) => [formatCurrency(value), '자산']}
                    />
                    <Area type="monotone" dataKey="equity" stroke="#2563eb" fill="#3b82f6" fillOpacity={0.3} />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </div>
          )}
        </div>
      )}

      {/* Run Tab - Configuration Panel */}
      {activeTab === 'run' && (
        <>

      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">설정</h2>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Strategy Selection */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              전략
            </label>
            <select
              value={selectedStrategy}
              onChange={(e) => handleStrategyChange(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-primary-500 focus:border-primary-500"
            >
              <option value="">전략 선택</option>
              {strategies.map((strategy) => (
                <option key={strategy.name} value={strategy.name}>
                  {strategy.description}
                </option>
              ))}
            </select>
          </div>

          {/* Date Range */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              시작일
            </label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-primary-500 focus:border-primary-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              종료일
            </label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-primary-500 focus:border-primary-500"
            />
          </div>

          {/* Initial Capital */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              초기 자본
            </label>
            <input
              type="number"
              value={initialCapital}
              onChange={(e) => setInitialCapital(Number(e.target.value))}
              step={1000000}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-primary-500 focus:border-primary-500"
            />
          </div>
        </div>

        {/* Strategy Parameters */}
        {currentStrategy && Object.keys(currentStrategy.parameters).length > 0 && (
          <div className="mt-4 p-4 bg-gray-50 rounded-lg">
            <h3 className="text-sm font-medium text-gray-700 mb-3">전략 파라미터</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {Object.entries(currentStrategy.parameters).map(([key, param]) => (
                <div key={key}>
                  <label className="block text-xs text-gray-500 mb-1">
                    {key} ({param.min}-{param.max})
                  </label>
                  <input
                    type="number"
                    value={params[key] || param.default}
                    onChange={(e) => setParams({ ...params, [key]: Number(e.target.value) })}
                    min={param.min}
                    max={param.max}
                    step={param.type === 'float' ? 0.1 : 1}
                    className="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:ring-primary-500 focus:border-primary-500"
                  />
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Symbol Selection */}
        <div className="mt-4">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            종목 선택
          </label>
          <div className="flex flex-wrap gap-2">
            {KOREAN_STOCKS.map((stock) => (
              <button
                key={stock.symbol}
                onClick={() => handleSymbolToggle(stock.symbol)}
                className={`px-3 py-1 rounded-full text-sm font-medium transition-colors ${
                  selectedSymbols.includes(stock.symbol)
                    ? 'bg-primary-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                {stock.name}
              </button>
            ))}
          </div>
        </div>

        {/* Run Button */}
        <div className="mt-6">
          <button
            onClick={handleRun}
            disabled={!selectedStrategy || selectedSymbols.length === 0 || runBacktest.isPending}
            className="px-6 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:bg-gray-300 font-medium"
          >
            {runBacktest.isPending ? '실행 중...' : '백테스트 실행'}
          </button>
        </div>
      </div>

      {/* Results */}
      {result && (
        <>
          {/* Summary Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-white rounded-lg shadow p-4">
              <p className="text-sm text-gray-500">총 수익률</p>
              <p className={`text-2xl font-bold ${result.total_return_pct >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {formatPercent(result.total_return_pct)}
              </p>
            </div>
            <div className="bg-white rounded-lg shadow p-4">
              <p className="text-sm text-gray-500">최종 자산</p>
              <p className="text-2xl font-bold text-gray-900">
                {formatCurrency(result.final_value)}
              </p>
            </div>
            <div className="bg-white rounded-lg shadow p-4">
              <p className="text-sm text-gray-500">샤프 비율</p>
              <p className="text-2xl font-bold text-gray-900">
                {result.metrics.risk_adjusted?.sharpe_ratio?.toFixed(2) || 'N/A'}
              </p>
            </div>
            <div className="bg-white rounded-lg shadow p-4">
              <p className="text-sm text-gray-500">승률</p>
              <p className="text-2xl font-bold text-gray-900">
                {result.metrics.trading?.win_rate?.toFixed(1) || 0}%
              </p>
            </div>
          </div>

          {/* Equity Curve Chart */}
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">자산 곡선</h2>
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart data={result.equity_curve}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis
                  dataKey="date"
                  tickFormatter={(date) => new Date(date).toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' })}
                />
                <YAxis
                  tickFormatter={(value) => `${(value / 1000000).toFixed(0)}M`}
                  domain={['dataMin', 'dataMax']}
                />
                <Tooltip
                  labelFormatter={(date) => new Date(date).toLocaleDateString('ko-KR')}
                  formatter={(value: number) => [formatCurrency(value), '자산']}
                />
                <Area
                  type="monotone"
                  dataKey="equity"
                  stroke="#2563eb"
                  fill="#3b82f6"
                  fillOpacity={0.3}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {/* Detailed Metrics */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Returns */}
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">수익률 지표</h3>
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-gray-600">총 수익금</span>
                  <span className="font-medium">{formatCurrency(result.metrics.returns?.total_return || 0)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">연환산 수익률</span>
                  <span className="font-medium">{formatPercent(result.metrics.returns?.annualized_return || 0)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">알파</span>
                  <span className="font-medium">{(result.metrics.returns?.alpha || 0).toFixed(4)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">베타</span>
                  <span className="font-medium">{(result.metrics.returns?.beta || 0).toFixed(4)}</span>
                </div>
              </div>
            </div>

            {/* Risk */}
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">리스크 지표</h3>
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-gray-600">연환산 변동성</span>
                  <span className="font-medium">{formatPercent(result.metrics.risk?.annualized_volatility || 0)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">최대 낙폭 (MDD)</span>
                  <span className="font-medium text-red-600">{formatPercent(result.metrics.risk?.max_drawdown || 0)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">VaR (95%)</span>
                  <span className="font-medium">{formatPercent(result.metrics.risk?.var_95 || 0)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">CVaR (95%)</span>
                  <span className="font-medium">{formatPercent(result.metrics.risk?.cvar_95 || 0)}</span>
                </div>
              </div>
            </div>

            {/* Risk-Adjusted */}
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">위험조정 수익률</h3>
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-gray-600">샤프 비율</span>
                  <span className="font-medium">{(result.metrics.risk_adjusted?.sharpe_ratio || 0).toFixed(4)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">소르티노 비율</span>
                  <span className="font-medium">{(result.metrics.risk_adjusted?.sortino_ratio || 0).toFixed(4)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">칼마 비율</span>
                  <span className="font-medium">{(result.metrics.risk_adjusted?.calmar_ratio || 0).toFixed(4)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">정보 비율</span>
                  <span className="font-medium">{(result.metrics.risk_adjusted?.information_ratio || 0).toFixed(4)}</span>
                </div>
              </div>
            </div>

            {/* Trading Stats */}
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">매매 통계</h3>
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-gray-600">총 거래 수</span>
                  <span className="font-medium">{result.metrics.trading?.total_trades || 0}회</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">승리 / 손실</span>
                  <span className="font-medium">
                    <span className="text-green-600">{result.metrics.trading?.winning_trades || 0}</span>
                    {' / '}
                    <span className="text-red-600">{result.metrics.trading?.losing_trades || 0}</span>
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">평균 수익</span>
                  <span className="font-medium text-green-600">{formatCurrency(result.metrics.trading?.avg_win || 0)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">평균 손실</span>
                  <span className="font-medium text-red-600">{formatCurrency(result.metrics.trading?.avg_loss || 0)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">손익비</span>
                  <span className="font-medium">{(result.metrics.trading?.profit_factor || 0).toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">평균 보유일</span>
                  <span className="font-medium">{(result.metrics.trading?.avg_holding_days || 0).toFixed(1)}일</span>
                </div>
              </div>
            </div>
          </div>

          {/* Trade History */}
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              거래 내역 ({result.trades.length}건)
            </h2>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead>
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">종목</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">진입일</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">진입가</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">청산일</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">청산가</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">수량</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">손익</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">수익률</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">청산사유</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {result.trades.slice(0, 50).map((trade, idx) => (
                    <tr key={idx} className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm font-medium text-gray-900">{trade.symbol}</td>
                      <td className="px-4 py-3 text-sm text-gray-500">
                        {new Date(trade.entry_date).toLocaleDateString('ko-KR')}
                      </td>
                      <td className="px-4 py-3 text-sm text-right text-gray-900">
                        {formatNumber(Math.round(trade.entry_price))}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-500">
                        {new Date(trade.exit_date).toLocaleDateString('ko-KR')}
                      </td>
                      <td className="px-4 py-3 text-sm text-right text-gray-900">
                        {formatNumber(Math.round(trade.exit_price))}
                      </td>
                      <td className="px-4 py-3 text-sm text-right text-gray-900">
                        {formatNumber(trade.quantity)}
                      </td>
                      <td className={`px-4 py-3 text-sm text-right font-medium ${trade.pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {trade.pnl >= 0 ? '+' : ''}{formatNumber(Math.round(trade.pnl))}
                      </td>
                      <td className={`px-4 py-3 text-sm text-right font-medium ${trade.pnl_pct >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {formatPercent(trade.pnl_pct)}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-500">{trade.exit_reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {result.trades.length > 50 && (
                <p className="text-center py-4 text-gray-500 text-sm">
                  최근 50건만 표시됩니다 (총 {result.trades.length}건)
                </p>
              )}
            </div>
          </div>
        </>
      )}
        </>
      )}
    </div>
  );
}

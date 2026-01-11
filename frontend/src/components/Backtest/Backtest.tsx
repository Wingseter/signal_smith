import { useState, useMemo } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
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

  // Fetch strategies
  const { data: strategiesData } = useQuery({
    queryKey: ['backtest', 'strategies'],
    queryFn: backtestApi.getStrategies,
  });

  const strategies: Strategy[] = strategiesData?.strategies || [];

  const currentStrategy = useMemo(
    () => strategies.find((s) => s.name === selectedStrategy),
    [strategies, selectedStrategy]
  );

  // Run backtest mutation
  const runBacktest = useMutation({
    mutationFn: backtestApi.run,
    onSuccess: (data) => {
      setResult(data);
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
      <div>
        <h1 className="text-2xl font-bold text-gray-900">백테스팅</h1>
        <p className="text-sm text-gray-500 mt-1">
          과거 데이터로 전략의 성과를 검증하세요
        </p>
      </div>

      {/* Configuration Panel */}
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
    </div>
  );
}

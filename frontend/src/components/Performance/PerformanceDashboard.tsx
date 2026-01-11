import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { performanceApi } from '../../services/api';
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from 'recharts';

interface SignalPerformance {
  signal_id: number;
  symbol: string;
  signal_type: string;
  signal_date: string;
  signal_price: number;
  current_price: number;
  pnl: number;
  pnl_pct: number;
  executed: boolean;
  strength: number;
}

interface RiskMetrics {
  sharpe_ratio: number;
  sortino_ratio: number;
  max_drawdown: number;
  max_drawdown_duration: number;
  volatility: number;
  var_95: number;
  calmar_ratio: number;
}

interface PerformanceDashboardData {
  summary: {
    total_signals: number;
    executed_signals: number;
    buy_signals: number;
    sell_signals: number;
    win_rate: number;
    avg_return: number;
    total_pnl: number;
    best_signal: SignalPerformance | null;
    worst_signal: SignalPerformance | null;
  };
  risk_metrics: RiskMetrics;
  equity_curve: Array<{ date: string; value: number }>;
  daily_returns: Array<{ date: string; value: number }>;
  drawdown_series: Array<{ date: string; value: number }>;
  signal_performance: SignalPerformance[];
  performance_by_symbol: Record<string, { signals: number; win_rate: number; total_pnl: number; avg_return: number }>;
  performance_by_type: Record<string, { count: number; win_rate: number; avg_return: number; total_pnl: number }>;
  monthly_returns: Array<{ month: string; return: number; start_value: number; end_value: number }>;
}

const PERIODS = [
  { value: '1m', label: '1개월' },
  { value: '3m', label: '3개월' },
  { value: '6m', label: '6개월' },
  { value: '1y', label: '1년' },
  { value: 'all', label: '전체' },
];

const COLORS = ['#2563eb', '#16a34a', '#dc2626', '#ca8a04', '#9333ea', '#0891b2'];

export default function PerformanceDashboard() {
  const [period, setPeriod] = useState('3m');

  const { data, isLoading, error } = useQuery<PerformanceDashboardData>({
    queryKey: ['performance', 'dashboard', period],
    queryFn: () => performanceApi.getDashboard(period),
  });

  const formatNumber = (num: number) => num.toLocaleString('ko-KR');
  const formatPercent = (num: number) => `${num >= 0 ? '+' : ''}${num.toFixed(2)}%`;
  const formatCurrency = (num: number) => `${formatNumber(Math.round(num))}원`;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 text-red-600 p-4 rounded-lg">
        성과 데이터를 불러오는데 실패했습니다.
      </div>
    );
  }

  if (!data) {
    return (
      <div className="bg-gray-50 text-gray-600 p-4 rounded-lg text-center">
        성과 데이터가 없습니다.
      </div>
    );
  }

  const { summary, risk_metrics, equity_curve, drawdown_series, signal_performance, performance_by_symbol, performance_by_type, monthly_returns } = data;

  // Prepare pie chart data for signal types
  const signalTypeData = Object.entries(performance_by_type).map(([type, stats]) => ({
    name: type === 'buy' ? '매수' : '매도',
    value: stats.count,
    winRate: stats.win_rate,
    avgReturn: stats.avg_return,
  }));

  // Prepare symbol performance for bar chart
  const symbolData = Object.entries(performance_by_symbol)
    .map(([symbol, stats]) => ({
      symbol,
      ...stats,
    }))
    .sort((a, b) => b.total_pnl - a.total_pnl)
    .slice(0, 10);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">성과 분석</h1>
          <p className="text-sm text-gray-500 mt-1">
            시그널별 수익률 및 리스크 지표 분석
          </p>
        </div>
        <div className="flex space-x-2">
          {PERIODS.map((p) => (
            <button
              key={p.value}
              onClick={() => setPeriod(p.value)}
              className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                period === p.value
                  ? 'bg-primary-600 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-xs text-gray-500">총 시그널</p>
          <p className="text-xl font-bold text-gray-900">{summary.total_signals}</p>
          <p className="text-xs text-gray-400">실행: {summary.executed_signals}</p>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-xs text-gray-500">승률</p>
          <p className={`text-xl font-bold ${summary.win_rate >= 50 ? 'text-green-600' : 'text-red-600'}`}>
            {summary.win_rate.toFixed(1)}%
          </p>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-xs text-gray-500">총 수익</p>
          <p className={`text-xl font-bold ${summary.total_pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {formatCurrency(summary.total_pnl)}
          </p>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-xs text-gray-500">평균 수익률</p>
          <p className={`text-xl font-bold ${summary.avg_return >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {formatPercent(summary.avg_return)}
          </p>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-xs text-gray-500">샤프 비율</p>
          <p className={`text-xl font-bold ${risk_metrics.sharpe_ratio >= 1 ? 'text-green-600' : 'text-gray-900'}`}>
            {risk_metrics.sharpe_ratio.toFixed(2)}
          </p>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-xs text-gray-500">최대 낙폭</p>
          <p className="text-xl font-bold text-red-600">
            {risk_metrics.max_drawdown.toFixed(2)}%
          </p>
        </div>
      </div>

      {/* Risk Metrics Detail */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg shadow p-4">
          <h3 className="text-sm font-medium text-gray-700 mb-3">위험조정 수익률</h3>
          <div className="space-y-2">
            <div className="flex justify-between">
              <span className="text-sm text-gray-500">샤프 비율</span>
              <span className="font-medium">{risk_metrics.sharpe_ratio.toFixed(4)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-gray-500">소르티노 비율</span>
              <span className="font-medium">{risk_metrics.sortino_ratio.toFixed(4)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-gray-500">칼마 비율</span>
              <span className="font-medium">{risk_metrics.calmar_ratio.toFixed(4)}</span>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <h3 className="text-sm font-medium text-gray-700 mb-3">리스크 지표</h3>
          <div className="space-y-2">
            <div className="flex justify-between">
              <span className="text-sm text-gray-500">변동성</span>
              <span className="font-medium">{risk_metrics.volatility.toFixed(2)}%</span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-gray-500">VaR (95%)</span>
              <span className="font-medium text-red-600">{risk_metrics.var_95.toFixed(2)}%</span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-gray-500">MDD</span>
              <span className="font-medium text-red-600">{risk_metrics.max_drawdown.toFixed(2)}%</span>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <h3 className="text-sm font-medium text-gray-700 mb-3">매수 시그널</h3>
          <div className="space-y-2">
            <div className="flex justify-between">
              <span className="text-sm text-gray-500">개수</span>
              <span className="font-medium">{performance_by_type.buy?.count || 0}건</span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-gray-500">승률</span>
              <span className="font-medium">{(performance_by_type.buy?.win_rate || 0).toFixed(1)}%</span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-gray-500">평균수익</span>
              <span className={`font-medium ${(performance_by_type.buy?.avg_return || 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {formatPercent(performance_by_type.buy?.avg_return || 0)}
              </span>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <h3 className="text-sm font-medium text-gray-700 mb-3">매도 시그널</h3>
          <div className="space-y-2">
            <div className="flex justify-between">
              <span className="text-sm text-gray-500">개수</span>
              <span className="font-medium">{performance_by_type.sell?.count || 0}건</span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-gray-500">승률</span>
              <span className="font-medium">{(performance_by_type.sell?.win_rate || 0).toFixed(1)}%</span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-gray-500">평균수익</span>
              <span className={`font-medium ${(performance_by_type.sell?.avg_return || 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {formatPercent(performance_by_type.sell?.avg_return || 0)}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Equity Curve */}
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">자산 곡선</h3>
          {equity_curve.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <AreaChart data={equity_curve}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis
                  dataKey="date"
                  tickFormatter={(d) => new Date(d).toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' })}
                  fontSize={11}
                />
                <YAxis
                  tickFormatter={(v) => `${(v / 1000000).toFixed(0)}M`}
                  fontSize={11}
                />
                <Tooltip
                  labelFormatter={(d) => new Date(d).toLocaleDateString('ko-KR')}
                  formatter={(v: number) => [formatCurrency(v), '자산']}
                />
                <Area type="monotone" dataKey="value" stroke="#2563eb" fill="#3b82f6" fillOpacity={0.3} />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[250px] flex items-center justify-center text-gray-400">
              데이터 없음
            </div>
          )}
        </div>

        {/* Drawdown Chart */}
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">낙폭 (Drawdown)</h3>
          {drawdown_series.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <AreaChart data={drawdown_series}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis
                  dataKey="date"
                  tickFormatter={(d) => new Date(d).toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' })}
                  fontSize={11}
                />
                <YAxis
                  tickFormatter={(v) => `${v}%`}
                  domain={['dataMin', 0]}
                  fontSize={11}
                />
                <Tooltip
                  labelFormatter={(d) => new Date(d).toLocaleDateString('ko-KR')}
                  formatter={(v: number) => [`${v.toFixed(2)}%`, 'Drawdown']}
                />
                <Area type="monotone" dataKey="value" stroke="#dc2626" fill="#ef4444" fillOpacity={0.3} />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[250px] flex items-center justify-center text-gray-400">
              데이터 없음
            </div>
          )}
        </div>
      </div>

      {/* Monthly Returns & Symbol Performance */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Monthly Returns */}
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">월별 수익률</h3>
          {monthly_returns.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={monthly_returns}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="month" fontSize={11} />
                <YAxis tickFormatter={(v) => `${v}%`} fontSize={11} />
                <Tooltip formatter={(v: number) => [`${v.toFixed(2)}%`, '수익률']} />
                <Bar
                  dataKey="return"
                  fill="#2563eb"
                  radius={[4, 4, 0, 0]}
                >
                  {monthly_returns.map((entry, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={entry.return >= 0 ? '#16a34a' : '#dc2626'}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[250px] flex items-center justify-center text-gray-400">
              데이터 없음
            </div>
          )}
        </div>

        {/* Symbol Performance */}
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">종목별 수익</h3>
          {symbolData.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={symbolData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" tickFormatter={(v) => formatCurrency(v)} fontSize={10} />
                <YAxis type="category" dataKey="symbol" width={70} fontSize={11} />
                <Tooltip formatter={(v: number) => [formatCurrency(v), '수익']} />
                <Bar dataKey="total_pnl" radius={[0, 4, 4, 0]}>
                  {symbolData.map((entry, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={entry.total_pnl >= 0 ? '#16a34a' : '#dc2626'}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[250px] flex items-center justify-center text-gray-400">
              데이터 없음
            </div>
          )}
        </div>
      </div>

      {/* Best/Worst Signals & Signal Type Distribution */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Best Signal */}
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">최고 성과</h3>
          {summary.best_signal ? (
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-lg font-bold">{summary.best_signal.symbol}</span>
                <span className={`px-2 py-1 rounded text-xs font-medium ${
                  summary.best_signal.signal_type === 'buy' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                }`}>
                  {summary.best_signal.signal_type === 'buy' ? '매수' : '매도'}
                </span>
              </div>
              <div className="text-3xl font-bold text-green-600">
                {formatPercent(summary.best_signal.pnl_pct)}
              </div>
              <div className="text-sm text-gray-500">
                {new Date(summary.best_signal.signal_date).toLocaleDateString('ko-KR')}
              </div>
              <div className="text-sm">
                <span className="text-gray-500">진입가:</span>{' '}
                <span className="font-medium">{formatNumber(summary.best_signal.signal_price)}원</span>
              </div>
            </div>
          ) : (
            <div className="text-gray-400 text-center py-8">데이터 없음</div>
          )}
        </div>

        {/* Worst Signal */}
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">최저 성과</h3>
          {summary.worst_signal ? (
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-lg font-bold">{summary.worst_signal.symbol}</span>
                <span className={`px-2 py-1 rounded text-xs font-medium ${
                  summary.worst_signal.signal_type === 'buy' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                }`}>
                  {summary.worst_signal.signal_type === 'buy' ? '매수' : '매도'}
                </span>
              </div>
              <div className="text-3xl font-bold text-red-600">
                {formatPercent(summary.worst_signal.pnl_pct)}
              </div>
              <div className="text-sm text-gray-500">
                {new Date(summary.worst_signal.signal_date).toLocaleDateString('ko-KR')}
              </div>
              <div className="text-sm">
                <span className="text-gray-500">진입가:</span>{' '}
                <span className="font-medium">{formatNumber(summary.worst_signal.signal_price)}원</span>
              </div>
            </div>
          ) : (
            <div className="text-gray-400 text-center py-8">데이터 없음</div>
          )}
        </div>

        {/* Signal Distribution */}
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">시그널 분포</h3>
          {signalTypeData.length > 0 && signalTypeData.some(d => d.value > 0) ? (
            <ResponsiveContainer width="100%" height={180}>
              <PieChart>
                <Pie
                  data={signalTypeData}
                  cx="50%"
                  cy="50%"
                  innerRadius={50}
                  outerRadius={70}
                  paddingAngle={2}
                  dataKey="value"
                  label={({ name, value }) => `${name}: ${value}`}
                  labelLine={false}
                >
                  {signalTypeData.map((entry, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={entry.name === '매수' ? '#16a34a' : '#dc2626'}
                    />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[180px] flex items-center justify-center text-gray-400">
              데이터 없음
            </div>
          )}
        </div>
      </div>

      {/* Recent Signals Table */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">최근 시그널 성과</h3>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead>
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">종목</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">유형</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">일자</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">시그널가</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">현재가</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">수익률</th>
                <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">강도</th>
                <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">실행</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {signal_performance.length > 0 ? (
                signal_performance.slice(0, 20).map((signal) => (
                  <tr key={signal.signal_id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">{signal.symbol}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-1 rounded text-xs font-medium ${
                        signal.signal_type === 'buy' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                      }`}>
                        {signal.signal_type === 'buy' ? '매수' : '매도'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500">
                      {new Date(signal.signal_date).toLocaleDateString('ko-KR')}
                    </td>
                    <td className="px-4 py-3 text-sm text-right">{formatNumber(Math.round(signal.signal_price))}</td>
                    <td className="px-4 py-3 text-sm text-right">{formatNumber(Math.round(signal.current_price))}</td>
                    <td className={`px-4 py-3 text-sm text-right font-medium ${
                      signal.pnl_pct >= 0 ? 'text-green-600' : 'text-red-600'
                    }`}>
                      {formatPercent(signal.pnl_pct)}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <div className="flex items-center justify-center">
                        <div className="w-16 bg-gray-200 rounded-full h-2">
                          <div
                            className="bg-primary-600 h-2 rounded-full"
                            style={{ width: `${Math.min(signal.strength * 100, 100)}%` }}
                          />
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-center">
                      {signal.executed ? (
                        <span className="text-green-600">O</span>
                      ) : (
                        <span className="text-gray-400">-</span>
                      )}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={8} className="px-4 py-8 text-center text-gray-400">
                    시그널 데이터가 없습니다
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

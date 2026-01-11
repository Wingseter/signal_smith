import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { optimizerApi } from '../../services/api';
import {
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';

interface Allocation {
  symbol: string;
  name: string;
  weight: number;
  shares: number;
  value: number;
  sector: string;
  expected_return: number;
  volatility: number;
  contribution_to_risk: number;
}

interface OptimizationResult {
  method: string;
  allocations: Allocation[];
  total_value: number;
  expected_return: number;
  expected_volatility: number;
  sharpe_ratio: number;
  diversification_ratio: number;
  max_drawdown_estimate: number;
  sector_allocation: Record<string, number>;
  risk_metrics: Record<string, number>;
  rebalance_suggestions: Array<{ action: string; symbol?: string; reason: string }>;
}

interface PositionSizeResult {
  symbol: string;
  recommended_shares: number;
  recommended_value: number;
  max_shares: number;
  max_value: number;
  risk_per_share: number;
  position_risk_pct: number;
  kelly_fraction: number;
  notes: string[];
}

interface DiversificationResult {
  diversification_score: number;
  sector_exposure: Record<string, number>;
  num_positions: number;
  num_sectors: number;
  warnings: Array<{ type: string; message: string }>;
  suggestions: Array<{ type: string; message: string; symbol?: string }>;
  recommended_actions: string[];
}

const KOREAN_STOCKS = [
  { symbol: '005930', name: '삼성전자', sector: 'IT' },
  { symbol: '000660', name: 'SK하이닉스', sector: 'IT' },
  { symbol: '035420', name: 'NAVER', sector: 'IT' },
  { symbol: '035720', name: '카카오', sector: 'IT' },
  { symbol: '051910', name: 'LG화학', sector: '화학' },
  { symbol: '006400', name: '삼성SDI', sector: '전자부품' },
  { symbol: '068270', name: '셀트리온', sector: '바이오' },
  { symbol: '105560', name: 'KB금융', sector: '금융' },
  { symbol: '055550', name: '신한지주', sector: '금융' },
  { symbol: '003550', name: 'LG', sector: '지주' },
  { symbol: '207940', name: '삼성바이오로직스', sector: '바이오' },
  { symbol: '000270', name: '기아', sector: '자동차' },
];

const COLORS = ['#2563eb', '#16a34a', '#dc2626', '#ca8a04', '#9333ea', '#0891b2', '#db2777', '#65a30d'];

export default function PortfolioOptimizer() {
  const [activeTab, setActiveTab] = useState<'optimize' | 'position' | 'diversify'>('optimize');
  const [selectedSymbols, setSelectedSymbols] = useState<string[]>([]);
  const [totalCapital, setTotalCapital] = useState(100000000);
  const [method, setMethod] = useState('max_sharpe');
  const [riskLevel, setRiskLevel] = useState('moderate');
  const [result, setResult] = useState<OptimizationResult | null>(null);

  // Position sizing state
  const [positionSymbol, setPositionSymbol] = useState('');
  const [entryPrice, setEntryPrice] = useState(0);
  const [stopLossPrice, setStopLossPrice] = useState(0);
  const [positionResult, setPositionResult] = useState<PositionSizeResult | null>(null);

  // Fetch methods
  const { data: methodsData } = useQuery({
    queryKey: ['optimizer', 'methods'],
    queryFn: optimizerApi.getMethods,
  });

  // Diversification analysis
  const { data: diversificationData } = useQuery<DiversificationResult>({
    queryKey: ['optimizer', 'diversification'],
    queryFn: () => optimizerApi.getDiversification(),
    enabled: activeTab === 'diversify',
  });

  // Optimize mutation
  const optimizeMutation = useMutation({
    mutationFn: optimizerApi.optimize,
    onSuccess: (data) => setResult(data),
  });

  // Position size mutation
  const positionSizeMutation = useMutation({
    mutationFn: optimizerApi.calculatePositionSize,
    onSuccess: (data) => setPositionResult(data),
  });

  const handleSymbolToggle = (symbol: string) => {
    setSelectedSymbols((prev) =>
      prev.includes(symbol) ? prev.filter((s) => s !== symbol) : [...prev, symbol]
    );
  };

  const handleOptimize = () => {
    if (selectedSymbols.length < 2) return;
    optimizeMutation.mutate({
      symbols: selectedSymbols,
      total_capital: totalCapital,
      method,
      risk_level: riskLevel,
    });
  };

  const handleCalculatePosition = () => {
    if (!positionSymbol || entryPrice <= 0 || stopLossPrice <= 0) return;
    positionSizeMutation.mutate({
      symbol: positionSymbol,
      entry_price: entryPrice,
      stop_loss_price: stopLossPrice,
      total_capital: totalCapital,
    });
  };

  const formatNumber = (num: number) => num.toLocaleString('ko-KR');
  const formatPercent = (num: number) => `${num >= 0 ? '+' : ''}${num.toFixed(2)}%`;
  const formatCurrency = (num: number) => `${formatNumber(Math.round(num))}원`;

  // Prepare chart data
  const sectorData = result
    ? Object.entries(result.sector_allocation).map(([sector, weight]) => ({
        name: sector,
        value: weight,
      }))
    : [];

  const allocationData = result?.allocations.map((a) => ({
    symbol: a.symbol,
    weight: a.weight,
    risk: a.contribution_to_risk,
  })) || [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">포트폴리오 최적화</h1>
        <p className="text-sm text-gray-500 mt-1">
          리스크 조정 포지션 크기 및 분산투자 제안
        </p>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="flex space-x-8">
          {[
            { id: 'optimize', label: '포트폴리오 최적화' },
            { id: 'position', label: '포지션 크기 계산' },
            { id: 'diversify', label: '분산투자 분석' },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as typeof activeTab)}
              className={`py-4 px-1 border-b-2 font-medium text-sm ${
                activeTab === tab.id
                  ? 'border-primary-600 text-primary-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Optimize Tab */}
      {activeTab === 'optimize' && (
        <div className="space-y-6">
          {/* Configuration */}
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">최적화 설정</h2>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  투자금액
                </label>
                <input
                  type="number"
                  value={totalCapital}
                  onChange={(e) => setTotalCapital(Number(e.target.value))}
                  step={10000000}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  최적화 방법
                </label>
                <select
                  value={method}
                  onChange={(e) => setMethod(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                >
                  {methodsData?.methods?.map((m: { id: string; name: string }) => (
                    <option key={m.id} value={m.id}>
                      {m.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  위험 수준
                </label>
                <select
                  value={riskLevel}
                  onChange={(e) => setRiskLevel(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                >
                  {methodsData?.risk_levels?.map((r: { id: string; name: string }) => (
                    <option key={r.id} value={r.id}>
                      {r.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Symbol Selection */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                종목 선택 (최소 2개)
              </label>
              <div className="flex flex-wrap gap-2">
                {KOREAN_STOCKS.map((stock) => (
                  <button
                    key={stock.symbol}
                    onClick={() => handleSymbolToggle(stock.symbol)}
                    className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                      selectedSymbols.includes(stock.symbol)
                        ? 'bg-primary-600 text-white'
                        : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                    }`}
                  >
                    {stock.name}
                    <span className="ml-1 text-xs opacity-70">({stock.sector})</span>
                  </button>
                ))}
              </div>
            </div>

            <div className="mt-6">
              <button
                onClick={handleOptimize}
                disabled={selectedSymbols.length < 2 || optimizeMutation.isPending}
                className="px-6 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:bg-gray-300 font-medium"
              >
                {optimizeMutation.isPending ? '최적화 중...' : '포트폴리오 최적화'}
              </button>
            </div>
          </div>

          {/* Results */}
          {result && (
            <>
              {/* Summary Cards */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="bg-white rounded-lg shadow p-4">
                  <p className="text-xs text-gray-500">기대 수익률</p>
                  <p className={`text-xl font-bold ${result.expected_return >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                    {formatPercent(result.expected_return)}
                  </p>
                </div>
                <div className="bg-white rounded-lg shadow p-4">
                  <p className="text-xs text-gray-500">예상 변동성</p>
                  <p className="text-xl font-bold text-gray-900">
                    {result.expected_volatility.toFixed(2)}%
                  </p>
                </div>
                <div className="bg-white rounded-lg shadow p-4">
                  <p className="text-xs text-gray-500">샤프 비율</p>
                  <p className={`text-xl font-bold ${result.sharpe_ratio >= 1 ? 'text-green-600' : 'text-gray-900'}`}>
                    {result.sharpe_ratio.toFixed(2)}
                  </p>
                </div>
                <div className="bg-white rounded-lg shadow p-4">
                  <p className="text-xs text-gray-500">예상 MDD</p>
                  <p className="text-xl font-bold text-red-600">
                    -{result.max_drawdown_estimate.toFixed(1)}%
                  </p>
                </div>
              </div>

              {/* Charts */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Sector Allocation Pie Chart */}
                <div className="bg-white rounded-lg shadow p-6">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">섹터 배분</h3>
                  <ResponsiveContainer width="100%" height={250}>
                    <PieChart>
                      <Pie
                        data={sectorData}
                        cx="50%"
                        cy="50%"
                        outerRadius={80}
                        dataKey="value"
                        label={({ name, value }) => `${name}: ${value}%`}
                      >
                        {sectorData.map((_, index) => (
                          <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip formatter={(v: number) => `${v}%`} />
                    </PieChart>
                  </ResponsiveContainer>
                </div>

                {/* Allocation vs Risk Contribution */}
                <div className="bg-white rounded-lg shadow p-6">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">비중 vs 리스크 기여도</h3>
                  <ResponsiveContainer width="100%" height={250}>
                    <BarChart data={allocationData} layout="vertical">
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis type="number" domain={[0, 'dataMax']} tickFormatter={(v) => `${v}%`} />
                      <YAxis type="category" dataKey="symbol" width={70} />
                      <Tooltip formatter={(v: number) => `${v.toFixed(2)}%`} />
                      <Legend />
                      <Bar dataKey="weight" name="비중" fill="#2563eb" />
                      <Bar dataKey="risk" name="리스크 기여" fill="#dc2626" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Allocation Table */}
              <div className="bg-white rounded-lg shadow p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">최적 배분</h3>
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead>
                      <tr>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">종목</th>
                        <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">비중</th>
                        <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">수량</th>
                        <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">금액</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">섹터</th>
                        <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">기대수익</th>
                        <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">변동성</th>
                        <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">리스크기여</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {result.allocations.map((alloc) => (
                        <tr key={alloc.symbol} className="hover:bg-gray-50">
                          <td className="px-4 py-3">
                            <div>
                              <p className="font-medium text-gray-900">{alloc.symbol}</p>
                              <p className="text-xs text-gray-500">{alloc.name}</p>
                            </div>
                          </td>
                          <td className="px-4 py-3 text-right font-medium">{alloc.weight}%</td>
                          <td className="px-4 py-3 text-right">{formatNumber(alloc.shares)}주</td>
                          <td className="px-4 py-3 text-right">{formatCurrency(alloc.value)}</td>
                          <td className="px-4 py-3 text-sm text-gray-500">{alloc.sector}</td>
                          <td className={`px-4 py-3 text-right ${alloc.expected_return >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                            {formatPercent(alloc.expected_return)}
                          </td>
                          <td className="px-4 py-3 text-right">{alloc.volatility}%</td>
                          <td className="px-4 py-3 text-right">{alloc.contribution_to_risk}%</td>
                        </tr>
                      ))}
                    </tbody>
                    <tfoot>
                      <tr className="bg-gray-50">
                        <td className="px-4 py-3 font-medium">합계</td>
                        <td className="px-4 py-3 text-right font-bold">100%</td>
                        <td className="px-4 py-3"></td>
                        <td className="px-4 py-3 text-right font-bold">{formatCurrency(result.total_value)}</td>
                        <td colSpan={4}></td>
                      </tr>
                    </tfoot>
                  </table>
                </div>
              </div>

              {/* Suggestions */}
              {result.rebalance_suggestions.length > 0 && (
                <div className="bg-yellow-50 rounded-lg p-4">
                  <h3 className="text-lg font-semibold text-yellow-800 mb-2">리밸런싱 제안</h3>
                  <ul className="space-y-2">
                    {result.rebalance_suggestions.map((suggestion, idx) => (
                      <li key={idx} className="text-yellow-700">
                        • {suggestion.reason}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* Position Sizing Tab */}
      {activeTab === 'position' && (
        <div className="space-y-6">
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">포지션 크기 계산</h2>
            <p className="text-sm text-gray-500 mb-6">
              진입가와 손절가를 기준으로 적정 포지션 크기를 계산합니다.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">종목코드</label>
                <input
                  type="text"
                  value={positionSymbol}
                  onChange={(e) => setPositionSymbol(e.target.value.toUpperCase())}
                  placeholder="005930"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">진입가</label>
                <input
                  type="number"
                  value={entryPrice || ''}
                  onChange={(e) => setEntryPrice(Number(e.target.value))}
                  placeholder="70000"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">손절가</label>
                <input
                  type="number"
                  value={stopLossPrice || ''}
                  onChange={(e) => setStopLossPrice(Number(e.target.value))}
                  placeholder="65000"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">총 자본</label>
                <input
                  type="number"
                  value={totalCapital}
                  onChange={(e) => setTotalCapital(Number(e.target.value))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                />
              </div>
            </div>

            <div className="mt-6">
              <button
                onClick={handleCalculatePosition}
                disabled={!positionSymbol || entryPrice <= 0 || stopLossPrice <= 0 || positionSizeMutation.isPending}
                className="px-6 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:bg-gray-300 font-medium"
              >
                {positionSizeMutation.isPending ? '계산 중...' : '포지션 크기 계산'}
              </button>
            </div>
          </div>

          {positionResult && (
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">계산 결과</h3>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                <div className="bg-green-50 rounded-lg p-4">
                  <p className="text-sm text-green-600">추천 수량</p>
                  <p className="text-2xl font-bold text-green-700">{formatNumber(positionResult.recommended_shares)}주</p>
                </div>
                <div className="bg-blue-50 rounded-lg p-4">
                  <p className="text-sm text-blue-600">추천 금액</p>
                  <p className="text-2xl font-bold text-blue-700">{formatCurrency(positionResult.recommended_value)}</p>
                </div>
                <div className="bg-gray-50 rounded-lg p-4">
                  <p className="text-sm text-gray-600">최대 수량</p>
                  <p className="text-2xl font-bold text-gray-700">{formatNumber(positionResult.max_shares)}주</p>
                </div>
                <div className="bg-red-50 rounded-lg p-4">
                  <p className="text-sm text-red-600">포지션 리스크</p>
                  <p className="text-2xl font-bold text-red-700">{(positionResult.position_risk_pct * 100).toFixed(2)}%</p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <span className="text-gray-500">주당 리스크</span>
                    <span className="font-medium">{formatCurrency(positionResult.risk_per_share)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">켈리 비율</span>
                    <span className="font-medium">{(positionResult.kelly_fraction * 100).toFixed(1)}%</span>
                  </div>
                </div>
              </div>

              {positionResult.notes.length > 0 && (
                <div className="mt-4 bg-yellow-50 rounded-lg p-4">
                  <ul className="space-y-1">
                    {positionResult.notes.map((note, idx) => (
                      <li key={idx} className="text-yellow-700 text-sm">⚠️ {note}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Diversification Tab */}
      {activeTab === 'diversify' && (
        <div className="space-y-6">
          {diversificationData ? (
            <>
              {/* Score Card */}
              <div className="bg-white rounded-lg shadow p-6">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-lg font-semibold text-gray-900">분산투자 점수</h2>
                  <div className={`text-4xl font-bold ${
                    diversificationData.diversification_score >= 70 ? 'text-green-600' :
                    diversificationData.diversification_score >= 40 ? 'text-yellow-600' : 'text-red-600'
                  }`}>
                    {diversificationData.diversification_score}점
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm text-gray-500">보유 종목 수</p>
                    <p className="text-xl font-bold">{diversificationData.num_positions}개</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500">섹터 수</p>
                    <p className="text-xl font-bold">{diversificationData.num_sectors}개</p>
                  </div>
                </div>
              </div>

              {/* Sector Exposure */}
              <div className="bg-white rounded-lg shadow p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">섹터별 노출</h3>
                <div className="space-y-3">
                  {Object.entries(diversificationData.sector_exposure).map(([sector, exposure]) => (
                    <div key={sector}>
                      <div className="flex justify-between text-sm mb-1">
                        <span>{sector}</span>
                        <span className={exposure > 40 ? 'text-red-600 font-medium' : ''}>{exposure}%</span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div
                          className={`h-2 rounded-full ${exposure > 40 ? 'bg-red-500' : 'bg-primary-600'}`}
                          style={{ width: `${Math.min(exposure, 100)}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Warnings */}
              {diversificationData.warnings.length > 0 && (
                <div className="bg-red-50 rounded-lg p-4">
                  <h3 className="text-lg font-semibold text-red-800 mb-2">경고</h3>
                  <ul className="space-y-2">
                    {diversificationData.warnings.map((warning, idx) => (
                      <li key={idx} className="text-red-700">⚠️ {warning.message}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Suggestions */}
              {diversificationData.suggestions.length > 0 && (
                <div className="bg-blue-50 rounded-lg p-4">
                  <h3 className="text-lg font-semibold text-blue-800 mb-2">제안</h3>
                  <ul className="space-y-2">
                    {diversificationData.suggestions.map((suggestion, idx) => (
                      <li key={idx} className="text-blue-700">💡 {suggestion.message}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Recommended Actions */}
              {diversificationData.recommended_actions.length > 0 && (
                <div className="bg-white rounded-lg shadow p-6">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">권장 조치</h3>
                  <ul className="space-y-2">
                    {diversificationData.recommended_actions.map((action, idx) => (
                      <li key={idx} className="flex items-start">
                        <span className="mr-2">{idx + 1}.</span>
                        <span>{action}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          ) : (
            <div className="bg-white rounded-lg shadow p-6 text-center text-gray-500">
              분산투자 분석 데이터를 불러오는 중...
            </div>
          )}
        </div>
      )}
    </div>
  );
}

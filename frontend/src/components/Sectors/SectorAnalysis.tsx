import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { sectorsApi } from '../../services/api';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  Treemap,
} from 'recharts';

interface SectorPerformance {
  sector_id: string;
  name: string;
  return_1d: number;
  return_1w: number;
  return_1m: number;
  return_3m: number;
  return_ytd: number;
  relative_strength: number;
  strength_rank: number;
  strength_level: string;
  volume_change: number;
  momentum_score: number;
  top_gainers: Array<{ symbol: string; return_1d: number }>;
  top_losers: Array<{ symbol: string; return_1d: number }>;
}

interface ThemePerformance {
  theme_id: string;
  name: string;
  description: string;
  is_hot: boolean;
  return_1d: number;
  return_1w: number;
  return_1m: number;
  momentum_score: number;
  stock_count: number;
  avg_volume_change: number;
  top_stocks: Array<{ symbol: string; return_1d: number; return_1w: number }>;
}

interface RotationSignal {
  detected: boolean;
  from_sectors: string[];
  to_sectors: string[];
  confidence: number;
  cycle_phase: string;
  rationale: string;
}

const CYCLE_NAMES: Record<string, string> = {
  early_expansion: '초기 확장',
  mid_expansion: '중기 확장',
  late_expansion: '후기 확장',
  early_recession: '초기 침체',
  mid_recession: '중기 침체',
  late_recession: '후기 침체',
};

const STRENGTH_COLORS: Record<string, string> = {
  strong_outperform: '#16a34a',
  outperform: '#22c55e',
  neutral: '#6b7280',
  underperform: '#f97316',
  strong_underperform: '#dc2626',
};

export default function SectorAnalysis() {
  const [activeTab, setActiveTab] = useState<'sectors' | 'themes' | 'rotation'>('sectors');
  const [selectedSector, setSelectedSector] = useState<string | null>(null);
  const [selectedTheme, setSelectedTheme] = useState<string | null>(null);

  // Fetch sector performance
  const { data: sectorsData, isLoading: sectorsLoading } = useQuery<SectorPerformance[]>({
    queryKey: ['sectors', 'performance'],
    queryFn: sectorsApi.getPerformance,
  });

  // Fetch themes
  const { data: themesData, isLoading: themesLoading } = useQuery<ThemePerformance[]>({
    queryKey: ['sectors', 'themes'],
    queryFn: () => sectorsApi.getThemes(false),
  });

  // Fetch rotation signal
  const { data: rotationData } = useQuery<RotationSignal>({
    queryKey: ['sectors', 'rotation'],
    queryFn: sectorsApi.getRotationSignal,
  });

  // Fetch sector detail
  const { data: sectorDetail } = useQuery({
    queryKey: ['sectors', 'detail', selectedSector],
    queryFn: () => sectorsApi.getSectorDetail(selectedSector!),
    enabled: !!selectedSector,
  });

  // Fetch theme detail
  const { data: themeDetail } = useQuery({
    queryKey: ['themes', 'detail', selectedTheme],
    queryFn: () => sectorsApi.getThemeDetail(selectedTheme!),
    enabled: !!selectedTheme,
  });

  const formatPercent = (num: number) => `${num >= 0 ? '+' : ''}${num.toFixed(2)}%`;
  const getReturnColor = (num: number) => (num >= 0 ? 'text-green-600' : 'text-red-600');

  // Prepare heatmap data
  const heatmapData = sectorsData?.map((s) => ({
    name: s.name,
    size: Math.abs(s.return_1m) + 10,
    value: s.return_1m,
  })) || [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">섹터/테마 분석</h1>
          <p className="text-sm text-gray-500 mt-1">
            섹터 로테이션 및 테마별 종목 분석
          </p>
        </div>
        {rotationData && (
          <div className="bg-blue-50 px-4 py-2 rounded-lg">
            <p className="text-sm text-blue-600">
              현재 사이클: <span className="font-medium">{CYCLE_NAMES[rotationData.cycle_phase] || rotationData.cycle_phase}</span>
            </p>
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="flex space-x-8">
          {[
            { id: 'sectors', label: '섹터 분석' },
            { id: 'themes', label: '테마 분석' },
            { id: 'rotation', label: '로테이션' },
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

      {/* Sectors Tab */}
      {activeTab === 'sectors' && (
        <div className="space-y-6">
          {/* Sector Performance Table */}
          <div className="bg-white rounded-lg shadow overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-gray-900">섹터별 성과</h2>
            </div>
            {sectorsLoading ? (
              <div className="p-8 text-center text-gray-500">로딩 중...</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">순위</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">섹터</th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">1일</th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">1주</th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">1개월</th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">3개월</th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">YTD</th>
                      <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">강도</th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">모멘텀</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {sectorsData?.map((sector) => (
                      <tr
                        key={sector.sector_id}
                        className="hover:bg-gray-50 cursor-pointer"
                        onClick={() => setSelectedSector(sector.sector_id)}
                      >
                        <td className="px-4 py-3 text-sm font-medium text-gray-900">
                          #{sector.strength_rank}
                        </td>
                        <td className="px-4 py-3">
                          <span className="font-medium text-gray-900">{sector.name}</span>
                        </td>
                        <td className={`px-4 py-3 text-sm text-right font-medium ${getReturnColor(sector.return_1d)}`}>
                          {formatPercent(sector.return_1d)}
                        </td>
                        <td className={`px-4 py-3 text-sm text-right font-medium ${getReturnColor(sector.return_1w)}`}>
                          {formatPercent(sector.return_1w)}
                        </td>
                        <td className={`px-4 py-3 text-sm text-right font-medium ${getReturnColor(sector.return_1m)}`}>
                          {formatPercent(sector.return_1m)}
                        </td>
                        <td className={`px-4 py-3 text-sm text-right font-medium ${getReturnColor(sector.return_3m)}`}>
                          {formatPercent(sector.return_3m)}
                        </td>
                        <td className={`px-4 py-3 text-sm text-right font-medium ${getReturnColor(sector.return_ytd)}`}>
                          {formatPercent(sector.return_ytd)}
                        </td>
                        <td className="px-4 py-3 text-center">
                          <span
                            className="px-2 py-1 text-xs font-medium rounded"
                            style={{
                              backgroundColor: STRENGTH_COLORS[sector.strength_level] + '20',
                              color: STRENGTH_COLORS[sector.strength_level],
                            }}
                          >
                            {sector.strength_level.replace(/_/g, ' ')}
                          </span>
                        </td>
                        <td className={`px-4 py-3 text-sm text-right font-medium ${getReturnColor(sector.momentum_score)}`}>
                          {sector.momentum_score.toFixed(1)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Sector Bar Chart */}
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">섹터별 월간 수익률</h3>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart
                data={sectorsData?.sort((a, b) => b.return_1m - a.return_1m)}
                layout="vertical"
              >
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" tickFormatter={(v) => `${v}%`} />
                <YAxis type="category" dataKey="name" width={80} fontSize={12} />
                <Tooltip formatter={(v: number) => `${v.toFixed(2)}%`} />
                <Bar dataKey="return_1m" radius={[0, 4, 4, 0]}>
                  {sectorsData?.sort((a, b) => b.return_1m - a.return_1m).map((entry, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={entry.return_1m >= 0 ? '#16a34a' : '#dc2626'}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Sector Detail Modal */}
          {selectedSector && sectorDetail && (
            <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
              <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[80vh] overflow-y-auto">
                <div className="p-6">
                  <div className="flex justify-between items-start mb-4">
                    <div>
                      <h2 className="text-xl font-bold text-gray-900">{sectorDetail.name}</h2>
                      <p className="text-sm text-gray-500">{sectorDetail.description}</p>
                    </div>
                    <button
                      onClick={() => setSelectedSector(null)}
                      className="text-gray-400 hover:text-gray-600"
                    >
                      x
                    </button>
                  </div>

                  {/* Performance */}
                  <div className="grid grid-cols-3 gap-4 mb-6">
                    {Object.entries(sectorDetail.performance || {}).map(([key, value]) => (
                      <div key={key} className="bg-gray-50 rounded-lg p-3">
                        <p className="text-xs text-gray-500">{key}</p>
                        <p className={`text-lg font-bold ${getReturnColor(value as number)}`}>
                          {formatPercent(value as number)}
                        </p>
                      </div>
                    ))}
                  </div>

                  {/* Stocks */}
                  <h3 className="font-semibold text-gray-900 mb-3">구성 종목</h3>
                  <div className="space-y-2">
                    {sectorDetail.stocks?.map((stock: any) => (
                      <div key={stock.symbol} className="flex justify-between items-center p-2 bg-gray-50 rounded">
                        <span className="font-medium">{stock.name}</span>
                        <span className="text-sm text-gray-500">{stock.symbol}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Themes Tab */}
      {activeTab === 'themes' && (
        <div className="space-y-6">
          {/* Hot Themes */}
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">주목 테마</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {themesData?.filter((t) => t.is_hot).map((theme) => (
                <div
                  key={theme.theme_id}
                  className="border-2 border-orange-200 bg-orange-50 rounded-lg p-4 cursor-pointer hover:border-orange-400"
                  onClick={() => setSelectedTheme(theme.theme_id)}
                >
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="font-semibold text-gray-900">{theme.name}</h3>
                    <span className="text-orange-500 text-xs font-medium">HOT</span>
                  </div>
                  <p className="text-sm text-gray-500 mb-3">{theme.description}</p>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-500">{theme.stock_count}종목</span>
                    <span className={`font-medium ${getReturnColor(theme.return_1w)}`}>
                      {formatPercent(theme.return_1w)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* All Themes */}
          <div className="bg-white rounded-lg shadow overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-gray-900">전체 테마</h2>
            </div>
            {themesLoading ? (
              <div className="p-8 text-center text-gray-500">로딩 중...</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">테마</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">설명</th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">종목수</th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">1일</th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">1주</th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">1개월</th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">모멘텀</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {themesData?.map((theme) => (
                      <tr
                        key={theme.theme_id}
                        className="hover:bg-gray-50 cursor-pointer"
                        onClick={() => setSelectedTheme(theme.theme_id)}
                      >
                        <td className="px-4 py-3">
                          <div className="flex items-center">
                            <span className="font-medium text-gray-900">{theme.name}</span>
                            {theme.is_hot && (
                              <span className="ml-2 px-1.5 py-0.5 text-xs bg-orange-100 text-orange-600 rounded">HOT</span>
                            )}
                          </div>
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-500 max-w-xs truncate">
                          {theme.description}
                        </td>
                        <td className="px-4 py-3 text-sm text-right text-gray-900">{theme.stock_count}</td>
                        <td className={`px-4 py-3 text-sm text-right font-medium ${getReturnColor(theme.return_1d)}`}>
                          {formatPercent(theme.return_1d)}
                        </td>
                        <td className={`px-4 py-3 text-sm text-right font-medium ${getReturnColor(theme.return_1w)}`}>
                          {formatPercent(theme.return_1w)}
                        </td>
                        <td className={`px-4 py-3 text-sm text-right font-medium ${getReturnColor(theme.return_1m)}`}>
                          {formatPercent(theme.return_1m)}
                        </td>
                        <td className={`px-4 py-3 text-sm text-right font-medium ${getReturnColor(theme.momentum_score)}`}>
                          {theme.momentum_score.toFixed(1)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Theme Detail Modal */}
          {selectedTheme && themeDetail && (
            <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
              <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[80vh] overflow-y-auto">
                <div className="p-6">
                  <div className="flex justify-between items-start mb-4">
                    <div>
                      <div className="flex items-center gap-2">
                        <h2 className="text-xl font-bold text-gray-900">{themeDetail.name}</h2>
                        {themeDetail.is_hot && (
                          <span className="px-2 py-0.5 text-xs bg-orange-100 text-orange-600 rounded">HOT</span>
                        )}
                      </div>
                      <p className="text-sm text-gray-500">{themeDetail.description}</p>
                    </div>
                    <button
                      onClick={() => setSelectedTheme(null)}
                      className="text-gray-400 hover:text-gray-600"
                    >
                      x
                    </button>
                  </div>

                  {/* Keywords */}
                  <div className="flex flex-wrap gap-2 mb-4">
                    {themeDetail.keywords?.map((keyword: string) => (
                      <span key={keyword} className="px-2 py-1 bg-blue-50 text-blue-600 text-sm rounded">
                        #{keyword}
                      </span>
                    ))}
                  </div>

                  {/* Performance */}
                  <div className="grid grid-cols-3 gap-4 mb-6">
                    {Object.entries(themeDetail.performance || {}).map(([key, value]) => (
                      <div key={key} className="bg-gray-50 rounded-lg p-3">
                        <p className="text-xs text-gray-500">{key}</p>
                        <p className={`text-lg font-bold ${getReturnColor(value as number)}`}>
                          {formatPercent(value as number)}
                        </p>
                      </div>
                    ))}
                  </div>

                  {/* Stocks */}
                  <h3 className="font-semibold text-gray-900 mb-3">관련 종목</h3>
                  <div className="space-y-2">
                    {themeDetail.stocks?.map((stock: any) => (
                      <div key={stock.symbol} className="flex justify-between items-center p-2 bg-gray-50 rounded">
                        <span className="font-medium">{stock.name}</span>
                        <span className="text-sm text-gray-500">{stock.symbol}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Rotation Tab */}
      {activeTab === 'rotation' && (
        <div className="space-y-6">
          {/* Current Cycle */}
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">경기 사이클 분석</h2>
            <div className="flex items-center justify-center mb-6">
              <div className="relative">
                <div className="w-48 h-48 rounded-full border-8 border-gray-200 flex items-center justify-center">
                  <div className="text-center">
                    <p className="text-2xl font-bold text-primary-600">
                      {CYCLE_NAMES[rotationData?.cycle_phase || 'mid_expansion']}
                    </p>
                    <p className="text-sm text-gray-500">현재 단계</p>
                  </div>
                </div>
              </div>
            </div>

            {/* Cycle Phases */}
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2">
              {Object.entries(CYCLE_NAMES).map(([phase, name]) => (
                <div
                  key={phase}
                  className={`p-3 rounded-lg text-center ${
                    rotationData?.cycle_phase === phase
                      ? 'bg-primary-100 border-2 border-primary-500'
                      : 'bg-gray-50'
                  }`}
                >
                  <p className={`text-sm font-medium ${
                    rotationData?.cycle_phase === phase ? 'text-primary-700' : 'text-gray-600'
                  }`}>
                    {name}
                  </p>
                </div>
              ))}
            </div>
          </div>

          {/* Rotation Signal */}
          {rotationData && (
            <div className={`rounded-lg shadow p-6 ${
              rotationData.detected ? 'bg-yellow-50' : 'bg-white'
            }`}>
              <h2 className="text-lg font-semibold text-gray-900 mb-4">
                {rotationData.detected ? '로테이션 신호 감지' : '로테이션 분석'}
              </h2>

              {rotationData.detected ? (
                <div className="space-y-4">
                  <div className="flex items-center justify-center gap-8">
                    <div className="text-center">
                      <p className="text-sm text-gray-500 mb-2">약세 전환</p>
                      <div className="space-y-1">
                        {rotationData.from_sectors.map((s) => (
                          <span key={s} className="block px-3 py-1 bg-red-100 text-red-700 rounded text-sm">
                            {s}
                          </span>
                        ))}
                      </div>
                    </div>
                    <div className="text-3xl text-gray-400">→</div>
                    <div className="text-center">
                      <p className="text-sm text-gray-500 mb-2">강세 전환</p>
                      <div className="space-y-1">
                        {rotationData.to_sectors.map((s) => (
                          <span key={s} className="block px-3 py-1 bg-green-100 text-green-700 rounded text-sm">
                            {s}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                  <div className="mt-4 p-4 bg-white rounded-lg">
                    <p className="text-gray-700">{rotationData.rationale}</p>
                    <p className="mt-2 text-sm text-gray-500">
                      신뢰도: {(rotationData.confidence * 100).toFixed(0)}%
                    </p>
                  </div>
                </div>
              ) : (
                <p className="text-gray-600">{rotationData.rationale}</p>
              )}
            </div>
          )}

          {/* Sector Strength Ranking */}
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">섹터 강도 순위</h2>
            <div className="space-y-3">
              {sectorsData?.map((sector, idx) => (
                <div key={sector.sector_id} className="flex items-center">
                  <span className="w-8 text-gray-500 font-medium">#{idx + 1}</span>
                  <span className="w-24 font-medium text-gray-900">{sector.name}</span>
                  <div className="flex-1 mx-4">
                    <div className="h-4 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full"
                        style={{
                          width: `${Math.max(0, Math.min(100, 50 + sector.relative_strength * 2))}%`,
                          backgroundColor: STRENGTH_COLORS[sector.strength_level],
                        }}
                      />
                    </div>
                  </div>
                  <span className={`w-16 text-right font-medium ${getReturnColor(sector.relative_strength)}`}>
                    {formatPercent(sector.relative_strength)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

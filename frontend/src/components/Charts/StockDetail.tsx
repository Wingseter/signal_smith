import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { stocksApi, analysisApi } from '../../services/api';
import StockChart from './StockChart';

export default function StockDetail() {
  const { symbol } = useParams<{ symbol: string }>();

  const { data: stock } = useQuery({
    queryKey: ['stock', symbol],
    queryFn: () => stocksApi.get(symbol!),
    enabled: !!symbol,
  });

  const { data: prices } = useQuery({
    queryKey: ['stockPrices', symbol],
    queryFn: () => stocksApi.getPrices(symbol!, { limit: 30 }),
    enabled: !!symbol,
  });

  const { data: analysis } = useQuery({
    queryKey: ['stockAnalysis', symbol],
    queryFn: () => analysisApi.getConsolidated(symbol!),
    enabled: !!symbol,
  });

  if (!symbol) return <div>Stock not found</div>;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">
              {stock?.name || symbol}
            </h1>
            <p className="text-gray-500">{symbol}</p>
          </div>
          {stock && (
            <span
              className={`px-3 py-1 rounded-full text-sm font-medium ${
                stock.market === 'KOSPI'
                  ? 'bg-blue-100 text-blue-800'
                  : 'bg-purple-100 text-purple-800'
              }`}
            >
              {stock.market}
            </span>
          )}
        </div>
        {stock && (
          <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <p className="text-sm text-gray-500">Sector</p>
              <p className="font-medium">{stock.sector || '-'}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Industry</p>
              <p className="font-medium">{stock.industry || '-'}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Market Cap</p>
              <p className="font-medium">
                {stock.market_cap
                  ? `${(stock.market_cap / 1000000000000).toFixed(2)}T`
                  : '-'}
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Chart */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Price Chart</h2>
        <StockChart
          symbol={symbol}
          data={prices?.map((p: { date: string; close: number }) => ({
            date: p.date.slice(0, 10),
            close: Number(p.close),
          }))}
        />
      </div>

      {/* AI Analysis */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">AI Analysis</h2>
        {analysis ? (
          <div className="space-y-4">
            <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
              <div>
                <p className="text-sm text-gray-500">Overall Score</p>
                <p className="text-2xl font-bold">{analysis.overall_score.toFixed(1)}</p>
              </div>
              <span
                className={`px-4 py-2 rounded-lg text-lg font-medium ${
                  analysis.overall_recommendation === 'buy'
                    ? 'bg-green-100 text-green-800'
                    : analysis.overall_recommendation === 'sell'
                    ? 'bg-red-100 text-red-800'
                    : 'bg-yellow-100 text-yellow-800'
                }`}
              >
                {analysis.overall_recommendation.toUpperCase()}
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {analysis.quant_analysis && (
                <div className="p-4 border rounded-lg">
                  <h3 className="font-medium text-gray-900">Quant Analysis</h3>
                  <p className="text-sm text-gray-500 mt-1">{analysis.quant_analysis.summary}</p>
                  <p className="text-sm mt-2">
                    Score: <span className="font-medium">{analysis.quant_analysis.score}</span>
                  </p>
                </div>
              )}
              {analysis.fundamental_analysis && (
                <div className="p-4 border rounded-lg">
                  <h3 className="font-medium text-gray-900">Fundamental Analysis</h3>
                  <p className="text-sm text-gray-500 mt-1">{analysis.fundamental_analysis.summary}</p>
                  <p className="text-sm mt-2">
                    Score: <span className="font-medium">{analysis.fundamental_analysis.score}</span>
                  </p>
                </div>
              )}
              {analysis.news_analysis && (
                <div className="p-4 border rounded-lg">
                  <h3 className="font-medium text-gray-900">News Analysis</h3>
                  <p className="text-sm text-gray-500 mt-1">{analysis.news_analysis.summary}</p>
                  <p className="text-sm mt-2">
                    Score: <span className="font-medium">{analysis.news_analysis.score}</span>
                  </p>
                </div>
              )}
              {analysis.technical_analysis && (
                <div className="p-4 border rounded-lg">
                  <h3 className="font-medium text-gray-900">Technical Analysis</h3>
                  <p className="text-sm text-gray-500 mt-1">{analysis.technical_analysis.summary}</p>
                  <p className="text-sm mt-2">
                    Score: <span className="font-medium">{analysis.technical_analysis.score}</span>
                  </p>
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="text-center py-8">
            <p className="text-gray-500">No analysis available for this stock.</p>
            <button className="mt-4 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700">
              Request Analysis
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

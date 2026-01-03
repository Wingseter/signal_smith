import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { stocksApi } from '../../services/api';

export default function StockList() {
  const [market, setMarket] = useState<string>('');

  const { data: stocks, isLoading } = useQuery({
    queryKey: ['stocks', market],
    queryFn: () => stocksApi.list({ market: market || undefined }),
  });

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-900">Stocks</h1>
        <div className="flex space-x-2">
          <button
            onClick={() => setMarket('')}
            className={`px-4 py-2 rounded-md text-sm font-medium ${
              market === '' ? 'bg-primary-600 text-white' : 'bg-gray-100 text-gray-700'
            }`}
          >
            All
          </button>
          <button
            onClick={() => setMarket('KOSPI')}
            className={`px-4 py-2 rounded-md text-sm font-medium ${
              market === 'KOSPI' ? 'bg-primary-600 text-white' : 'bg-gray-100 text-gray-700'
            }`}
          >
            KOSPI
          </button>
          <button
            onClick={() => setMarket('KOSDAQ')}
            className={`px-4 py-2 rounded-md text-sm font-medium ${
              market === 'KOSDAQ' ? 'bg-primary-600 text-white' : 'bg-gray-100 text-gray-700'
            }`}
          >
            KOSDAQ
          </button>
        </div>
      </div>

      <div className="bg-white shadow rounded-lg overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center text-gray-500">Loading...</div>
        ) : stocks && stocks.length > 0 ? (
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Symbol
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Name
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Market
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Sector
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Market Cap
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {stocks.map((stock: {
                id: number;
                symbol: string;
                name: string;
                market: string;
                sector: string | null;
                market_cap: number | null;
              }) => (
                <tr key={stock.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <Link
                      to={`/stocks/${stock.symbol}`}
                      className="text-primary-600 hover:text-primary-900 font-medium"
                    >
                      {stock.symbol}
                    </Link>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {stock.name}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span
                      className={`inline-block px-2 py-1 text-xs font-medium rounded ${
                        stock.market === 'KOSPI'
                          ? 'bg-blue-100 text-blue-800'
                          : 'bg-purple-100 text-purple-800'
                      }`}
                    >
                      {stock.market}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {stock.sector || '-'}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 text-right">
                    {stock.market_cap
                      ? `${(stock.market_cap / 1000000000000).toFixed(2)}T`
                      : '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="p-8 text-center text-gray-500">
            No stocks found. Add stocks through the API or data collection.
          </div>
        )}
      </div>
    </div>
  );
}

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { portfolioApi } from '../../services/api';

interface PortfolioData {
  id: number;
  name: string;
  description: string | null;
  is_default: boolean;
}

interface HoldingData {
  id: number;
  symbol: string;
  quantity: number;
  avg_buy_price: number;
  current_price: number | null;
  profit_loss: number | null;
  profit_loss_percent: number | null;
}

interface PortfolioDetail {
  id: number;
  name: string;
  description: string | null;
  is_default: boolean;
  holdings: HoldingData[];
  total_value: number;
  total_profit_loss: number;
}

export default function Portfolio() {
  const queryClient = useQueryClient();
  const [selectedPortfolio, setSelectedPortfolio] = useState<number | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newPortfolioName, setNewPortfolioName] = useState('');

  const { data: portfolios } = useQuery<PortfolioData[]>({
    queryKey: ['portfolios'],
    queryFn: portfolioApi.list,
  });

  const { data: portfolioDetail } = useQuery<PortfolioDetail>({
    queryKey: ['portfolio', selectedPortfolio],
    queryFn: () => portfolioApi.get(selectedPortfolio!),
    enabled: !!selectedPortfolio,
  });

  const createMutation = useMutation({
    mutationFn: (name: string) => portfolioApi.create({ name }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['portfolios'] });
      setShowCreateForm(false);
      setNewPortfolioName('');
    },
  });

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    if (newPortfolioName.trim()) {
      createMutation.mutate(newPortfolioName);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-900">Portfolio</h1>
        <button
          onClick={() => setShowCreateForm(true)}
          className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
        >
          Create Portfolio
        </button>
      </div>

      {/* Create Form Modal */}
      {showCreateForm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-md">
            <h2 className="text-lg font-semibold mb-4">Create New Portfolio</h2>
            <form onSubmit={handleCreate}>
              <input
                type="text"
                value={newPortfolioName}
                onChange={(e) => setNewPortfolioName(e.target.value)}
                placeholder="Portfolio name"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-primary-500 focus:border-primary-500"
              />
              <div className="mt-4 flex justify-end space-x-2">
                <button
                  type="button"
                  onClick={() => setShowCreateForm(false)}
                  className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
                >
                  Create
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Portfolio List */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">My Portfolios</h2>
          {portfolios && portfolios.length > 0 ? (
            <div className="space-y-2">
              {portfolios.map((portfolio) => (
                <button
                  key={portfolio.id}
                  onClick={() => setSelectedPortfolio(portfolio.id)}
                  className={`w-full text-left p-3 rounded-lg transition-colors ${
                    selectedPortfolio === portfolio.id
                      ? 'bg-primary-100 border-primary-500 border'
                      : 'bg-gray-50 hover:bg-gray-100'
                  }`}
                >
                  <p className="font-medium">{portfolio.name}</p>
                  {portfolio.is_default && (
                    <span className="text-xs text-primary-600">Default</span>
                  )}
                </button>
              ))}
            </div>
          ) : (
            <p className="text-gray-500 text-center py-4">No portfolios yet</p>
          )}
        </div>

        {/* Portfolio Detail */}
        <div className="lg:col-span-2 bg-white rounded-lg shadow p-6">
          {portfolioDetail ? (
            <>
              <div className="flex justify-between items-center mb-6">
                <div>
                  <h2 className="text-lg font-semibold text-gray-900">
                    {portfolioDetail.name}
                  </h2>
                  {portfolioDetail.description && (
                    <p className="text-sm text-gray-500">{portfolioDetail.description}</p>
                  )}
                </div>
                <div className="text-right">
                  <p className="text-sm text-gray-500">Total Value</p>
                  <p className="text-2xl font-bold">
                    {portfolioDetail.total_value.toLocaleString()}
                  </p>
                  <p
                    className={`text-sm ${
                      portfolioDetail.total_profit_loss >= 0
                        ? 'text-green-600'
                        : 'text-red-600'
                    }`}
                  >
                    {portfolioDetail.total_profit_loss >= 0 ? '+' : ''}
                    {portfolioDetail.total_profit_loss.toLocaleString()}
                  </p>
                </div>
              </div>

              {portfolioDetail.holdings.length > 0 ? (
                <table className="min-w-full">
                  <thead>
                    <tr className="border-b border-gray-200">
                      <th className="text-left py-2 text-sm font-medium text-gray-500">
                        Symbol
                      </th>
                      <th className="text-right py-2 text-sm font-medium text-gray-500">
                        Quantity
                      </th>
                      <th className="text-right py-2 text-sm font-medium text-gray-500">
                        Avg Price
                      </th>
                      <th className="text-right py-2 text-sm font-medium text-gray-500">
                        Current
                      </th>
                      <th className="text-right py-2 text-sm font-medium text-gray-500">
                        P/L
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {portfolioDetail.holdings.map((holding) => (
                      <tr key={holding.id} className="border-b border-gray-100">
                        <td className="py-3 font-medium">{holding.symbol}</td>
                        <td className="py-3 text-right">{holding.quantity}</td>
                        <td className="py-3 text-right">
                          {Number(holding.avg_buy_price).toLocaleString()}
                        </td>
                        <td className="py-3 text-right">
                          {holding.current_price
                            ? Number(holding.current_price).toLocaleString()
                            : '-'}
                        </td>
                        <td
                          className={`py-3 text-right ${
                            (holding.profit_loss || 0) >= 0
                              ? 'text-green-600'
                              : 'text-red-600'
                          }`}
                        >
                          {holding.profit_loss_percent
                            ? `${Number(holding.profit_loss_percent).toFixed(2)}%`
                            : '-'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="text-gray-500 text-center py-8">No holdings in this portfolio</p>
              )}
            </>
          ) : (
            <div className="text-center py-16 text-gray-500">
              Select a portfolio to view details
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

import { useQuery } from '@tanstack/react-query';
import { stocksApi, tradingApi, analysisApi } from '../../services/api';
import StockChart from '../Charts/StockChart';

export default function Dashboard() {
  const { data: signals } = useQuery({
    queryKey: ['signals'],
    queryFn: () => tradingApi.getSignals({ limit: 5 }),
  });

  const { data: agentsStatus } = useQuery({
    queryKey: ['agentsStatus'],
    queryFn: analysisApi.getAgentsStatus,
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>

      {/* Market Overview */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-sm font-medium text-gray-500">KOSPI</h3>
          <p className="mt-2 text-3xl font-semibold text-gray-900">2,650.25</p>
          <p className="text-sm text-green-600">+1.25%</p>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-sm font-medium text-gray-500">KOSDAQ</h3>
          <p className="mt-2 text-3xl font-semibold text-gray-900">845.32</p>
          <p className="text-sm text-red-600">-0.48%</p>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-sm font-medium text-gray-500">Trading Status</h3>
          <p className="mt-2 text-3xl font-semibold text-gray-900">Active</p>
          <p className="text-sm text-gray-500">Market Open</p>
        </div>
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Chart Section */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Market Chart</h2>
          <StockChart symbol="KOSPI" />
        </div>

        {/* AI Signals */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">AI Trading Signals</h2>
          {signals && signals.length > 0 ? (
            <div className="space-y-3">
              {signals.map((signal: {
                id: number;
                symbol: string;
                signal_type: string;
                strength: number;
                source_agent: string;
                reason: string;
              }) => (
                <div
                  key={signal.id}
                  className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                >
                  <div>
                    <p className="font-medium">{signal.symbol}</p>
                    <p className="text-sm text-gray-500">{signal.source_agent}</p>
                  </div>
                  <div className="text-right">
                    <span
                      className={`inline-block px-2 py-1 rounded text-sm font-medium ${
                        signal.signal_type === 'buy'
                          ? 'bg-green-100 text-green-800'
                          : signal.signal_type === 'sell'
                          ? 'bg-red-100 text-red-800'
                          : 'bg-gray-100 text-gray-800'
                      }`}
                    >
                      {signal.signal_type.toUpperCase()}
                    </span>
                    <p className="text-sm text-gray-500 mt-1">Strength: {signal.strength}%</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-500 text-center py-8">No signals available</p>
          )}
        </div>
      </div>

      {/* AI Agents Status */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">AI Agents Status</h2>
        {agentsStatus ? (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {agentsStatus.agents.map((agent: {
              name: string;
              role: string;
              status: string;
            }) => (
              <div key={agent.name} className="p-4 bg-gray-50 rounded-lg">
                <div className="flex items-center justify-between">
                  <span className="font-medium capitalize">{agent.name}</span>
                  <span
                    className={`w-2 h-2 rounded-full ${
                      agent.status === 'active' ? 'bg-green-500' : 'bg-gray-400'
                    }`}
                  />
                </div>
                <p className="text-sm text-gray-500 mt-1">{agent.role}</p>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-gray-500">Loading agents status...</p>
        )}
      </div>
    </div>
  );
}

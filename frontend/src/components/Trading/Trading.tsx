import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { tradingApi } from '../../services/api';

interface Order {
  id: number;
  symbol: string;
  transaction_type: string;
  quantity: number;
  price: number;
  total_amount: number;
  status: string;
  created_at: string;
}

export default function Trading() {
  const queryClient = useQueryClient();
  const [showOrderForm, setShowOrderForm] = useState(false);
  const [orderForm, setOrderForm] = useState({
    symbol: '',
    transaction_type: 'buy' as 'buy' | 'sell',
    quantity: 0,
    price: 0,
  });

  const { data: orders } = useQuery<Order[]>({
    queryKey: ['orders'],
    queryFn: () => tradingApi.listOrders(),
  });

  const { data: signals } = useQuery({
    queryKey: ['signals'],
    queryFn: () => tradingApi.getSignals({ limit: 10 }),
  });

  const createOrderMutation = useMutation({
    mutationFn: tradingApi.createOrder,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['orders'] });
      setShowOrderForm(false);
      setOrderForm({ symbol: '', transaction_type: 'buy', quantity: 0, price: 0 });
    },
  });

  const cancelOrderMutation = useMutation({
    mutationFn: tradingApi.cancelOrder,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['orders'] });
    },
  });

  const handleSubmitOrder = (e: React.FormEvent) => {
    e.preventDefault();
    createOrderMutation.mutate(orderForm);
  };

  const getStatusBadgeClass = (status: string) => {
    switch (status) {
      case 'filled':
        return 'bg-green-100 text-green-800';
      case 'cancelled':
      case 'rejected':
        return 'bg-red-100 text-red-800';
      case 'pending':
      case 'submitted':
        return 'bg-yellow-100 text-yellow-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-900">Trading</h1>
        <button
          onClick={() => setShowOrderForm(true)}
          className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
        >
          New Order
        </button>
      </div>

      {/* Order Form Modal */}
      {showOrderForm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-md">
            <h2 className="text-lg font-semibold mb-4">Create Order</h2>
            <form onSubmit={handleSubmitOrder} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700">Symbol</label>
                <input
                  type="text"
                  value={orderForm.symbol}
                  onChange={(e) => setOrderForm({ ...orderForm, symbol: e.target.value.toUpperCase() })}
                  className="mt-1 w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-primary-500 focus:border-primary-500"
                  placeholder="e.g., 005930"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Type</label>
                <select
                  value={orderForm.transaction_type}
                  onChange={(e) => setOrderForm({ ...orderForm, transaction_type: e.target.value as 'buy' | 'sell' })}
                  className="mt-1 w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-primary-500 focus:border-primary-500"
                >
                  <option value="buy">Buy</option>
                  <option value="sell">Sell</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Quantity</label>
                <input
                  type="number"
                  value={orderForm.quantity}
                  onChange={(e) => setOrderForm({ ...orderForm, quantity: parseInt(e.target.value) || 0 })}
                  className="mt-1 w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-primary-500 focus:border-primary-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Price</label>
                <input
                  type="number"
                  value={orderForm.price}
                  onChange={(e) => setOrderForm({ ...orderForm, price: parseFloat(e.target.value) || 0 })}
                  className="mt-1 w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-primary-500 focus:border-primary-500"
                />
              </div>
              <div className="pt-2">
                <p className="text-sm text-gray-500">
                  Total: {(orderForm.quantity * orderForm.price).toLocaleString()} KRW
                </p>
              </div>
              <div className="flex justify-end space-x-2 pt-4">
                <button
                  type="button"
                  onClick={() => setShowOrderForm(false)}
                  className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className={`px-4 py-2 text-white rounded-lg ${
                    orderForm.transaction_type === 'buy'
                      ? 'bg-green-600 hover:bg-green-700'
                      : 'bg-red-600 hover:bg-red-700'
                  }`}
                >
                  {orderForm.transaction_type === 'buy' ? 'Buy' : 'Sell'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Orders */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Orders</h2>
          {orders && orders.length > 0 ? (
            <div className="space-y-3">
              {orders.map((order) => (
                <div
                  key={order.id}
                  className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                >
                  <div>
                    <p className="font-medium">{order.symbol}</p>
                    <p className="text-sm text-gray-500">
                      {order.transaction_type.toUpperCase()} {order.quantity} @ {Number(order.price).toLocaleString()}
                    </p>
                    <p className="text-xs text-gray-400">
                      {new Date(order.created_at).toLocaleString()}
                    </p>
                  </div>
                  <div className="text-right">
                    <span
                      className={`inline-block px-2 py-1 rounded text-xs font-medium ${getStatusBadgeClass(
                        order.status
                      )}`}
                    >
                      {order.status.toUpperCase()}
                    </span>
                    {(order.status === 'pending' || order.status === 'submitted') && (
                      <button
                        onClick={() => cancelOrderMutation.mutate(order.id)}
                        className="block mt-2 text-xs text-red-600 hover:text-red-800"
                      >
                        Cancel
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-500 text-center py-8">No orders yet</p>
          )}
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
                target_price: number | null;
                stop_loss: number | null;
              }) => (
                <div
                  key={signal.id}
                  className="p-3 bg-gray-50 rounded-lg"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium">{signal.symbol}</p>
                      <p className="text-xs text-gray-500">{signal.source_agent}</p>
                    </div>
                    <span
                      className={`px-2 py-1 rounded text-sm font-medium ${
                        signal.signal_type === 'buy'
                          ? 'bg-green-100 text-green-800'
                          : signal.signal_type === 'sell'
                          ? 'bg-red-100 text-red-800'
                          : 'bg-gray-100 text-gray-800'
                      }`}
                    >
                      {signal.signal_type.toUpperCase()}
                    </span>
                  </div>
                  <p className="text-sm text-gray-600 mt-2">{signal.reason}</p>
                  <div className="flex justify-between mt-2 text-xs text-gray-500">
                    <span>Strength: {signal.strength}%</span>
                    {signal.target_price && <span>Target: {Number(signal.target_price).toLocaleString()}</span>}
                    {signal.stop_loss && <span>Stop: {Number(signal.stop_loss).toLocaleString()}</span>}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-500 text-center py-8">No signals available</p>
          )}
        </div>
      </div>
    </div>
  );
}

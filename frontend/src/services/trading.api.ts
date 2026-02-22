import { api } from './client';

export const tradingApi = {
  createOrder: async (data: {
    symbol: string;
    side: 'buy' | 'sell';
    quantity: number;
    price: number;
    order_type?: 'limit' | 'market';
    note?: string;
  }) => {
    const response = await api.post('/trading/orders', data);
    return response.data;
  },
  listOrders: async (params?: { status?: string; symbol?: string; limit?: number }) => {
    const response = await api.get('/trading/orders', { params });
    return response.data;
  },
  getOrder: async (id: number) => {
    const response = await api.get(`/trading/orders/${id}`);
    return response.data;
  },
  cancelOrder: async (id: number) => {
    const response = await api.post(`/trading/orders/${id}/cancel`);
    return response.data;
  },
  getAccountBalance: async () => {
    const response = await api.get('/trading/account/balance');
    return response.data;
  },
  getHoldings: async () => {
    const response = await api.get('/trading/account/holdings');
    return response.data;
  },
  getSignals: async (params?: { symbol?: string; signal_type?: string; executed?: boolean; limit?: number }) => {
    const response = await api.get('/trading/signals', { params });
    return response.data;
  },
  getPendingSignals: async (limit: number = 20) => {
    const response = await api.get('/trading/signals/pending', { params: { limit } });
    return response.data;
  },
  executeSignal: async (signalId: number, quantity: number) => {
    const response = await api.post(`/trading/signals/${signalId}/execute`, { quantity });
    return response.data;
  },
  getTradingSettings: async () => {
    const response = await api.get('/trading/settings');
    return response.data;
  },
};

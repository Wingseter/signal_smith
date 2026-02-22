import { api } from './client';

export const performanceApi = {
  getDashboard: async (period: string = '3m') => {
    const response = await api.get('/performance/dashboard', { params: { period } });
    return response.data;
  },
  getSignalPerformance: async (params?: {
    symbol?: string;
    signal_type?: string;
    executed_only?: boolean;
    limit?: number;
  }) => {
    const response = await api.get('/performance/signals', { params });
    return response.data;
  },
  getRiskMetrics: async (period: string = '3m') => {
    const response = await api.get('/performance/risk-metrics', { params: { period } });
    return response.data;
  },
  getBySymbol: async (period: string = '3m') => {
    const response = await api.get('/performance/by-symbol', { params: { period } });
    return response.data;
  },
  getDrawdown: async (period: string = '3m') => {
    const response = await api.get('/performance/drawdown', { params: { period } });
    return response.data;
  },
  getMonthlyReturns: async (year?: number) => {
    const response = await api.get('/performance/monthly-returns', { params: { year } });
    return response.data;
  },
};

import { api } from './client';

export const backtestApi = {
  getStrategies: async () => {
    const response = await api.get('/backtest/strategies');
    return response.data;
  },
  run: async (data: {
    strategy: string;
    symbols: string[];
    start_date: string;
    end_date: string;
    initial_capital?: number;
    parameters?: Record<string, unknown>;
    config?: Record<string, unknown>;
    save_result?: boolean;
  }) => {
    const response = await api.post('/backtest/run', data);
    return response.data;
  },
  compare: async (params: {
    symbols: string[];
    start_date: string;
    end_date: string;
    strategies?: string[];
    initial_capital?: number;
  }) => {
    const response = await api.post('/backtest/compare', null, { params });
    return response.data;
  },
  getHistory: async (params?: {
    limit?: number;
    offset?: number;
    strategy?: string;
    favorites_only?: boolean;
  }) => {
    const response = await api.get('/backtest/history', { params });
    return response.data;
  },
  getDetail: async (id: number) => {
    const response = await api.get(`/backtest/history/${id}`);
    return response.data;
  },
  updateBacktest: async (id: number, data: {
    is_favorite?: boolean;
    notes?: string;
    tags?: string[];
  }) => {
    const response = await api.patch(`/backtest/history/${id}`, data);
    return response.data;
  },
  deleteBacktest: async (id: number) => {
    const response = await api.delete(`/backtest/history/${id}`);
    return response.data;
  },
  getComparisons: async (limit?: number) => {
    const response = await api.get('/backtest/comparisons', { params: { limit } });
    return response.data;
  },
};

import { api } from './client';

export const stocksApi = {
  list: async (params?: { market?: string; sector?: string; skip?: number; limit?: number }) => {
    const response = await api.get('/stocks', { params });
    return response.data;
  },
  get: async (symbol: string) => {
    const response = await api.get(`/stocks/${symbol}`);
    return response.data;
  },
  getRealtimePrice: async (symbol: string) => {
    const response = await api.get(`/stocks/price/${symbol}`);
    return response.data;
  },
  getMultiplePrices: async (symbols: string[]) => {
    const response = await api.post('/stocks/prices', symbols);
    return response.data;
  },
  getPriceHistory: async (symbol: string, period: string = 'daily', count: number = 100) => {
    const response = await api.get(`/stocks/${symbol}/history`, {
      params: { period, count },
    });
    return response.data;
  },
  getPrices: async (symbol: string, params?: { start_date?: string; end_date?: string; limit?: number }) => {
    const response = await api.get(`/stocks/${symbol}/prices`, { params });
    return response.data;
  },
  getAnalysis: async (symbol: string, analysisType?: string) => {
    const response = await api.get(`/stocks/${symbol}/analysis`, { params: { analysis_type: analysisType } });
    return response.data;
  },
  getWatchlist: async () => {
    const response = await api.get('/stocks/watchlist/me');
    return response.data;
  },
  addToWatchlist: async (symbol: string) => {
    const response = await api.post(`/stocks/watchlist/${symbol}`);
    return response.data;
  },
  removeFromWatchlist: async (symbol: string) => {
    const response = await api.delete(`/stocks/watchlist/${symbol}`);
    return response.data;
  },
  collectPriceData: async (symbol: string) => {
    const response = await api.post(`/stocks/${symbol}/collect`);
    return response.data;
  },
};

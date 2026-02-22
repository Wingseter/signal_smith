import { api, createWebSocket } from './client';

export const analysisApi = {
  runFullAnalysis: async (symbol: string, options?: {
    analysis_types?: string[];
    include_price_data?: boolean;
    save_to_db?: boolean;
  }) => {
    const response = await api.post('/analysis/run', {
      symbol,
      ...options,
    });
    return response.data;
  },
  runQuickAnalysis: async (symbol: string) => {
    const response = await api.post('/analysis/quick', { symbol });
    return response.data;
  },
  requestBackgroundAnalysis: async (symbol: string, analysisTypes?: string[]) => {
    const response = await api.post('/analysis/request', {
      symbol,
      analysis_types: analysisTypes,
    });
    return response.data;
  },
  getTaskStatus: async (taskId: string) => {
    const response = await api.get(`/analysis/task/${taskId}`);
    return response.data;
  },
  getConsolidated: async (symbol: string) => {
    const response = await api.get(`/analysis/consolidated/${symbol}`);
    return response.data;
  },
  getHistory: async (symbol: string, analysisType?: string, limit?: number) => {
    const response = await api.get(`/analysis/history/${symbol}`, {
      params: { analysis_type: analysisType, limit },
    });
    return response.data;
  },
  getMarketSentiment: async (market: string = 'KOSPI') => {
    const response = await api.get('/analysis/market/sentiment', { params: { market } });
    return response.data;
  },
  getAgentsStatus: async () => {
    const response = await api.get('/analysis/agents/status');
    return response.data;
  },
  getCoordinatorStatus: async () => {
    const response = await api.get('/analysis/agents/coordinator');
    return response.data;
  },
  getLatestSignals: async (limit: number = 10, signalType?: string) => {
    const response = await api.get('/analysis/signals/latest', {
      params: { limit, signal_type: signalType },
    });
    return response.data;
  },
  getSignalsStats: async () => {
    const response = await api.get('/analysis/signals/stats');
    return response.data;
  },
};

export const analysisWebSocket = {
  connect: () => createWebSocket('analysis'),
  subscribeSymbol: (ws: WebSocket, symbol: string) => {
    ws.send(JSON.stringify({ action: 'subscribe_symbol', symbol }));
  },
  ping: (ws: WebSocket) => {
    ws.send(JSON.stringify({ action: 'ping' }));
  },
};

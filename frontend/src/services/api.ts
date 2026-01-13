import axios from 'axios';
import { useAuthStore } from '../store/authStore';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const api = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor
api.interceptors.request.use(
  (config) => {
    const token = useAuthStore.getState().accessToken;
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      useAuthStore.getState().logout();
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// Auth API
export const authApi = {
  login: async (email: string, password: string) => {
    const formData = new FormData();
    formData.append('username', email);
    formData.append('password', password);
    const response = await api.post('/auth/login', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },
  register: async (email: string, password: string, fullName?: string) => {
    const response = await api.post('/auth/register', {
      email,
      password,
      full_name: fullName,
    });
    return response.data;
  },
  getMe: async (token?: string) => {
    const config = token ? { headers: { Authorization: `Bearer ${token}` } } : {};
    const response = await api.get('/auth/me', config);
    return response.data;
  },
};

// Stocks API
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

// Portfolio API
export const portfolioApi = {
  list: async () => {
    const response = await api.get('/portfolio');
    return response.data;
  },
  get: async (id: number) => {
    const response = await api.get(`/portfolio/${id}`);
    return response.data;
  },
  create: async (data: { name: string; description?: string; is_default?: boolean }) => {
    const response = await api.post('/portfolio', data);
    return response.data;
  },
  addHolding: async (portfolioId: number, data: { symbol: string; quantity: number; avg_buy_price: number }) => {
    const response = await api.post(`/portfolio/${portfolioId}/holdings`, data);
    return response.data;
  },
  delete: async (id: number) => {
    await api.delete(`/portfolio/${id}`);
  },
};

// Trading API
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

// Analysis API
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

// WebSocket connection helper
export const createWebSocket = (endpoint: string): WebSocket => {
  const wsUrl = API_BASE_URL.replace('http', 'ws');
  return new WebSocket(`${wsUrl}/ws/${endpoint}`);
};

// Market WebSocket
export const marketWebSocket = {
  connect: () => createWebSocket('market'),
  subscribe: (ws: WebSocket, symbols: string[]) => {
    ws.send(JSON.stringify({ action: 'subscribe', symbols }));
  },
  unsubscribe: (ws: WebSocket, symbols: string[]) => {
    ws.send(JSON.stringify({ action: 'unsubscribe', symbols }));
  },
  getPrice: (ws: WebSocket, symbol: string) => {
    ws.send(JSON.stringify({ action: 'get_price', symbol }));
  },
  ping: (ws: WebSocket) => {
    ws.send(JSON.stringify({ action: 'ping' }));
  },
};

// Analysis WebSocket
export const analysisWebSocket = {
  connect: () => createWebSocket('analysis'),
  subscribeSymbol: (ws: WebSocket, symbol: string) => {
    ws.send(JSON.stringify({ action: 'subscribe_symbol', symbol }));
  },
  ping: (ws: WebSocket) => {
    ws.send(JSON.stringify({ action: 'ping' }));
  },
};

// Trading WebSocket
export const tradingWebSocket = {
  connect: () => createWebSocket('trading'),
  ping: (ws: WebSocket) => {
    ws.send(JSON.stringify({ type: 'ping' }));
  },
};

// Notifications API
export const notificationsApi = {
  getStatus: async () => {
    const response = await api.get('/notifications/status');
    return response.data;
  },
  getChannels: async () => {
    const response = await api.get('/notifications/channels');
    return response.data;
  },
  getSettings: async () => {
    const response = await api.get('/notifications/settings');
    return response.data;
  },
  updateSettings: async (settings: Record<string, unknown>) => {
    const response = await api.put('/notifications/settings', settings);
    return response.data;
  },
  sendTest: async (channel: string, message?: string) => {
    const response = await api.post('/notifications/test', { channel, message });
    return response.data;
  },
  sendNotification: async (data: {
    type: string;
    title: string;
    message: string;
    priority?: string;
    data?: Record<string, unknown>;
    channels?: string[];
  }) => {
    const response = await api.post('/notifications/send', data);
    return response.data;
  },
  getAlerts: async () => {
    const response = await api.get('/notifications/alerts');
    return response.data;
  },
  createAlert: async (alert: {
    symbol: string;
    price_above?: number | null;
    price_below?: number | null;
    note?: string | null;
  }) => {
    const response = await api.post('/notifications/alerts', alert);
    return response.data;
  },
  deleteAlert: async (alertId: number) => {
    const response = await api.delete(`/notifications/alerts/${alertId}`);
    return response.data;
  },
};

// Backtesting API
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

// Performance Analytics API
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

// Portfolio Optimizer API
export const optimizerApi = {
  getMethods: async () => {
    const response = await api.get('/optimizer/methods');
    return response.data;
  },
  optimize: async (data: {
    symbols: string[];
    total_capital: number;
    method?: string;
    risk_level?: string;
    max_position_size?: number;
    max_sector_exposure?: number;
  }) => {
    const response = await api.post('/optimizer/optimize', data);
    return response.data;
  },
  calculatePositionSize: async (data: {
    symbol: string;
    entry_price: number;
    stop_loss_price: number;
    total_capital: number;
    current_portfolio_value?: number;
    win_rate?: number;
    avg_win_loss_ratio?: number;
    max_risk_per_trade?: number;
  }) => {
    const response = await api.post('/optimizer/position-size', data);
    return response.data;
  },
  getDiversification: async (portfolioId?: number) => {
    const response = await api.get('/optimizer/diversification', {
      params: portfolioId ? { portfolio_id: portfolioId } : {},
    });
    return response.data;
  },
  getRebalanceSuggestions: async (portfolioId?: number, method?: string) => {
    const response = await api.post('/optimizer/rebalance', null, {
      params: { portfolio_id: portfolioId, target_method: method },
    });
    return response.data;
  },
};

// Sector Analysis API
export const sectorsApi = {
  list: async () => {
    const response = await api.get('/sectors/list');
    return response.data;
  },
  getPerformance: async () => {
    const response = await api.get('/sectors/performance');
    return response.data;
  },
  getSectorDetail: async (sectorId: string) => {
    const response = await api.get(`/sectors/sector/${sectorId}`);
    return response.data;
  },
  getThemes: async (hotOnly: boolean = false) => {
    const response = await api.get('/sectors/themes', { params: { hot_only: hotOnly } });
    return response.data;
  },
  getThemeDetail: async (themeId: string) => {
    const response = await api.get(`/sectors/theme/${themeId}`);
    return response.data;
  },
  getRotationSignal: async () => {
    const response = await api.get('/sectors/rotation');
    return response.data;
  },
  getRecommended: async (cyclePhase?: string) => {
    const response = await api.get('/sectors/recommended', {
      params: cyclePhase ? { cycle_phase: cyclePhase } : {},
    });
    return response.data;
  },
  getCorrelation: async (periodDays: number = 60) => {
    const response = await api.get('/sectors/correlation', { params: { period_days: periodDays } });
    return response.data;
  },
  search: async (keyword: string) => {
    const response = await api.get('/sectors/search', { params: { keyword } });
    return response.data;
  },
  getHeatmap: async () => {
    const response = await api.get('/sectors/heatmap');
    return response.data;
  },
};

// AI Council API
export const councilApi = {
  getStatus: async () => {
    const response = await api.get('/council/status');
    return response.data;
  },
  start: async (config?: {
    council_threshold?: number;
    sell_threshold?: number;
    auto_execute?: boolean;
    max_position_per_stock?: number;
    poll_interval?: number;
  }) => {
    const response = await api.post('/council/start', config || {});
    return response.data;
  },
  stop: async () => {
    const response = await api.post('/council/stop');
    return response.data;
  },
  getMeetings: async (limit: number = 10) => {
    const response = await api.get('/council/meetings', { params: { limit } });
    return response.data;
  },
  getMeeting: async (meetingId: string) => {
    const response = await api.get(`/council/meetings/${meetingId}`);
    return response.data;
  },
  getTranscript: async (meetingId: string) => {
    const response = await api.get(`/council/meetings/${meetingId}/transcript`);
    return response.data;
  },
  getPendingSignals: async () => {
    const response = await api.get('/council/signals/pending');
    return response.data;
  },
  approveSignal: async (signalId: string) => {
    const response = await api.post('/council/signals/approve', { signal_id: signalId });
    return response.data;
  },
  rejectSignal: async (signalId: string) => {
    const response = await api.post('/council/signals/reject', { signal_id: signalId });
    return response.data;
  },
  executeSignal: async (signalId: string) => {
    const response = await api.post('/council/signals/execute', { signal_id: signalId });
    return response.data;
  },
  updateConfig: async (config: {
    council_threshold?: number;
    sell_threshold?: number;
    auto_execute?: boolean;
    max_position_per_stock?: number;
    poll_interval?: number;
  }) => {
    const response = await api.put('/council/config', config);
    return response.data;
  },
  startManualMeeting: async (data: {
    symbol: string;
    company_name: string;
    news_title: string;
    news_score?: number;
  }) => {
    const response = await api.post('/council/meetings/manual', data);
    return response.data;
  },
};

// Council WebSocket (uses different path than other websockets)
export const councilWebSocket = {
  connect: () => {
    const wsUrl = API_BASE_URL.replace('http', 'ws');
    return new WebSocket(`${wsUrl}/api/v1/council/ws`);
  },
  ping: (ws: WebSocket) => {
    ws.send(JSON.stringify({ type: 'ping' }));
  },
  getStatus: (ws: WebSocket) => {
    ws.send(JSON.stringify({ type: 'get_status' }));
  },
};

// News Monitor API
export const newsMonitorApi = {
  getStatus: async () => {
    const response = await api.get('/news-monitor/status');
    return response.data;
  },
  getCrawledNews: async (limit: number = 20) => {
    const response = await api.get('/news-monitor/crawled', { params: { limit } });
    return response.data;
  },
  getAnalysisHistory: async (limit: number = 20) => {
    const response = await api.get('/news-monitor/analysis', { params: { limit } });
    return response.data;
  },
  testCrawl: async () => {
    const response = await api.post('/news-monitor/test-crawl');
    return response.data;
  },
  testAnalyze: async (title: string, symbol?: string) => {
    const response = await api.post('/news-monitor/test-analyze', null, {
      params: { title, symbol },
    });
    return response.data;
  },
};

// News Monitor WebSocket
export const newsMonitorWebSocket = {
  connect: () => {
    const wsUrl = API_BASE_URL.replace('http', 'ws');
    return new WebSocket(`${wsUrl}/api/v1/news-monitor/ws`);
  },
  ping: (ws: WebSocket) => {
    ws.send(JSON.stringify({ type: 'ping' }));
  },
  getStatus: (ws: WebSocket) => {
    ws.send(JSON.stringify({ type: 'get_status' }));
  },
};

// Reports API
export const reportsApi = {
  getTypes: async () => {
    const response = await api.get('/reports/types');
    return response.data;
  },
  generateStockReport: async (symbol: string, includeAiInsights: boolean = true) => {
    const response = await api.post(
      '/reports/stock',
      { symbol, include_ai_insights: includeAiInsights },
      { responseType: 'blob' }
    );
    return response.data;
  },
  generatePortfolioReport: async (portfolioId?: number, includeRiskMetrics: boolean = true) => {
    const response = await api.post(
      '/reports/portfolio',
      { portfolio_id: portfolioId, include_risk_metrics: includeRiskMetrics },
      { responseType: 'blob' }
    );
    return response.data;
  },
  generateTradingReport: async (periodDays: number = 30) => {
    const response = await api.post(
      '/reports/trading',
      { period_days: periodDays },
      { responseType: 'blob' }
    );
    return response.data;
  },
  generateMarketReport: async (includeSectors: boolean = true) => {
    const response = await api.post(
      '/reports/market',
      { include_sectors: includeSectors },
      { responseType: 'blob' }
    );
    return response.data;
  },
};

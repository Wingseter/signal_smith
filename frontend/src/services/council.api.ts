import { api } from './client';
import { WS_BASE_URL } from '../config';

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
    const response = await api.post('/council/start', config ?? undefined);
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
  getTradingStatus: async () => {
    const response = await api.get('/council/trading-status');
    return response.data;
  },
  getCostStats: async () => {
    const response = await api.get('/council/cost-stats');
    return response.data;
  },
  getQueuedExecutions: async () => {
    const response = await api.get('/council/queued-executions');
    return response.data;
  },
  processQueue: async () => {
    const response = await api.post('/council/process-queue');
    return response.data;
  },
  getAccountSummary: async () => {
    const response = await api.get('/council/account/summary');
    return response.data;
  },
  getAccountBalance: async () => {
    const summary = await councilApi.getAccountSummary();
    return summary.balance;
  },
  getAccountHoldings: async () => {
    const summary = await councilApi.getAccountSummary();
    return { holdings: summary.holdings, count: summary.count };
  },
  testAnalyzeNews: async () => {
    const response = await api.post('/council/test/analyze-news');
    return response.data;
  },
  testForceCouncil: async () => {
    const response = await api.post('/council/test/force-council');
    return response.data;
  },
  testMockCouncil: async (symbol: string = '005930', companyName: string = '삼성전자') => {
    const response = await api.post(`/council/test/mock-council?symbol=${symbol}&company_name=${encodeURIComponent(companyName)}`);
    return response.data;
  },
};

export const councilWebSocket = {
  connect: () => {
    return new WebSocket(`${WS_BASE_URL}/api/v1/council/ws`);
  },
  ping: (ws: WebSocket) => {
    ws.send(JSON.stringify({ type: 'ping' }));
  },
  getStatus: (ws: WebSocket) => {
    ws.send(JSON.stringify({ type: 'get_status' }));
  },
};

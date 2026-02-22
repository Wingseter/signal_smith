import { api } from './client';
import { WS_BASE_URL } from '../config';

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

export const newsMonitorWebSocket = {
  connect: () => {
    return new WebSocket(`${WS_BASE_URL}/api/v1/news-monitor/ws`);
  },
  ping: (ws: WebSocket) => {
    ws.send(JSON.stringify({ type: 'ping' }));
  },
  getStatus: (ws: WebSocket) => {
    ws.send(JSON.stringify({ type: 'get_status' }));
  },
};

import { api } from './client';
import { WS_BASE_URL } from '../config';

export const quantSignalsApi = {
  getStatus: async () => {
    const response = await api.get('/signals/status');
    return response.data;
  },
  getResults: async (limit: number = 50) => {
    const response = await api.get('/signals/results', { params: { limit } });
    return response.data;
  },
  scanStock: async (symbol: string) => {
    const response = await api.get(`/signals/scan/${symbol}`);
    return response.data;
  },
  scanWatchlist: async (symbols: string[]) => {
    const response = await api.post('/signals/scan', { symbols });
    return response.data;
  },
  getTopSignals: async (limit: number = 20) => {
    const response = await api.get('/signals/top', { params: { limit } });
    return response.data;
  },
};

export const signalsWebSocket = {
  connect: () => {
    return new WebSocket(`${WS_BASE_URL}/api/v1/signals/ws`);
  },
  ping: (ws: WebSocket) => {
    ws.send(JSON.stringify({ type: 'ping' }));
  },
};

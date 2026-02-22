import { api } from './client';

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

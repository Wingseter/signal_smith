import { api } from './client';

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

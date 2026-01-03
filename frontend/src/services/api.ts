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
  getMe: async () => {
    const response = await api.get('/auth/me');
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
  getPrices: async (symbol: string, params?: { start_date?: string; end_date?: string; limit?: number }) => {
    const response = await api.get(`/stocks/${symbol}/prices`, { params });
    return response.data;
  },
  getAnalysis: async (symbol: string, analysisType?: string) => {
    const response = await api.get(`/stocks/${symbol}/analysis`, { params: { analysis_type: analysisType } });
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
    transaction_type: 'buy' | 'sell';
    quantity: number;
    price: number;
    note?: string;
  }) => {
    const response = await api.post('/trading/orders', data);
    return response.data;
  },
  listOrders: async (params?: { status?: string; symbol?: string; skip?: number; limit?: number }) => {
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
  getSignals: async (params?: { symbol?: string; signal_type?: string; limit?: number }) => {
    const response = await api.get('/trading/signals', { params });
    return response.data;
  },
};

// Analysis API
export const analysisApi = {
  request: async (symbol: string, analysisTypes?: string[]) => {
    const response = await api.post('/analysis/request', {
      symbol,
      analysis_types: analysisTypes,
    });
    return response.data;
  },
  getConsolidated: async (symbol: string) => {
    const response = await api.get(`/analysis/consolidated/${symbol}`);
    return response.data;
  },
  getAgentsStatus: async () => {
    const response = await api.get('/analysis/agents/status');
    return response.data;
  },
};

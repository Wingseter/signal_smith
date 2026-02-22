/**
 * Axios HTTP client with auth interceptors.
 * All domain API modules import from here.
 */

import axios from 'axios';
import { useAuthStore } from '../store/authStore';
import { API_BASE_URL, WS_BASE_URL } from '../config';

export const api = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor - attach JWT
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

// Response interceptor - handle 401
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

/** Create a WebSocket connection to a /ws/ endpoint */
export const createWebSocket = (endpoint: string): WebSocket => {
  return new WebSocket(`${WS_BASE_URL}/ws/${endpoint}`);
};

export { WS_BASE_URL };

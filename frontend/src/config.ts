/**
 * Application-wide configuration constants.
 * Single source of truth for API and WebSocket URLs.
 */

export const API_BASE_URL =
  import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const WS_BASE_URL =
  import.meta.env.VITE_WS_URL || API_BASE_URL.replace(/^http/, 'ws');

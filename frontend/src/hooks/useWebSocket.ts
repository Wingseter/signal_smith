import { useEffect, useRef, useState, useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';

type WebSocketStatus = 'connecting' | 'connected' | 'disconnected' | 'error';

interface WebSocketOptions {
  onMessage?: (data: unknown) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Event) => void;
  reconnect?: boolean;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
  pingInterval?: number;
}

interface WebSocketHookReturn {
  status: WebSocketStatus;
  sendMessage: (message: unknown) => void;
  disconnect: () => void;
  reconnect: () => void;
}

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const WS_BASE_URL = import.meta.env.VITE_WS_URL || API_BASE_URL.replace(/^http/, 'ws');

export function useWebSocket(
  endpoint: string,
  options: WebSocketOptions = {}
): WebSocketHookReturn {
  const {
    onMessage,
    onConnect,
    onDisconnect,
    onError,
    reconnect: shouldReconnect = true,
    reconnectInterval = 3000,
    maxReconnectAttempts = 5,
    pingInterval = 30000,
  } = options;

  const [status, setStatus] = useState<WebSocketStatus>('disconnected');
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    setStatus('connecting');
    const ws = new WebSocket(`${WS_BASE_URL}/ws/${endpoint}`);

    ws.onopen = () => {
      setStatus('connected');
      reconnectAttemptsRef.current = 0;
      onConnect?.();

      // Start ping interval
      pingIntervalRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'ping' }));
        }
      }, pingInterval);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type !== 'pong') {
          onMessage?.(data);
        }
      } catch {
        onMessage?.(event.data);
      }
    };

    ws.onclose = () => {
      setStatus('disconnected');
      onDisconnect?.();

      // Clear ping interval
      if (pingIntervalRef.current) {
        clearInterval(pingIntervalRef.current);
        pingIntervalRef.current = null;
      }

      // Attempt reconnection
      if (shouldReconnect && reconnectAttemptsRef.current < maxReconnectAttempts) {
        reconnectAttemptsRef.current += 1;
        reconnectTimeoutRef.current = setTimeout(() => {
          connect();
        }, reconnectInterval);
      }
    };

    ws.onerror = (error) => {
      setStatus('error');
      onError?.(error);
    };

    wsRef.current = ws;
  }, [endpoint, onConnect, onDisconnect, onError, onMessage, shouldReconnect, reconnectInterval, maxReconnectAttempts, pingInterval]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setStatus('disconnected');
  }, []);

  const sendMessage = useCallback((message: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(typeof message === 'string' ? message : JSON.stringify(message));
    }
  }, []);

  const manualReconnect = useCallback(() => {
    reconnectAttemptsRef.current = 0;
    disconnect();
    connect();
  }, [connect, disconnect]);

  useEffect(() => {
    connect();
    return () => disconnect();
  }, [connect, disconnect]);

  return {
    status,
    sendMessage,
    disconnect,
    reconnect: manualReconnect,
  };
}

// Market WebSocket Hook
interface MarketData {
  symbol: string;
  price: number;
  change: number;
  change_percent: number;
  volume: number;
  timestamp: string;
}

interface UseMarketWebSocketOptions {
  symbols: string[];
  onPriceUpdate?: (data: MarketData) => void;
}

export function useMarketWebSocket({ symbols, onPriceUpdate }: UseMarketWebSocketOptions) {
  const queryClient = useQueryClient();

  const handleMessage = useCallback((data: unknown) => {
    const message = data as { type: string; data?: MarketData };
    if ((message.type === 'price_update' || message.type === 'price') && message.data) {
      onPriceUpdate?.(message.data);
      // Update query cache
      queryClient.setQueryData(['price', message.data.symbol], message.data);
    }
  }, [onPriceUpdate, queryClient]);

  const { status, sendMessage, disconnect, reconnect } = useWebSocket('market', {
    onMessage: handleMessage,
    onConnect: () => {
      // Subscribe to symbols on connect
      if (symbols.length > 0) {
        sendMessage({ action: 'subscribe', symbols });
      }
    },
  });

  const subscribe = useCallback((newSymbols: string[]) => {
    sendMessage({ action: 'subscribe', symbols: newSymbols });
  }, [sendMessage]);

  const unsubscribe = useCallback((symbolsToRemove: string[]) => {
    sendMessage({ action: 'unsubscribe', symbols: symbolsToRemove });
  }, [sendMessage]);

  // Subscribe when symbols change
  useEffect(() => {
    if (status === 'connected' && symbols.length > 0) {
      subscribe(symbols);
    }
  }, [status, symbols, subscribe]);

  return {
    status,
    subscribe,
    unsubscribe,
    disconnect,
    reconnect,
  };
}

// Analysis WebSocket Hook
interface AnalysisUpdate {
  symbol: string;
  agent: string;
  status: string;
  result?: unknown;
}

interface UseAnalysisWebSocketOptions {
  symbol?: string;
  onAnalysisUpdate?: (data: AnalysisUpdate) => void;
}

export function useAnalysisWebSocket({ symbol, onAnalysisUpdate }: UseAnalysisWebSocketOptions) {
  const queryClient = useQueryClient();

  const handleMessage = useCallback((data: unknown) => {
    const message = data as { type: string; symbol?: string; data?: AnalysisUpdate & { symbol?: string } };
    if ((message.type === 'analysis_update' || message.type === 'analysis') && message.data) {
      onAnalysisUpdate?.(message.data);
      // Invalidate related queries
      const symbolKey = message.symbol || message.data.symbol;
      queryClient.invalidateQueries({ queryKey: symbolKey ? ['analysis', symbolKey] : ['analysis'] });
    }
  }, [onAnalysisUpdate, queryClient]);

  const { status, sendMessage, disconnect, reconnect } = useWebSocket('analysis', {
    onMessage: handleMessage,
    onConnect: () => {
      if (symbol) {
        sendMessage({ action: 'subscribe_symbol', symbol });
      }
    },
  });

  const subscribeSymbol = useCallback((newSymbol: string) => {
    sendMessage({ action: 'subscribe_symbol', symbol: newSymbol });
  }, [sendMessage]);

  // Subscribe when symbol changes
  useEffect(() => {
    if (status === 'connected' && symbol) {
      subscribeSymbol(symbol);
    }
  }, [status, symbol, subscribeSymbol]);

  return {
    status,
    subscribeSymbol,
    disconnect,
    reconnect,
  };
}

// Trading WebSocket Hook
interface TradingUpdate {
  type: 'order_update' | 'signal_update' | 'balance_update';
  data: unknown;
}

interface UseTradingWebSocketOptions {
  onOrderUpdate?: (data: unknown) => void;
  onSignalUpdate?: (data: unknown) => void;
  onBalanceUpdate?: (data: unknown) => void;
}

export function useTradingWebSocket({
  onOrderUpdate,
  onSignalUpdate,
  onBalanceUpdate,
}: UseTradingWebSocketOptions = {}) {
  const queryClient = useQueryClient();

  const handleMessage = useCallback((data: unknown) => {
    const message = data as TradingUpdate;
    switch (message.type) {
      case 'order_update':
        onOrderUpdate?.(message.data);
        queryClient.invalidateQueries({ queryKey: ['orders'] });
        break;
      case 'signal_update':
        onSignalUpdate?.(message.data);
        queryClient.invalidateQueries({ queryKey: ['signals'] });
        break;
      case 'balance_update':
        onBalanceUpdate?.(message.data);
        queryClient.invalidateQueries({ queryKey: ['account'] });
        break;
    }
  }, [onOrderUpdate, onSignalUpdate, onBalanceUpdate, queryClient]);

  const { status, disconnect, reconnect } = useWebSocket('trading', {
    onMessage: handleMessage,
  });

  return {
    status,
    disconnect,
    reconnect,
  };
}

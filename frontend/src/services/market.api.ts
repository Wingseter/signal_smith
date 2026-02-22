import { createWebSocket } from './client';

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

export const tradingWebSocket = {
  connect: () => createWebSocket('trading'),
  ping: (ws: WebSocket) => {
    ws.send(JSON.stringify({ type: 'ping' }));
  },
};

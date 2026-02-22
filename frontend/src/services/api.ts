/**
 * Barrel re-export for backward compatibility.
 * New code should import directly from domain modules (e.g. './council.api').
 */

// Shared axios instance & helpers
export { api, createWebSocket } from './client';

// Domain APIs
export { authApi } from './auth.api';
export { stocksApi } from './stocks.api';
export { portfolioApi } from './portfolio.api';
export { tradingApi } from './trading.api';
export { analysisApi } from './analysis.api';
export { notificationsApi } from './notifications.api';
export { backtestApi } from './backtest.api';
export { performanceApi } from './performance.api';
export { optimizerApi } from './optimizer.api';
export { sectorsApi } from './sectors.api';
export { councilApi } from './council.api';
export { quantSignalsApi } from './signals.api';
export { newsMonitorApi } from './news-monitor.api';
export { reportsApi } from './reports.api';

// WebSockets
export { marketWebSocket, tradingWebSocket } from './market.api';
export { analysisWebSocket } from './analysis.api';
export { councilWebSocket } from './council.api';
export { signalsWebSocket } from './signals.api';
export { newsMonitorWebSocket } from './news-monitor.api';

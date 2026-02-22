import { api } from './client';

export const reportsApi = {
  getTypes: async () => {
    const response = await api.get('/reports/types');
    return response.data;
  },
  generateStockReport: async (symbol: string, includeAiInsights: boolean = true) => {
    const response = await api.post(
      '/reports/stock',
      { symbol, include_ai_insights: includeAiInsights },
      { responseType: 'blob' }
    );
    return response.data;
  },
  generatePortfolioReport: async (portfolioId?: number, includeRiskMetrics: boolean = true) => {
    const response = await api.post(
      '/reports/portfolio',
      { portfolio_id: portfolioId, include_risk_metrics: includeRiskMetrics },
      { responseType: 'blob' }
    );
    return response.data;
  },
  generateTradingReport: async (periodDays: number = 30) => {
    const response = await api.post(
      '/reports/trading',
      { period_days: periodDays },
      { responseType: 'blob' }
    );
    return response.data;
  },
  generateMarketReport: async (includeSectors: boolean = true) => {
    const response = await api.post(
      '/reports/market',
      { include_sectors: includeSectors },
      { responseType: 'blob' }
    );
    return response.data;
  },
};

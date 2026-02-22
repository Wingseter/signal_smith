import { api } from './client';

export const optimizerApi = {
  getMethods: async () => {
    const response = await api.get('/optimizer/methods');
    return response.data;
  },
  optimize: async (data: {
    symbols: string[];
    total_capital: number;
    method?: string;
    risk_level?: string;
    max_position_size?: number;
    max_sector_exposure?: number;
  }) => {
    const response = await api.post('/optimizer/optimize', data);
    return response.data;
  },
  calculatePositionSize: async (data: {
    symbol: string;
    entry_price: number;
    stop_loss_price: number;
    total_capital: number;
    current_portfolio_value?: number;
    win_rate?: number;
    avg_win_loss_ratio?: number;
    max_risk_per_trade?: number;
  }) => {
    const response = await api.post('/optimizer/position-size', data);
    return response.data;
  },
  getDiversification: async (portfolioId?: number) => {
    const response = await api.get('/optimizer/diversification', {
      params: portfolioId ? { portfolio_id: portfolioId } : {},
    });
    return response.data;
  },
  getRebalanceSuggestions: async (portfolioId?: number, method?: string) => {
    const response = await api.post('/optimizer/rebalance', null, {
      params: { portfolio_id: portfolioId, target_method: method },
    });
    return response.data;
  },
};

export interface User {
  id: number;
  email: string;
  full_name: string | null;
  is_active: boolean;
}

export interface Stock {
  id: number;
  symbol: string;
  name: string;
  market: string;
  sector: string | null;
  industry: string | null;
  market_cap: number | null;
}

export interface StockPrice {
  symbol: string;
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  change_percent: number | null;
}

export interface StockAnalysis {
  id: number;
  symbol: string;
  analysis_type: string;
  agent_name: string;
  summary: string;
  score: number | null;
  recommendation: string | null;
  created_at: string;
}

export interface Portfolio {
  id: number;
  name: string;
  description: string | null;
  is_default: boolean;
}

export interface PortfolioHolding {
  id: number;
  symbol: string;
  quantity: number;
  avg_buy_price: number;
  current_price: number | null;
  profit_loss: number | null;
  profit_loss_percent: number | null;
}

export interface Transaction {
  id: number;
  symbol: string;
  transaction_type: 'buy' | 'sell';
  quantity: number;
  price: number;
  total_amount: number;
  status: string;
  order_id: string | null;
  created_at: string;
}

export interface TradingSignal {
  id: number;
  symbol: string;
  signal_type: 'buy' | 'sell' | 'hold';
  strength: number;
  source_agent: string;
  reason: string;
  target_price: number | null;
  stop_loss: number | null;
  created_at: string;
}

export interface ConsolidatedAnalysis {
  symbol: string;
  overall_score: number;
  overall_recommendation: 'buy' | 'sell' | 'hold';
  quant_analysis: AgentAnalysis | null;
  fundamental_analysis: AgentAnalysis | null;
  news_analysis: AgentAnalysis | null;
  technical_analysis: AgentAnalysis | null;
}

export interface AgentAnalysis {
  agent: string;
  summary: string;
  score: number | null;
  recommendation: string | null;
  created_at: string;
}

export interface Agent {
  name: string;
  role: string;
  status: 'active' | 'inactive' | 'error';
  last_run: string | null;
}

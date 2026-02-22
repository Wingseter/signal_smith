export interface CouncilMessage {
  id: string;
  role: string;
  speaker: string;
  content: string;
  data: Record<string, unknown> | null;
  timestamp: string;
}

export interface InvestmentSignal {
  id: string;
  symbol: string;
  company_name: string;
  action: string;
  allocation_percent: number;
  suggested_amount: number;
  suggested_quantity: number;
  target_price: number | null;
  stop_loss_price: number | null;
  quant_summary: string;
  fundamental_summary: string;
  consensus_reason: string;
  confidence: number;
  quant_score: number;
  fundamental_score: number;
  status: string;
  created_at: string;
  executed_at: string | null;
}

export interface CouncilMeeting {
  id: string;
  symbol: string;
  company_name: string;
  news_title: string;
  news_score: number;
  messages: CouncilMessage[];
  current_round: number;
  max_rounds: number;
  signal: InvestmentSignal | null;
  consensus_reached: boolean;
  started_at: string;
  ended_at: string | null;
  transcript: string;
}

export interface TradingStatus {
  session: string;
  can_trade: boolean;
  reason: string;
  status_message: string;
  queued_count: number;
  auto_execute: boolean;
  respect_trading_hours: boolean;
}

export interface CostStats {
  daily_cost: number;
  monthly_cost: number;
  daily_remaining: number;
  monthly_remaining: number;
  daily_limit: number;
  monthly_limit: number;
}

export interface CouncilStatus {
  running: boolean;
  auto_execute: boolean;
  council_threshold: number;
  pending_signals: number;
  total_meetings: number;
  daily_trades: number;
  monitor_running: boolean;
  trading?: TradingStatus;
  cost?: CostStats;
}

export interface CouncilConfig {
  council_threshold: number;
  sell_threshold: number;
  auto_execute: boolean;
  max_position_per_stock: number;
  poll_interval: number;
}

export interface AccountBalance {
  total_deposit: number;
  available_amount: number;
  total_purchase: number;
  total_evaluation: number;
  total_profit_loss: number;
  profit_rate: number;
  [key: string]: unknown;
}

export interface Holding {
  symbol: string;
  name: string;
  quantity: number;
  avg_price: number;
  current_price: number;
  evaluation: number;
  profit_loss: number;
  profit_rate: number;
  [key: string]: unknown;
}

export interface AccountSummary {
  balance: AccountBalance;
  holdings: Holding[];
  count: number;
}

import { useState, useEffect, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { tradingApi, analysisApi, tradingWebSocket } from '../../services/api';

interface TradingSignal {
  id: number;
  symbol: string;
  signal_type: 'buy' | 'sell' | 'hold';
  strength: number;
  source_agent: string;
  reason: string;
  target_price: number | null;
  stop_loss: number | null;
  entry_price: number | null;
  confidence: number;
  risk_level: 'low' | 'medium' | 'high';
  time_horizon: 'short' | 'medium' | 'long';
  executed: boolean;
  executed_at: string | null;
  created_at: string;
}

interface SignalStats {
  total: number;
  pending: number;
  executed: number;
  by_type: {
    buy: number;
    sell: number;
    hold: number;
  };
  success_rate: number;
  avg_return: number;
}

interface AccountBalance {
  total_deposit: number;
  available_amount: number;
  total_purchase: number;
  total_evaluation: number;
  total_profit_loss: number;
  profit_rate: number;
}

interface ExecuteModalProps {
  signal: TradingSignal;
  balance: AccountBalance | null;
  onClose: () => void;
  onExecute: (signalId: number, quantity: number) => void;
  isLoading: boolean;
}

function ExecuteModal({ signal, balance, onClose, onExecute, isLoading }: ExecuteModalProps) {
  const [quantity, setQuantity] = useState(1);
  const entryPrice = signal.entry_price || signal.target_price || 0;
  const totalAmount = quantity * entryPrice;
  const maxQuantity = balance ? Math.floor((balance.available_amount ?? 0) / entryPrice) : 0;

  const riskAmount = signal.stop_loss
    ? quantity * Math.abs(entryPrice - signal.stop_loss)
    : 0;
  const potentialProfit = signal.target_price
    ? quantity * Math.abs(signal.target_price - entryPrice)
    : 0;
  const riskRewardRatio = riskAmount > 0 ? (potentialProfit / riskAmount).toFixed(2) : 'N/A';

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 w-full max-w-lg">
        <div className="flex justify-between items-start mb-4">
          <div>
            <h2 className="text-xl font-bold text-gray-900">시그널 실행</h2>
            <p className="text-sm text-gray-500">{signal.symbol}</p>
          </div>
          <span
            className={`px-3 py-1 rounded-full text-sm font-bold ${
              signal.signal_type === 'buy'
                ? 'bg-green-100 text-green-800'
                : 'bg-red-100 text-red-800'
            }`}
          >
            {signal.signal_type === 'buy' ? '매수' : '매도'}
          </span>
        </div>

        {/* Signal Details */}
        <div className="bg-gray-50 rounded-lg p-4 mb-4">
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div>
              <span className="text-gray-500">진입가</span>
              <p className="font-semibold">{entryPrice.toLocaleString()}원</p>
            </div>
            <div>
              <span className="text-gray-500">목표가</span>
              <p className="font-semibold text-green-600">
                {signal.target_price?.toLocaleString() || '-'}원
              </p>
            </div>
            <div>
              <span className="text-gray-500">손절가</span>
              <p className="font-semibold text-red-600">
                {signal.stop_loss?.toLocaleString() || '-'}원
              </p>
            </div>
            <div>
              <span className="text-gray-500">신호 강도</span>
              <p className="font-semibold">{signal.strength}%</p>
            </div>
          </div>
          <div className="mt-3 pt-3 border-t">
            <p className="text-sm text-gray-600">{signal.reason}</p>
          </div>
        </div>

        {/* Order Form */}
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              수량
            </label>
            <div className="flex items-center space-x-2">
              <input
                type="number"
                min={1}
                max={maxQuantity}
                value={quantity}
                onChange={(e) => setQuantity(Math.max(1, parseInt(e.target.value) || 1))}
                className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:ring-primary-500 focus:border-primary-500"
              />
              <button
                onClick={() => setQuantity(Math.max(1, Math.floor(maxQuantity * 0.1)))}
                className="px-3 py-2 bg-gray-100 text-gray-700 rounded-md text-sm hover:bg-gray-200"
              >
                10%
              </button>
              <button
                onClick={() => setQuantity(Math.max(1, Math.floor(maxQuantity * 0.25)))}
                className="px-3 py-2 bg-gray-100 text-gray-700 rounded-md text-sm hover:bg-gray-200"
              >
                25%
              </button>
              <button
                onClick={() => setQuantity(Math.max(1, Math.floor(maxQuantity * 0.5)))}
                className="px-3 py-2 bg-gray-100 text-gray-700 rounded-md text-sm hover:bg-gray-200"
              >
                50%
              </button>
            </div>
            <p className="text-xs text-gray-500 mt-1">
              최대 주문 가능: {maxQuantity.toLocaleString()}주
            </p>
          </div>

          {/* Order Summary */}
          <div className="bg-blue-50 rounded-lg p-4">
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-600">주문 금액</span>
                <span className="font-semibold">{totalAmount.toLocaleString()}원</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">예상 손실 (손절 시)</span>
                <span className="font-semibold text-red-600">
                  -{riskAmount.toLocaleString()}원
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">예상 수익 (목표가 도달)</span>
                <span className="font-semibold text-green-600">
                  +{potentialProfit.toLocaleString()}원
                </span>
              </div>
              <div className="flex justify-between pt-2 border-t">
                <span className="text-gray-600">위험/보상 비율</span>
                <span className="font-bold">{riskRewardRatio}</span>
              </div>
            </div>
          </div>

          {/* Risk Warning */}
          {signal.risk_level === 'high' && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-3">
              <div className="flex items-center">
                <svg className="w-5 h-5 text-red-600 mr-2" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
                <span className="text-sm text-red-800 font-medium">
                  고위험 시그널입니다. 신중하게 결정하세요.
                </span>
              </div>
            </div>
          )}

          {/* Balance Info */}
          {balance && (
            <div className="text-sm text-gray-500">
              사용 가능 잔고: {(balance.available_amount ?? 0).toLocaleString()}원
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex justify-end space-x-3 mt-6">
          <button
            onClick={onClose}
            className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg"
            disabled={isLoading}
          >
            취소
          </button>
          <button
            onClick={() => onExecute(signal.id, quantity)}
            disabled={isLoading || totalAmount > (balance?.available_amount ?? 0)}
            className={`px-6 py-2 text-white rounded-lg font-medium ${
              signal.signal_type === 'buy'
                ? 'bg-green-600 hover:bg-green-700 disabled:bg-green-300'
                : 'bg-red-600 hover:bg-red-700 disabled:bg-red-300'
            }`}
          >
            {isLoading ? (
              <span className="flex items-center">
                <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                처리 중...
              </span>
            ) : (
              signal.signal_type === 'buy' ? '매수 실행' : '매도 실행'
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function TradingSignals() {
  const queryClient = useQueryClient();
  const [selectedSignal, setSelectedSignal] = useState<TradingSignal | null>(null);
  const [filter, setFilter] = useState<'all' | 'buy' | 'sell' | 'pending'>('pending');
  const [wsConnected, setWsConnected] = useState(false);

  // Fetch pending signals
  const { data: pendingSignals, isLoading: pendingLoading } = useQuery<TradingSignal[]>({
    queryKey: ['signals', 'pending'],
    queryFn: () => tradingApi.getPendingSignals(50),
    refetchInterval: 30000,
  });

  // Fetch all signals
  const { data: allSignals } = useQuery<TradingSignal[]>({
    queryKey: ['signals', 'all'],
    queryFn: () => tradingApi.getSignals({ limit: 100 }),
  });

  // Fetch signal stats
  const { data: signalStats } = useQuery<SignalStats>({
    queryKey: ['signals', 'stats'],
    queryFn: () => analysisApi.getSignalsStats(),
  });

  // Fetch account balance
  const { data: accountBalance } = useQuery<AccountBalance>({
    queryKey: ['account', 'balance'],
    queryFn: () => tradingApi.getAccountBalance(),
  });

  // Execute signal mutation
  const executeMutation = useMutation({
    mutationFn: ({ signalId, quantity }: { signalId: number; quantity: number }) =>
      tradingApi.executeSignal(signalId, quantity),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['signals'] });
      queryClient.invalidateQueries({ queryKey: ['account'] });
      queryClient.invalidateQueries({ queryKey: ['orders'] });
      setSelectedSignal(null);
    },
  });

  // WebSocket connection
  useEffect(() => {
    const ws = tradingWebSocket.connect();

    ws.onopen = () => {
      setWsConnected(true);
      tradingWebSocket.ping(ws);
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'new_signal') {
        queryClient.invalidateQueries({ queryKey: ['signals'] });
      } else if (data.type === 'signal_executed') {
        queryClient.invalidateQueries({ queryKey: ['signals'] });
        queryClient.invalidateQueries({ queryKey: ['account'] });
      } else if (data.type === 'trading') {
        queryClient.invalidateQueries({ queryKey: ['signals'] });
        queryClient.invalidateQueries({ queryKey: ['account'] });
        queryClient.invalidateQueries({ queryKey: ['orders'] });
      }
    };

    ws.onclose = () => setWsConnected(false);
    ws.onerror = () => setWsConnected(false);

    const pingInterval = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        tradingWebSocket.ping(ws);
      }
    }, 30000);

    return () => {
      clearInterval(pingInterval);
      ws.close();
    };
  }, [queryClient]);

  const handleExecute = useCallback((signalId: number, quantity: number) => {
    executeMutation.mutate({ signalId, quantity });
  }, [executeMutation]);

  // Filter signals
  const displaySignals = filter === 'pending'
    ? pendingSignals || []
    : (allSignals || []).filter((s) => {
        if (filter === 'all') return true;
        return s.signal_type === filter;
      });

  const getRiskBadgeClass = (risk: string) => {
    switch (risk) {
      case 'low': return 'bg-green-100 text-green-700';
      case 'medium': return 'bg-yellow-100 text-yellow-700';
      case 'high': return 'bg-red-100 text-red-700';
      default: return 'bg-gray-100 text-gray-700';
    }
  };

  const getHorizonLabel = (horizon: string) => {
    switch (horizon) {
      case 'short': return '단기';
      case 'medium': return '중기';
      case 'long': return '장기';
      default: return horizon;
    }
  };

  const formatTimeAgo = (dateStr: string) => {
    const now = new Date();
    const date = new Date(dateStr);
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 1) return '방금';
    if (diffMins < 60) return `${diffMins}분 전`;
    if (diffHours < 24) return `${diffHours}시간 전`;
    return `${diffDays}일 전`;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">AI 매매 시그널</h1>
          <p className="text-sm text-gray-500 mt-1">
            AI 에이전트가 생성한 매매 신호를 검토하고 실행하세요
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <span className={`flex items-center text-sm ${wsConnected ? 'text-green-600' : 'text-gray-400'}`}>
            <span className={`w-2 h-2 rounded-full mr-2 ${wsConnected ? 'bg-green-500' : 'bg-gray-400'}`} />
            {wsConnected ? '실시간 연결' : '연결 끊김'}
          </span>
        </div>
      </div>

      {/* Stats Cards */}
      {signalStats && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <div className="bg-white rounded-lg shadow p-4">
            <p className="text-sm text-gray-500">전체 시그널</p>
            <p className="text-2xl font-bold text-gray-900">{signalStats.total}</p>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <p className="text-sm text-gray-500">대기 중</p>
            <p className="text-2xl font-bold text-yellow-600">{signalStats.pending}</p>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <p className="text-sm text-gray-500">실행됨</p>
            <p className="text-2xl font-bold text-blue-600">{signalStats.executed}</p>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <p className="text-sm text-gray-500">성공률</p>
            <p className="text-2xl font-bold text-green-600">
              {signalStats.success_rate?.toFixed(1) || 0}%
            </p>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <p className="text-sm text-gray-500">평균 수익률</p>
            <p className={`text-2xl font-bold ${signalStats.avg_return >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {signalStats.avg_return >= 0 ? '+' : ''}{signalStats.avg_return?.toFixed(2) || 0}%
            </p>
          </div>
        </div>
      )}

      {/* Account Balance */}
      {accountBalance && (
        <div className="bg-gradient-to-r from-primary-600 to-primary-800 rounded-lg shadow-lg p-6 text-white">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            <div>
              <p className="text-primary-200 text-sm">예수금</p>
              <p className="text-2xl font-bold">{(accountBalance.total_deposit ?? 0).toLocaleString()}원</p>
            </div>
            <div>
              <p className="text-primary-200 text-sm">주문가능</p>
              <p className="text-2xl font-bold">{(accountBalance.available_amount ?? 0).toLocaleString()}원</p>
            </div>
            <div>
              <p className="text-primary-200 text-sm">매입금액</p>
              <p className="text-2xl font-bold">{(accountBalance.total_purchase ?? 0).toLocaleString()}원</p>
            </div>
            <div>
              <p className="text-primary-200 text-sm">평가손익</p>
              <p className={`text-2xl font-bold ${(accountBalance.total_profit_loss ?? 0) >= 0 ? 'text-green-300' : 'text-red-300'}`}>
                {(accountBalance.total_profit_loss ?? 0) >= 0 ? '+' : ''}{(accountBalance.total_profit_loss ?? 0).toLocaleString()}원
                <span className="text-sm ml-1">
                  ({(accountBalance.profit_rate ?? 0) >= 0 ? '+' : ''}{(accountBalance.profit_rate ?? 0).toFixed(2)}%)
                </span>
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Filter Tabs */}
      <div className="flex space-x-2 border-b">
        {[
          { key: 'pending', label: '대기 중', count: signalStats?.pending },
          { key: 'buy', label: '매수', count: signalStats?.by_type?.buy },
          { key: 'sell', label: '매도', count: signalStats?.by_type?.sell },
          { key: 'all', label: '전체', count: signalStats?.total },
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => setFilter(tab.key as typeof filter)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
              filter === tab.key
                ? 'border-primary-600 text-primary-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            {tab.label}
            {tab.count !== undefined && (
              <span className="ml-2 px-2 py-0.5 bg-gray-100 text-gray-600 rounded-full text-xs">
                {tab.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Signals List */}
      <div className="bg-white rounded-lg shadow">
        {pendingLoading ? (
          <div className="flex items-center justify-center py-12">
            <svg className="animate-spin h-8 w-8 text-primary-600" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
            </svg>
          </div>
        ) : displaySignals.length === 0 ? (
          <div className="text-center py-12 text-gray-500">
            <svg className="w-12 h-12 mx-auto mb-4 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
            <p>시그널이 없습니다</p>
          </div>
        ) : (
          <div className="divide-y">
            {displaySignals.map((signal) => (
              <div
                key={signal.id}
                className={`p-4 hover:bg-gray-50 transition-colors ${signal.executed ? 'opacity-60' : ''}`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center space-x-3">
                      <span
                        className={`px-3 py-1 rounded-full text-sm font-bold ${
                          signal.signal_type === 'buy'
                            ? 'bg-green-100 text-green-800'
                            : signal.signal_type === 'sell'
                            ? 'bg-red-100 text-red-800'
                            : 'bg-gray-100 text-gray-800'
                        }`}
                      >
                        {signal.signal_type === 'buy' ? '매수' : signal.signal_type === 'sell' ? '매도' : '보유'}
                      </span>
                      <h3 className="text-lg font-bold text-gray-900">{signal.symbol}</h3>
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${getRiskBadgeClass(signal.risk_level)}`}>
                        {signal.risk_level === 'low' ? '저위험' : signal.risk_level === 'medium' ? '중위험' : '고위험'}
                      </span>
                      <span className="text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded">
                        {getHorizonLabel(signal.time_horizon)}
                      </span>
                    </div>

                    <p className="text-gray-600 mt-2">{signal.reason}</p>

                    <div className="flex items-center space-x-6 mt-3 text-sm">
                      <div>
                        <span className="text-gray-500">진입가:</span>
                        <span className="ml-1 font-medium">
                          {signal.entry_price?.toLocaleString() || '-'}원
                        </span>
                      </div>
                      <div>
                        <span className="text-gray-500">목표가:</span>
                        <span className="ml-1 font-medium text-green-600">
                          {signal.target_price?.toLocaleString() || '-'}원
                        </span>
                      </div>
                      <div>
                        <span className="text-gray-500">손절가:</span>
                        <span className="ml-1 font-medium text-red-600">
                          {signal.stop_loss?.toLocaleString() || '-'}원
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center space-x-4 mt-3 text-xs text-gray-500">
                      <span>신호 강도: {signal.strength}%</span>
                      <span>신뢰도: {signal.confidence}%</span>
                      <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium ${
                        signal.source_agent === 'news'
                          ? 'bg-blue-100 text-blue-700'
                          : signal.source_agent === 'quant'
                          ? 'bg-purple-100 text-purple-700'
                          : 'bg-gray-100 text-gray-600'
                      }`}>
                        {signal.source_agent === 'news' ? '📰 뉴스' : signal.source_agent === 'quant' ? '📊 퀀트' : signal.source_agent}
                      </span>
                      <span>{formatTimeAgo(signal.created_at)}</span>
                    </div>
                  </div>

                  <div className="ml-4 flex flex-col items-end space-y-2">
                    {/* Strength Indicator */}
                    <div className="w-24">
                      <div className="flex justify-between text-xs mb-1">
                        <span className="text-gray-500">강도</span>
                        <span className="font-medium">{signal.strength}%</span>
                      </div>
                      <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all ${
                            signal.strength >= 70
                              ? 'bg-green-500'
                              : signal.strength >= 40
                              ? 'bg-yellow-500'
                              : 'bg-red-500'
                          }`}
                          style={{ width: `${signal.strength}%` }}
                        />
                      </div>
                    </div>

                    {/* Execute Button */}
                    {!signal.executed && signal.signal_type !== 'hold' && (
                      <button
                        onClick={() => setSelectedSignal(signal)}
                        className={`px-4 py-2 rounded-lg text-sm font-medium text-white transition-colors ${
                          signal.signal_type === 'buy'
                            ? 'bg-green-600 hover:bg-green-700'
                            : 'bg-red-600 hover:bg-red-700'
                        }`}
                      >
                        {signal.signal_type === 'buy' ? '매수 실행' : '매도 실행'}
                      </button>
                    )}

                    {signal.executed && (
                      <span className="px-3 py-1 bg-blue-100 text-blue-700 rounded-full text-xs font-medium">
                        실행됨
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Execute Modal */}
      {selectedSignal && (
        <ExecuteModal
          signal={selectedSignal}
          balance={accountBalance || null}
          onClose={() => setSelectedSignal(null)}
          onExecute={handleExecute}
          isLoading={executeMutation.isPending}
        />
      )}
    </div>
  );
}

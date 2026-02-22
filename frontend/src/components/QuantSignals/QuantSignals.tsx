import { useState, useEffect, useCallback } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { quantSignalsApi, signalsWebSocket } from '../../services/api';

// ============ Types ============

interface TriggerResult {
  trigger_id: string;
  name: string;
  signal: 'bullish' | 'bearish' | 'neutral';
  strength: 'strong' | 'moderate' | 'weak' | 'none';
  score: number;
  details: string;
  values: Record<string, number | string>;
}

interface SignalResult {
  id: string;
  symbol: string;
  company_name: string;
  indicators: Record<string, unknown>;
  triggers: TriggerResult[];
  composite_score: number;
  bullish_count: number;
  bearish_count: number;
  neutral_count: number;
  action: string;
  scanned_at: string;
}

interface SignalResultsResponse {
  results: SignalResult[];
  total: number;
}

// ============ Helper Functions ============

function getActionBadge(action: string) {
  const map: Record<string, { label: string; className: string }> = {
    strong_buy: { label: '강력 매수', className: 'bg-green-600 text-white' },
    buy: { label: '매수', className: 'bg-green-100 text-green-800' },
    hold: { label: '보유', className: 'bg-gray-100 text-gray-700' },
    sell: { label: '매도', className: 'bg-red-100 text-red-800' },
    strong_sell: { label: '강력 매도', className: 'bg-red-600 text-white' },
  };
  return map[action] || { label: action, className: 'bg-gray-100 text-gray-700' };
}

function getSignalBadge(signal: string) {
  switch (signal) {
    case 'bullish': return { label: '매수', className: 'bg-green-100 text-green-700' };
    case 'bearish': return { label: '매도', className: 'bg-red-100 text-red-700' };
    default: return { label: '중립', className: 'bg-gray-100 text-gray-500' };
  }
}

function getStrengthBadge(strength: string) {
  switch (strength) {
    case 'strong': return { label: '강', className: 'bg-purple-100 text-purple-700' };
    case 'moderate': return { label: '중', className: 'bg-blue-100 text-blue-700' };
    case 'weak': return { label: '약', className: 'bg-gray-100 text-gray-500' };
    default: return { label: '-', className: 'bg-gray-50 text-gray-400' };
  }
}

function getScoreColor(score: number) {
  if (score >= 70) return 'bg-green-500';
  if (score >= 50) return 'bg-blue-500';
  if (score >= 30) return 'bg-yellow-500';
  return 'bg-red-500';
}

function formatTime(dateStr: string) {
  const date = new Date(dateStr);
  return date.toLocaleString('ko-KR', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function formatValue(value: number | string): string {
  if (typeof value === 'string') return value;
  if (Math.abs(value) >= 1_000_000_000_000) return `${(value / 1_000_000_000_000).toFixed(1)}조`;
  if (Math.abs(value) >= 100_000_000) return `${(value / 100_000_000).toFixed(1)}억`;
  if (Math.abs(value) >= 10_000) return `${(value / 10_000).toFixed(1)}만`;
  if (Number.isInteger(value)) return value.toLocaleString();
  return value.toFixed(2);
}

// ============ Sub-Components ============

function TriggerDetail({ trigger }: { trigger: TriggerResult }) {
  const signalBadge = getSignalBadge(trigger.signal);
  const strengthBadge = getStrengthBadge(trigger.strength);

  return (
    <div className="border border-gray-100 rounded-lg p-3 hover:bg-gray-50 transition-colors">
      <div className="flex items-center justify-between mb-1.5">
        <div className="flex items-center space-x-2">
          <span className="text-xs font-mono text-gray-400">{trigger.trigger_id}</span>
          <span className="font-medium text-sm text-gray-900">{trigger.name}</span>
        </div>
        <div className="flex items-center space-x-1.5">
          <span className={`px-2 py-0.5 rounded text-xs font-medium ${signalBadge.className}`}>
            {signalBadge.label}
          </span>
          <span className={`px-2 py-0.5 rounded text-xs font-medium ${strengthBadge.className}`}>
            {strengthBadge.label}
          </span>
          <span className="text-xs font-bold text-gray-700 ml-1">{trigger.score > 0 ? '+' : ''}{trigger.score}</span>
        </div>
      </div>

      {/* Details: 판정 근거 */}
      {trigger.details && (
        <p className="text-sm text-gray-600 mt-1 leading-relaxed">{trigger.details}</p>
      )}

      {/* Values: 참고 수치 */}
      {trigger.values && Object.keys(trigger.values).length > 0 && (
        <div className="mt-2 flex flex-wrap gap-2">
          {Object.entries(trigger.values).map(([key, val]) => (
            <span
              key={key}
              className="inline-flex items-center space-x-1 px-2 py-0.5 bg-indigo-50 text-indigo-700 rounded text-xs"
            >
              <span className="font-medium">{key}:</span>
              <span>{formatValue(val)}</span>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function SignalCard({ result }: { result: SignalResult }) {
  const [expanded, setExpanded] = useState(false);
  const [showNeutral, setShowNeutral] = useState(false);
  const actionBadge = getActionBadge(result.action);

  const activeTriggers = result.triggers.filter(t => t.signal !== 'neutral');
  const neutralTriggers = result.triggers.filter(t => t.signal === 'neutral');
  const bullishTriggers = activeTriggers.filter(t => t.signal === 'bullish');
  const bearishTriggers = activeTriggers.filter(t => t.signal === 'bearish');

  return (
    <div className="bg-white rounded-lg shadow hover:shadow-md transition-shadow">
      {/* Card Header */}
      <div
        className="p-4 cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <div className="flex items-center space-x-3">
              <h3 className="text-lg font-bold text-gray-900">{result.company_name}</h3>
              <span className="text-sm text-gray-400 font-mono">{result.symbol}</span>
              <span className={`px-3 py-0.5 rounded-full text-xs font-bold ${actionBadge.className}`}>
                {actionBadge.label}
              </span>
            </div>

            {/* Score gauge */}
            <div className="mt-3 flex items-center space-x-3">
              <div className="flex-1 max-w-xs">
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-gray-500">종합점수</span>
                  <span className="font-bold text-gray-700">{result.composite_score}</span>
                </div>
                <div className="h-2.5 bg-gray-200 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all ${getScoreColor(result.composite_score)}`}
                    style={{ width: `${result.composite_score}%` }}
                  />
                </div>
              </div>

              {/* Trigger summary counts */}
              <div className="flex items-center space-x-2 text-xs">
                <span className="px-2 py-1 bg-green-50 text-green-700 rounded font-medium">
                  매수 {result.bullish_count}
                </span>
                <span className="px-2 py-1 bg-red-50 text-red-700 rounded font-medium">
                  매도 {result.bearish_count}
                </span>
                <span className="px-2 py-1 bg-gray-50 text-gray-500 rounded font-medium">
                  중립 {result.neutral_count}
                </span>
              </div>
            </div>

            <div className="mt-2 text-xs text-gray-400">
              {formatTime(result.scanned_at)}
            </div>
          </div>

          {/* Expand arrow */}
          <div className="ml-3 pt-1">
            <svg
              className={`w-5 h-5 text-gray-400 transition-transform ${expanded ? 'rotate-180' : ''}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </div>
        </div>
      </div>

      {/* Expanded Trigger Details */}
      {expanded && (
        <div className="border-t px-4 pb-4 pt-3 space-y-3">
          {/* Active triggers (bullish + bearish) */}
          {activeTriggers.length > 0 ? (
            <>
              {bullishTriggers.length > 0 && (
                <div>
                  <h4 className="text-xs font-semibold text-green-700 uppercase tracking-wider mb-2">
                    매수 트리거 ({bullishTriggers.length})
                  </h4>
                  <div className="space-y-2">
                    {bullishTriggers.map(t => (
                      <TriggerDetail key={t.trigger_id} trigger={t} />
                    ))}
                  </div>
                </div>
              )}

              {bearishTriggers.length > 0 && (
                <div>
                  <h4 className="text-xs font-semibold text-red-700 uppercase tracking-wider mb-2">
                    매도 트리거 ({bearishTriggers.length})
                  </h4>
                  <div className="space-y-2">
                    {bearishTriggers.map(t => (
                      <TriggerDetail key={t.trigger_id} trigger={t} />
                    ))}
                  </div>
                </div>
              )}
            </>
          ) : (
            <p className="text-sm text-gray-500 text-center py-4">활성 트리거 없음</p>
          )}

          {/* Neutral triggers (collapsed by default) */}
          {neutralTriggers.length > 0 && (
            <div>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setShowNeutral(!showNeutral);
                }}
                className="text-xs text-gray-500 hover:text-gray-700 font-medium flex items-center space-x-1"
              >
                <svg
                  className={`w-3 h-3 transition-transform ${showNeutral ? 'rotate-90' : ''}`}
                  fill="currentColor"
                  viewBox="0 0 20 20"
                >
                  <path d="M6 6L14 10L6 14V6Z" />
                </svg>
                <span>중립 {neutralTriggers.length}개 보기</span>
              </button>
              {showNeutral && (
                <div className="mt-2 space-y-2">
                  {neutralTriggers.map(t => (
                    <TriggerDetail key={t.trigger_id} trigger={t} />
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ============ Main Component ============

export default function QuantSignals() {
  const queryClient = useQueryClient();
  const [scanSymbol, setScanSymbol] = useState('');
  const [scanLoading, setScanLoading] = useState(false);
  const [scanError, setScanError] = useState('');
  const [wsConnected, setWsConnected] = useState(false);

  // Fetch recent results
  const { data: resultsData, isLoading } = useQuery<SignalResultsResponse>({
    queryKey: ['quant-signals', 'results'],
    queryFn: () => quantSignalsApi.getResults(50),
    refetchInterval: 60000,
  });

  // Fetch scanner status
  const { data: status } = useQuery({
    queryKey: ['quant-signals', 'status'],
    queryFn: () => quantSignalsApi.getStatus(),
    refetchInterval: 30000,
  });

  const results = resultsData?.results || [];

  // Stats
  const totalScanned = results.length;
  const buySignals = results.filter(r => r.action === 'buy' || r.action === 'strong_buy').length;
  const sellSignals = results.filter(r => r.action === 'sell' || r.action === 'strong_sell').length;
  const avgScore = totalScanned > 0
    ? Math.round(results.reduce((sum, r) => sum + r.composite_score, 0) / totalScanned)
    : 0;

  // WebSocket
  useEffect(() => {
    let ws: WebSocket | null = null;
    let pingInterval: ReturnType<typeof setInterval>;

    try {
      ws = signalsWebSocket.connect();

      ws.onopen = () => {
        setWsConnected(true);
      };

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'signal_result' || data.type === 'scan_update') {
          queryClient.invalidateQueries({ queryKey: ['quant-signals'] });
        }
      };

      ws.onclose = () => setWsConnected(false);
      ws.onerror = () => setWsConnected(false);

      pingInterval = setInterval(() => {
        if (ws?.readyState === WebSocket.OPEN) {
          signalsWebSocket.ping(ws);
        }
      }, 30000);
    } catch {
      setWsConnected(false);
    }

    return () => {
      clearInterval(pingInterval);
      ws?.close();
    };
  }, [queryClient]);

  // Scan single stock
  const handleScan = useCallback(async () => {
    const symbol = scanSymbol.trim();
    if (!symbol) return;

    if (symbol.length !== 6 || !/^\d{6}$/.test(symbol)) {
      setScanError('6자리 숫자 종목코드를 입력하세요');
      return;
    }

    setScanLoading(true);
    setScanError('');
    try {
      await quantSignalsApi.scanStock(symbol);
      queryClient.invalidateQueries({ queryKey: ['quant-signals'] });
      setScanSymbol('');
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      setScanError(error.response?.data?.detail || '스캔 실패');
    } finally {
      setScanLoading(false);
    }
  }, [scanSymbol, queryClient]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">퀀트 시그널</h1>
          <p className="text-sm text-gray-500 mt-1">
            42개 트리거 기반 종합 매매 판단 — 트리거별 판정 근거와 수치를 확인하세요
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <span className={`flex items-center text-sm ${wsConnected ? 'text-green-600' : 'text-gray-400'}`}>
            <span className={`w-2 h-2 rounded-full mr-2 ${wsConnected ? 'bg-green-500 animate-pulse' : 'bg-gray-300'}`} />
            {wsConnected ? '실시간 연결' : '폴링 모드'}
          </span>
          {status?.scan_count !== undefined && (
            <span className="text-xs text-gray-400">
              총 스캔: {status.scan_count}회
            </span>
          )}
        </div>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-500">스캔 종목</p>
          <p className="text-2xl font-bold text-gray-900">{totalScanned}</p>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-500">매수 시그널</p>
          <p className="text-2xl font-bold text-green-600">{buySignals}</p>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-500">매도 시그널</p>
          <p className="text-2xl font-bold text-red-600">{sellSignals}</p>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-500">평균 종합점수</p>
          <p className="text-2xl font-bold text-indigo-600">{avgScore}</p>
        </div>
      </div>

      {/* Scan Input */}
      <div className="bg-white rounded-lg shadow p-4">
        <div className="flex items-center space-x-3">
          <input
            type="text"
            value={scanSymbol}
            onChange={(e) => {
              setScanSymbol(e.target.value);
              setScanError('');
            }}
            onKeyDown={(e) => e.key === 'Enter' && handleScan()}
            placeholder="종목코드 (예: 005930)"
            maxLength={6}
            className="flex-1 max-w-xs px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 text-sm font-mono"
          />
          <button
            onClick={handleScan}
            disabled={scanLoading || !scanSymbol.trim()}
            className="px-5 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:bg-indigo-300 transition-colors flex items-center space-x-2"
          >
            {scanLoading ? (
              <>
                <svg className="animate-spin h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                <span>스캔 중...</span>
              </>
            ) : (
              <>
                <span>🔬</span>
                <span>스캔</span>
              </>
            )}
          </button>
        </div>
        {scanError && (
          <p className="text-sm text-red-600 mt-2">{scanError}</p>
        )}
      </div>

      {/* Signal Cards */}
      {isLoading ? (
        <div className="flex items-center justify-center py-16">
          <svg className="animate-spin h-8 w-8 text-indigo-600" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
        </div>
      ) : results.length === 0 ? (
        <div className="bg-white rounded-lg shadow text-center py-16 text-gray-500">
          <span className="text-5xl block mb-4">🔬</span>
          <p className="text-lg font-medium">스캔 결과가 없습니다</p>
          <p className="text-sm mt-1">종목코드를 입력하여 퀀트 시그널을 확인하세요</p>
        </div>
      ) : (
        <div className="space-y-3">
          {results.map((result) => (
            <SignalCard key={result.id} result={result} />
          ))}
        </div>
      )}
    </div>
  );
}

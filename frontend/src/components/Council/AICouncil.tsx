import { useState, useEffect, useRef, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { councilApi, councilWebSocket } from '../../services/api';

interface CouncilMessage {
  id: string;
  role: string;
  speaker: string;
  content: string;
  data: Record<string, unknown> | null;
  timestamp: string;
}

interface InvestmentSignal {
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

interface CouncilMeeting {
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

interface CouncilStatus {
  running: boolean;
  auto_execute: boolean;
  council_threshold: number;
  pending_signals: number;
  total_meetings: number;
  daily_trades: number;
  monitor_running: boolean;
}

interface CouncilConfig {
  council_threshold: number;
  sell_threshold: number;
  auto_execute: boolean;
  max_position_per_stock: number;
  poll_interval: number;
}

function getSpeakerIcon(role: string): string {
  switch (role) {
    case 'gemini_judge': return '🔔';
    case 'gpt_quant': return '📊';
    case 'claude_fundamental': return '📈';
    case 'moderator': return '⚖️';
    default: return '💬';
  }
}

function getSpeakerColor(role: string): string {
  switch (role) {
    case 'gemini_judge': return 'bg-blue-50 border-blue-200';
    case 'gpt_quant': return 'bg-green-50 border-green-200';
    case 'claude_fundamental': return 'bg-purple-50 border-purple-200';
    case 'moderator': return 'bg-yellow-50 border-yellow-200';
    default: return 'bg-gray-50 border-gray-200';
  }
}

function MessageBubble({ message }: { message: CouncilMessage }) {
  return (
    <div className={`p-4 rounded-lg border ${getSpeakerColor(message.role)} mb-3`}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center space-x-2">
          <span className="text-xl">{getSpeakerIcon(message.role)}</span>
          <span className="font-semibold text-gray-800">{message.speaker}</span>
        </div>
        <span className="text-xs text-gray-500">
          {new Date(message.timestamp).toLocaleTimeString()}
        </span>
      </div>
      <div className="text-gray-700 whitespace-pre-wrap text-sm leading-relaxed">
        {message.content}
      </div>
    </div>
  );
}

function SignalCard({
  signal,
  onApprove,
  onReject,
  onExecute,
  isLoading
}: {
  signal: InvestmentSignal;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
  onExecute: (id: string) => void;
  isLoading: boolean;
}) {
  const statusColors: Record<string, string> = {
    pending: 'bg-yellow-100 text-yellow-800',
    approved: 'bg-blue-100 text-blue-800',
    rejected: 'bg-red-100 text-red-800',
    executed: 'bg-green-100 text-green-800',
    auto_executed: 'bg-green-100 text-green-800',
  };

  const statusLabels: Record<string, string> = {
    pending: '승인 대기',
    approved: '승인됨',
    rejected: '거부됨',
    executed: '체결됨',
    auto_executed: '자동 체결',
  };

  return (
    <div className="bg-white rounded-lg border shadow-sm p-4">
      <div className="flex justify-between items-start mb-3">
        <div>
          <div className="flex items-center space-x-2">
            <span className={`px-2 py-1 rounded text-xs font-bold ${
              signal.action === 'BUY' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
            }`}>
              {signal.action === 'BUY' ? '매수' : signal.action === 'SELL' ? '매도' : '보유'}
            </span>
            <h3 className="font-bold text-gray-900">{signal.company_name}</h3>
            <span className="text-gray-500 text-sm">({signal.symbol})</span>
          </div>
        </div>
        <span className={`px-2 py-1 rounded text-xs font-medium ${statusColors[signal.status] || 'bg-gray-100'}`}>
          {statusLabels[signal.status] || signal.status}
        </span>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3 text-sm">
        <div>
          <span className="text-gray-500">투자 비율</span>
          <p className="font-semibold">{signal.allocation_percent.toFixed(1)}%</p>
        </div>
        <div>
          <span className="text-gray-500">제안 금액</span>
          <p className="font-semibold">{signal.suggested_amount.toLocaleString()}원</p>
        </div>
        <div>
          <span className="text-gray-500">신뢰도</span>
          <p className="font-semibold">{(signal.confidence * 100).toFixed(0)}%</p>
        </div>
        <div>
          <span className="text-gray-500">퀀트/펀더멘털</span>
          <p className="font-semibold">{signal.quant_score}/{signal.fundamental_score}</p>
        </div>
      </div>

      <div className="text-xs text-gray-600 mb-3 line-clamp-2">
        {signal.consensus_reason}
      </div>

      {signal.status === 'pending' && (
        <div className="flex space-x-2">
          <button
            onClick={() => onApprove(signal.id)}
            disabled={isLoading}
            className="flex-1 px-3 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            승인
          </button>
          <button
            onClick={() => onReject(signal.id)}
            disabled={isLoading}
            className="flex-1 px-3 py-2 bg-gray-200 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-300 disabled:opacity-50"
          >
            거부
          </button>
        </div>
      )}

      {signal.status === 'approved' && (
        <button
          onClick={() => onExecute(signal.id)}
          disabled={isLoading}
          className="w-full px-3 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 disabled:opacity-50"
        >
          체결 실행
        </button>
      )}
    </div>
  );
}

function MeetingViewer({ meeting }: { meeting: CouncilMeeting }) {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [meeting.messages]);

  return (
    <div className="bg-white rounded-lg border shadow-sm">
      <div className="p-4 border-b bg-gray-50">
        <div className="flex justify-between items-start">
          <div>
            <h3 className="font-bold text-gray-900">{meeting.company_name} ({meeting.symbol})</h3>
            <p className="text-sm text-gray-600 mt-1">{meeting.news_title}</p>
          </div>
          <div className="text-right">
            <span className={`px-2 py-1 rounded text-xs font-medium ${
              meeting.consensus_reached ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'
            }`}>
              {meeting.consensus_reached ? '합의 완료' : `라운드 ${meeting.current_round}/${meeting.max_rounds}`}
            </span>
            <p className="text-xs text-gray-500 mt-1">
              뉴스 점수: {meeting.news_score}/10
            </p>
          </div>
        </div>
      </div>

      <div className="p-4 max-h-[500px] overflow-y-auto">
        {meeting.messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        <div ref={messagesEndRef} />
      </div>

      {meeting.signal && (
        <div className="p-4 border-t bg-gray-50">
          <h4 className="font-semibold text-gray-800 mb-2">📌 투자 시그널</h4>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
            <div>
              <span className="text-gray-500">행동</span>
              <p className={`font-bold ${meeting.signal.action === 'BUY' ? 'text-green-600' : 'text-red-600'}`}>
                {meeting.signal.action === 'BUY' ? '매수' : meeting.signal.action === 'SELL' ? '매도' : '보유'}
              </p>
            </div>
            <div>
              <span className="text-gray-500">투자 비율</span>
              <p className="font-bold">{meeting.signal.allocation_percent.toFixed(1)}%</p>
            </div>
            <div>
              <span className="text-gray-500">제안 금액</span>
              <p className="font-bold">{meeting.signal.suggested_amount.toLocaleString()}원</p>
            </div>
            <div>
              <span className="text-gray-500">신뢰도</span>
              <p className="font-bold">{(meeting.signal.confidence * 100).toFixed(0)}%</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function ConfigPanel({
  config,
  onUpdate,
  isLoading
}: {
  config: CouncilConfig;
  onUpdate: (config: CouncilConfig) => void;
  isLoading: boolean;
}) {
  const [localConfig, setLocalConfig] = useState(config);

  useEffect(() => {
    setLocalConfig(config);
  }, [config]);

  return (
    <div className="bg-white rounded-lg border shadow-sm p-4">
      <h3 className="font-semibold text-gray-800 mb-4">⚙️ 회의 설정</h3>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm text-gray-600 mb-1">회의 소집 점수 (1-10)</label>
          <input
            type="number"
            min={1}
            max={10}
            value={localConfig.council_threshold}
            onChange={(e) => setLocalConfig({ ...localConfig, council_threshold: parseInt(e.target.value) })}
            className="w-full px-3 py-2 border rounded-lg text-sm"
          />
        </div>
        <div>
          <label className="block text-sm text-gray-600 mb-1">매도 기준 점수 (1-10)</label>
          <input
            type="number"
            min={1}
            max={10}
            value={localConfig.sell_threshold}
            onChange={(e) => setLocalConfig({ ...localConfig, sell_threshold: parseInt(e.target.value) })}
            className="w-full px-3 py-2 border rounded-lg text-sm"
          />
        </div>
        <div>
          <label className="block text-sm text-gray-600 mb-1">종목당 최대 금액</label>
          <input
            type="number"
            value={localConfig.max_position_per_stock}
            onChange={(e) => setLocalConfig({ ...localConfig, max_position_per_stock: parseInt(e.target.value) })}
            className="w-full px-3 py-2 border rounded-lg text-sm"
          />
        </div>
        <div>
          <label className="block text-sm text-gray-600 mb-1">뉴스 체크 주기 (초)</label>
          <input
            type="number"
            min={30}
            value={localConfig.poll_interval}
            onChange={(e) => setLocalConfig({ ...localConfig, poll_interval: parseInt(e.target.value) })}
            className="w-full px-3 py-2 border rounded-lg text-sm"
          />
        </div>
        <div className="col-span-2">
          <label className="flex items-center space-x-2">
            <input
              type="checkbox"
              checked={localConfig.auto_execute}
              onChange={(e) => setLocalConfig({ ...localConfig, auto_execute: e.target.checked })}
              className="rounded"
            />
            <span className="text-sm text-gray-700">자동 체결 활성화</span>
          </label>
          <p className="text-xs text-gray-500 mt-1">활성화 시 신뢰도 60% 이상 시그널이 자동 체결됩니다</p>
        </div>
      </div>
      <button
        onClick={() => onUpdate(localConfig)}
        disabled={isLoading}
        className="mt-4 w-full px-4 py-2 bg-primary-600 text-white rounded-lg text-sm font-medium hover:bg-primary-700 disabled:opacity-50"
      >
        설정 저장
      </button>
    </div>
  );
}

export default function AICouncil() {
  const queryClient = useQueryClient();
  const [wsConnected, setWsConnected] = useState(false);
  const [selectedMeeting, setSelectedMeeting] = useState<CouncilMeeting | null>(null);
  const [showConfig, setShowConfig] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  // Fetch status
  const { data: status } = useQuery<CouncilStatus>({
    queryKey: ['council', 'status'],
    queryFn: councilApi.getStatus,
    refetchInterval: 10000,
  });

  // Fetch pending signals
  const { data: pendingSignals } = useQuery<{ signals: InvestmentSignal[]; total: number }>({
    queryKey: ['council', 'signals', 'pending'],
    queryFn: councilApi.getPendingSignals,
  });

  // Fetch meetings
  const { data: meetings } = useQuery<{ meetings: CouncilMeeting[]; total: number }>({
    queryKey: ['council', 'meetings'],
    queryFn: () => councilApi.getMeetings(10),
  });

  // Start monitoring mutation
  const startMutation = useMutation({
    mutationFn: councilApi.start,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['council'] });
    },
  });

  // Stop monitoring mutation
  const stopMutation = useMutation({
    mutationFn: councilApi.stop,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['council'] });
    },
  });

  // Update config mutation
  const configMutation = useMutation({
    mutationFn: councilApi.updateConfig,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['council'] });
      setShowConfig(false);
    },
  });

  // Approve signal mutation
  const approveMutation = useMutation({
    mutationFn: councilApi.approveSignal,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['council', 'signals'] });
    },
  });

  // Reject signal mutation
  const rejectMutation = useMutation({
    mutationFn: councilApi.rejectSignal,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['council', 'signals'] });
    },
  });

  // Execute signal mutation
  const executeMutation = useMutation({
    mutationFn: councilApi.executeSignal,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['council', 'signals'] });
    },
  });

  // WebSocket connection
  const connectWebSocket = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = councilWebSocket.connect();
    wsRef.current = ws;

    ws.onopen = () => {
      setWsConnected(true);
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      if (data.type === 'meeting_update') {
        // Update selected meeting if it's the one being updated
        if (selectedMeeting?.id === data.meeting.id) {
          setSelectedMeeting(data.meeting);
        }
        queryClient.invalidateQueries({ queryKey: ['council', 'meetings'] });
      } else if (data.type === 'signal_created' || data.type === 'signal_approved' ||
                 data.type === 'signal_rejected' || data.type === 'signal_executed') {
        queryClient.invalidateQueries({ queryKey: ['council', 'signals'] });
      } else if (data.type === 'connected') {
        // Initial state from server
        queryClient.invalidateQueries({ queryKey: ['council'] });
      }
    };

    ws.onclose = () => {
      setWsConnected(false);
      // Reconnect after 3 seconds
      setTimeout(connectWebSocket, 3000);
    };

    ws.onerror = () => {
      setWsConnected(false);
    };
  }, [queryClient, selectedMeeting?.id]);

  useEffect(() => {
    connectWebSocket();

    const pingInterval = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        councilWebSocket.ping(wsRef.current);
      }
    }, 30000);

    return () => {
      clearInterval(pingInterval);
      wsRef.current?.close();
    };
  }, [connectWebSocket]);

  const defaultConfig: CouncilConfig = {
    council_threshold: status?.council_threshold || 7,
    sell_threshold: 3,
    auto_execute: status?.auto_execute || false,
    max_position_per_stock: 500000,
    poll_interval: 60,
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">🏛️ AI 투자 회의</h1>
          <p className="text-sm text-gray-500 mt-1">
            GPT, Claude, Gemini가 협업하여 투자 결정을 내립니다
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <span className={`flex items-center text-sm ${wsConnected ? 'text-green-600' : 'text-gray-400'}`}>
            <span className={`w-2 h-2 rounded-full mr-2 ${wsConnected ? 'bg-green-500 animate-pulse' : 'bg-gray-400'}`} />
            {wsConnected ? '실시간 연결' : '연결 끊김'}
          </span>
          <button
            onClick={() => setShowConfig(!showConfig)}
            className="px-3 py-2 text-gray-600 hover:bg-gray-100 rounded-lg"
          >
            ⚙️ 설정
          </button>
        </div>
      </div>

      {/* Status Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-500">상태</p>
          <p className={`text-lg font-bold ${status?.running ? 'text-green-600' : 'text-gray-400'}`}>
            {status?.running ? '🟢 실행 중' : '⭕ 중지됨'}
          </p>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-500">대기 시그널</p>
          <p className="text-2xl font-bold text-yellow-600">{status?.pending_signals || 0}</p>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-500">총 회의</p>
          <p className="text-2xl font-bold text-blue-600">{status?.total_meetings || 0}</p>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-500">오늘 거래</p>
          <p className="text-2xl font-bold text-green-600">{status?.daily_trades || 0}</p>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-500">자동 체결</p>
          <p className={`text-lg font-bold ${status?.auto_execute ? 'text-green-600' : 'text-gray-400'}`}>
            {status?.auto_execute ? '활성화' : '비활성화'}
          </p>
        </div>
      </div>

      {/* Control Buttons */}
      <div className="flex space-x-3">
        {!status?.running ? (
          <button
            onClick={() => startMutation.mutate()}
            disabled={startMutation.isPending}
            className="px-6 py-3 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 disabled:opacity-50"
          >
            {startMutation.isPending ? '시작 중...' : '🚀 모니터링 시작'}
          </button>
        ) : (
          <button
            onClick={() => stopMutation.mutate()}
            disabled={stopMutation.isPending}
            className="px-6 py-3 bg-red-600 text-white rounded-lg font-medium hover:bg-red-700 disabled:opacity-50"
          >
            {stopMutation.isPending ? '중지 중...' : '⏹️ 모니터링 중지'}
          </button>
        )}
      </div>

      {/* Config Panel */}
      {showConfig && (
        <ConfigPanel
          config={defaultConfig}
          onUpdate={(config) => configMutation.mutate(config)}
          isLoading={configMutation.isPending}
        />
      )}

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Pending Signals */}
        <div>
          <h2 className="text-lg font-semibold text-gray-800 mb-4">📋 대기 중인 시그널</h2>
          {pendingSignals?.signals && pendingSignals.signals.length > 0 ? (
            <div className="space-y-3">
              {pendingSignals.signals.map((signal) => (
                <SignalCard
                  key={signal.id}
                  signal={signal}
                  onApprove={(id) => approveMutation.mutate(id)}
                  onReject={(id) => rejectMutation.mutate(id)}
                  onExecute={(id) => executeMutation.mutate(id)}
                  isLoading={approveMutation.isPending || rejectMutation.isPending || executeMutation.isPending}
                />
              ))}
            </div>
          ) : (
            <div className="bg-white rounded-lg border p-8 text-center text-gray-500">
              <p>대기 중인 시그널이 없습니다</p>
              <p className="text-sm mt-1">AI 회의에서 새로운 시그널이 생성되면 여기에 표시됩니다</p>
            </div>
          )}
        </div>

        {/* Recent Meetings */}
        <div>
          <h2 className="text-lg font-semibold text-gray-800 mb-4">🏛️ 최근 회의</h2>
          {meetings?.meetings && meetings.meetings.length > 0 ? (
            <div className="space-y-2">
              {meetings.meetings.map((meeting) => (
                <div
                  key={meeting.id}
                  onClick={() => setSelectedMeeting(meeting)}
                  className={`bg-white rounded-lg border p-3 cursor-pointer hover:bg-gray-50 transition-colors ${
                    selectedMeeting?.id === meeting.id ? 'ring-2 ring-primary-500' : ''
                  }`}
                >
                  <div className="flex justify-between items-start">
                    <div>
                      <h4 className="font-semibold text-gray-900">{meeting.company_name}</h4>
                      <p className="text-xs text-gray-500 truncate max-w-xs">{meeting.news_title}</p>
                    </div>
                    <span className={`px-2 py-1 rounded text-xs ${
                      meeting.consensus_reached ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'
                    }`}>
                      {meeting.consensus_reached ? '완료' : '진행 중'}
                    </span>
                  </div>
                  <div className="flex items-center space-x-4 mt-2 text-xs text-gray-500">
                    <span>뉴스 점수: {meeting.news_score}/10</span>
                    <span>{meeting.messages.length}개 발언</span>
                    <span>{new Date(meeting.started_at).toLocaleTimeString()}</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="bg-white rounded-lg border p-8 text-center text-gray-500">
              <p>아직 회의가 없습니다</p>
              <p className="text-sm mt-1">모니터링을 시작하면 AI 회의가 자동으로 소집됩니다</p>
            </div>
          )}
        </div>
      </div>

      {/* Selected Meeting Detail */}
      {selectedMeeting && (
        <div>
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-lg font-semibold text-gray-800">📝 회의 상세</h2>
            <button
              onClick={() => setSelectedMeeting(null)}
              className="text-gray-500 hover:text-gray-700"
            >
              ✕ 닫기
            </button>
          </div>
          <MeetingViewer meeting={selectedMeeting} />
        </div>
      )}
    </div>
  );
}

import { useState, useEffect, useRef, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { councilApi, councilWebSocket } from '../../services/api';
import type { CouncilStatus, CouncilConfig, CouncilMeeting, InvestmentSignal } from './types';
import { AITeamIntroduction } from './AITeamIntroduction';
import { SignalCard } from './SignalCard';
import { MeetingViewer } from './MeetingViewer';
import { ConfigPanel } from './ConfigPanel';
import { AccountHoldingsPanel } from './AccountHoldingsPanel';

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

  // Mutations
  const startMutation = useMutation({
    mutationFn: councilApi.start,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['council'] }),
  });

  const stopMutation = useMutation({
    mutationFn: councilApi.stop,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['council'] }),
  });

  const configMutation = useMutation({
    mutationFn: councilApi.updateConfig,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['council'] });
      setShowConfig(false);
    },
  });

  const approveMutation = useMutation({
    mutationFn: councilApi.approveSignal,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['council', 'signals'] }),
  });

  const rejectMutation = useMutation({
    mutationFn: councilApi.rejectSignal,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['council', 'signals'] }),
  });

  const executeMutation = useMutation({
    mutationFn: councilApi.executeSignal,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['council', 'signals'] }),
  });

  // Test mutations
  const [testResult, setTestResult] = useState<Record<string, unknown> | null>(null);
  const [testLoading, setTestLoading] = useState(false);

  const handleTestAnalyze = async () => {
    setTestLoading(true);
    try {
      const result = await councilApi.testAnalyzeNews();
      setTestResult(result);
    } catch (error) {
      setTestResult({ error: String(error) });
    } finally {
      setTestLoading(false);
    }
  };

  const handleForceCouncil = async () => {
    setTestLoading(true);
    try {
      const result = await councilApi.testForceCouncil();
      setTestResult(result);
      queryClient.invalidateQueries({ queryKey: ['council'] });
    } catch (error) {
      setTestResult({ error: String(error) });
    } finally {
      setTestLoading(false);
    }
  };

  const handleMockCouncil = async () => {
    setTestLoading(true);
    try {
      const result = await councilApi.testMockCouncil('005930', '삼성전자');
      setTestResult(result);
      queryClient.invalidateQueries({ queryKey: ['council'] });
    } catch (error) {
      setTestResult({ error: String(error) });
    } finally {
      setTestLoading(false);
    }
  };

  // WebSocket connection
  const connectWebSocket = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = councilWebSocket.connect();
    wsRef.current = ws;

    ws.onopen = () => setWsConnected(true);

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      if (data.type === 'meeting_update') {
        if (selectedMeeting?.id === data.meeting.id) {
          setSelectedMeeting(data.meeting);
        }
        queryClient.invalidateQueries({ queryKey: ['council', 'meetings'] });
      } else if (['signal_created', 'signal_approved', 'signal_rejected', 'signal_executed'].includes(data.type)) {
        queryClient.invalidateQueries({ queryKey: ['council', 'signals'] });
      } else if (data.type === 'connected') {
        queryClient.invalidateQueries({ queryKey: ['council'] });
      }
    };

    ws.onclose = () => {
      setWsConnected(false);
      setTimeout(connectWebSocket, 3000);
    };

    ws.onerror = () => setWsConnected(false);
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

  // 페이지 진입 시 모니터링 자동 시작
  const autoStarted = useRef(false);
  useEffect(() => {
    if (status && !status.running && !autoStarted.current && !startMutation.isPending) {
      autoStarted.current = true;
      startMutation.mutate(undefined);
    }
  }, [status]);

  const defaultConfig: CouncilConfig = {
    council_threshold: status?.council_threshold || 7,
    sell_threshold: 3,
    auto_execute: status?.auto_execute ?? true,
    max_position_per_stock: 500000,
    poll_interval: 60,
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-500 rounded-2xl p-6 text-white shadow-xl">
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-3xl font-bold flex items-center">
              <span className="mr-3">🏛️</span>
              AI 투자 위원회
            </h1>
            <p className="text-white/80 mt-2 max-w-xl">
              Gemini, GPT, Claude 3개의 전문 AI가 실시간으로 협력하여
              최적의 투자 결정을 도출합니다.
            </p>
          </div>
          <div className="flex items-center space-x-3">
            <span className={`flex items-center px-4 py-2 rounded-full text-sm font-medium ${
              wsConnected
                ? 'bg-green-500/20 text-green-100 border border-green-400/50'
                : 'bg-red-500/20 text-red-100 border border-red-400/50'
            }`}>
              <span className={`w-2 h-2 rounded-full mr-2 ${
                wsConnected ? 'bg-green-400 animate-pulse' : 'bg-red-400'
              }`} />
              {wsConnected ? '실시간 연결됨' : '연결 끊김'}
            </span>
            <button
              onClick={() => setShowConfig(!showConfig)}
              className="px-4 py-2 bg-white/20 hover:bg-white/30 rounded-full text-sm font-medium transition-all"
            >
              ⚙️ 설정
            </button>
          </div>
        </div>
      </div>

      {/* AI 팀 소개 */}
      <AITeamIntroduction />

      {/* Trading Status Card */}
      {status?.trading && (
        <div className={`rounded-xl shadow-lg p-5 ${
          status.trading.can_trade
            ? 'bg-gradient-to-r from-green-50 to-emerald-50 border-2 border-green-300'
            : 'bg-gradient-to-r from-gray-50 to-slate-50 border-2 border-gray-300'
        }`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <div className={`w-14 h-14 rounded-full flex items-center justify-center ${
                status.trading.can_trade
                  ? 'bg-green-500'
                  : 'bg-gray-400'
              }`}>
                <span className="text-2xl">
                  {status.trading.session === 'regular' ? '📈' :
                   status.trading.session === 'pre_market' ? '🌅' :
                   status.trading.session === 'post_market' ? '🌆' :
                   status.trading.session === 'closed' ? '🌙' : '⏰'}
                </span>
              </div>
              <div>
                <h3 className={`text-lg font-bold ${
                  status.trading.can_trade ? 'text-green-800' : 'text-gray-700'
                }`}>
                  {status.trading.status_message}
                </h3>
                <p className="text-sm text-gray-500">{status.trading.reason}</p>
              </div>
            </div>
            <div className="flex items-center space-x-4">
              {status.trading.queued_count > 0 && (
                <div className="bg-orange-100 border border-orange-300 rounded-lg px-4 py-2 text-center">
                  <p className="text-xs text-orange-600">대기 주문</p>
                  <p className="text-xl font-bold text-orange-700">{status.trading.queued_count}건</p>
                </div>
              )}
              <div className={`px-4 py-2 rounded-lg text-center ${
                status.trading.auto_execute
                  ? 'bg-purple-100 border border-purple-300'
                  : 'bg-gray-100 border border-gray-300'
              }`}>
                <p className="text-xs text-gray-600">자동매매</p>
                <p className={`text-sm font-bold ${
                  status.trading.auto_execute ? 'text-purple-700' : 'text-gray-500'
                }`}>
                  {status.trading.auto_execute ? '🤖 ON' : '⏸️ OFF'}
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 계좌 보유종목 현황 */}
      <AccountHoldingsPanel />

      {/* Status Cards */}
      <div className="grid grid-cols-2 md:grid-cols-6 gap-4">
        <div className="bg-white rounded-xl shadow-md p-5 border-l-4 border-indigo-500">
          <p className="text-sm text-gray-500 mb-1">운영 상태</p>
          <p className={`text-xl font-bold ${status?.running ? 'text-green-600' : 'text-gray-400'}`}>
            {status?.running ? '🟢 실행 중' : '⭕ 중지됨'}
          </p>
        </div>
        <div className="bg-white rounded-xl shadow-md p-5 border-l-4 border-yellow-500">
          <p className="text-sm text-gray-500 mb-1">대기 시그널</p>
          <p className="text-3xl font-bold text-yellow-600">{status?.pending_signals || 0}</p>
        </div>
        <div className="bg-white rounded-xl shadow-md p-5 border-l-4 border-blue-500">
          <p className="text-sm text-gray-500 mb-1">총 회의</p>
          <p className="text-3xl font-bold text-blue-600">{status?.total_meetings || 0}</p>
        </div>
        <div className="bg-white rounded-xl shadow-md p-5 border-l-4 border-green-500">
          <p className="text-sm text-gray-500 mb-1">오늘 거래</p>
          <p className="text-3xl font-bold text-green-600">{status?.daily_trades || 0}</p>
        </div>
        <div className="bg-white rounded-xl shadow-md p-5 border-l-4 border-purple-500">
          <p className="text-sm text-gray-500 mb-1">자동 체결</p>
          <p className={`text-xl font-bold ${status?.auto_execute ? 'text-purple-600' : 'text-gray-400'}`}>
            {status?.auto_execute ? '🤖 활성화' : '⏸️ 비활성화'}
          </p>
        </div>
        {/* AI 비용 통계 카드 */}
        <div className="bg-white rounded-xl shadow-md p-5 border-l-4 border-orange-500">
          <p className="text-sm text-gray-500 mb-1">AI 비용 (일/월)</p>
          {status?.cost ? (
            <div>
              <p className="text-lg font-bold text-orange-600">
                ${status.cost.daily_cost.toFixed(2)} / ${status.cost.monthly_cost.toFixed(2)}
              </p>
              <div className="mt-1">
                <div className="w-full bg-gray-200 rounded-full h-1.5">
                  <div
                    className={`h-1.5 rounded-full transition-all ${
                      (status.cost.daily_cost / status.cost.daily_limit) > 0.8
                        ? 'bg-red-500'
                        : (status.cost.daily_cost / status.cost.daily_limit) > 0.5
                          ? 'bg-yellow-500'
                          : 'bg-green-500'
                    }`}
                    style={{ width: `${Math.min(100, (status.cost.daily_cost / status.cost.daily_limit) * 100)}%` }}
                  />
                </div>
                <p className="text-xs text-gray-400 mt-0.5">
                  일일 한도: ${status.cost.daily_limit} (${status.cost.daily_remaining.toFixed(2)} 남음)
                </p>
              </div>
            </div>
          ) : (
            <p className="text-lg font-bold text-gray-400">-</p>
          )}
        </div>
      </div>

      {/* Control Buttons */}
      <div className="flex flex-wrap gap-3">
        {!status?.running ? (
          <button
            onClick={() => startMutation.mutate(undefined)}
            disabled={startMutation.isPending}
            className="px-8 py-4 bg-gradient-to-r from-green-500 to-emerald-600 text-white rounded-xl font-bold text-lg hover:from-green-600 hover:to-emerald-700 disabled:opacity-50 transition-all shadow-lg hover:shadow-xl"
          >
            {startMutation.isPending ? '⏳ 시작 중...' : '🚀 AI 모니터링 시작'}
          </button>
        ) : (
          <button
            onClick={() => stopMutation.mutate()}
            disabled={stopMutation.isPending}
            className="px-8 py-4 bg-gradient-to-r from-red-500 to-rose-600 text-white rounded-xl font-bold text-lg hover:from-red-600 hover:to-rose-700 disabled:opacity-50 transition-all shadow-lg hover:shadow-xl"
          >
            {stopMutation.isPending ? '⏳ 중지 중...' : '⏹️ 모니터링 중지'}
          </button>
        )}

        {/* 테스트 버튼들 */}
        <button
          onClick={handleTestAnalyze}
          disabled={testLoading}
          className="px-6 py-4 bg-gradient-to-r from-blue-500 to-cyan-600 text-white rounded-xl font-bold hover:from-blue-600 hover:to-cyan-700 disabled:opacity-50 transition-all shadow-lg"
        >
          {testLoading ? '⏳ 분석 중...' : '🔍 뉴스 분석 테스트'}
        </button>
        <button
          onClick={handleForceCouncil}
          disabled={testLoading}
          className="px-6 py-4 bg-gradient-to-r from-purple-500 to-pink-600 text-white rounded-xl font-bold hover:from-purple-600 hover:to-pink-700 disabled:opacity-50 transition-all shadow-lg"
        >
          {testLoading ? '⏳ 회의 소집 중...' : '🏛️ 실제 뉴스로 회의'}
        </button>
        <button
          onClick={handleMockCouncil}
          disabled={testLoading}
          className="px-6 py-4 bg-gradient-to-r from-amber-500 to-orange-600 text-white rounded-xl font-bold hover:from-amber-600 hover:to-orange-700 disabled:opacity-50 transition-all shadow-lg"
        >
          {testLoading ? '⏳ 회의 소집 중...' : '🧪 삼성전자 테스트 회의'}
        </button>
      </div>

      {/* 테스트 결과 표시 */}
      {testResult && (
        <div className={`rounded-xl p-4 shadow-lg ${testResult.error ? 'bg-red-900' : 'bg-gray-900'}`}>
          <div className="flex justify-between items-center mb-3">
            <h3 className="text-white font-bold flex items-center">
              <span className="mr-2">{testResult.error ? '❌' : testResult.status === 'council_started' ? '✅' : '🧪'}</span>
              {testResult.error ? '오류 발생' : testResult.status === 'council_started' ? '회의 시작됨!' : '테스트 결과'}
            </h3>
            <button
              onClick={() => setTestResult(null)}
              className="text-gray-400 hover:text-white text-sm"
            >
              ✕ 닫기
            </button>
          </div>
          {/* 요약 정보 표시 */}
          {'article' in testResult && testResult.article ? (
            <div className="bg-gray-800 rounded-lg p-3 mb-3">
              <p className="text-white font-medium">{String((testResult.article as Record<string, unknown>).title)}</p>
              <p className="text-gray-400 text-sm mt-1">
                종목: {String((testResult.article as Record<string, unknown>).company_name)} ({String((testResult.article as Record<string, unknown>).symbol)})
              </p>
            </div>
          ) : null}
          {'analysis_result' in testResult && testResult.analysis_result ? (
            <div className="grid grid-cols-2 gap-2 mb-3">
              <div className="bg-gray-800 rounded-lg p-2 text-center">
                <p className="text-gray-400 text-xs">점수</p>
                <p className="text-2xl font-bold text-white">{Number((testResult.analysis_result as Record<string, unknown>).score)}/10</p>
              </div>
              <div className="bg-gray-800 rounded-lg p-2 text-center">
                <p className="text-gray-400 text-xs">신뢰도</p>
                <p className="text-2xl font-bold text-white">{Math.round(Number((testResult.analysis_result as Record<string, unknown>).confidence) * 100)}%</p>
              </div>
            </div>
          ) : null}
          {testResult.should_trigger_council !== undefined && (
            <div className={`rounded-lg p-3 mb-3 ${testResult.should_trigger_council ? 'bg-green-800' : 'bg-yellow-800'}`}>
              <p className="text-white font-medium">
                {testResult.should_trigger_council
                  ? '✅ 회의 소집 조건 충족!'
                  : `⚠️ 회의 소집 조건 미충족 (threshold: ${testResult.council_threshold})`}
              </p>
            </div>
          )}
          <details className="mt-2">
            <summary className="text-gray-400 text-sm cursor-pointer hover:text-white">📋 상세 JSON 보기</summary>
            <pre className={`text-sm overflow-auto max-h-64 whitespace-pre-wrap mt-2 ${testResult.error ? 'text-red-400' : 'text-green-400'}`}>
              {JSON.stringify(testResult, null, 2)}
            </pre>
          </details>
        </div>
      )}

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
          <h2 className="text-xl font-bold text-gray-800 mb-4 flex items-center">
            <span className="mr-2">📋</span>
            대기 중인 투자 시그널
          </h2>
          {pendingSignals?.signals && pendingSignals.signals.length > 0 ? (
            <div className="space-y-4">
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
            <div className="bg-white rounded-xl border-2 border-dashed border-gray-300 p-10 text-center">
              <span className="text-5xl mb-4 block">📭</span>
              <p className="text-gray-500 font-medium">대기 중인 시그널이 없습니다</p>
              <p className="text-sm text-gray-400 mt-2">
                AI 회의에서 새로운 투자 시그널이 생성되면 여기에 표시됩니다
              </p>
            </div>
          )}
        </div>

        {/* Recent Meetings */}
        <div>
          <h2 className="text-xl font-bold text-gray-800 mb-4 flex items-center">
            <span className="mr-2">🏛️</span>
            최근 AI 회의
          </h2>
          {meetings?.meetings && meetings.meetings.length > 0 ? (
            <div className="space-y-3">
              {meetings.meetings.map((meeting) => (
                <div
                  key={meeting.id}
                  onClick={() => setSelectedMeeting(meeting)}
                  className={`bg-white rounded-xl border-2 p-4 cursor-pointer transition-all hover:shadow-lg ${
                    selectedMeeting?.id === meeting.id
                      ? 'ring-2 ring-indigo-500 border-indigo-300'
                      : 'border-gray-200 hover:border-indigo-300'
                  }`}
                >
                  <div className="flex justify-between items-start">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center space-x-2">
                        <h4 className="font-bold text-gray-900">{meeting.company_name}</h4>
                        <span className="text-gray-400 text-sm">({meeting.symbol})</span>
                      </div>
                      <p className="text-sm text-gray-500 truncate mt-1">{meeting.news_title}</p>
                    </div>
                    <span className={`px-3 py-1 rounded-full text-xs font-bold ${
                      meeting.consensus_reached
                        ? 'bg-green-100 text-green-700'
                        : 'bg-yellow-100 text-yellow-700'
                    }`}>
                      {meeting.consensus_reached ? '✅ 완료' : '🔄 진행 중'}
                    </span>
                  </div>
                  <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-100">
                    <div className="flex items-center space-x-3 text-xs text-gray-500">
                      <span>⭐ {meeting.news_score}/10</span>
                      <span>💬 {meeting.messages.length}개 발언</span>
                    </div>
                    <span className="text-xs text-gray-400">
                      {new Date(meeting.started_at).toLocaleString('ko-KR', {
                        month: 'short',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit'
                      })}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="bg-white rounded-xl border-2 border-dashed border-gray-300 p-10 text-center">
              <span className="text-5xl mb-4 block">🏛️</span>
              <p className="text-gray-500 font-medium">아직 회의가 없습니다</p>
              <p className="text-sm text-gray-400 mt-2">
                모니터링을 시작하면 AI 회의가 자동으로 소집됩니다
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Selected Meeting Detail */}
      {selectedMeeting && (
        <div>
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-bold text-gray-800 flex items-center">
              <span className="mr-2">📝</span>
              회의 상세 내용
            </h2>
            <button
              onClick={() => setSelectedMeeting(null)}
              className="px-4 py-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-all"
            >
              ✕ 닫기
            </button>
          </div>
          <MeetingViewer
            meeting={selectedMeeting}
            onApproveSignal={(id) => approveMutation.mutate(id)}
            onRejectSignal={(id) => rejectMutation.mutate(id)}
            onExecuteSignal={(id) => executeMutation.mutate(id)}
            isLoading={approveMutation.isPending || rejectMutation.isPending || executeMutation.isPending}
          />
        </div>
      )}

      {/* 투자 유의사항 */}
      <div className="bg-gradient-to-r from-amber-50 to-orange-50 border-2 border-amber-200 rounded-xl p-5">
        <div className="flex items-start space-x-3">
          <span className="text-2xl">⚠️</span>
          <div>
            <h4 className="font-bold text-amber-800">투자 유의사항</h4>
            <p className="text-sm text-amber-700 mt-1">
              AI 투자 위원회의 결정은 참고용이며, 최종 투자 결정은 사용자 본인의 판단에 따라 이루어져야 합니다.
              투자에는 원금 손실의 위험이 있으며, 과거의 성과가 미래 수익을 보장하지 않습니다.
              자동 체결 기능 사용 시 실제 주문이 실행되므로 신중하게 설정해 주세요.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

import { useEffect, useRef } from 'react';
import { AI_ANALYSTS } from './constants';
import { MessageBubble } from './MessageBubble';
import type { CouncilMeeting } from './types';

export function MeetingViewer({
  meeting,
  onApproveSignal,
  onRejectSignal,
  onExecuteSignal,
  isLoading
}: {
  meeting: CouncilMeeting;
  onApproveSignal?: (signalId: string) => void;
  onRejectSignal?: (signalId: string) => void;
  onExecuteSignal?: (signalId: string) => void;
  isLoading?: boolean;
}) {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [meeting.messages]);

  // AI별 발언 횟수 계산
  const speakerStats = meeting.messages.reduce((acc, msg) => {
    acc[msg.role] = (acc[msg.role] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  return (
    <div className="bg-white rounded-xl border-2 shadow-lg overflow-hidden">
      {/* 회의 헤더 */}
      <div className="bg-gradient-to-r from-indigo-600 to-purple-600 p-5">
        <div className="flex justify-between items-start">
          <div className="text-white">
            <div className="flex items-center space-x-2">
              <span className="text-2xl">🏛️</span>
              <h3 className="font-bold text-xl">{meeting.company_name}</h3>
              <span className="text-white/70">({meeting.symbol})</span>
            </div>
            <p className="text-white/80 text-sm mt-2 max-w-lg">{meeting.news_title}</p>
          </div>
          <div className="text-right">
            <span className={`px-3 py-1 rounded-full text-sm font-bold ${
              meeting.consensus_reached
                ? 'bg-green-100 text-green-800'
                : 'bg-yellow-100 text-yellow-800'
            }`}>
              {meeting.consensus_reached ? '✅ 합의 완료' : `🔄 라운드 ${meeting.current_round}/${meeting.max_rounds}`}
            </span>
            <p className="text-white/70 text-xs mt-2">
              뉴스 중요도: {'⭐'.repeat(Math.round(meeting.news_score / 2))} ({meeting.news_score}/10)
            </p>
          </div>
        </div>

        {/* AI 참여 현황 */}
        <div className="flex items-center space-x-4 mt-4 pt-4 border-t border-white/20">
          {Object.entries(AI_ANALYSTS).map(([key, analyst]) => {
            const count = speakerStats[key] || 0;
            if (count === 0) return null;
            return (
              <div key={key} className="flex items-center space-x-2 text-white/90 text-sm">
                <span>{analyst.avatar}</span>
                <span>{analyst.name}</span>
                <span className="bg-white/20 px-2 py-0.5 rounded-full text-xs">{count}회</span>
              </div>
            );
          })}
        </div>
      </div>

      {/* 회의 내용 */}
      <div className="p-5 max-h-[600px] overflow-y-auto bg-gray-50">
        {meeting.messages.length === 0 ? (
          <div className="text-center py-10 text-gray-500">
            <span className="text-4xl mb-3 block">💬</span>
            <p>아직 발언이 없습니다</p>
            <p className="text-sm">회의가 시작되면 AI들의 토론이 여기에 표시됩니다</p>
          </div>
        ) : (
          <>
            {meeting.messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}
            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      {/* 시그널 요약 */}
      {meeting.signal && (
        <div className="p-5 bg-gradient-to-r from-indigo-50 to-purple-50 border-t-2 border-indigo-200">
          <h4 className="font-bold text-indigo-800 mb-3 flex items-center">
            <span className="text-xl mr-2">📌</span>
            최종 투자 시그널
          </h4>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <div className="bg-white rounded-lg p-3 text-center border">
              <span className="text-xs text-gray-500">행동</span>
              <p className={`font-bold text-lg ${
                meeting.signal.action === 'BUY' ? 'text-green-600' :
                meeting.signal.action === 'SELL' ? 'text-red-600' : 'text-gray-600'
              }`}>
                {meeting.signal.action === 'BUY' ? '📈 매수' :
                 meeting.signal.action === 'SELL' ? '📉 매도' : '📊 보유'}
              </p>
            </div>
            <div className="bg-white rounded-lg p-3 text-center border">
              <span className="text-xs text-gray-500">투자 비율</span>
              <p className="font-bold text-lg text-gray-800">{meeting.signal.allocation_percent.toFixed(1)}%</p>
            </div>
            <div className="bg-white rounded-lg p-3 text-center border">
              <span className="text-xs text-gray-500">제안 금액</span>
              <p className="font-bold text-lg text-gray-800">{(meeting.signal.suggested_amount / 10000).toFixed(0)}만원</p>
            </div>
            <div className="bg-white rounded-lg p-3 text-center border">
              <span className="text-xs text-gray-500">신뢰도</span>
              <p className="font-bold text-lg text-indigo-600">{(meeting.signal.confidence * 100).toFixed(0)}%</p>
            </div>
            <div className="bg-white rounded-lg p-3 text-center border">
              <span className="text-xs text-gray-500">AI 점수</span>
              <p className="font-bold text-lg">
                <span className="text-green-600">{meeting.signal.quant_score}</span>
                <span className="text-gray-400 mx-1">/</span>
                <span className="text-purple-600">{meeting.signal.fundamental_score}</span>
              </p>
            </div>
          </div>
          <div className="mt-3 bg-white rounded-lg p-3 border">
            <p className="text-sm text-gray-700">{meeting.signal.consensus_reason}</p>
          </div>

          {/* 시그널 액션 버튼 */}
          {meeting.signal.status === 'pending' && onApproveSignal && onRejectSignal && (
            <div className="mt-4 flex space-x-3">
              <button
                onClick={() => onApproveSignal(meeting.signal!.id)}
                disabled={isLoading}
                className="flex-1 px-4 py-3 bg-gradient-to-r from-blue-500 to-blue-600 text-white rounded-xl text-sm font-bold hover:from-blue-600 hover:to-blue-700 disabled:opacity-50 transition-all shadow-md hover:shadow-lg"
              >
                ✅ 승인하기
              </button>
              <button
                onClick={() => onRejectSignal(meeting.signal!.id)}
                disabled={isLoading}
                className="flex-1 px-4 py-3 bg-gray-100 text-gray-700 rounded-xl text-sm font-bold hover:bg-gray-200 disabled:opacity-50 transition-all"
              >
                ❌ 거부하기
              </button>
            </div>
          )}

          {meeting.signal.status === 'queued' && (
            <div className="mt-4 px-4 py-3 bg-orange-50 border border-orange-200 rounded-xl text-center">
              <p className="text-sm font-bold text-orange-700">🕐 장 개시 후 자동 체결 예정</p>
              <p className="text-xs text-orange-500 mt-1">거래 시간에 자동으로 주문이 실행됩니다</p>
            </div>
          )}

          {meeting.signal.status === 'approved' && onExecuteSignal && (
            <button
              onClick={() => onExecuteSignal(meeting.signal!.id)}
              disabled={isLoading}
              className="mt-4 w-full px-4 py-3 bg-gradient-to-r from-green-500 to-emerald-600 text-white rounded-xl text-sm font-bold hover:from-green-600 hover:to-emerald-700 disabled:opacity-50 transition-all shadow-md hover:shadow-lg"
            >
              💰 지금 체결하기
            </button>
          )}

          {(meeting.signal.status === 'executed' || meeting.signal.status === 'auto_executed') && (
            <div className="mt-4 p-3 bg-green-100 border border-green-300 rounded-xl text-center">
              <span className="text-green-700 font-bold">✅ 체결 완료</span>
            </div>
          )}

          {meeting.signal.status === 'rejected' && (
            <div className="mt-4 p-3 bg-red-100 border border-red-300 rounded-xl text-center">
              <span className="text-red-700 font-bold">❌ 거부됨</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

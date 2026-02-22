import { useState } from 'react';
import type { InvestmentSignal } from './types';

export function SignalCard({
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
  const [showDetail, setShowDetail] = useState(false);

  const statusConfig: Record<string, { bg: string; text: string; label: string; icon: string }> = {
    pending: { bg: 'bg-yellow-100', text: 'text-yellow-800', label: '승인 대기', icon: '⏳' },
    queued: { bg: 'bg-orange-100', text: 'text-orange-800', label: '구매 대기', icon: '🕐' },
    approved: { bg: 'bg-blue-100', text: 'text-blue-800', label: '승인됨', icon: '✅' },
    rejected: { bg: 'bg-red-100', text: 'text-red-800', label: '거부됨', icon: '❌' },
    executed: { bg: 'bg-green-100', text: 'text-green-800', label: '체결됨', icon: '💰' },
    auto_executed: { bg: 'bg-green-100', text: 'text-green-800', label: '자동 체결', icon: '🤖' },
  };

  const status = statusConfig[signal.status] || { bg: 'bg-gray-100', text: 'text-gray-800', label: signal.status, icon: '📋' };

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.8) return 'text-green-600 bg-green-50';
    if (confidence >= 0.6) return 'text-blue-600 bg-blue-50';
    if (confidence >= 0.4) return 'text-yellow-600 bg-yellow-50';
    return 'text-red-600 bg-red-50';
  };

  return (
    <div className="bg-white rounded-xl border-2 shadow-sm hover:shadow-lg transition-all overflow-hidden">
      {/* 헤더 */}
      <div className={`p-4 ${signal.action === 'BUY' ? 'bg-gradient-to-r from-green-500 to-emerald-600' : signal.action === 'SELL' ? 'bg-gradient-to-r from-red-500 to-rose-600' : 'bg-gradient-to-r from-gray-500 to-gray-600'}`}>
        <div className="flex justify-between items-start">
          <div className="text-white">
            <div className="flex items-center space-x-2">
              <span className="text-2xl font-bold">
                {signal.action === 'BUY' ? '📈 매수' : signal.action === 'SELL' ? '📉 매도' : '📊 보유'}
              </span>
            </div>
            <h3 className="text-xl font-bold mt-1">{signal.company_name}</h3>
            <span className="text-white/80 text-sm">{signal.symbol}</span>
          </div>
          <span className={`px-3 py-1 rounded-full text-xs font-bold ${status.bg} ${status.text}`}>
            {status.icon} {status.label}
          </span>
        </div>
      </div>

      {/* 주요 지표 */}
      <div className="p-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
          <div className="text-center p-3 bg-gray-50 rounded-lg">
            <p className="text-xs text-gray-500 mb-1">투자 비율</p>
            <p className="text-xl font-bold text-gray-800">{signal.allocation_percent.toFixed(1)}%</p>
          </div>
          <div className="text-center p-3 bg-gray-50 rounded-lg">
            <p className="text-xs text-gray-500 mb-1">제안 금액</p>
            <p className="text-xl font-bold text-gray-800">{(signal.suggested_amount / 10000).toFixed(0)}만원</p>
          </div>
          <div className={`text-center p-3 rounded-lg ${getConfidenceColor(signal.confidence)}`}>
            <p className="text-xs opacity-70 mb-1">종합 신뢰도</p>
            <p className="text-xl font-bold">{(signal.confidence * 100).toFixed(0)}%</p>
          </div>
          <div className="text-center p-3 bg-gray-50 rounded-lg">
            <p className="text-xs text-gray-500 mb-1">AI 점수</p>
            <div className="flex items-center justify-center space-x-1">
              <span className="text-green-600 font-bold">{signal.quant_score}</span>
              <span className="text-gray-400">/</span>
              <span className="text-purple-600 font-bold">{signal.fundamental_score}</span>
            </div>
          </div>
        </div>

        {/* AI 점수 시각화 바 */}
        <div className="space-y-2 mb-4">
          <div>
            <div className="flex justify-between items-center mb-1">
              <span className="text-xs text-green-600 font-medium">📊 퀀트 분석 (GPT)</span>
              <span className="text-xs text-gray-500">{signal.quant_score}/100</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className="bg-gradient-to-r from-green-400 to-green-600 h-2 rounded-full transition-all"
                style={{ width: `${signal.quant_score}%` }}
              />
            </div>
          </div>
          <div>
            <div className="flex justify-between items-center mb-1">
              <span className="text-xs text-purple-600 font-medium">📈 펀더멘털 분석 (Claude)</span>
              <span className="text-xs text-gray-500">{signal.fundamental_score}/100</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className="bg-gradient-to-r from-purple-400 to-purple-600 h-2 rounded-full transition-all"
                style={{ width: `${signal.fundamental_score}%` }}
              />
            </div>
          </div>
        </div>

        {/* 합의 이유 */}
        <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-3 mb-4">
          <p className="text-xs text-indigo-600 font-semibold mb-1">💡 AI 합의 이유</p>
          <p className="text-sm text-indigo-800">{signal.consensus_reason}</p>
        </div>

        {/* 상세 정보 토글 */}
        <button
          onClick={() => setShowDetail(!showDetail)}
          className="w-full text-center text-sm text-gray-500 hover:text-gray-700 py-2"
        >
          {showDetail ? '▲ 상세 정보 접기' : '▼ 상세 정보 보기'}
        </button>

        {showDetail && (
          <div className="mt-4 space-y-3 pt-4 border-t">
            {signal.quant_summary && (
              <div className="bg-green-50 rounded-lg p-3">
                <p className="text-xs text-green-600 font-semibold mb-1">📊 GPT 퀀트 분석 요약</p>
                <p className="text-sm text-green-800">{signal.quant_summary}</p>
              </div>
            )}
            {signal.fundamental_summary && (
              <div className="bg-purple-50 rounded-lg p-3">
                <p className="text-xs text-purple-600 font-semibold mb-1">📈 Claude 펀더멘털 분석 요약</p>
                <p className="text-sm text-purple-800">{signal.fundamental_summary}</p>
              </div>
            )}
            <div className="grid grid-cols-2 gap-3 text-sm">
              {signal.target_price && (
                <div className="bg-gray-50 rounded-lg p-2">
                  <span className="text-gray-500 text-xs">목표가</span>
                  <p className="font-bold text-gray-800">{signal.target_price.toLocaleString()}원</p>
                </div>
              )}
              {signal.stop_loss_price && (
                <div className="bg-gray-50 rounded-lg p-2">
                  <span className="text-gray-500 text-xs">손절가</span>
                  <p className="font-bold text-red-600">{signal.stop_loss_price.toLocaleString()}원</p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* 액션 버튼 */}
        {signal.status === 'pending' && (
          <div className="flex space-x-3 mt-4">
            <button
              onClick={() => onApprove(signal.id)}
              disabled={isLoading}
              className="flex-1 px-4 py-3 bg-gradient-to-r from-blue-500 to-blue-600 text-white rounded-xl text-sm font-bold hover:from-blue-600 hover:to-blue-700 disabled:opacity-50 transition-all shadow-md hover:shadow-lg"
            >
              ✅ 승인하기
            </button>
            <button
              onClick={() => onReject(signal.id)}
              disabled={isLoading}
              className="flex-1 px-4 py-3 bg-gray-100 text-gray-700 rounded-xl text-sm font-bold hover:bg-gray-200 disabled:opacity-50 transition-all"
            >
              ❌ 거부하기
            </button>
          </div>
        )}

        {signal.status === 'queued' && (
          <div className="mt-4 px-4 py-3 bg-orange-50 border border-orange-200 rounded-xl text-center">
            <p className="text-sm font-bold text-orange-700">🕐 장 개시 후 자동 체결 예정</p>
            <p className="text-xs text-orange-500 mt-1">거래 시간에 자동으로 주문이 실행됩니다</p>
          </div>
        )}

        {signal.status === 'approved' && (
          <button
            onClick={() => onExecute(signal.id)}
            disabled={isLoading}
            className="w-full mt-4 px-4 py-3 bg-gradient-to-r from-green-500 to-emerald-600 text-white rounded-xl text-sm font-bold hover:from-green-600 hover:to-emerald-700 disabled:opacity-50 transition-all shadow-md hover:shadow-lg"
          >
            💰 지금 체결하기
          </button>
        )}
      </div>
    </div>
  );
}

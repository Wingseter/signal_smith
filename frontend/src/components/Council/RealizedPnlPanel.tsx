import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { councilApi } from '../../services/api';
import type { RealizedPnlResponse } from './types';

const PERIOD_OPTIONS = [
  { label: '1주', value: '1w' },
  { label: '1개월', value: '1m' },
  { label: '3개월', value: '3m' },
] as const;

export function RealizedPnlPanel() {
  const [period, setPeriod] = useState('1m');

  const { data, isLoading, isError } = useQuery<RealizedPnlResponse>({
    queryKey: ['council', 'account', 'realized-pnl', period],
    queryFn: () => councilApi.getRealizedPnl(period),
    refetchInterval: 60000,
    retry: 2,
    staleTime: 30000,
  });

  const summary = data?.summary;
  const items = data?.items ?? [];

  return (
    <div className="bg-white rounded-xl border-2 shadow-lg overflow-hidden">
      {/* Header */}
      <div className="bg-gradient-to-r from-violet-600 to-purple-600 p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <span className="text-2xl">💰</span>
            <div>
              <h2 className="font-bold text-white text-lg">실현 수익</h2>
              <p className="text-white/80 text-sm">매도 완료된 거래의 실현 손익</p>
            </div>
          </div>
          {/* 기간 선택 탭 */}
          <div className="flex bg-white/20 rounded-lg p-0.5">
            {PERIOD_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => setPeriod(opt.value)}
                className={`px-3 py-1 text-sm font-medium rounded-md transition-all ${
                  period === opt.value
                    ? 'bg-white text-violet-700 shadow-sm'
                    : 'text-white/80 hover:text-white hover:bg-white/10'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* 로딩 */}
      {isLoading && !summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="bg-gray-100 rounded-lg p-3 text-center animate-pulse">
              <div className="h-3 bg-gray-200 rounded w-12 mx-auto mb-2" />
              <div className="h-6 bg-gray-200 rounded w-20 mx-auto" />
            </div>
          ))}
        </div>
      )}

      {/* 에러 */}
      {isError && !summary && !isLoading && (
        <div className="p-6 text-center">
          <span className="text-3xl mb-2 block">⚠️</span>
          <p className="text-gray-500 font-medium">실현 수익 정보를 불러올 수 없습니다</p>
        </div>
      )}

      {/* 요약 카드 */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-4">
          <div className={`rounded-lg p-3 text-center ${
            summary.total_profit_loss >= 0 ? 'bg-red-50' : 'bg-blue-50'
          }`}>
            <p className="text-xs text-gray-500 mb-1">총실현손익</p>
            <p className={`text-lg font-bold ${
              summary.total_profit_loss >= 0 ? 'text-red-600' : 'text-blue-600'
            }`}>
              {summary.total_profit_loss >= 0 ? '+' : ''}{summary.total_profit_loss.toLocaleString()}원
            </p>
          </div>
          <div className="bg-gray-50 rounded-lg p-3 text-center">
            <p className="text-xs text-gray-500 mb-1">수수료+세금</p>
            <p className="text-lg font-bold text-gray-700">
              {(summary.total_commission + summary.total_tax).toLocaleString()}원
            </p>
          </div>
          <div className={`rounded-lg p-3 text-center ${
            summary.net_profit >= 0 ? 'bg-red-50' : 'bg-blue-50'
          }`}>
            <p className="text-xs text-gray-500 mb-1">순수익</p>
            <p className={`text-lg font-bold ${
              summary.net_profit >= 0 ? 'text-red-600' : 'text-blue-600'
            }`}>
              {summary.net_profit >= 0 ? '+' : ''}{summary.net_profit.toLocaleString()}원
            </p>
          </div>
          <div className="bg-gray-50 rounded-lg p-3 text-center">
            <p className="text-xs text-gray-500 mb-1">거래 건수</p>
            <p className="text-lg font-bold text-gray-800">{summary.trade_count}건</p>
          </div>
        </div>
      )}

      {/* 종목별 테이블 */}
      <div className="px-4 pb-4">
        {isLoading && items.length === 0 ? (
          <div className="space-y-2 py-4">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-10 bg-gray-100 rounded animate-pulse" />
            ))}
          </div>
        ) : items.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b-2 border-gray-200">
                  <th className="text-left py-2 px-2 text-gray-600 font-semibold">일자</th>
                  <th className="text-left py-2 px-2 text-gray-600 font-semibold">종목명</th>
                  <th className="text-right py-2 px-2 text-gray-600 font-semibold">체결량</th>
                  <th className="text-right py-2 px-2 text-gray-600 font-semibold">매입단가</th>
                  <th className="text-right py-2 px-2 text-gray-600 font-semibold">체결가</th>
                  <th className="text-right py-2 px-2 text-gray-600 font-semibold">손익</th>
                  <th className="text-right py-2 px-2 text-gray-600 font-semibold">손익률</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item, idx) => (
                  <tr key={`${item.date}-${item.symbol}-${idx}`} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="py-2 px-2 text-gray-500 text-xs">
                      {item.date.length === 8
                        ? `${item.date.slice(4, 6)}/${item.date.slice(6, 8)}`
                        : item.date}
                    </td>
                    <td className="py-2 px-2">
                      <div>
                        <span className="font-medium text-gray-800">{item.name}</span>
                        <span className="text-gray-400 text-xs ml-1">({item.symbol})</span>
                      </div>
                    </td>
                    <td className="text-right py-2 px-2 text-gray-700">{item.quantity.toLocaleString()}</td>
                    <td className="text-right py-2 px-2 text-gray-700">{item.buy_price > 0 ? item.buy_price.toLocaleString() : '-'}</td>
                    <td className="text-right py-2 px-2 text-gray-700">{item.sell_price.toLocaleString()}</td>
                    <td className={`text-right py-2 px-2 font-medium ${
                      item.profit_loss >= 0 ? 'text-red-600' : 'text-blue-600'
                    }`}>
                      {item.profit_loss >= 0 ? '+' : ''}{item.profit_loss.toLocaleString()}
                    </td>
                    <td className={`text-right py-2 px-2 font-bold ${
                      item.profit_rate >= 0 ? 'text-red-600' : 'text-blue-600'
                    }`}>
                      {item.profit_rate >= 0 ? '+' : ''}{item.profit_rate.toFixed(2)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : summary ? (
          <div className="text-center py-8 text-gray-500">
            <span className="text-3xl mb-2 block">📭</span>
            <p className="font-medium">실현 손익 내역 없음</p>
            <p className="text-xs text-gray-400 mt-1">해당 기간에 매도 완료된 거래가 없습니다</p>
          </div>
        ) : null}
      </div>
    </div>
  );
}

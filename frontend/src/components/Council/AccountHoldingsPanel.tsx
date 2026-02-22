import { useQuery, useQueryClient } from '@tanstack/react-query';
import { councilApi } from '../../services/api';
import type { AccountSummary } from './types';

export function AccountHoldingsPanel() {
  const queryClient = useQueryClient();

  const { data: summary, isLoading, isError } = useQuery<AccountSummary>({
    queryKey: ['council', 'account', 'summary'],
    queryFn: councilApi.getAccountSummary,
    refetchInterval: 30000,
    retry: 3,
    retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 10000),
    staleTime: 15000,
  });

  const balance = summary?.balance;
  const holdingsData = summary ? { holdings: summary.holdings, count: summary.count } : undefined;

  const handleRetry = () => {
    queryClient.invalidateQueries({ queryKey: ['council', 'account'] });
  };

  return (
    <div className="bg-white rounded-xl border-2 shadow-lg overflow-hidden">
      <div className="bg-gradient-to-r from-emerald-600 to-teal-600 p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <span className="text-2xl">💼</span>
            <div>
              <h2 className="font-bold text-white text-lg">키움 계좌 현황</h2>
              <p className="text-white/80 text-sm">실시간 보유종목 및 잔고 (30초 갱신)</p>
            </div>
          </div>
          <div className="flex items-center space-x-2">
            {isLoading && (
              <span className="text-white/60 text-sm animate-pulse">갱신 중...</span>
            )}
            {isError && !isLoading && (
              <button
                onClick={handleRetry}
                className="px-3 py-1 bg-white/20 hover:bg-white/30 text-white text-sm rounded-full transition-all"
              >
                다시 시도
              </button>
            )}
          </div>
        </div>
      </div>

      {/* 로딩 스켈레톤 */}
      {isLoading && !balance && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="bg-gray-100 rounded-lg p-3 text-center animate-pulse">
              <div className="h-3 bg-gray-200 rounded w-12 mx-auto mb-2" />
              <div className="h-6 bg-gray-200 rounded w-20 mx-auto" />
            </div>
          ))}
        </div>
      )}

      {/* 에러 상태 */}
      {isError && !balance && !isLoading && (
        <div className="p-6 text-center">
          <span className="text-3xl mb-2 block">⚠️</span>
          <p className="text-gray-500 font-medium">계좌 정보를 불러올 수 없습니다</p>
          <button
            onClick={handleRetry}
            className="mt-3 px-4 py-2 bg-emerald-500 text-white text-sm rounded-lg hover:bg-emerald-600 transition-all"
          >
            다시 시도
          </button>
        </div>
      )}

      {/* 계좌 잔고 카드 */}
      {balance && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-4">
          <div className="bg-gray-50 rounded-lg p-3 text-center">
            <p className="text-xs text-gray-500 mb-1">예수금</p>
            <p className="text-lg font-bold text-gray-800">
              {(balance.available_amount / 10000).toLocaleString()}만원
            </p>
          </div>
          <div className="bg-gray-50 rounded-lg p-3 text-center">
            <p className="text-xs text-gray-500 mb-1">총평가금액</p>
            <p className="text-lg font-bold text-gray-800">
              {(balance.total_evaluation / 10000).toLocaleString()}만원
            </p>
          </div>
          <div className={`rounded-lg p-3 text-center ${
            balance.total_profit_loss >= 0 ? 'bg-red-50' : 'bg-blue-50'
          }`}>
            <p className="text-xs text-gray-500 mb-1">총손익</p>
            <p className={`text-lg font-bold ${
              balance.total_profit_loss >= 0 ? 'text-red-600' : 'text-blue-600'
            }`}>
              {balance.total_profit_loss >= 0 ? '+' : ''}{balance.total_profit_loss.toLocaleString()}원
            </p>
          </div>
          <div className={`rounded-lg p-3 text-center ${
            balance.profit_rate >= 0 ? 'bg-red-50' : 'bg-blue-50'
          }`}>
            <p className="text-xs text-gray-500 mb-1">수익률</p>
            <p className={`text-lg font-bold ${
              balance.profit_rate >= 0 ? 'text-red-600' : 'text-blue-600'
            }`}>
              {balance.profit_rate >= 0 ? '+' : ''}{balance.profit_rate.toFixed(2)}%
            </p>
          </div>
        </div>
      )}

      {/* 보유종목 테이블 */}
      <div className="px-4 pb-4">
        {isLoading && !holdingsData ? (
          <div className="space-y-2 py-4">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-10 bg-gray-100 rounded animate-pulse" />
            ))}
          </div>
        ) : holdingsData && holdingsData.holdings.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b-2 border-gray-200">
                  <th className="text-left py-2 px-2 text-gray-600 font-semibold">종목명</th>
                  <th className="text-right py-2 px-2 text-gray-600 font-semibold">수량</th>
                  <th className="text-right py-2 px-2 text-gray-600 font-semibold">평균단가</th>
                  <th className="text-right py-2 px-2 text-gray-600 font-semibold">현재가</th>
                  <th className="text-right py-2 px-2 text-gray-600 font-semibold">평가금액</th>
                  <th className="text-right py-2 px-2 text-gray-600 font-semibold">손익</th>
                  <th className="text-right py-2 px-2 text-gray-600 font-semibold">수익률</th>
                </tr>
              </thead>
              <tbody>
                {holdingsData.holdings.map((holding) => (
                  <tr key={holding.symbol} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="py-2 px-2">
                      <div>
                        <span className="font-medium text-gray-800">{holding.name}</span>
                        <span className="text-gray-400 text-xs ml-1">({holding.symbol})</span>
                      </div>
                    </td>
                    <td className="text-right py-2 px-2 text-gray-700">{holding.quantity.toLocaleString()}</td>
                    <td className="text-right py-2 px-2 text-gray-700">{holding.avg_price.toLocaleString()}</td>
                    <td className="text-right py-2 px-2 text-gray-700">{holding.current_price.toLocaleString()}</td>
                    <td className="text-right py-2 px-2 font-medium text-gray-800">
                      {holding.evaluation.toLocaleString()}
                    </td>
                    <td className={`text-right py-2 px-2 font-medium ${
                      holding.profit_loss >= 0 ? 'text-red-600' : 'text-blue-600'
                    }`}>
                      {holding.profit_loss >= 0 ? '+' : ''}{holding.profit_loss.toLocaleString()}
                    </td>
                    <td className={`text-right py-2 px-2 font-bold ${
                      holding.profit_rate >= 0 ? 'text-red-600' : 'text-blue-600'
                    }`}>
                      {holding.profit_rate >= 0 ? '+' : ''}{holding.profit_rate.toFixed(2)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : holdingsData ? (
          <div className="text-center py-8 text-gray-500">
            <span className="text-3xl mb-2 block">📭</span>
            <p className="font-medium">보유종목 없음</p>
            <p className="text-xs text-gray-400 mt-1">AI 위원회가 매수 결정을 내리면 여기에 표시됩니다</p>
          </div>
        ) : null}
      </div>
    </div>
  );
}

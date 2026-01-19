import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { tradingApi } from '../../services/api';

interface Order {
  id: number;
  symbol: string;
  transaction_type: string;
  quantity: number;
  price: number;
  total_amount: number;
  status: string;
  created_at: string;
}

interface TradingSignal {
  id: number;
  symbol: string;
  signal_type: string;
  strength: number;
  source_agent: string;
  reason: string;
  target_price: number | null;
  stop_loss: number | null;
  created_at?: string;
}

// 매매 시그널 해석 가이드
function SignalInterpretationGuide() {
  const [showGuide, setShowGuide] = useState(false);

  return (
    <div className="bg-white rounded-xl border-2 shadow-lg overflow-hidden">
      <div
        className="bg-gradient-to-r from-violet-600 to-purple-600 p-4 cursor-pointer"
        onClick={() => setShowGuide(!showGuide)}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <span className="text-2xl">📖</span>
            <div>
              <h3 className="font-bold text-white">AI 시그널 해석 가이드</h3>
              <p className="text-white/80 text-sm">매매 신호를 이해하고 활용하는 방법</p>
            </div>
          </div>
          <span className="text-white">{showGuide ? '▲' : '▼'}</span>
        </div>
      </div>

      {showGuide && (
        <div className="p-5 space-y-4">
          {/* 시그널 강도 설명 */}
          <div className="bg-gray-50 rounded-lg p-4">
            <h4 className="font-semibold text-gray-800 mb-3">📊 시그널 강도 해석</h4>
            <div className="space-y-2">
              <div className="flex items-center space-x-3">
                <div className="w-20 h-2 bg-gradient-to-r from-green-400 to-green-600 rounded-full" />
                <span className="text-sm text-gray-700"><strong>80-100%</strong>: 강력한 신호 - 적극적 행동 고려</span>
              </div>
              <div className="flex items-center space-x-3">
                <div className="w-20 h-2 bg-gradient-to-r from-blue-400 to-blue-600 rounded-full" />
                <span className="text-sm text-gray-700"><strong>60-79%</strong>: 보통 신호 - 추가 확인 후 행동</span>
              </div>
              <div className="flex items-center space-x-3">
                <div className="w-20 h-2 bg-gradient-to-r from-yellow-400 to-yellow-600 rounded-full" />
                <span className="text-sm text-gray-700"><strong>40-59%</strong>: 약한 신호 - 주의 관찰</span>
              </div>
              <div className="flex items-center space-x-3">
                <div className="w-20 h-2 bg-gradient-to-r from-gray-300 to-gray-400 rounded-full" />
                <span className="text-sm text-gray-700"><strong>0-39%</strong>: 매우 약함 - 참고용</span>
              </div>
            </div>
          </div>

          {/* 시그널 타입 설명 */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className="bg-green-50 border border-green-200 rounded-lg p-3">
              <h5 className="font-bold text-green-700 flex items-center">
                <span className="mr-2">📈</span> 매수 (BUY)
              </h5>
              <p className="text-xs text-green-600 mt-1">
                AI가 해당 종목의 상승 가능성이 높다고 판단.
                기술적/펀더멘털 분석 기반의 매수 추천.
              </p>
            </div>
            <div className="bg-red-50 border border-red-200 rounded-lg p-3">
              <h5 className="font-bold text-red-700 flex items-center">
                <span className="mr-2">📉</span> 매도 (SELL)
              </h5>
              <p className="text-xs text-red-600 mt-1">
                하락 위험 또는 적정 가치 도달 판단.
                이익 실현 또는 손실 제한을 위한 매도 추천.
              </p>
            </div>
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-3">
              <h5 className="font-bold text-gray-700 flex items-center">
                <span className="mr-2">⏸️</span> 관망 (HOLD)
              </h5>
              <p className="text-xs text-gray-600 mt-1">
                현재 포지션 유지 권고.
                추가 매수/매도 없이 상황 관찰 필요.
              </p>
            </div>
          </div>

          {/* 목표가/손절가 설명 */}
          <div className="bg-blue-50 rounded-lg p-4">
            <h4 className="font-semibold text-blue-800 mb-2">🎯 목표가 & 손절가</h4>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <p className="text-blue-700 font-medium">목표가 (Target)</p>
                <p className="text-blue-600 text-xs mt-1">
                  AI가 예측한 상승 도달 가격. 이 가격에서 일부 또는 전량 익절을 고려하세요.
                </p>
              </div>
              <div>
                <p className="text-red-700 font-medium">손절가 (Stop Loss)</p>
                <p className="text-red-600 text-xs mt-1">
                  손실 제한을 위한 하한 가격. 이 가격 아래로 떨어지면 손절을 권장합니다.
                </p>
              </div>
            </div>
          </div>

          {/* 주의사항 */}
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
            <p className="text-xs text-amber-700">
              ⚠️ AI 시그널은 과거 데이터와 패턴 분석에 기반한 <strong>참고 정보</strong>입니다.
              실제 투자 결정은 다양한 요소를 고려하여 본인 판단 하에 신중하게 내리세요.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

// 개선된 시그널 카드
function EnhancedSignalCard({
  signal,
  onQuickOrder
}: {
  signal: TradingSignal;
  onQuickOrder: (symbol: string, type: 'buy' | 'sell') => void;
}) {
  const [showDetails, setShowDetails] = useState(false);

  const getStrengthColor = (strength: number) => {
    if (strength >= 80) return 'from-green-400 to-green-600';
    if (strength >= 60) return 'from-blue-400 to-blue-600';
    if (strength >= 40) return 'from-yellow-400 to-yellow-600';
    return 'from-gray-300 to-gray-400';
  };

  const getStrengthLabel = (strength: number) => {
    if (strength >= 80) return '강력';
    if (strength >= 60) return '보통';
    if (strength >= 40) return '약함';
    return '참고';
  };

  const getSourceIcon = (source: string) => {
    if (source.toLowerCase().includes('gemini')) return '🔔';
    if (source.toLowerCase().includes('gpt') || source.toLowerCase().includes('quant')) return '📊';
    if (source.toLowerCase().includes('claude') || source.toLowerCase().includes('fundamental')) return '📈';
    return '🤖';
  };

  const isBuy = signal.signal_type.toLowerCase() === 'buy';
  const isSell = signal.signal_type.toLowerCase() === 'sell';

  return (
    <div className="bg-white rounded-xl border-2 shadow-md hover:shadow-lg transition-all overflow-hidden">
      {/* 헤더 */}
      <div className={`p-4 ${
        isBuy ? 'bg-gradient-to-r from-green-500 to-emerald-600' :
        isSell ? 'bg-gradient-to-r from-red-500 to-rose-600' :
        'bg-gradient-to-r from-gray-500 to-gray-600'
      }`}>
        <div className="flex justify-between items-center">
          <div className="flex items-center space-x-3">
            <span className="text-2xl">
              {isBuy ? '📈' : isSell ? '📉' : '⏸️'}
            </span>
            <div>
              <h3 className="font-bold text-white text-xl">{signal.symbol}</h3>
              <p className="text-white/80 text-sm">{getSourceIcon(signal.source_agent)} {signal.source_agent}</p>
            </div>
          </div>
          <div className="text-right">
            <span className={`px-3 py-1 rounded-full text-sm font-bold ${
              isBuy ? 'bg-white/20 text-white' :
              isSell ? 'bg-white/20 text-white' :
              'bg-white/20 text-white'
            }`}>
              {signal.signal_type.toUpperCase()}
            </span>
          </div>
        </div>
      </div>

      {/* 본문 */}
      <div className="p-4">
        {/* 시그널 강도 */}
        <div className="mb-4">
          <div className="flex justify-between items-center mb-1">
            <span className="text-xs text-gray-500">시그널 강도</span>
            <span className="text-sm font-bold text-gray-700">{signal.strength}% ({getStrengthLabel(signal.strength)})</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-3">
            <div
              className={`bg-gradient-to-r ${getStrengthColor(signal.strength)} h-3 rounded-full transition-all`}
              style={{ width: `${signal.strength}%` }}
            />
          </div>
        </div>

        {/* 분석 이유 */}
        <div className="bg-gray-50 rounded-lg p-3 mb-4">
          <p className="text-xs text-gray-500 mb-1">💡 AI 분석 근거</p>
          <p className="text-sm text-gray-700">{signal.reason}</p>
        </div>

        {/* 목표가/손절가 */}
        {(signal.target_price || signal.stop_loss) && (
          <div className="grid grid-cols-2 gap-3 mb-4">
            {signal.target_price && (
              <div className="bg-green-50 border border-green-200 rounded-lg p-2 text-center">
                <p className="text-xs text-green-600">🎯 목표가</p>
                <p className="font-bold text-green-700">{Number(signal.target_price).toLocaleString()}원</p>
              </div>
            )}
            {signal.stop_loss && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-2 text-center">
                <p className="text-xs text-red-600">🛑 손절가</p>
                <p className="font-bold text-red-700">{Number(signal.stop_loss).toLocaleString()}원</p>
              </div>
            )}
          </div>
        )}

        {/* 상세 정보 토글 */}
        <button
          onClick={() => setShowDetails(!showDetails)}
          className="w-full text-center text-xs text-gray-500 hover:text-gray-700 py-1"
        >
          {showDetails ? '▲ 간략히' : '▼ 자세히 보기'}
        </button>

        {showDetails && (
          <div className="mt-3 pt-3 border-t space-y-2 text-xs text-gray-600">
            <div className="flex justify-between">
              <span>분석 출처</span>
              <span className="font-medium">{signal.source_agent}</span>
            </div>
            <div className="flex justify-between">
              <span>신호 유형</span>
              <span className={`font-medium ${isBuy ? 'text-green-600' : isSell ? 'text-red-600' : 'text-gray-600'}`}>
                {signal.signal_type.toUpperCase()}
              </span>
            </div>
            <div className="flex justify-between">
              <span>신뢰도</span>
              <span className="font-medium">{signal.strength}%</span>
            </div>
          </div>
        )}

        {/* 빠른 주문 버튼 */}
        {(isBuy || isSell) && (
          <button
            onClick={() => onQuickOrder(signal.symbol, isBuy ? 'buy' : 'sell')}
            className={`w-full mt-4 py-3 rounded-xl font-bold text-white transition-all shadow-md hover:shadow-lg ${
              isBuy
                ? 'bg-gradient-to-r from-green-500 to-emerald-600 hover:from-green-600 hover:to-emerald-700'
                : 'bg-gradient-to-r from-red-500 to-rose-600 hover:from-red-600 hover:to-rose-700'
            }`}
          >
            {isBuy ? '📈 이 종목 매수하기' : '📉 이 종목 매도하기'}
          </button>
        )}
      </div>
    </div>
  );
}

// 주문 현황 요약
function OrderSummary({ orders }: { orders: Order[] }) {
  const summary = useMemo(() => {
    const pending = orders.filter(o => o.status === 'pending' || o.status === 'submitted');
    const filled = orders.filter(o => o.status === 'filled');
    const cancelled = orders.filter(o => o.status === 'cancelled' || o.status === 'rejected');

    const totalBought = filled
      .filter(o => o.transaction_type === 'buy')
      .reduce((sum, o) => sum + o.total_amount, 0);

    const totalSold = filled
      .filter(o => o.transaction_type === 'sell')
      .reduce((sum, o) => sum + o.total_amount, 0);

    return { pending, filled, cancelled, totalBought, totalSold };
  }, [orders]);

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
      <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-4 text-center">
        <p className="text-xs text-yellow-600 mb-1">대기 중</p>
        <p className="text-2xl font-bold text-yellow-700">{summary.pending.length}</p>
      </div>
      <div className="bg-green-50 border border-green-200 rounded-xl p-4 text-center">
        <p className="text-xs text-green-600 mb-1">체결 완료</p>
        <p className="text-2xl font-bold text-green-700">{summary.filled.length}</p>
      </div>
      <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-center">
        <p className="text-xs text-blue-600 mb-1">총 매수액</p>
        <p className="text-lg font-bold text-blue-700">{(summary.totalBought / 10000).toFixed(0)}만원</p>
      </div>
      <div className="bg-purple-50 border border-purple-200 rounded-xl p-4 text-center">
        <p className="text-xs text-purple-600 mb-1">총 매도액</p>
        <p className="text-lg font-bold text-purple-700">{(summary.totalSold / 10000).toFixed(0)}만원</p>
      </div>
    </div>
  );
}

// 개선된 주문 카드
function OrderCard({
  order,
  onCancel,
  isCancelling
}: {
  order: Order;
  onCancel: (id: number) => void;
  isCancelling: boolean;
}) {
  const isBuy = order.transaction_type === 'buy';
  const isPending = order.status === 'pending' || order.status === 'submitted';

  const getStatusConfig = (status: string) => {
    switch (status) {
      case 'filled':
        return { bg: 'bg-green-100', text: 'text-green-800', label: '체결 완료', icon: '✅' };
      case 'cancelled':
        return { bg: 'bg-gray-100', text: 'text-gray-800', label: '취소됨', icon: '🚫' };
      case 'rejected':
        return { bg: 'bg-red-100', text: 'text-red-800', label: '거부됨', icon: '❌' };
      case 'pending':
        return { bg: 'bg-yellow-100', text: 'text-yellow-800', label: '대기 중', icon: '⏳' };
      case 'submitted':
        return { bg: 'bg-blue-100', text: 'text-blue-800', label: '제출됨', icon: '📤' };
      default:
        return { bg: 'bg-gray-100', text: 'text-gray-800', label: status, icon: '📋' };
    }
  };

  const statusConfig = getStatusConfig(order.status);

  return (
    <div className={`rounded-xl border-2 overflow-hidden transition-all hover:shadow-md ${
      isBuy ? 'border-green-200' : 'border-red-200'
    }`}>
      <div className={`px-4 py-2 ${isBuy ? 'bg-green-50' : 'bg-red-50'}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <span className={`text-lg font-bold ${isBuy ? 'text-green-700' : 'text-red-700'}`}>
              {isBuy ? '📈 매수' : '📉 매도'}
            </span>
            <span className="font-bold text-gray-800">{order.symbol}</span>
          </div>
          <span className={`px-2 py-1 rounded-full text-xs font-medium ${statusConfig.bg} ${statusConfig.text}`}>
            {statusConfig.icon} {statusConfig.label}
          </span>
        </div>
      </div>

      <div className="p-4 bg-white">
        <div className="grid grid-cols-3 gap-4 text-sm">
          <div>
            <p className="text-gray-500 text-xs">수량</p>
            <p className="font-bold text-gray-800">{order.quantity.toLocaleString()}주</p>
          </div>
          <div>
            <p className="text-gray-500 text-xs">가격</p>
            <p className="font-bold text-gray-800">{Number(order.price).toLocaleString()}원</p>
          </div>
          <div>
            <p className="text-gray-500 text-xs">총액</p>
            <p className="font-bold text-gray-800">{Number(order.total_amount).toLocaleString()}원</p>
          </div>
        </div>

        <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-100">
          <span className="text-xs text-gray-400">
            {new Date(order.created_at).toLocaleString('ko-KR')}
          </span>
          {isPending && (
            <button
              onClick={() => onCancel(order.id)}
              disabled={isCancelling}
              className="px-3 py-1 text-xs text-red-600 hover:bg-red-50 rounded-lg transition-colors disabled:opacity-50"
            >
              주문 취소
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// 주문 가이드
function TradingTips() {
  const [showTips, setShowTips] = useState(false);

  return (
    <div className="bg-white rounded-xl border-2 shadow-lg overflow-hidden">
      <div
        className="bg-gradient-to-r from-amber-500 to-orange-500 p-4 cursor-pointer"
        onClick={() => setShowTips(!showTips)}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <span className="text-2xl">💡</span>
            <div>
              <h3 className="font-bold text-white">매매 성공 팁</h3>
              <p className="text-white/80 text-sm">수익을 극대화하는 거래 전략</p>
            </div>
          </div>
          <span className="text-white">{showTips ? '▲' : '▼'}</span>
        </div>
      </div>

      {showTips && (
        <div className="p-5 space-y-4">
          <div className="space-y-3">
            <div className="flex items-start space-x-3 p-3 bg-green-50 rounded-lg">
              <span className="flex-shrink-0 text-xl">✅</span>
              <div>
                <p className="font-medium text-green-800 text-sm">분할 매수/매도</p>
                <p className="text-xs text-green-600">한 번에 전량을 거래하지 말고 2-3회에 나눠서 진행하세요.</p>
              </div>
            </div>

            <div className="flex items-start space-x-3 p-3 bg-blue-50 rounded-lg">
              <span className="flex-shrink-0 text-xl">📊</span>
              <div>
                <p className="font-medium text-blue-800 text-sm">손절매 설정</p>
                <p className="text-xs text-blue-600">매수 전에 반드시 손절 라인(-5~10%)을 정하고 지키세요.</p>
              </div>
            </div>

            <div className="flex items-start space-x-3 p-3 bg-purple-50 rounded-lg">
              <span className="flex-shrink-0 text-xl">🎯</span>
              <div>
                <p className="font-medium text-purple-800 text-sm">목표가 설정</p>
                <p className="text-xs text-purple-600">욕심 부리지 말고 적정 수익률에서 익절하세요.</p>
              </div>
            </div>

            <div className="flex items-start space-x-3 p-3 bg-amber-50 rounded-lg">
              <span className="flex-shrink-0 text-xl">⏰</span>
              <div>
                <p className="font-medium text-amber-800 text-sm">시장 시간 확인</p>
                <p className="text-xs text-amber-600">장 시작/마감 직후 10분은 변동성이 크니 주의하세요.</p>
              </div>
            </div>
          </div>

          <div className="bg-gray-50 rounded-lg p-3">
            <p className="text-xs text-gray-600">
              💬 <strong>기억하세요:</strong> 가장 중요한 것은 원금 보존입니다.
              작은 수익을 여러 번 내는 것이 한 번의 큰 손실보다 낫습니다.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

export default function Trading() {
  const queryClient = useQueryClient();
  const [showOrderForm, setShowOrderForm] = useState(false);
  const [orderForm, setOrderForm] = useState({
    symbol: '',
    side: 'buy' as 'buy' | 'sell',
    quantity: 0,
    price: 0,
  });

  const { data: orders = [] } = useQuery<Order[]>({
    queryKey: ['orders'],
    queryFn: () => tradingApi.listOrders(),
  });

  const { data: signals = [] } = useQuery<TradingSignal[]>({
    queryKey: ['signals'],
    queryFn: () => tradingApi.getSignals({ limit: 10 }),
  });

  const createOrderMutation = useMutation({
    mutationFn: tradingApi.createOrder,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['orders'] });
      setShowOrderForm(false);
      setOrderForm({ symbol: '', side: 'buy', quantity: 0, price: 0 });
    },
  });

  const cancelOrderMutation = useMutation({
    mutationFn: tradingApi.cancelOrder,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['orders'] });
    },
  });

  const handleSubmitOrder = (e: React.FormEvent) => {
    e.preventDefault();
    createOrderMutation.mutate(orderForm);
  };

  const handleQuickOrder = (symbol: string, type: 'buy' | 'sell') => {
    setOrderForm({
      symbol,
      side: type,
      quantity: 0,
      price: 0,
    });
    setShowOrderForm(true);
  };

  const totalAmount = orderForm.quantity * orderForm.price;

  return (
    <div className="space-y-6">
      {/* 헤더 */}
      <div className="bg-gradient-to-r from-blue-600 via-indigo-600 to-violet-600 rounded-2xl p-6 text-white shadow-xl">
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-3xl font-bold flex items-center">
              <span className="mr-3">💹</span>
              실시간 매매
            </h1>
            <p className="text-white/80 mt-2">
              AI 시그널을 참고하여 최적의 타이밍에 매매하세요
            </p>
          </div>
          <button
            onClick={() => setShowOrderForm(true)}
            className="px-6 py-3 bg-white/20 hover:bg-white/30 text-white rounded-xl font-bold transition-all"
          >
            + 새 주문
          </button>
        </div>
      </div>

      {/* Order Form Modal */}
      {showOrderForm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl p-6 w-full max-w-md shadow-2xl">
            <h2 className="text-xl font-bold mb-4 flex items-center">
              <span className="mr-2">{orderForm.side === 'buy' ? '📈' : '📉'}</span>
              {orderForm.side === 'buy' ? '매수' : '매도'} 주문
            </h2>
            <form onSubmit={handleSubmitOrder} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">종목 코드</label>
                <input
                  type="text"
                  value={orderForm.symbol}
                  onChange={(e) => setOrderForm({ ...orderForm, symbol: e.target.value.toUpperCase() })}
                  className="w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:outline-none focus:border-blue-500"
                  placeholder="예: 005930"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">주문 유형</label>
                <div className="grid grid-cols-2 gap-3">
                  <button
                    type="button"
                    onClick={() => setOrderForm({ ...orderForm, side: 'buy' })}
                    className={`py-3 rounded-xl font-bold transition-all ${
                      orderForm.side === 'buy'
                        ? 'bg-green-500 text-white'
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    }`}
                  >
                    📈 매수
                  </button>
                  <button
                    type="button"
                    onClick={() => setOrderForm({ ...orderForm, side: 'sell' })}
                    className={`py-3 rounded-xl font-bold transition-all ${
                      orderForm.side === 'sell'
                        ? 'bg-red-500 text-white'
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    }`}
                  >
                    📉 매도
                  </button>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">수량 (주)</label>
                  <input
                    type="number"
                    value={orderForm.quantity || ''}
                    onChange={(e) => setOrderForm({ ...orderForm, quantity: parseInt(e.target.value) || 0 })}
                    className="w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:outline-none focus:border-blue-500"
                    placeholder="0"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">가격 (원)</label>
                  <input
                    type="number"
                    value={orderForm.price || ''}
                    onChange={(e) => setOrderForm({ ...orderForm, price: parseFloat(e.target.value) || 0 })}
                    className="w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:outline-none focus:border-blue-500"
                    placeholder="0"
                  />
                </div>
              </div>

              {/* 예상 금액 */}
              <div className={`p-4 rounded-xl ${
                orderForm.side === 'buy' ? 'bg-green-50' : 'bg-red-50'
              }`}>
                <div className="flex justify-between items-center">
                  <span className={`text-sm ${
                    orderForm.side === 'buy' ? 'text-green-700' : 'text-red-700'
                  }`}>
                    예상 {orderForm.side === 'buy' ? '매수' : '매도'} 금액
                  </span>
                  <span className={`text-xl font-bold ${
                    orderForm.side === 'buy' ? 'text-green-800' : 'text-red-800'
                  }`}>
                    {totalAmount.toLocaleString()}원
                  </span>
                </div>
              </div>

              <div className="flex space-x-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowOrderForm(false)}
                  className="flex-1 px-4 py-3 text-gray-600 hover:bg-gray-100 rounded-xl font-medium"
                >
                  취소
                </button>
                <button
                  type="submit"
                  disabled={!orderForm.symbol || !orderForm.quantity || !orderForm.price}
                  className={`flex-1 px-4 py-3 text-white rounded-xl font-bold transition-all disabled:opacity-50 ${
                    orderForm.side === 'buy'
                      ? 'bg-gradient-to-r from-green-500 to-emerald-600 hover:from-green-600 hover:to-emerald-700'
                      : 'bg-gradient-to-r from-red-500 to-rose-600 hover:from-red-600 hover:to-rose-700'
                  }`}
                >
                  {orderForm.side === 'buy' ? '매수 주문' : '매도 주문'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 주문 현황 요약 */}
      {orders.length > 0 && <OrderSummary orders={orders} />}

      {/* 시그널 해석 가이드 */}
      <SignalInterpretationGuide />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* AI 시그널 */}
        <div>
          <h2 className="text-xl font-bold text-gray-800 mb-4 flex items-center">
            <span className="mr-2">🤖</span>
            AI 매매 시그널
          </h2>
          {signals && signals.length > 0 ? (
            <div className="space-y-4">
              {signals.map((signal) => (
                <EnhancedSignalCard
                  key={signal.id}
                  signal={signal}
                  onQuickOrder={handleQuickOrder}
                />
              ))}
            </div>
          ) : (
            <div className="bg-white rounded-xl border-2 border-dashed border-gray-300 p-10 text-center">
              <span className="text-5xl mb-4 block">📡</span>
              <p className="text-gray-500 font-medium">아직 시그널이 없습니다</p>
              <p className="text-sm text-gray-400 mt-2">
                AI가 새로운 매매 기회를 발견하면 여기에 표시됩니다
              </p>
            </div>
          )}
        </div>

        {/* 주문 내역 */}
        <div>
          <h2 className="text-xl font-bold text-gray-800 mb-4 flex items-center">
            <span className="mr-2">📋</span>
            내 주문 내역
          </h2>
          {orders && orders.length > 0 ? (
            <div className="space-y-3">
              {orders.map((order) => (
                <OrderCard
                  key={order.id}
                  order={order}
                  onCancel={(id) => cancelOrderMutation.mutate(id)}
                  isCancelling={cancelOrderMutation.isPending}
                />
              ))}
            </div>
          ) : (
            <div className="bg-white rounded-xl border-2 border-dashed border-gray-300 p-10 text-center">
              <span className="text-5xl mb-4 block">📭</span>
              <p className="text-gray-500 font-medium">주문 내역이 없습니다</p>
              <p className="text-sm text-gray-400 mt-2">
                AI 시그널을 참고하여 첫 주문을 해보세요
              </p>
            </div>
          )}

          {/* 매매 팁 */}
          <div className="mt-6">
            <TradingTips />
          </div>
        </div>
      </div>

      {/* 투자 유의사항 */}
      <div className="bg-gradient-to-r from-amber-50 to-orange-50 border-2 border-amber-200 rounded-xl p-5">
        <div className="flex items-start space-x-3">
          <span className="text-2xl">⚠️</span>
          <div>
            <h4 className="font-bold text-amber-800">매매 유의사항</h4>
            <p className="text-sm text-amber-700 mt-1">
              모든 주문은 실제 시장에 제출됩니다. AI 시그널은 참고 정보이며, 최종 투자 판단은 본인 책임입니다.
              투자에는 원금 손실의 위험이 있으므로 신중하게 결정하세요.
              장 운영 시간을 확인하고 주문하시기 바랍니다.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

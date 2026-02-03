import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { portfolioApi } from '../../services/api';

interface PortfolioData {
  id: number;
  name: string;
  description: string | null;
  is_default: boolean;
}

interface HoldingData {
  id: number;
  symbol: string;
  quantity: number;
  avg_buy_price: number;
  current_price: number | null;
  profit_loss: number | null;
  profit_loss_percent: number | null;
}

interface PortfolioDetail {
  id: number;
  name: string;
  description: string | null;
  is_default: boolean;
  holdings: HoldingData[];
  total_value: number;
  total_profit_loss: number;
}

// 포트폴리오 분석 결과 타입
interface PortfolioAnalysis {
  diversificationScore: number;
  riskLevel: 'low' | 'medium' | 'high';
  concentrationRisk: string[];
  recommendations: string[];
  sectorDistribution: { sector: string; percent: number }[];
}

// 포트폴리오 건강도 지표 컴포넌트
function PortfolioHealthCard({ analysis, holdingsCount }: { analysis: PortfolioAnalysis; holdingsCount: number }) {
  const getRiskColor = (level: string) => {
    switch (level) {
      case 'low': return 'text-green-600 bg-green-100';
      case 'medium': return 'text-yellow-600 bg-yellow-100';
      case 'high': return 'text-red-600 bg-red-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  const getRiskLabel = (level: string) => {
    switch (level) {
      case 'low': return '안정적';
      case 'medium': return '보통';
      case 'high': return '높음';
      default: return '분석 필요';
    }
  };

  return (
    <div className="bg-white rounded-xl border-2 shadow-lg overflow-hidden">
      <div className="bg-gradient-to-r from-indigo-600 to-purple-600 p-4">
        <h3 className="font-bold text-white flex items-center">
          <span className="mr-2">📊</span>
          포트폴리오 건강도 분석
        </h3>
        <p className="text-white/70 text-sm mt-1">AI가 분석한 포트폴리오 상태입니다</p>
      </div>

      <div className="p-5 space-y-4">
        {/* 핵심 지표 */}
        <div className="grid grid-cols-3 gap-4">
          <div className="text-center p-3 bg-blue-50 rounded-lg">
            <p className="text-xs text-blue-600 mb-1">분산 점수</p>
            <p className="text-2xl font-bold text-blue-700">{analysis.diversificationScore}</p>
            <p className="text-xs text-blue-500">/100</p>
          </div>
          <div className="text-center p-3 bg-gray-50 rounded-lg">
            <p className="text-xs text-gray-600 mb-1">보유 종목</p>
            <p className="text-2xl font-bold text-gray-700">{holdingsCount}</p>
            <p className="text-xs text-gray-500">개</p>
          </div>
          <div className={`text-center p-3 rounded-lg ${getRiskColor(analysis.riskLevel)}`}>
            <p className="text-xs mb-1 opacity-70">리스크 수준</p>
            <p className="text-2xl font-bold">{getRiskLabel(analysis.riskLevel)}</p>
          </div>
        </div>

        {/* 집중 리스크 경고 */}
        {analysis.concentrationRisk.length > 0 && (
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
            <p className="text-xs font-semibold text-amber-700 mb-2">⚠️ 집중 리스크 경고</p>
            <ul className="space-y-1">
              {analysis.concentrationRisk.map((risk, idx) => (
                <li key={idx} className="text-xs text-amber-600 flex items-start">
                  <span className="mr-1">•</span>
                  {risk}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* 추천 사항 */}
        {analysis.recommendations.length > 0 && (
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
            <p className="text-xs font-semibold text-blue-700 mb-2">💡 수익 최적화 추천</p>
            <ul className="space-y-1">
              {analysis.recommendations.map((rec, idx) => (
                <li key={idx} className="text-xs text-blue-600 flex items-start">
                  <span className="mr-1">•</span>
                  {rec}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

// 투자 전략 가이드 컴포넌트
function InvestmentStrategyGuide({ totalProfitLoss, holdingsCount }: { totalProfitLoss: number; holdingsCount: number }) {
  const [showGuide, setShowGuide] = useState(false);

  const getStrategy = () => {
    if (totalProfitLoss > 0) {
      if (holdingsCount < 5) {
        return {
          status: '수익 중 - 집중 투자',
          color: 'from-green-500 to-emerald-600',
          advice: '현재 수익 중이지만 종목 수가 적어 리스크가 있습니다.',
          actions: [
            '수익 일부 실현하여 리스크 관리',
            '다른 섹터의 우량주로 분산 투자 고려',
            '손절매 라인을 설정하여 수익 보호'
          ]
        };
      }
      return {
        status: '안정적 수익',
        color: 'from-green-500 to-emerald-600',
        advice: '좋은 성과를 보이고 있습니다. 현재 전략을 유지하면서 리밸런싱을 고려하세요.',
        actions: [
          '분기별 리밸런싱으로 비중 조정',
          '목표 수익률 달성 시 부분 익절 고려',
          '신규 투자 기회 탐색 지속'
        ]
      };
    } else if (totalProfitLoss < 0) {
      const lossPercent = Math.abs(totalProfitLoss);
      if (lossPercent > 1000000) {
        return {
          status: '손실 관리 필요',
          color: 'from-red-500 to-rose-600',
          advice: '상당한 손실이 발생했습니다. 전략적 검토가 필요합니다.',
          actions: [
            '각 종목별 손실 원인 분석',
            '회복 가능성 낮은 종목 정리 검토',
            '물타기보다 손절매 원칙 준수',
            '현금 비중 확보 후 재진입 기회 모색'
          ]
        };
      }
      return {
        status: '소폭 손실',
        color: 'from-yellow-500 to-amber-600',
        advice: '일시적 손실일 수 있습니다. 침착하게 대응하세요.',
        actions: [
          '펀더멘털 변화 여부 점검',
          '추가 매수 적정성 검토 (물타기 주의)',
          '시장 전반적 흐름 파악'
        ]
      };
    }
    return {
      status: '시작 단계',
      color: 'from-blue-500 to-indigo-600',
      advice: '포트폴리오를 구성하고 있습니다.',
      actions: [
        '투자 목표와 기간 설정',
        '리스크 허용 범위 결정',
        '분산 투자 원칙 준수'
      ]
    };
  };

  const strategy = getStrategy();

  return (
    <div className="bg-white rounded-xl border-2 shadow-lg overflow-hidden">
      <div
        className={`bg-gradient-to-r ${strategy.color} p-4 cursor-pointer`}
        onClick={() => setShowGuide(!showGuide)}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <span className="text-2xl">🎯</span>
            <div>
              <h3 className="font-bold text-white">{strategy.status}</h3>
              <p className="text-white/80 text-sm">맞춤형 투자 전략 가이드</p>
            </div>
          </div>
          <span className="text-white">{showGuide ? '▲' : '▼'}</span>
        </div>
      </div>

      {showGuide && (
        <div className="p-5 space-y-4">
          <div className="bg-gray-50 rounded-lg p-4">
            <p className="text-sm text-gray-700">{strategy.advice}</p>
          </div>

          <div>
            <h4 className="font-semibold text-gray-800 text-sm mb-2">📋 권장 행동</h4>
            <ul className="space-y-2">
              {strategy.actions.map((action, idx) => (
                <li key={idx} className="flex items-start text-sm text-gray-600">
                  <span className="flex-shrink-0 w-5 h-5 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center text-xs mr-2 mt-0.5">
                    {idx + 1}
                  </span>
                  {action}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}

// 포트폴리오 분배 시각화
function PortfolioDistribution({ holdings }: { holdings: HoldingData[] }) {
  const distribution = useMemo(() => {
    if (holdings.length === 0) return [];

    const totalValue = holdings.reduce((sum, h) => {
      const value = h.current_price ? h.quantity * h.current_price : h.quantity * h.avg_buy_price;
      return sum + value;
    }, 0);

    return holdings
      .map(h => {
        const value = h.current_price ? h.quantity * h.current_price : h.quantity * h.avg_buy_price;
        return {
          symbol: h.symbol,
          value,
          percent: (value / totalValue) * 100,
          profitPercent: h.profit_loss_percent || 0
        };
      })
      .sort((a, b) => b.percent - a.percent);
  }, [holdings]);

  const colors = [
    'bg-blue-500', 'bg-green-500', 'bg-purple-500', 'bg-yellow-500',
    'bg-red-500', 'bg-indigo-500', 'bg-pink-500', 'bg-cyan-500'
  ];

  if (distribution.length === 0) {
    return null;
  }

  return (
    <div className="bg-white rounded-xl border-2 shadow-lg p-5">
      <h3 className="font-bold text-gray-800 mb-4 flex items-center">
        <span className="mr-2">🥧</span>
        포트폴리오 비중
      </h3>

      {/* 시각적 바 차트 */}
      <div className="h-8 rounded-full overflow-hidden flex mb-4">
        {distribution.map((item, idx) => (
          <div
            key={item.symbol}
            className={`${colors[idx % colors.length]} transition-all`}
            style={{ width: `${Math.max(item.percent, 2)}%` }}
            title={`${item.symbol}: ${item.percent.toFixed(1)}%`}
          />
        ))}
      </div>

      {/* 범례 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
        {distribution.map((item, idx) => (
          <div key={item.symbol} className="flex items-center space-x-2 text-sm">
            <span className={`w-3 h-3 rounded-full ${colors[idx % colors.length]}`} />
            <span className="text-gray-700 font-medium">{item.symbol}</span>
            <span className="text-gray-500">{item.percent.toFixed(1)}%</span>
          </div>
        ))}
      </div>

      {/* 집중도 경고 */}
      {distribution.length > 0 && distribution[0].percent > 30 && (
        <div className="mt-4 bg-amber-50 border border-amber-200 rounded-lg p-3">
          <p className="text-xs text-amber-700">
            ⚠️ <strong>{distribution[0].symbol}</strong>이(가) 포트폴리오의 {distribution[0].percent.toFixed(1)}%를 차지합니다.
            단일 종목 비중이 높으면 리스크가 증가합니다.
          </p>
        </div>
      )}
    </div>
  );
}

// 수익률 분석 카드
function ProfitAnalysisCard({ holdings, totalProfitLoss }: { holdings: HoldingData[]; totalProfitLoss: number }) {
  const analysis = useMemo(() => {
    const winners = holdings.filter(h => (h.profit_loss || 0) > 0);
    const losers = holdings.filter(h => (h.profit_loss || 0) < 0);
    const neutral = holdings.filter(h => h.profit_loss === 0 || h.profit_loss === null);

    const bestPerformer = holdings.reduce((best, h) =>
      (h.profit_loss_percent || 0) > (best?.profit_loss_percent || -Infinity) ? h : best
    , holdings[0]);

    const worstPerformer = holdings.reduce((worst, h) =>
      (h.profit_loss_percent || 0) < (worst?.profit_loss_percent || Infinity) ? h : worst
    , holdings[0]);

    return { winners, losers, neutral, bestPerformer, worstPerformer };
  }, [holdings]);

  if (holdings.length === 0) {
    return null;
  }

  return (
    <div className="bg-white rounded-xl border-2 shadow-lg p-5">
      <h3 className="font-bold text-gray-800 mb-4 flex items-center">
        <span className="mr-2">📈</span>
        수익률 분석
      </h3>

      {/* 승/패 현황 */}
      <div className="grid grid-cols-3 gap-4 mb-4">
        <div className="text-center p-3 bg-green-50 rounded-lg">
          <p className="text-xs text-green-600 mb-1">수익 종목</p>
          <p className="text-2xl font-bold text-green-700">{analysis.winners.length}</p>
        </div>
        <div className="text-center p-3 bg-red-50 rounded-lg">
          <p className="text-xs text-red-600 mb-1">손실 종목</p>
          <p className="text-2xl font-bold text-red-700">{analysis.losers.length}</p>
        </div>
        <div className="text-center p-3 bg-gray-50 rounded-lg">
          <p className="text-xs text-gray-600 mb-1">보합</p>
          <p className="text-2xl font-bold text-gray-700">{analysis.neutral.length}</p>
        </div>
      </div>

      {/* 최고/최저 수익 종목 */}
      {analysis.bestPerformer && (
        <div className="grid grid-cols-2 gap-3 mb-4">
          <div className="bg-gradient-to-r from-green-50 to-emerald-50 border border-green-200 rounded-lg p-3">
            <p className="text-xs text-green-600 mb-1">🏆 최고 수익</p>
            <p className="font-bold text-green-800">{analysis.bestPerformer.symbol}</p>
            <p className="text-sm text-green-600">
              +{(analysis.bestPerformer.profit_loss_percent || 0).toFixed(2)}%
            </p>
          </div>
          {analysis.worstPerformer && (
            <div className="bg-gradient-to-r from-red-50 to-rose-50 border border-red-200 rounded-lg p-3">
              <p className="text-xs text-red-600 mb-1">📉 최저 수익</p>
              <p className="font-bold text-red-800">{analysis.worstPerformer.symbol}</p>
              <p className="text-sm text-red-600">
                {(analysis.worstPerformer.profit_loss_percent || 0).toFixed(2)}%
              </p>
            </div>
          )}
        </div>
      )}

      {/* 총 수익 현황 */}
      <div className={`p-4 rounded-lg ${totalProfitLoss >= 0 ? 'bg-green-100' : 'bg-red-100'}`}>
        <div className="flex justify-between items-center">
          <span className={`text-sm ${totalProfitLoss >= 0 ? 'text-green-700' : 'text-red-700'}`}>
            총 평가손익
          </span>
          <span className={`text-xl font-bold ${totalProfitLoss >= 0 ? 'text-green-800' : 'text-red-800'}`}>
            {totalProfitLoss >= 0 ? '+' : ''}{totalProfitLoss.toLocaleString()}원
          </span>
        </div>
      </div>
    </div>
  );
}

// AI 추천 기반 리밸런싱 컴포넌트
function AIRebalancingRecommendation({ holdings, totalValue }: { holdings: HoldingData[]; totalValue: number }) {
  const recommendations = useMemo(() => {
    if (holdings.length === 0) return [];

    const recs: Array<{
      symbol: string;
      currentPercent: number;
      targetPercent: number;
      action: 'increase' | 'decrease' | 'hold';
      reason: string;
      priority: 'high' | 'medium' | 'low';
    }> = [];

    const weights = holdings.map(h => {
      const value = h.current_price ? h.quantity * h.current_price : h.quantity * h.avg_buy_price;
      return { symbol: h.symbol, value, percent: (value / totalValue) * 100, profitPercent: h.profit_loss_percent || 0 };
    });

    weights.forEach(w => {
      // 집중도 기반 추천
      if (w.percent > 30) {
        recs.push({
          symbol: w.symbol,
          currentPercent: w.percent,
          targetPercent: 20,
          action: 'decrease',
          reason: `비중이 ${w.percent.toFixed(1)}%로 과도합니다. 20% 이하로 분산을 권장합니다.`,
          priority: 'high'
        });
      } else if (w.percent > 25) {
        recs.push({
          symbol: w.symbol,
          currentPercent: w.percent,
          targetPercent: 20,
          action: 'decrease',
          reason: `비중이 높은 편입니다. 부분 익절을 고려하세요.`,
          priority: 'medium'
        });
      }

      // 수익률 기반 추천
      if (w.profitPercent > 30) {
        if (!recs.find(r => r.symbol === w.symbol)) {
          recs.push({
            symbol: w.symbol,
            currentPercent: w.percent,
            targetPercent: w.percent * 0.7,
            action: 'decrease',
            reason: `${w.profitPercent.toFixed(1)}% 수익 중. 30% 부분 익절로 수익 확정을 권장합니다.`,
            priority: 'medium'
          });
        }
      } else if (w.profitPercent < -15) {
        recs.push({
          symbol: w.symbol,
          currentPercent: w.percent,
          targetPercent: 0,
          action: 'decrease',
          reason: `${Math.abs(w.profitPercent).toFixed(1)}% 손실 중. 손절 또는 비중 축소를 검토하세요.`,
          priority: 'high'
        });
      }
    });

    // 분산 부족 시 추천
    if (holdings.length < 5 && holdings.length > 0) {
      recs.push({
        symbol: '신규 종목',
        currentPercent: 0,
        targetPercent: 15,
        action: 'increase',
        reason: `보유 종목이 ${holdings.length}개로 부족합니다. AI Council에서 추천 종목을 확인하세요.`,
        priority: 'medium'
      });
    }

    return recs.sort((a, b) => {
      const priorityOrder = { high: 0, medium: 1, low: 2 };
      return priorityOrder[a.priority] - priorityOrder[b.priority];
    });
  }, [holdings, totalValue]);

  if (recommendations.length === 0) {
    return (
      <div className="bg-white rounded-xl border-2 shadow-lg p-5">
        <div className="flex items-center space-x-3 mb-4">
          <span className="text-2xl">🤖</span>
          <div>
            <h3 className="font-bold text-gray-800">AI 리밸런싱 추천</h3>
            <p className="text-sm text-gray-500">현재 포트폴리오가 균형 잡혀 있습니다</p>
          </div>
        </div>
        <div className="bg-green-50 border border-green-200 rounded-lg p-4 text-center">
          <span className="text-3xl mb-2 block">✅</span>
          <p className="text-green-700 font-medium">리밸런싱이 필요하지 않습니다</p>
          <p className="text-sm text-green-600 mt-1">현재 자산 배분이 적절합니다</p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border-2 shadow-lg overflow-hidden">
      <div className="bg-gradient-to-r from-violet-600 to-purple-600 p-4">
        <div className="flex items-center space-x-3">
          <span className="text-2xl">🤖</span>
          <div>
            <h3 className="font-bold text-white">AI 리밸런싱 추천</h3>
            <p className="text-white/80 text-sm">3개 AI 분석 기반 포트폴리오 최적화 제안</p>
          </div>
        </div>
      </div>

      <div className="p-5 space-y-3">
        {recommendations.map((rec, idx) => (
          <div
            key={idx}
            className={`rounded-lg p-4 border-2 ${
              rec.priority === 'high' ? 'bg-red-50 border-red-200' :
              rec.priority === 'medium' ? 'bg-amber-50 border-amber-200' :
              'bg-blue-50 border-blue-200'
            }`}
          >
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center space-x-2">
                <span className={`px-2 py-1 rounded-full text-xs font-bold ${
                  rec.priority === 'high' ? 'bg-red-200 text-red-800' :
                  rec.priority === 'medium' ? 'bg-amber-200 text-amber-800' :
                  'bg-blue-200 text-blue-800'
                }`}>
                  {rec.priority === 'high' ? '긴급' : rec.priority === 'medium' ? '권장' : '참고'}
                </span>
                <span className="font-bold text-gray-800">{rec.symbol}</span>
              </div>
              <span className={`text-xl ${
                rec.action === 'decrease' ? 'text-red-500' :
                rec.action === 'increase' ? 'text-green-500' : 'text-gray-500'
              }`}>
                {rec.action === 'decrease' ? '📉' : rec.action === 'increase' ? '📈' : '➡️'}
              </span>
            </div>
            <p className="text-sm text-gray-700">{rec.reason}</p>
            {rec.currentPercent > 0 && (
              <div className="mt-2 flex items-center space-x-2 text-xs">
                <span className="text-gray-500">현재: {rec.currentPercent.toFixed(1)}%</span>
                <span>→</span>
                <span className="font-medium text-gray-700">목표: {rec.targetPercent.toFixed(1)}%</span>
              </div>
            )}
          </div>
        ))}

        <a
          href="/council"
          className="block mt-4 text-center py-3 bg-gradient-to-r from-violet-500 to-purple-600 text-white rounded-xl font-bold hover:from-violet-600 hover:to-purple-700 transition-all"
        >
          🏛️ AI Council에서 추천 종목 확인하기
        </a>
      </div>
    </div>
  );
}

// 리밸런싱 가이드
function RebalancingGuide() {
  const [showGuide, setShowGuide] = useState(false);

  return (
    <div className="bg-white rounded-xl border-2 shadow-lg overflow-hidden">
      <div
        className="bg-gradient-to-r from-cyan-600 to-blue-600 p-4 cursor-pointer"
        onClick={() => setShowGuide(!showGuide)}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <span className="text-2xl">⚖️</span>
            <div>
              <h3 className="font-bold text-white">포트폴리오 리밸런싱 가이드</h3>
              <p className="text-white/80 text-sm">최적의 자산 배분을 유지하는 방법</p>
            </div>
          </div>
          <span className="text-white">{showGuide ? '▲' : '▼'}</span>
        </div>
      </div>

      {showGuide && (
        <div className="p-5 space-y-4">
          <div className="bg-blue-50 rounded-lg p-4">
            <h4 className="font-semibold text-blue-800 mb-2">📚 리밸런싱이란?</h4>
            <p className="text-sm text-blue-700">
              시장 변동으로 인해 변화한 자산 비중을 원래 목표한 비율로 되돌리는 것입니다.
              이를 통해 리스크를 관리하고 '고점 매도, 저점 매수'를 자동으로 실현할 수 있습니다.
            </p>
          </div>

          <div className="space-y-3">
            <h4 className="font-semibold text-gray-800">🔄 리밸런싱 원칙</h4>

            <div className="flex items-start space-x-3 p-3 bg-gray-50 rounded-lg">
              <span className="flex-shrink-0 w-6 h-6 bg-indigo-100 text-indigo-600 rounded-full flex items-center justify-center text-xs font-bold">1</span>
              <div>
                <p className="font-medium text-gray-800 text-sm">주기적 리밸런싱</p>
                <p className="text-xs text-gray-600">분기마다 또는 반기마다 정기적으로 비중을 점검합니다.</p>
              </div>
            </div>

            <div className="flex items-start space-x-3 p-3 bg-gray-50 rounded-lg">
              <span className="flex-shrink-0 w-6 h-6 bg-indigo-100 text-indigo-600 rounded-full flex items-center justify-center text-xs font-bold">2</span>
              <div>
                <p className="font-medium text-gray-800 text-sm">임계점 리밸런싱</p>
                <p className="text-xs text-gray-600">특정 종목이 목표 비중에서 5% 이상 벗어나면 조정합니다.</p>
              </div>
            </div>

            <div className="flex items-start space-x-3 p-3 bg-gray-50 rounded-lg">
              <span className="flex-shrink-0 w-6 h-6 bg-indigo-100 text-indigo-600 rounded-full flex items-center justify-center text-xs font-bold">3</span>
              <div>
                <p className="font-medium text-gray-800 text-sm">세금 효율성 고려</p>
                <p className="text-xs text-gray-600">매도 차익에 대한 세금을 고려하여 신규 자금 투입으로 조정합니다.</p>
              </div>
            </div>
          </div>

          <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
            <p className="text-xs text-amber-700">
              💡 <strong>팁:</strong> 거래 비용과 세금을 고려할 때, 소폭의 비중 변화는 무시하고
              5% 이상의 편차가 발생했을 때만 리밸런싱하는 것이 효율적입니다.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

// 개선된 보유 종목 테이블
function HoldingsTable({ holdings }: { holdings: HoldingData[] }) {
  const [sortField, setSortField] = useState<'symbol' | 'profit_loss_percent'>('profit_loss_percent');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');

  const sortedHoldings = useMemo(() => {
    return [...holdings].sort((a, b) => {
      let aVal = sortField === 'symbol' ? a.symbol : (a.profit_loss_percent || 0);
      let bVal = sortField === 'symbol' ? b.symbol : (b.profit_loss_percent || 0);

      if (typeof aVal === 'string') {
        return sortDir === 'asc' ? aVal.localeCompare(bVal as string) : (bVal as string).localeCompare(aVal);
      }
      return sortDir === 'asc' ? (aVal as number) - (bVal as number) : (bVal as number) - (aVal as number);
    });
  }, [holdings, sortField, sortDir]);

  const toggleSort = (field: 'symbol' | 'profit_loss_percent') => {
    if (sortField === field) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDir('desc');
    }
  };

  if (holdings.length === 0) {
    return (
      <div className="text-center py-10 text-gray-500">
        <span className="text-4xl mb-3 block">📭</span>
        <p>보유 종목이 없습니다</p>
        <p className="text-sm">종목을 매수하면 여기에 표시됩니다</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full">
        <thead>
          <tr className="bg-gray-50">
            <th
              className="text-left py-3 px-4 text-sm font-semibold text-gray-600 cursor-pointer hover:text-gray-900"
              onClick={() => toggleSort('symbol')}
            >
              종목명 {sortField === 'symbol' && (sortDir === 'asc' ? '↑' : '↓')}
            </th>
            <th className="text-right py-3 px-4 text-sm font-semibold text-gray-600">수량</th>
            <th className="text-right py-3 px-4 text-sm font-semibold text-gray-600">평균단가</th>
            <th className="text-right py-3 px-4 text-sm font-semibold text-gray-600">현재가</th>
            <th className="text-right py-3 px-4 text-sm font-semibold text-gray-600">평가금액</th>
            <th
              className="text-right py-3 px-4 text-sm font-semibold text-gray-600 cursor-pointer hover:text-gray-900"
              onClick={() => toggleSort('profit_loss_percent')}
            >
              수익률 {sortField === 'profit_loss_percent' && (sortDir === 'asc' ? '↑' : '↓')}
            </th>
          </tr>
        </thead>
        <tbody>
          {sortedHoldings.map((holding) => {
            const currentValue = holding.current_price
              ? holding.quantity * holding.current_price
              : holding.quantity * holding.avg_buy_price;
            const profitPercent = holding.profit_loss_percent || 0;
            const isProfit = profitPercent >= 0;

            return (
              <tr key={holding.id} className="border-b border-gray-100 hover:bg-gray-50 transition-colors">
                <td className="py-4 px-4">
                  <div className="flex items-center space-x-2">
                    <span className={`w-2 h-2 rounded-full ${isProfit ? 'bg-green-500' : 'bg-red-500'}`} />
                    <span className="font-bold text-gray-900">{holding.symbol}</span>
                  </div>
                </td>
                <td className="py-4 px-4 text-right font-medium text-gray-700">
                  {holding.quantity.toLocaleString()}주
                </td>
                <td className="py-4 px-4 text-right text-gray-600">
                  {Number(holding.avg_buy_price).toLocaleString()}원
                </td>
                <td className="py-4 px-4 text-right font-medium text-gray-700">
                  {holding.current_price ? `${Number(holding.current_price).toLocaleString()}원` : '-'}
                </td>
                <td className="py-4 px-4 text-right font-medium text-gray-900">
                  {currentValue.toLocaleString()}원
                </td>
                <td className="py-4 px-4 text-right">
                  <div className="flex flex-col items-end">
                    <span className={`font-bold ${isProfit ? 'text-green-600' : 'text-red-600'}`}>
                      {isProfit ? '+' : ''}{profitPercent.toFixed(2)}%
                    </span>
                    {holding.profit_loss && (
                      <span className={`text-xs ${isProfit ? 'text-green-500' : 'text-red-500'}`}>
                        {isProfit ? '+' : ''}{holding.profit_loss.toLocaleString()}원
                      </span>
                    )}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default function Portfolio() {
  const queryClient = useQueryClient();
  const [selectedPortfolio, setSelectedPortfolio] = useState<number | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newPortfolioName, setNewPortfolioName] = useState('');

  const { data: portfolios } = useQuery<PortfolioData[]>({
    queryKey: ['portfolios'],
    queryFn: portfolioApi.list,
  });

  const { data: portfolioDetail } = useQuery<PortfolioDetail>({
    queryKey: ['portfolio', selectedPortfolio],
    queryFn: () => portfolioApi.get(selectedPortfolio!),
    enabled: !!selectedPortfolio,
  });

  const createMutation = useMutation({
    mutationFn: (name: string) => portfolioApi.create({ name }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['portfolios'] });
      setShowCreateForm(false);
      setNewPortfolioName('');
    },
  });

  // 포트폴리오 분석 계산
  const portfolioAnalysis = useMemo((): PortfolioAnalysis => {
    if (!portfolioDetail || portfolioDetail.holdings.length === 0) {
      return {
        diversificationScore: 0,
        riskLevel: 'high',
        concentrationRisk: ['보유 종목이 없습니다'],
        recommendations: ['종목을 추가하여 포트폴리오를 구성하세요'],
        sectorDistribution: []
      };
    }

    const holdings = portfolioDetail.holdings;
    const totalValue = holdings.reduce((sum, h) => {
      const value = h.current_price ? h.quantity * h.current_price : h.quantity * h.avg_buy_price;
      return sum + value;
    }, 0);

    // 비중 계산
    const weights = holdings.map(h => {
      const value = h.current_price ? h.quantity * h.current_price : h.quantity * h.avg_buy_price;
      return value / totalValue;
    });

    // 분산 점수 (HHI 기반, 반대로)
    const hhi = weights.reduce((sum, w) => sum + w * w, 0);
    const diversificationScore = Math.round((1 - hhi) * 100);

    // 리스크 레벨
    let riskLevel: 'low' | 'medium' | 'high' = 'medium';
    if (holdings.length < 3 || Math.max(...weights) > 0.5) {
      riskLevel = 'high';
    } else if (holdings.length >= 7 && Math.max(...weights) < 0.25) {
      riskLevel = 'low';
    }

    // 집중 리스크 식별
    const concentrationRisk: string[] = [];
    holdings.forEach((h, idx) => {
      if (weights[idx] > 0.3) {
        concentrationRisk.push(`${h.symbol}의 비중이 ${(weights[idx] * 100).toFixed(1)}%로 높습니다`);
      }
    });
    if (holdings.length < 5) {
      concentrationRisk.push(`보유 종목이 ${holdings.length}개로 분산이 부족합니다`);
    }

    // 추천 사항
    const recommendations: string[] = [];
    if (holdings.length < 5) {
      recommendations.push('최소 5개 이상의 종목으로 분산 투자를 권장합니다');
    }
    if (Math.max(...weights) > 0.3) {
      recommendations.push('단일 종목 비중을 30% 이하로 조정하세요');
    }
    const losers = holdings.filter(h => (h.profit_loss_percent || 0) < -10);
    if (losers.length > 0) {
      recommendations.push(`${losers.map(h => h.symbol).join(', ')} 종목의 손절 여부를 검토하세요`);
    }
    const winners = holdings.filter(h => (h.profit_loss_percent || 0) > 20);
    if (winners.length > 0) {
      recommendations.push(`${winners.map(h => h.symbol).join(', ')} 종목의 일부 익절을 고려하세요`);
    }

    return {
      diversificationScore,
      riskLevel,
      concentrationRisk,
      recommendations,
      sectorDistribution: []
    };
  }, [portfolioDetail]);

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    if (newPortfolioName.trim()) {
      createMutation.mutate(newPortfolioName);
    }
  };

  return (
    <div className="space-y-6">
      {/* 헤더 */}
      <div className="bg-gradient-to-r from-emerald-600 via-teal-600 to-cyan-600 rounded-2xl p-6 text-white shadow-xl">
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-3xl font-bold flex items-center">
              <span className="mr-3">💼</span>
              포트폴리오 관리
            </h1>
            <p className="text-white/80 mt-2">
              AI가 분석한 최적의 포트폴리오 전략으로 수익을 극대화하세요
            </p>
          </div>
          <button
            onClick={() => setShowCreateForm(true)}
            className="px-6 py-3 bg-white/20 hover:bg-white/30 text-white rounded-xl font-medium transition-all"
          >
            + 새 포트폴리오
          </button>
        </div>
      </div>

      {/* Create Form Modal */}
      {showCreateForm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 w-full max-w-md shadow-2xl">
            <h2 className="text-xl font-bold mb-4 flex items-center">
              <span className="mr-2">📁</span>
              새 포트폴리오 생성
            </h2>
            <form onSubmit={handleCreate}>
              <input
                type="text"
                value={newPortfolioName}
                onChange={(e) => setNewPortfolioName(e.target.value)}
                placeholder="포트폴리오 이름"
                className="w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:outline-none focus:border-emerald-500"
              />
              <div className="mt-4 flex justify-end space-x-3">
                <button
                  type="button"
                  onClick={() => setShowCreateForm(false)}
                  className="px-5 py-2 text-gray-600 hover:bg-gray-100 rounded-xl"
                >
                  취소
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 bg-emerald-600 text-white rounded-xl hover:bg-emerald-700"
                >
                  생성
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Portfolio List */}
        <div className="lg:col-span-1">
          <div className="bg-white rounded-xl border-2 shadow-lg p-5">
            <h2 className="text-lg font-bold text-gray-800 mb-4 flex items-center">
              <span className="mr-2">📂</span>
              내 포트폴리오
            </h2>
            {portfolios && portfolios.length > 0 ? (
              <div className="space-y-2">
                {portfolios.map((portfolio) => (
                  <button
                    key={portfolio.id}
                    onClick={() => setSelectedPortfolio(portfolio.id)}
                    className={`w-full text-left p-4 rounded-xl transition-all ${
                      selectedPortfolio === portfolio.id
                        ? 'bg-emerald-100 border-2 border-emerald-500 shadow-md'
                        : 'bg-gray-50 hover:bg-gray-100 border-2 border-transparent'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <p className="font-bold text-gray-800">{portfolio.name}</p>
                      {portfolio.is_default && (
                        <span className="text-xs bg-emerald-200 text-emerald-700 px-2 py-1 rounded-full">기본</span>
                      )}
                    </div>
                  </button>
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-gray-500">
                <span className="text-3xl mb-2 block">📭</span>
                <p>포트폴리오가 없습니다</p>
                <p className="text-sm">새 포트폴리오를 생성하세요</p>
              </div>
            )}
          </div>

          {/* 리밸런싱 가이드 */}
          <div className="mt-6">
            <RebalancingGuide />
          </div>
        </div>

        {/* Portfolio Detail */}
        <div className="lg:col-span-3 space-y-6">
          {portfolioDetail ? (
            <>
              {/* 포트폴리오 요약 */}
              <div className="bg-white rounded-xl border-2 shadow-lg p-6">
                <div className="flex justify-between items-start mb-6">
                  <div>
                    <h2 className="text-2xl font-bold text-gray-900 flex items-center">
                      <span className="mr-2">💼</span>
                      {portfolioDetail.name}
                    </h2>
                    {portfolioDetail.description && (
                      <p className="text-gray-500 mt-1">{portfolioDetail.description}</p>
                    )}
                  </div>
                  <div className="text-right">
                    <p className="text-sm text-gray-500">총 평가금액</p>
                    <p className="text-3xl font-bold text-gray-900">
                      {portfolioDetail.total_value.toLocaleString()}원
                    </p>
                    <p className={`text-lg font-semibold ${
                      portfolioDetail.total_profit_loss >= 0 ? 'text-green-600' : 'text-red-600'
                    }`}>
                      {portfolioDetail.total_profit_loss >= 0 ? '+' : ''}
                      {portfolioDetail.total_profit_loss.toLocaleString()}원
                    </p>
                  </div>
                </div>

                {/* 보유 종목 테이블 */}
                <HoldingsTable holdings={portfolioDetail.holdings} />
              </div>

              {/* 분석 카드들 */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* 포트폴리오 건강도 */}
                <PortfolioHealthCard
                  analysis={portfolioAnalysis}
                  holdingsCount={portfolioDetail.holdings.length}
                />

                {/* 수익률 분석 */}
                <ProfitAnalysisCard
                  holdings={portfolioDetail.holdings}
                  totalProfitLoss={portfolioDetail.total_profit_loss}
                />
              </div>

              {/* 포트폴리오 비중 */}
              <PortfolioDistribution holdings={portfolioDetail.holdings} />

              {/* AI 리밸런싱 추천 */}
              <AIRebalancingRecommendation
                holdings={portfolioDetail.holdings}
                totalValue={portfolioDetail.total_value}
              />

              {/* 투자 전략 가이드 */}
              <InvestmentStrategyGuide
                totalProfitLoss={portfolioDetail.total_profit_loss}
                holdingsCount={portfolioDetail.holdings.length}
              />
            </>
          ) : (
            <div className="bg-white rounded-xl border-2 shadow-lg p-16 text-center">
              <span className="text-6xl mb-4 block">📊</span>
              <p className="text-xl text-gray-500 font-medium">포트폴리오를 선택하세요</p>
              <p className="text-gray-400 mt-2">좌측에서 포트폴리오를 선택하면 상세 정보가 표시됩니다</p>
            </div>
          )}
        </div>
      </div>

      {/* 투자 유의사항 */}
      <div className="bg-gradient-to-r from-amber-50 to-orange-50 border-2 border-amber-200 rounded-xl p-5">
        <div className="flex items-start space-x-3">
          <span className="text-2xl">⚠️</span>
          <div>
            <h4 className="font-bold text-amber-800">포트폴리오 관리 안내</h4>
            <p className="text-sm text-amber-700 mt-1">
              AI 분석 결과는 참고용이며, 실제 투자 결정은 본인의 판단에 따라 신중하게 이루어져야 합니다.
              분산 투자와 정기적인 리밸런싱을 통해 리스크를 관리하시기 바랍니다.
              과거 성과가 미래 수익을 보장하지 않습니다.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

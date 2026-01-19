import { useState, useEffect, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { analysisApi, stocksApi, analysisWebSocket } from '../../services/api';

// AI 분석가 정보 - 각 AI의 분석 방법론과 전문 분야
const AI_ANALYSTS = {
  gemini: {
    name: 'Gemini',
    role: '뉴스/심리 분석가',
    icon: '📰',
    color: 'purple',
    methodology: ['뉴스 헤드라인 감성 분석', '소셜 미디어 트렌드', '시장 심리 지표', '이벤트 기반 분석'],
    strengths: ['빠른 뉴스 반응', '대중 심리 파악', '이슈 분석'],
    interpretation: {
      high: '긍정적 뉴스와 시장 심리가 매수 기회를 시사합니다',
      medium: '뉴스 흐름이 중립적이며 관망이 필요합니다',
      low: '부정적 뉴스와 불안한 심리가 감지됩니다'
    }
  },
  chatgpt: {
    name: 'GPT',
    role: '퀀트/기술적 분석가',
    icon: '📊',
    color: 'green',
    methodology: ['기술적 지표 분석 (RSI, MACD, 볼린저밴드)', '차트 패턴 인식', '거래량 분석', '모멘텀 분석'],
    strengths: ['정확한 진입점 파악', '추세 분석', '리스크 관리'],
    interpretation: {
      high: '기술적 지표가 강한 매수 신호를 보여줍니다',
      medium: '기술적 지표가 혼조세이며 추가 확인이 필요합니다',
      low: '기술적 지표가 과매수 또는 하락 신호를 보여줍니다'
    }
  },
  claude: {
    name: 'Claude',
    role: '펀더멘털 분석가',
    icon: '📈',
    color: 'orange',
    methodology: ['재무제표 심층 분석', '밸류에이션 (PER, PBR, EV/EBITDA)', '산업 분석', '경쟁력 평가'],
    strengths: ['장기 가치 판단', '기업 본질 분석', '안전마진 계산'],
    interpretation: {
      high: '기업의 펀더멘털이 우수하며 적정 가치 대비 저평가 상태입니다',
      medium: '펀더멘털이 양호하나 밸류에이션이 적정 수준입니다',
      low: '펀더멘털 약화 또는 고평가 상태로 주의가 필요합니다'
    }
  },
  ml: {
    name: 'ML Engine',
    role: '머신러닝 예측',
    icon: '🤖',
    color: 'blue',
    methodology: ['패턴 인식 딥러닝', '시계열 예측 모델', '다변량 회귀 분석', '앙상블 기법'],
    strengths: ['객관적 예측', '빅데이터 처리', '숨겨진 패턴 발견'],
    interpretation: {
      high: 'ML 모델이 높은 확률로 상승을 예측합니다',
      medium: 'ML 모델의 예측 신뢰도가 중간 수준입니다',
      low: 'ML 모델이 하락 가능성을 감지했습니다'
    }
  }
};

// 분석 유형별 설명
const ANALYSIS_TYPES = {
  news: {
    name: '뉴스 분석',
    description: '최신 뉴스와 시장 심리를 분석하여 단기적인 주가 방향성을 예측합니다.',
    indicators: ['뉴스 감성 점수', '기사 빈도', '키워드 트렌드', '소셜 버즈'],
    timeframe: '단기 (1-7일)'
  },
  quant: {
    name: '퀀트 분석',
    description: '기술적 지표와 통계적 모델을 활용하여 매매 타이밍을 분석합니다.',
    indicators: ['RSI', 'MACD', '볼린저밴드', '이동평균선', '거래량'],
    timeframe: '단기-중기 (1-30일)'
  },
  fundamental: {
    name: '펀더멘털 분석',
    description: '기업의 재무 건전성과 내재 가치를 분석하여 장기 투자 가치를 평가합니다.',
    indicators: ['PER', 'PBR', 'ROE', 'EPS 성장률', '부채비율'],
    timeframe: '중기-장기 (1개월-1년)'
  },
  technical: {
    name: '기술적 분석',
    description: '차트 패턴과 가격 흐름을 분석하여 추세와 지지/저항선을 파악합니다.',
    indicators: ['추세선', '패턴', '지지/저항', '피보나치', '일목균형표'],
    timeframe: '단기-중기 (1-30일)'
  }
};

interface AnalysisResult {
  agent: string;
  analysis_type: string;
  symbol: string;
  score: number | null;
  summary: string;
  recommendation: 'buy' | 'hold' | 'sell' | null;
  confidence: number;
  analyzed_at: string;
  details?: Record<string, unknown>;
}

interface ConsolidatedAnalysis {
  symbol: string;
  final_score: number;
  recommendation: string;
  confidence: number;
  signal_generated: boolean;
  agent_results: {
    news?: AnalysisResult;
    quant?: AnalysisResult;
    fundamental?: AnalysisResult;
    technical?: AnalysisResult;
  };
  summary: string;
  analyzed_at: string;
}

interface AnalysisHistory {
  id: number;
  symbol: string;
  analysis_type: string;
  agent_name: string;
  score: number | null;
  summary: string;
  recommendation: string | null;
  created_at: string;
}

interface TaskStatus {
  task_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  result?: ConsolidatedAnalysis;
  error?: string;
}

interface PriceData {
  close: number;
  change_percent: number;
}

// 분석 이해 가이드 컴포넌트
function AnalysisGuide({ onClose }: { onClose: () => void }) {
  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl max-w-4xl max-h-[90vh] overflow-auto">
        <div className="sticky top-0 bg-gradient-to-r from-indigo-600 to-purple-600 text-white p-6 rounded-t-2xl">
          <div className="flex justify-between items-center">
            <h2 className="text-2xl font-bold">AI 분석 가이드</h2>
            <button onClick={onClose} className="p-2 hover:bg-white hover:bg-opacity-20 rounded-lg">
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          <p className="mt-2 opacity-90">4개의 AI가 협력하여 종합적인 투자 분석을 제공합니다</p>
        </div>

        <div className="p-6 space-y-6">
          {/* 점수 해석 */}
          <div>
            <h3 className="text-lg font-bold text-gray-900 mb-3">📊 점수 해석 방법</h3>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
              {[
                { range: '+50 ~ +100', label: '강력 매수', color: 'bg-green-500' },
                { range: '+20 ~ +49', label: '매수', color: 'bg-green-400' },
                { range: '-19 ~ +19', label: '중립', color: 'bg-gray-400' },
                { range: '-49 ~ -20', label: '매도', color: 'bg-red-400' },
                { range: '-100 ~ -50', label: '강력 매도', color: 'bg-red-500' },
              ].map((item) => (
                <div key={item.range} className="text-center p-3 bg-gray-50 rounded-lg">
                  <div className={`w-8 h-8 ${item.color} rounded-full mx-auto mb-2`} />
                  <p className="text-sm font-bold">{item.label}</p>
                  <p className="text-xs text-gray-500">{item.range}</p>
                </div>
              ))}
            </div>
          </div>

          {/* AI 분석가 소개 */}
          <div>
            <h3 className="text-lg font-bold text-gray-900 mb-3">🤖 AI 분석가 팀</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {Object.entries(AI_ANALYSTS).map(([key, ai]) => (
                <div key={key} className={`p-4 rounded-lg border-l-4 border-${ai.color}-500 bg-${ai.color}-50`}>
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-2xl">{ai.icon}</span>
                    <div>
                      <h4 className="font-bold">{ai.name}</h4>
                      <p className="text-sm text-gray-600">{ai.role}</p>
                    </div>
                  </div>
                  <div className="text-sm text-gray-700">
                    <p className="font-medium mb-1">분석 방법:</p>
                    <div className="flex flex-wrap gap-1">
                      {ai.methodology.slice(0, 3).map((m, i) => (
                        <span key={i} className="px-2 py-0.5 bg-white rounded text-xs">{m}</span>
                      ))}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* 분석 유형 */}
          <div>
            <h3 className="text-lg font-bold text-gray-900 mb-3">📈 분석 유형별 설명</h3>
            <div className="space-y-3">
              {Object.entries(ANALYSIS_TYPES).map(([key, type]) => (
                <div key={key} className="p-4 bg-gray-50 rounded-lg">
                  <div className="flex justify-between items-start mb-2">
                    <h4 className="font-bold text-gray-900">{type.name}</h4>
                    <span className="text-xs px-2 py-1 bg-blue-100 text-blue-700 rounded">{type.timeframe}</span>
                  </div>
                  <p className="text-sm text-gray-600 mb-2">{type.description}</p>
                  <div className="flex flex-wrap gap-1">
                    {type.indicators.map((indicator, i) => (
                      <span key={i} className="text-xs px-2 py-1 bg-white border rounded">{indicator}</span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* 신뢰도 설명 */}
          <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
            <h3 className="font-bold text-yellow-800 mb-2">💡 신뢰도(Confidence)란?</h3>
            <p className="text-sm text-yellow-700">
              신뢰도는 AI 분석의 확신 정도를 나타냅니다. 높은 신뢰도(70% 이상)는 분석 데이터가 충분하고
              일관된 결과를 보일 때 부여됩니다. 낮은 신뢰도의 경우 추가 확인이 필요할 수 있습니다.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

// 종합 점수 해석 컴포넌트
function ScoreInterpretation({ score, confidence }: {
  score: number;
  confidence: number;
  recommendation: string;
}) {
  const getInterpretation = () => {
    if (score >= 50) {
      return {
        title: '강력 매수 신호',
        description: '모든 AI 분석가들이 긍정적인 의견을 보이고 있습니다. 기술적, 펀더멘털, 뉴스 분석이 일치하여 상승 가능성이 높습니다.',
        action: '매수 포지션 진입을 고려해보세요. 단, 적절한 손절가를 설정하세요.',
        color: 'green'
      };
    } else if (score >= 20) {
      return {
        title: '매수 우위',
        description: '대체로 긍정적인 분석 결과입니다. 일부 불확실성이 있지만 상승 가능성이 더 높게 평가됩니다.',
        action: '분할 매수를 고려하거나, 추가 확인 후 진입하세요.',
        color: 'green'
      };
    } else if (score >= -20) {
      return {
        title: '중립 / 관망',
        description: 'AI 분석가들의 의견이 엇갈리고 있습니다. 뚜렷한 방향성이 보이지 않습니다.',
        action: '새로운 매수는 보류하고, 기존 포지션은 유지하면서 상황을 지켜보세요.',
        color: 'gray'
      };
    } else if (score >= -50) {
      return {
        title: '매도 우위',
        description: '부정적인 분석 결과가 우세합니다. 하락 위험이 상승 가능성보다 높게 평가됩니다.',
        action: '보유 중이라면 일부 이익 실현을 고려하세요. 신규 매수는 자제하세요.',
        color: 'red'
      };
    } else {
      return {
        title: '강력 매도 신호',
        description: '모든 AI 분석가들이 부정적인 의견을 보이고 있습니다. 하락 위험이 매우 높습니다.',
        action: '리스크 관리를 최우선으로 하세요. 손절 또는 헤지를 고려하세요.',
        color: 'red'
      };
    }
  };

  const interpretation = getInterpretation();
  const confidenceLevel = confidence >= 70 ? '높음' : confidence >= 40 ? '보통' : '낮음';

  return (
    <div className={`p-4 rounded-lg border-l-4 border-${interpretation.color}-500 bg-${interpretation.color}-50`}>
      <div className="flex items-start justify-between mb-2">
        <h4 className={`font-bold text-${interpretation.color}-700`}>{interpretation.title}</h4>
        <span className={`text-xs px-2 py-1 rounded-full ${
          confidenceLevel === '높음' ? 'bg-green-100 text-green-700' :
          confidenceLevel === '보통' ? 'bg-yellow-100 text-yellow-700' :
          'bg-red-100 text-red-700'
        }`}>
          신뢰도 {confidenceLevel}
        </span>
      </div>
      <p className={`text-sm text-${interpretation.color}-600 mb-2`}>{interpretation.description}</p>
      <div className="flex items-center gap-2 text-sm">
        <span className="font-medium">💡 권장 행동:</span>
        <span className="text-gray-700">{interpretation.action}</span>
      </div>
    </div>
  );
}

// 개별 분석 결과 상세 카드
function DetailedAnalysisCard({ result, type }: { result: AnalysisResult; type: string }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const analyst = AI_ANALYSTS[result.agent as keyof typeof AI_ANALYSTS] || AI_ANALYSTS.ml;
  const analysisType = ANALYSIS_TYPES[type as keyof typeof ANALYSIS_TYPES] || ANALYSIS_TYPES.technical;

  const getScoreLevel = (score: number | null) => {
    if (score === null) return 'medium';
    if (score >= 30) return 'high';
    if (score <= -30) return 'low';
    return 'medium';
  };

  const scoreLevel = getScoreLevel(result.score);
  const interpretation = analyst.interpretation[scoreLevel];

  return (
    <div className={`bg-white rounded-xl shadow-sm border hover:shadow-md transition-all overflow-hidden`}>
      {/* 헤더 */}
      <div className={`p-4 bg-gradient-to-r from-${analyst.color}-500 to-${analyst.color}-600`}>
        <div className="flex items-center justify-between text-white">
          <div className="flex items-center gap-3">
            <span className="text-3xl">{analyst.icon}</span>
            <div>
              <h4 className="font-bold text-lg">{analysisType.name}</h4>
              <p className="text-sm opacity-90">{analyst.name} - {analyst.role}</p>
            </div>
          </div>
          <div className="text-right">
            <div className="text-3xl font-bold">
              {result.score !== null ? (result.score >= 0 ? '+' : '') + result.score.toFixed(0) : '-'}
            </div>
            <div className={`px-2 py-1 rounded text-xs font-medium ${
              result.recommendation === 'buy' ? 'bg-green-200 text-green-800' :
              result.recommendation === 'sell' ? 'bg-red-200 text-red-800' :
              'bg-gray-200 text-gray-800'
            }`}>
              {result.recommendation === 'buy' ? '매수' :
               result.recommendation === 'sell' ? '매도' : '보유'}
            </div>
          </div>
        </div>
      </div>

      {/* 본문 */}
      <div className="p-4">
        {/* 점수 바 */}
        <div className="mb-4">
          <div className="flex justify-between text-xs text-gray-500 mb-1">
            <span>매도 (-100)</span>
            <span>중립 (0)</span>
            <span>매수 (+100)</span>
          </div>
          <div className="h-3 bg-gradient-to-r from-red-300 via-gray-300 to-green-300 rounded-full relative">
            <div
              className="absolute w-4 h-4 bg-white border-2 border-gray-800 rounded-full -top-0.5 transform -translate-x-1/2"
              style={{ left: `${((result.score || 0) + 100) / 2}%` }}
            />
          </div>
        </div>

        {/* AI 해석 */}
        <div className="p-3 bg-gray-50 rounded-lg mb-3">
          <p className="text-sm text-gray-700">
            <span className="font-medium">🤖 AI 해석: </span>
            {interpretation}
          </p>
        </div>

        {/* 요약 */}
        <p className="text-sm text-gray-600 mb-3">{result.summary}</p>

        {/* 신뢰도 */}
        <div className="flex items-center justify-between text-sm">
          <span className="text-gray-500">신뢰도</span>
          <div className="flex items-center gap-2">
            <div className="w-24 h-2 bg-gray-200 rounded-full">
              <div
                className={`h-full rounded-full ${
                  result.confidence >= 70 ? 'bg-green-500' :
                  result.confidence >= 40 ? 'bg-yellow-500' : 'bg-red-500'
                }`}
                style={{ width: `${result.confidence}%` }}
              />
            </div>
            <span className="font-medium">{result.confidence?.toFixed(0)}%</span>
          </div>
        </div>

        {/* 확장 정보 */}
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="mt-3 w-full text-center text-sm text-blue-600 hover:text-blue-800"
        >
          {isExpanded ? '간략히 보기 ▲' : '상세 보기 ▼'}
        </button>

        {isExpanded && (
          <div className="mt-3 pt-3 border-t space-y-3">
            <div>
              <h5 className="text-sm font-medium text-gray-700 mb-2">분석 방법론</h5>
              <div className="flex flex-wrap gap-1">
                {analyst.methodology.map((m, i) => (
                  <span key={i} className="text-xs px-2 py-1 bg-gray-100 rounded">{m}</span>
                ))}
              </div>
            </div>
            <div>
              <h5 className="text-sm font-medium text-gray-700 mb-2">주요 지표</h5>
              <div className="flex flex-wrap gap-1">
                {analysisType.indicators.map((ind, i) => (
                  <span key={i} className="text-xs px-2 py-1 bg-blue-50 text-blue-700 rounded">{ind}</span>
                ))}
              </div>
            </div>
            <div className="text-xs text-gray-500">
              분석 유효 기간: {analysisType.timeframe}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// 분석 비교 차트 컴포넌트
function AnalysisComparisonChart({ results }: { results: ConsolidatedAnalysis['agent_results'] }) {
  const analysisData = useMemo(() => {
    return Object.entries(results)
      .filter(([_, v]) => v !== undefined)
      .map(([type, result]) => ({
        type,
        name: ANALYSIS_TYPES[type as keyof typeof ANALYSIS_TYPES]?.name || type,
        score: result?.score || 0,
        confidence: result?.confidence || 0,
        recommendation: result?.recommendation
      }));
  }, [results]);

  return (
    <div className="bg-white rounded-xl shadow p-6">
      <h3 className="text-lg font-bold text-gray-900 mb-4">📊 분석 결과 비교</h3>

      <div className="space-y-4">
        {analysisData.map((item) => (
          <div key={item.type} className="space-y-1">
            <div className="flex justify-between items-center">
              <span className="text-sm font-medium text-gray-700">{item.name}</span>
              <div className="flex items-center gap-2">
                <span className={`text-sm font-bold ${
                  item.score >= 20 ? 'text-green-600' :
                  item.score <= -20 ? 'text-red-600' : 'text-gray-600'
                }`}>
                  {item.score >= 0 ? '+' : ''}{item.score}
                </span>
                <span className={`text-xs px-2 py-0.5 rounded ${
                  item.recommendation === 'buy' ? 'bg-green-100 text-green-700' :
                  item.recommendation === 'sell' ? 'bg-red-100 text-red-700' :
                  'bg-gray-100 text-gray-700'
                }`}>
                  {item.recommendation === 'buy' ? '매수' :
                   item.recommendation === 'sell' ? '매도' : '보유'}
                </span>
              </div>
            </div>
            <div className="h-6 bg-gray-100 rounded-full relative overflow-hidden">
              {/* 중앙선 */}
              <div className="absolute left-1/2 top-0 bottom-0 w-0.5 bg-gray-300" />
              {/* 점수 바 */}
              <div
                className={`absolute top-0 bottom-0 ${item.score >= 0 ? 'bg-green-400' : 'bg-red-400'}`}
                style={{
                  left: item.score >= 0 ? '50%' : `${50 + item.score / 2}%`,
                  width: `${Math.abs(item.score) / 2}%`
                }}
              />
              {/* 신뢰도 표시 */}
              <div
                className="absolute top-1/2 -translate-y-1/2 w-2 h-2 bg-gray-800 rounded-full"
                style={{ left: `${(item.score + 100) / 2}%` }}
                title={`신뢰도: ${item.confidence}%`}
              />
            </div>
          </div>
        ))}
      </div>

      {/* 범례 */}
      <div className="mt-4 pt-4 border-t flex justify-center gap-6 text-xs text-gray-500">
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 bg-green-400 rounded" />
          <span>긍정적 (매수)</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 bg-red-400 rounded" />
          <span>부정적 (매도)</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-2 h-2 bg-gray-800 rounded-full" />
          <span>현재 점수</span>
        </div>
      </div>
    </div>
  );
}

// 투자 전략 제안 컴포넌트
function InvestmentStrategyCard({ analysis, currentPrice }: {
  analysis: ConsolidatedAnalysis;
  currentPrice: PriceData | undefined;
}) {
  const strategy = useMemo(() => {
    const score = analysis.final_score;
    const confidence = analysis.confidence;
    const price = currentPrice?.close || 0;

    if (score >= 50 && confidence >= 60) {
      return {
        type: '적극 매수',
        icon: '🚀',
        color: 'green',
        description: '강한 상승 신호와 높은 신뢰도를 바탕으로 적극적인 매수 전략을 제안합니다.',
        actions: [
          `목표 비중: 포트폴리오의 10-15%`,
          `진입가: 현재가 ${price.toLocaleString()}원 부근`,
          `1차 목표가: ${Math.round(price * 1.1).toLocaleString()}원 (+10%)`,
          `손절가: ${Math.round(price * 0.95).toLocaleString()}원 (-5%)`
        ],
        riskLevel: '중간'
      };
    } else if (score >= 20 && confidence >= 50) {
      return {
        type: '분할 매수',
        icon: '📈',
        color: 'green',
        description: '긍정적 신호가 있으나 확실성이 높지 않아 분할 매수를 권장합니다.',
        actions: [
          `목표 비중: 포트폴리오의 5-10%`,
          `1차 매수: 현재가에서 50%`,
          `2차 매수: -3% 하락 시 나머지 50%`,
          `손절가: ${Math.round(price * 0.92).toLocaleString()}원 (-8%)`
        ],
        riskLevel: '중간'
      };
    } else if (score >= -20) {
      return {
        type: '관망',
        icon: '👀',
        color: 'gray',
        description: '뚜렷한 방향성이 없어 신규 진입을 보류하고 상황을 지켜보세요.',
        actions: [
          '신규 매수 보류',
          '기존 보유분은 유지',
          '다음 분석 결과 확인 필요',
          '뉴스 및 시장 상황 모니터링'
        ],
        riskLevel: '낮음'
      };
    } else if (score >= -50) {
      return {
        type: '일부 매도',
        icon: '📉',
        color: 'red',
        description: '하락 위험이 감지되어 보유분 일부 정리를 권장합니다.',
        actions: [
          '보유분의 30-50% 매도 고려',
          `손절가: ${Math.round(price * 0.95).toLocaleString()}원 (-5%)`,
          '추가 매수 금지',
          '시장 상황 주시'
        ],
        riskLevel: '높음'
      };
    } else {
      return {
        type: '전량 매도',
        icon: '🔴',
        color: 'red',
        description: '강한 하락 신호가 감지되어 리스크 관리를 최우선으로 하세요.',
        actions: [
          '보유분 전량 매도 고려',
          '손실 최소화 우선',
          '반등 시에도 재진입 신중',
          '현금 비중 확대'
        ],
        riskLevel: '매우 높음'
      };
    }
  }, [analysis, currentPrice]);

  return (
    <div className={`bg-gradient-to-br from-${strategy.color}-50 to-white rounded-xl shadow p-6 border border-${strategy.color}-200`}>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <span className="text-4xl">{strategy.icon}</span>
          <div>
            <h3 className="text-xl font-bold text-gray-900">{strategy.type}</h3>
            <span className={`text-xs px-2 py-1 rounded-full ${
              strategy.riskLevel === '낮음' ? 'bg-green-100 text-green-700' :
              strategy.riskLevel === '중간' ? 'bg-yellow-100 text-yellow-700' :
              'bg-red-100 text-red-700'
            }`}>
              리스크: {strategy.riskLevel}
            </span>
          </div>
        </div>
      </div>

      <p className="text-gray-600 mb-4">{strategy.description}</p>

      <div className="space-y-2">
        <h4 className="font-medium text-gray-800">💡 권장 행동</h4>
        <ul className="space-y-1">
          {strategy.actions.map((action, i) => (
            <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
              <span className="text-blue-500">•</span>
              {action}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

export default function AnalysisPanel() {
  const queryClient = useQueryClient();
  const [selectedSymbol, setSelectedSymbol] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [activeTab, setActiveTab] = useState<'result' | 'history'>('result');
  const [taskId, setTaskId] = useState<string | null>(null);
  const [wsConnected, setWsConnected] = useState(false);
  const [showGuide, setShowGuide] = useState(false);

  // Search stocks
  const { data: searchResults } = useQuery({
    queryKey: ['stocks', 'search', searchInput],
    queryFn: () => stocksApi.list({ limit: 10 }),
    enabled: searchInput.length >= 2,
  });

  // Fetch consolidated analysis for selected symbol
  const { data: consolidatedAnalysis, refetch: refetchAnalysis } = useQuery<ConsolidatedAnalysis>({
    queryKey: ['analysis', 'consolidated', selectedSymbol],
    queryFn: () => analysisApi.getConsolidated(selectedSymbol),
    enabled: !!selectedSymbol,
  });

  // Fetch analysis history
  const { data: analysisHistory } = useQuery<AnalysisHistory[]>({
    queryKey: ['analysis', 'history', selectedSymbol],
    queryFn: () => analysisApi.getHistory(selectedSymbol, undefined, 20),
    enabled: !!selectedSymbol && activeTab === 'history',
  });

  // Fetch current price
  const { data: currentPrice } = useQuery<PriceData>({
    queryKey: ['price', selectedSymbol],
    queryFn: () => stocksApi.getRealtimePrice(selectedSymbol),
    enabled: !!selectedSymbol,
    refetchInterval: 10000,
  });

  // Poll task status
  const { data: taskStatus } = useQuery<TaskStatus>({
    queryKey: ['analysis', 'task', taskId],
    queryFn: () => analysisApi.getTaskStatus(taskId!),
    enabled: !!taskId,
    refetchInterval: (query) => {
      const data = query.state.data as TaskStatus | undefined;
      if (data?.status === 'completed' || data?.status === 'failed') {
        return false;
      }
      return 2000;
    },
  });

  // Run quick analysis mutation
  const quickAnalysisMutation = useMutation({
    mutationFn: (symbol: string) => analysisApi.runQuickAnalysis(symbol),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['analysis', 'consolidated', selectedSymbol] });
      queryClient.invalidateQueries({ queryKey: ['analysis', 'history', selectedSymbol] });
    },
  });

  // Request background analysis mutation
  const backgroundAnalysisMutation = useMutation({
    mutationFn: (symbol: string) => analysisApi.requestBackgroundAnalysis(symbol),
    onSuccess: (data) => {
      setTaskId(data.task_id);
    },
  });

  // Run full analysis mutation
  const fullAnalysisMutation = useMutation({
    mutationFn: (symbol: string) => analysisApi.runFullAnalysis(symbol, {
      analysis_types: ['news', 'quant', 'fundamental', 'technical'],
      save_to_db: true,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['analysis', 'consolidated', selectedSymbol] });
      queryClient.invalidateQueries({ queryKey: ['analysis', 'history', selectedSymbol] });
    },
  });

  // Handle task completion
  useEffect(() => {
    if (taskStatus?.status === 'completed') {
      queryClient.invalidateQueries({ queryKey: ['analysis', 'consolidated', selectedSymbol] });
      queryClient.invalidateQueries({ queryKey: ['analysis', 'history', selectedSymbol] });
      setTaskId(null);
    }
  }, [taskStatus, selectedSymbol, queryClient]);

  // WebSocket connection
  useEffect(() => {
    if (!selectedSymbol) return;

    const ws = analysisWebSocket.connect();

    ws.onopen = () => {
      setWsConnected(true);
      analysisWebSocket.subscribeSymbol(ws, selectedSymbol);
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'analysis_update' && data.symbol === selectedSymbol) {
        refetchAnalysis();
      }
    };

    ws.onclose = () => setWsConnected(false);
    ws.onerror = () => setWsConnected(false);

    const pingInterval = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        analysisWebSocket.ping(ws);
      }
    }, 30000);

    return () => {
      clearInterval(pingInterval);
      ws.close();
    };
  }, [selectedSymbol, refetchAnalysis]);

  const handleSymbolSelect = (symbol: string) => {
    setSelectedSymbol(symbol);
    setSearchInput('');
  };

  const getScoreColor = (score: number | null) => {
    if (score === null) return 'text-gray-500';
    if (score >= 50) return 'text-green-600';
    if (score >= 20) return 'text-green-500';
    if (score >= -20) return 'text-gray-600';
    if (score >= -50) return 'text-red-500';
    return 'text-red-600';
  };

  // getScoreBgColor is kept for potential future use
  const _getScoreBgColor = (score: number | null) => {
    if (score === null) return 'bg-gray-100';
    if (score >= 50) return 'bg-green-100';
    if (score >= 20) return 'bg-green-50';
    if (score >= -20) return 'bg-gray-50';
    if (score >= -50) return 'bg-red-50';
    return 'bg-red-100';
  };
  void _getScoreBgColor; // Silence unused warning

  const getRecommendationBadge = (rec: string | null) => {
    switch (rec) {
      case 'buy':
        return <span className="px-3 py-1 bg-green-100 text-green-800 rounded-full font-bold">매수</span>;
      case 'sell':
        return <span className="px-3 py-1 bg-red-100 text-red-800 rounded-full font-bold">매도</span>;
      case 'hold':
        return <span className="px-3 py-1 bg-yellow-100 text-yellow-800 rounded-full font-bold">보유</span>;
      default:
        return <span className="px-3 py-1 bg-gray-100 text-gray-800 rounded-full">-</span>;
    }
  };

  const getAgentIcon = (agent: string) => {
    switch (agent) {
      case 'gemini':
        return (
          <div className="w-8 h-8 rounded-full bg-purple-100 flex items-center justify-center">
            <span className="text-purple-600 font-bold text-xs">G</span>
          </div>
        );
      case 'chatgpt':
        return (
          <div className="w-8 h-8 rounded-full bg-green-100 flex items-center justify-center">
            <span className="text-green-600 font-bold text-xs">C</span>
          </div>
        );
      case 'claude':
        return (
          <div className="w-8 h-8 rounded-full bg-orange-100 flex items-center justify-center">
            <span className="text-orange-600 font-bold text-xs">CL</span>
          </div>
        );
      case 'ml':
        return (
          <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center">
            <span className="text-blue-600 font-bold text-xs">ML</span>
          </div>
        );
      default:
        return (
          <div className="w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center">
            <span className="text-gray-600 font-bold text-xs">?</span>
          </div>
        );
    }
  };

  const isAnalyzing = quickAnalysisMutation.isPending ||
    backgroundAnalysisMutation.isPending ||
    fullAnalysisMutation.isPending ||
    !!(taskId && taskStatus?.status !== 'completed' && taskStatus?.status !== 'failed');

  return (
    <div className="space-y-6">
      {/* 분석 가이드 모달 */}
      {showGuide && <AnalysisGuide onClose={() => setShowGuide(false)} />}

      {/* Header */}
      <div className="bg-gradient-to-r from-indigo-600 to-purple-600 rounded-2xl p-6 text-white">
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-2xl font-bold">🔬 AI 종목 분석</h1>
            <p className="text-indigo-100 mt-2">
              4개의 AI 에이전트가 뉴스, 기술적, 펀더멘털, 퀀트 분석을 종합하여 투자 인사이트를 제공합니다
            </p>
            <div className="flex flex-wrap gap-2 mt-4">
              {Object.values(AI_ANALYSTS).slice(0, 4).map((ai) => (
                <span key={ai.name} className="px-3 py-1 bg-white bg-opacity-20 rounded-full text-sm">
                  {ai.icon} {ai.name}
                </span>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowGuide(true)}
              className="px-4 py-2 bg-white bg-opacity-20 hover:bg-opacity-30 rounded-lg text-sm font-medium"
            >
              📖 분석 가이드
            </button>
            <span className={`flex items-center text-sm px-3 py-1 rounded-full ${
              wsConnected ? 'bg-green-400 bg-opacity-30' : 'bg-gray-400 bg-opacity-30'
            }`}>
              <span className={`w-2 h-2 rounded-full mr-2 ${
                wsConnected ? 'bg-green-400 animate-pulse' : 'bg-gray-400'
              }`} />
              {wsConnected ? '실시간 연결' : '오프라인'}
            </span>
          </div>
        </div>
      </div>

      {/* Search */}
      <div className="relative">
        <div className="flex space-x-3">
          <div className="flex-1 relative">
            <input
              type="text"
              value={searchInput || selectedSymbol}
              onChange={(e) => {
                setSearchInput(e.target.value.toUpperCase());
                if (e.target.value === '') setSelectedSymbol('');
              }}
              placeholder="종목 코드를 입력하세요 (예: 005930)"
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            />
            {searchInput && searchResults && (
              <div className="absolute z-10 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-60 overflow-auto">
                {searchResults.map((stock: { symbol: string; name: string; market: string }) => (
                  <button
                    key={stock.symbol}
                    onClick={() => handleSymbolSelect(stock.symbol)}
                    className="w-full px-4 py-2 text-left hover:bg-gray-50 flex justify-between items-center"
                  >
                    <span className="font-medium">{stock.symbol}</span>
                    <span className="text-sm text-gray-500">{stock.name}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Analysis Buttons */}
          <button
            onClick={() => quickAnalysisMutation.mutate(selectedSymbol)}
            disabled={!selectedSymbol || isAnalyzing}
            className="px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed font-medium"
          >
            빠른 분석
          </button>
          <button
            onClick={() => fullAnalysisMutation.mutate(selectedSymbol)}
            disabled={!selectedSymbol || isAnalyzing}
            className="px-4 py-3 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:bg-gray-300 disabled:cursor-not-allowed font-medium"
          >
            전체 분석
          </button>
          <button
            onClick={() => backgroundAnalysisMutation.mutate(selectedSymbol)}
            disabled={!selectedSymbol || isAnalyzing}
            className="px-4 py-3 bg-gray-600 text-white rounded-lg hover:bg-gray-700 disabled:bg-gray-300 disabled:cursor-not-allowed font-medium"
          >
            백그라운드
          </button>
        </div>
      </div>

      {/* Current Price */}
      {selectedSymbol && currentPrice && (
        <div className="bg-white rounded-lg shadow p-4 flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <div>
              <h2 className="text-xl font-bold text-gray-900">{selectedSymbol}</h2>
              <p className="text-sm text-gray-500">실시간 시세</p>
            </div>
          </div>
          <div className="text-right">
            <p className="text-2xl font-bold text-gray-900">
              {currentPrice.close?.toLocaleString()}원
            </p>
            <p className={`text-sm font-medium ${currentPrice.change_percent >= 0 ? 'text-red-600' : 'text-blue-600'}`}>
              {currentPrice.change_percent >= 0 ? '+' : ''}{currentPrice.change_percent?.toFixed(2)}%
            </p>
          </div>
        </div>
      )}

      {/* Loading / Task Status */}
      {isAnalyzing && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <div className="flex items-center">
            <svg className="animate-spin h-5 w-5 text-blue-600 mr-3" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
            </svg>
            <div>
              <p className="text-blue-800 font-medium">
                {taskId ? `분석 진행 중... (${taskStatus?.status || 'pending'})` : '분석 실행 중...'}
              </p>
              <p className="text-blue-600 text-sm">
                AI 에이전트가 {selectedSymbol} 종목을 분석하고 있습니다
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Tabs */}
      {selectedSymbol && (
        <div className="flex space-x-4 border-b">
          <button
            onClick={() => setActiveTab('result')}
            className={`pb-2 px-1 font-medium border-b-2 transition-colors ${
              activeTab === 'result'
                ? 'border-primary-600 text-primary-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            분석 결과
          </button>
          <button
            onClick={() => setActiveTab('history')}
            className={`pb-2 px-1 font-medium border-b-2 transition-colors ${
              activeTab === 'history'
                ? 'border-primary-600 text-primary-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            분석 히스토리
          </button>
        </div>
      )}

      {/* Analysis Result */}
      {activeTab === 'result' && consolidatedAnalysis && (
        <div className="space-y-6">
          {/* Final Score Card */}
          <div className={`rounded-2xl shadow-lg overflow-hidden`}>
            <div className={`p-6 bg-gradient-to-r ${
              consolidatedAnalysis.final_score >= 50 ? 'from-green-500 to-emerald-600' :
              consolidatedAnalysis.final_score >= 20 ? 'from-green-400 to-teal-500' :
              consolidatedAnalysis.final_score >= -20 ? 'from-gray-400 to-gray-500' :
              consolidatedAnalysis.final_score >= -50 ? 'from-orange-400 to-red-500' :
              'from-red-500 to-red-600'
            } text-white`}>
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-lg font-medium opacity-90">AI 종합 분석 점수</h3>
                  <p className="text-6xl font-bold mt-2">
                    {consolidatedAnalysis.final_score >= 0 ? '+' : ''}{consolidatedAnalysis.final_score?.toFixed(1)}
                  </p>
                  <div className="flex items-center gap-3 mt-3">
                    <span className={`px-4 py-2 rounded-lg text-sm font-bold ${
                      consolidatedAnalysis.recommendation === 'buy' ? 'bg-green-200 text-green-800' :
                      consolidatedAnalysis.recommendation === 'sell' ? 'bg-red-200 text-red-800' :
                      'bg-gray-200 text-gray-800'
                    }`}>
                      {consolidatedAnalysis.recommendation === 'buy' ? '🚀 매수 추천' :
                       consolidatedAnalysis.recommendation === 'sell' ? '📉 매도 추천' : '⏸️ 보유 유지'}
                    </span>
                    {consolidatedAnalysis.signal_generated && (
                      <span className="px-3 py-1 bg-white bg-opacity-20 rounded-lg text-sm">
                        ✨ 시그널 생성됨
                      </span>
                    )}
                  </div>
                </div>
                <div className="text-right">
                  <div className="mb-2">
                    <span className="text-sm opacity-80">신뢰도</span>
                    <div className="flex items-center gap-2 mt-1">
                      <div className="w-32 h-3 bg-white bg-opacity-30 rounded-full">
                        <div
                          className="h-full bg-white rounded-full"
                          style={{ width: `${consolidatedAnalysis.confidence}%` }}
                        />
                      </div>
                      <span className="font-bold">{consolidatedAnalysis.confidence?.toFixed(0)}%</span>
                    </div>
                  </div>
                  <p className="text-xs opacity-70 mt-3">
                    분석: {new Date(consolidatedAnalysis.analyzed_at).toLocaleString()}
                  </p>
                </div>
              </div>
            </div>

            {/* Summary with interpretation */}
            <div className="p-6 bg-white">
              <p className="text-gray-700 mb-4">{consolidatedAnalysis.summary}</p>
              <ScoreInterpretation
                score={consolidatedAnalysis.final_score}
                confidence={consolidatedAnalysis.confidence}
                recommendation={consolidatedAnalysis.recommendation}
              />
            </div>
          </div>

          {/* Analysis Comparison Chart */}
          <AnalysisComparisonChart results={consolidatedAnalysis.agent_results} />

          {/* Investment Strategy */}
          <InvestmentStrategyCard
            analysis={consolidatedAnalysis}
            currentPrice={currentPrice}
          />

          {/* Agent Results Grid */}
          <div>
            <h3 className="text-lg font-bold text-gray-900 mb-4">🤖 AI 에이전트별 상세 분석</h3>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {(['news', 'quant', 'fundamental', 'technical'] as const).map((type) => {
                const result = consolidatedAnalysis.agent_results[type];
                if (!result) return null;

                return (
                  <DetailedAnalysisCard key={type} result={result} type={type} />
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* Analysis History */}
      {activeTab === 'history' && (
        <div className="bg-white rounded-lg shadow">
          {analysisHistory && analysisHistory.length > 0 ? (
            <div className="divide-y">
              {analysisHistory.map((item) => (
                <div key={item.id} className="p-4 hover:bg-gray-50">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center space-x-3">
                      {getAgentIcon(item.agent_name)}
                      <div>
                        <div className="flex items-center space-x-2">
                          <span className="font-medium text-gray-900">{item.analysis_type}</span>
                          <span className="text-xs px-2 py-0.5 bg-gray-100 text-gray-600 rounded">
                            {item.agent_name}
                          </span>
                        </div>
                        <p className="text-sm text-gray-600 mt-1 line-clamp-2">{item.summary}</p>
                        <p className="text-xs text-gray-400 mt-1">
                          {new Date(item.created_at).toLocaleString()}
                        </p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className={`text-lg font-bold ${getScoreColor(item.score)}`}>
                        {item.score !== null ? (item.score >= 0 ? '+' : '') + item.score : '-'}
                      </p>
                      {getRecommendationBadge(item.recommendation)}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-12 text-gray-500">
              <svg className="w-12 h-12 mx-auto mb-4 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <p>분석 히스토리가 없습니다</p>
            </div>
          )}
        </div>
      )}

      {/* Empty State */}
      {!selectedSymbol && (
        <div className="space-y-6">
          {/* 분석 유형 설명 */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {Object.entries(ANALYSIS_TYPES).map(([key, type]) => (
              <div key={key} className="bg-white rounded-xl shadow-sm p-5 hover:shadow-md transition-shadow">
                <div className="flex items-center gap-3 mb-3">
                  <span className="text-2xl">
                    {key === 'news' ? '📰' : key === 'quant' ? '📊' : key === 'fundamental' ? '📈' : '📉'}
                  </span>
                  <div>
                    <h3 className="font-bold text-gray-900">{type.name}</h3>
                    <span className="text-xs text-blue-600">{type.timeframe}</span>
                  </div>
                </div>
                <p className="text-sm text-gray-600 mb-3">{type.description}</p>
                <div className="flex flex-wrap gap-1">
                  {type.indicators.slice(0, 3).map((ind, i) => (
                    <span key={i} className="text-xs px-2 py-0.5 bg-gray-100 rounded">{ind}</span>
                  ))}
                </div>
              </div>
            ))}
          </div>

          {/* 종목 선택 안내 */}
          <div className="bg-white rounded-2xl shadow p-8 text-center">
            <div className="w-20 h-20 mx-auto mb-4 bg-indigo-100 rounded-full flex items-center justify-center">
              <svg className="w-10 h-10 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </div>
            <h3 className="text-xl font-bold text-gray-900 mb-2">분석할 종목을 선택하세요</h3>
            <p className="text-gray-500 mb-6 max-w-md mx-auto">
              종목 코드를 입력하면 4개의 AI 에이전트가 뉴스, 기술적, 펀더멘털, 퀀트 분석을
              종합하여 투자 인사이트를 제공합니다.
            </p>

            <div className="mb-6">
              <p className="text-sm text-gray-500 mb-3">인기 종목으로 시작하기</p>
              <div className="flex justify-center flex-wrap gap-3">
                {[
                  { symbol: '005930', name: '삼성전자' },
                  { symbol: '000660', name: 'SK하이닉스' },
                  { symbol: '035420', name: 'NAVER' },
                  { symbol: '035720', name: '카카오' },
                  { symbol: '005380', name: '현대자동차' },
                  { symbol: '051910', name: 'LG화학' }
                ].map((stock) => (
                  <button
                    key={stock.symbol}
                    onClick={() => handleSymbolSelect(stock.symbol)}
                    className="px-4 py-2 bg-gradient-to-r from-indigo-500 to-purple-500 text-white rounded-lg hover:from-indigo-600 hover:to-purple-600 text-sm font-medium transition-all"
                  >
                    {stock.name}
                    <span className="ml-1 opacity-70">({stock.symbol})</span>
                  </button>
                ))}
              </div>
            </div>

            {/* 분석 프로세스 설명 */}
            <div className="bg-gray-50 rounded-xl p-6 text-left max-w-2xl mx-auto">
              <h4 className="font-bold text-gray-900 mb-4 text-center">🔄 AI 분석 프로세스</h4>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                {[
                  { step: 1, title: '데이터 수집', desc: '실시간 시세, 뉴스, 재무정보 수집' },
                  { step: 2, title: 'AI 분석', desc: '4개 AI가 각자의 전문 영역 분석' },
                  { step: 3, title: '종합 평가', desc: '모든 분석을 종합하여 점수화' },
                  { step: 4, title: '전략 제안', desc: '분석 기반 투자 전략 제시' }
                ].map((item) => (
                  <div key={item.step} className="text-center">
                    <div className="w-10 h-10 mx-auto mb-2 bg-indigo-500 text-white rounded-full flex items-center justify-center font-bold">
                      {item.step}
                    </div>
                    <h5 className="font-medium text-gray-900 text-sm">{item.title}</h5>
                    <p className="text-xs text-gray-500">{item.desc}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 투자 경고 */}
      <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
        <div className="flex items-start gap-3">
          <span className="text-amber-500 text-xl">⚠️</span>
          <div>
            <h4 className="font-bold text-amber-800">투자 주의사항</h4>
            <p className="text-sm text-amber-700 mt-1">
              본 AI 분석은 투자 참고 자료이며, 투자 결정은 본인의 판단과 책임 하에 이루어져야 합니다.
              과거 데이터 기반 분석이 미래 수익을 보장하지 않으며, 모든 투자에는 원금 손실 위험이 있습니다.
              분산 투자와 리스크 관리를 권장합니다.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

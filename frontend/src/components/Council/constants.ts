// AI 분석가 정보 - 각 AI의 역할과 분석 방법론 설명
export const AI_ANALYSTS = {
  gemini_judge: {
    name: 'Sonnet',
    role: '뉴스 트리거',
    icon: '🔔',
    color: 'blue',
    bgColor: 'bg-blue-50',
    borderColor: 'border-blue-200',
    textColor: 'text-blue-700',
    gradientFrom: 'from-blue-500',
    gradientTo: 'to-blue-600',
    description: '실시간 뉴스를 분석하여 투자 회의를 소집합니다.',
    methodology: [
      '뉴스 헤드라인 감성 분석',
      '종목 연관도 평가',
      '시장 영향도 점수 산정',
      '이벤트 드리븐 투자 기회 포착'
    ],
    strengths: ['빠른 뉴스 대응', '감성 분석', '이벤트 분석'],
    avatar: '📰'
  },
  gpt_quant: {
    name: 'GPT',
    role: '퀀트/기술적 분석가',
    icon: '📊',
    color: 'green',
    bgColor: 'bg-green-50',
    borderColor: 'border-green-200',
    textColor: 'text-green-700',
    gradientFrom: 'from-green-500',
    gradientTo: 'to-green-600',
    description: '기술적 지표와 수학적 모델로 매매 타이밍을 분석합니다.',
    methodology: [
      'RSI, MACD, Bollinger Bands 등 기술적 지표',
      '이동평균선 교차 분석',
      '거래량 패턴 및 가격 모멘텀 분석',
      '통계적 아비트라지 기회 탐색'
    ],
    strengths: ['정밀한 진입/청산 타이밍', '리스크 수치화', '패턴 인식'],
    avatar: '🧮'
  },
  claude_fundamental: {
    name: 'Claude',
    role: '펀더멘털 분석가',
    icon: '📈',
    color: 'purple',
    bgColor: 'bg-purple-50',
    borderColor: 'border-purple-200',
    textColor: 'text-purple-700',
    gradientFrom: 'from-purple-500',
    gradientTo: 'to-purple-600',
    description: '기업의 재무제표와 내재가치를 분석하여 장기 투자 가치를 평가합니다.',
    methodology: [
      'PER, PBR, ROE 등 가치평가 지표 분석',
      '재무제표 심층 분석 (수익성, 안정성, 성장성)',
      '산업 경쟁력 및 해자(Moat) 분석',
      'DCF 및 상대가치 평가 모델'
    ],
    strengths: ['기업 내재가치 평가', '장기 투자 관점', '리스크 분석'],
    avatar: '📚'
  },
  gpt_devils_advocate: {
    name: 'GPT 반대론자',
    role: '투자 반대론자',
    icon: '😈',
    color: 'red',
    bgColor: 'bg-red-50',
    borderColor: 'border-red-200',
    textColor: 'text-red-700',
    gradientFrom: 'from-red-500',
    gradientTo: 'to-red-600',
    description: '모든 투자 결정에 반대하며 리스크를 극대화하여 제시합니다.',
    methodology: [
      '기술적 지표 기반 하락 리스크 분석',
      '재무제표 기반 펀더멘털 약점 공격',
      '최악의 시나리오 시뮬레이션',
      '다른 분석가 논리 허점 반박'
    ],
    strengths: ['리스크 발굴', '논리적 반박', '냉정한 판단'],
    avatar: '😈'
  },
  moderator: {
    name: '조정자',
    role: '회의 진행자',
    icon: '⚖️',
    color: 'yellow',
    bgColor: 'bg-yellow-50',
    borderColor: 'border-yellow-200',
    textColor: 'text-yellow-700',
    gradientFrom: 'from-yellow-500',
    gradientTo: 'to-yellow-600',
    description: '3개 AI의 의견을 종합하여 최종 투자 결정을 조율합니다.',
    methodology: [
      '다수결 및 가중 투표 시스템',
      '의견 충돌 시 중재 및 조정',
      '리스크/리턴 균형 최적화',
      '최종 합의 도출 및 시그널 생성'
    ],
    strengths: ['균형 잡힌 결정', '리스크 관리', '합의 도출'],
    avatar: '👨‍⚖️'
  }
} as const;

export type AnalystKey = keyof typeof AI_ANALYSTS;

export interface AnalystInfo {
  name: string;
  role: string;
  icon: string;
  color: string;
  bgColor: string;
  borderColor: string;
  textColor: string;
  gradientFrom: string;
  gradientTo: string;
  description: string;
  methodology: readonly string[];
  strengths: readonly string[];
  avatar: string;
}

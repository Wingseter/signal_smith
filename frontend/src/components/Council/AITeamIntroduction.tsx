import { useState } from 'react';
import { AI_ANALYSTS } from './constants';
import { AIAnalystCard } from './AIAnalystCard';

export function AITeamIntroduction() {
  const [expandedAnalyst, setExpandedAnalyst] = useState<string | null>(null);
  const [showGuide, setShowGuide] = useState(false);

  return (
    <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
      <div
        className="p-4 bg-gradient-to-r from-indigo-600 to-purple-600 cursor-pointer"
        onClick={() => setShowGuide(!showGuide)}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <span className="text-2xl">🤖</span>
            <div>
              <h2 className="font-bold text-white text-lg">AI 투자 위원회 소개</h2>
              <p className="text-white/80 text-sm">3개의 전문 AI가 협력하여 최적의 투자 결정을 내립니다</p>
            </div>
          </div>
          <span className="text-white">{showGuide ? '▲ 접기' : '▼ 펼치기'}</span>
        </div>
      </div>

      {showGuide && (
        <div className="p-6 space-y-6">
          {/* 투자 결정 프로세스 설명 */}
          <div className="bg-gray-50 rounded-lg p-4">
            <h3 className="font-bold text-gray-800 mb-3">🔄 AI 투자 결정 프로세스</h3>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="text-center">
                <div className="w-12 h-12 mx-auto bg-blue-100 rounded-full flex items-center justify-center mb-2">
                  <span className="text-xl">📰</span>
                </div>
                <p className="text-sm font-medium text-gray-800">1. 뉴스 감지</p>
                <p className="text-xs text-gray-500">Gemini가 중요 뉴스 발굴</p>
              </div>
              <div className="text-center">
                <div className="w-12 h-12 mx-auto bg-green-100 rounded-full flex items-center justify-center mb-2">
                  <span className="text-xl">📊</span>
                </div>
                <p className="text-sm font-medium text-gray-800">2. 기술적 분석</p>
                <p className="text-xs text-gray-500">GPT가 차트/지표 분석</p>
              </div>
              <div className="text-center">
                <div className="w-12 h-12 mx-auto bg-purple-100 rounded-full flex items-center justify-center mb-2">
                  <span className="text-xl">📈</span>
                </div>
                <p className="text-sm font-medium text-gray-800">3. 가치 평가</p>
                <p className="text-xs text-gray-500">Claude가 기업가치 분석</p>
              </div>
              <div className="text-center">
                <div className="w-12 h-12 mx-auto bg-yellow-100 rounded-full flex items-center justify-center mb-2">
                  <span className="text-xl">⚖️</span>
                </div>
                <p className="text-sm font-medium text-gray-800">4. 합의 도출</p>
                <p className="text-xs text-gray-500">최종 투자 시그널 생성</p>
              </div>
            </div>
          </div>

          {/* AI 분석가 카드들 */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {Object.entries(AI_ANALYSTS).map(([key, analyst]) => (
              <AIAnalystCard
                key={key}
                analyst={analyst}
                isExpanded={expandedAnalyst === key}
                onToggle={() => setExpandedAnalyst(expandedAnalyst === key ? null : key)}
              />
            ))}
          </div>

          {/* 신뢰도 지표 설명 */}
          <div className="bg-gradient-to-r from-gray-50 to-gray-100 rounded-lg p-4">
            <h3 className="font-bold text-gray-800 mb-3">📊 신뢰도 지표 이해하기</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
              <div className="bg-white rounded-lg p-3 border">
                <div className="flex items-center space-x-2 mb-2">
                  <span className="text-green-600 font-bold">퀀트 점수</span>
                  <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded">GPT</span>
                </div>
                <p className="text-gray-600 text-xs">기술적 지표 기반 점수입니다. RSI, MACD 등의 신호 강도를 0-100으로 수치화합니다.</p>
              </div>
              <div className="bg-white rounded-lg p-3 border">
                <div className="flex items-center space-x-2 mb-2">
                  <span className="text-purple-600 font-bold">펀더멘털 점수</span>
                  <span className="text-xs bg-purple-100 text-purple-700 px-2 py-0.5 rounded">Claude</span>
                </div>
                <p className="text-gray-600 text-xs">재무제표 기반 가치평가 점수입니다. PER, ROE 등을 종합하여 0-100으로 평가합니다.</p>
              </div>
              <div className="bg-white rounded-lg p-3 border">
                <div className="flex items-center space-x-2 mb-2">
                  <span className="text-indigo-600 font-bold">종합 신뢰도</span>
                  <span className="text-xs bg-indigo-100 text-indigo-700 px-2 py-0.5 rounded">합의</span>
                </div>
                <p className="text-gray-600 text-xs">3개 AI의 의견 일치도입니다. 60% 이상이면 자동 체결이 가능합니다.</p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

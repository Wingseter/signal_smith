import { useState, useEffect } from 'react';
import type { CouncilConfig } from './types';

export function ConfigPanel({
  config,
  onUpdate,
  isLoading
}: {
  config: CouncilConfig;
  onUpdate: (config: CouncilConfig) => void;
  isLoading: boolean;
}) {
  const [localConfig, setLocalConfig] = useState(config);

  useEffect(() => {
    setLocalConfig(config);
  }, [config]);

  return (
    <div className="bg-white rounded-xl border-2 shadow-lg overflow-hidden">
      <div className="bg-gradient-to-r from-gray-700 to-gray-800 p-4">
        <h3 className="font-bold text-white flex items-center">
          <span className="mr-2">⚙️</span>
          AI 회의 설정
        </h3>
        <p className="text-gray-300 text-sm mt-1">투자 회의의 민감도와 자동화 수준을 조정합니다</p>
      </div>
      <div className="p-5">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              📰 뉴스 중요도 기준 (1-10)
            </label>
            <input
              type="range"
              min={1}
              max={10}
              value={localConfig.council_threshold}
              onChange={(e) => setLocalConfig({ ...localConfig, council_threshold: parseInt(e.target.value) })}
              className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
            />
            <div className="flex justify-between text-xs text-gray-500 mt-1">
              <span>민감 (1)</span>
              <span className="font-bold text-indigo-600">{localConfig.council_threshold}</span>
              <span>엄격 (10)</span>
            </div>
            <p className="text-xs text-gray-400 mt-1">낮을수록 더 많은 뉴스에 대해 회의가 소집됩니다</p>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              📉 매도 기준 점수 (1-10)
            </label>
            <input
              type="range"
              min={1}
              max={10}
              value={localConfig.sell_threshold}
              onChange={(e) => setLocalConfig({ ...localConfig, sell_threshold: parseInt(e.target.value) })}
              className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
            />
            <div className="flex justify-between text-xs text-gray-500 mt-1">
              <span>민감 (1)</span>
              <span className="font-bold text-red-600">{localConfig.sell_threshold}</span>
              <span>엄격 (10)</span>
            </div>
            <p className="text-xs text-gray-400 mt-1">낮을수록 매도 신호가 더 자주 발생합니다</p>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              💰 종목당 최대 투자금
            </label>
            <input
              type="number"
              value={localConfig.max_position_per_stock}
              onChange={(e) => setLocalConfig({ ...localConfig, max_position_per_stock: parseInt(e.target.value) })}
              className="w-full px-4 py-2 border-2 rounded-lg text-sm focus:border-indigo-500 focus:outline-none"
            />
            <p className="text-xs text-gray-400 mt-1">단일 종목에 투자할 최대 금액 (원)</p>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              ⏰ 뉴스 체크 주기 (초)
            </label>
            <input
              type="number"
              min={30}
              value={localConfig.poll_interval}
              onChange={(e) => setLocalConfig({ ...localConfig, poll_interval: parseInt(e.target.value) })}
              className="w-full px-4 py-2 border-2 rounded-lg text-sm focus:border-indigo-500 focus:outline-none"
            />
            <p className="text-xs text-gray-400 mt-1">새로운 뉴스를 확인하는 간격</p>
          </div>
        </div>

        <div className="mt-5 p-4 bg-yellow-50 border-2 border-yellow-200 rounded-xl">
          <label className="flex items-start space-x-3 cursor-pointer">
            <input
              type="checkbox"
              checked={localConfig.auto_execute}
              onChange={(e) => setLocalConfig({ ...localConfig, auto_execute: e.target.checked })}
              className="w-5 h-5 rounded border-2 border-yellow-400 text-yellow-600 focus:ring-yellow-500 mt-0.5"
            />
            <div>
              <span className="font-bold text-yellow-800">🤖 자동 체결 활성화</span>
              <p className="text-sm text-yellow-700 mt-1">
                활성화 시 신뢰도 60% 이상의 시그널이 자동으로 체결됩니다.
                <br/>
                <span className="text-yellow-600 font-medium">⚠️ 주의: 실제 주문이 자동으로 실행됩니다.</span>
              </p>
            </div>
          </label>
        </div>

        <button
          onClick={() => onUpdate(localConfig)}
          disabled={isLoading}
          className="mt-5 w-full px-6 py-3 bg-gradient-to-r from-indigo-500 to-purple-600 text-white rounded-xl font-bold hover:from-indigo-600 hover:to-purple-700 disabled:opacity-50 transition-all shadow-md hover:shadow-lg"
        >
          {isLoading ? '저장 중...' : '💾 설정 저장'}
        </button>
      </div>
    </div>
  );
}

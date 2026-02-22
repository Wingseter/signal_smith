import type { AnalystInfo } from './constants';

export function AIAnalystCard({
  analyst,
  isExpanded,
  onToggle
}: {
  analyst: AnalystInfo;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  return (
    <div
      className={`rounded-xl border-2 ${analyst.borderColor} overflow-hidden transition-all duration-300 ${
        isExpanded ? 'shadow-lg' : 'shadow-sm hover:shadow-md'
      }`}
    >
      <div
        className={`bg-gradient-to-r ${analyst.gradientFrom} ${analyst.gradientTo} p-4 cursor-pointer`}
        onClick={onToggle}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <span className="text-3xl">{analyst.avatar}</span>
            <div>
              <h3 className="font-bold text-white text-lg">{analyst.name}</h3>
              <p className="text-white/80 text-sm">{analyst.role}</p>
            </div>
          </div>
          <span className="text-white text-xl">
            {isExpanded ? '▲' : '▼'}
          </span>
        </div>
      </div>

      {isExpanded && (
        <div className={`${analyst.bgColor} p-4 space-y-4`}>
          <p className="text-gray-700 text-sm">{analyst.description}</p>

          <div>
            <h4 className="font-semibold text-gray-800 text-sm mb-2">📋 분석 방법론</h4>
            <ul className="space-y-1">
              {analyst.methodology.map((method, idx) => (
                <li key={idx} className="text-xs text-gray-600 flex items-start">
                  <span className="text-gray-400 mr-2">•</span>
                  {method}
                </li>
              ))}
            </ul>
          </div>

          <div>
            <h4 className="font-semibold text-gray-800 text-sm mb-2">💪 강점</h4>
            <div className="flex flex-wrap gap-2">
              {analyst.strengths.map((strength, idx) => (
                <span
                  key={idx}
                  className={`px-2 py-1 rounded-full text-xs font-medium ${analyst.bgColor} ${analyst.textColor} border ${analyst.borderColor}`}
                >
                  {strength}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

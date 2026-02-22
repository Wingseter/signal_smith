import { AI_ANALYSTS, type AnalystInfo } from './constants';
import type { CouncilMessage } from './types';

function getAnalyst(role: string, speaker: string): AnalystInfo {
  const known = AI_ANALYSTS[role as keyof typeof AI_ANALYSTS];
  if (known) return known;
  return {
    name: speaker,
    role: '',
    icon: '💬',
    color: 'gray',
    bgColor: 'bg-gray-50',
    borderColor: 'border-gray-200',
    textColor: 'text-gray-700',
    gradientFrom: 'from-gray-400',
    gradientTo: 'to-gray-500',
    description: '',
    methodology: [],
    strengths: [],
    avatar: '🤖'
  };
}

export function MessageBubble({ message }: { message: CouncilMessage }) {
  const analyst = getAnalyst(message.role, message.speaker);

  return (
    <div className={`p-4 rounded-xl border-2 ${analyst.borderColor} ${analyst.bgColor} mb-4 transition-all hover:shadow-md`}>
      <div className="flex items-start space-x-3">
        <div className={`w-10 h-10 rounded-full bg-gradient-to-br ${analyst.gradientFrom || 'from-gray-400'} ${analyst.gradientTo || 'to-gray-500'} flex items-center justify-center flex-shrink-0`}>
          <span className="text-lg">{analyst.avatar || analyst.icon}</span>
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center space-x-2">
              <span className={`font-bold ${analyst.textColor}`}>{analyst.name || message.speaker}</span>
              {analyst.role && (
                <span className={`text-xs px-2 py-0.5 rounded-full ${analyst.bgColor} ${analyst.textColor} border ${analyst.borderColor}`}>
                  {analyst.role}
                </span>
              )}
            </div>
            <span className="text-xs text-gray-400">
              {new Date(message.timestamp).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })}
            </span>
          </div>
          <div className="text-gray-700 whitespace-pre-wrap text-sm leading-relaxed">
            {message.content}
          </div>
        </div>
      </div>
    </div>
  );
}

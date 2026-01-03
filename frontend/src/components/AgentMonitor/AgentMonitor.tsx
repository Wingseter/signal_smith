import { useQuery } from '@tanstack/react-query';
import { analysisApi } from '../../services/api';

interface Agent {
  name: string;
  role: string;
  status: string;
  last_run: string | null;
}

interface AgentsStatusResponse {
  agents: Agent[];
  coordinator: {
    status: string;
    workflow: string;
  };
}

export default function AgentMonitor() {
  const { data: agentsStatus, isLoading } = useQuery<AgentsStatusResponse>({
    queryKey: ['agentsStatus'],
    queryFn: analysisApi.getAgentsStatus,
    refetchInterval: 10000, // Refresh every 10 seconds
  });

  const getAgentIcon = (name: string) => {
    switch (name) {
      case 'gemini':
        return '🔮';
      case 'chatgpt':
        return '🤖';
      case 'claude':
        return '🧠';
      case 'ml':
        return '📊';
      default:
        return '⚙️';
    }
  };

  const getAgentDescription = (name: string) => {
    switch (name) {
      case 'gemini':
        return 'Analyzes real-time news and market sentiment using Google Gemini AI.';
      case 'chatgpt':
        return 'Performs quantitative analysis and develops automated trading strategies.';
      case 'claude':
        return 'Conducts in-depth fundamental analysis of financial reports and company data.';
      case 'ml':
        return 'Analyzes chart patterns, trading volume, and technical indicators using ML models.';
      default:
        return '';
    }
  };

  if (isLoading) {
    return <div className="text-center py-8">Loading...</div>;
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">AI Agents Monitor</h1>

      {/* Coordinator Status */}
      {agentsStatus?.coordinator && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Coordinator</h2>
          <div className="flex items-center space-x-4">
            <div
              className={`w-4 h-4 rounded-full ${
                agentsStatus.coordinator.status === 'active' ? 'bg-green-500' : 'bg-gray-400'
              }`}
            />
            <div>
              <p className="font-medium">LangGraph Orchestrator</p>
              <p className="text-sm text-gray-500">
                Workflow: {agentsStatus.coordinator.workflow}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Agent Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {agentsStatus?.agents.map((agent) => (
          <div key={agent.name} className="bg-white rounded-lg shadow p-6">
            <div className="flex items-start justify-between">
              <div className="flex items-center space-x-3">
                <span className="text-3xl">{getAgentIcon(agent.name)}</span>
                <div>
                  <h3 className="text-lg font-semibold capitalize">{agent.name}</h3>
                  <p className="text-sm text-gray-500">{agent.role}</p>
                </div>
              </div>
              <div className="flex items-center space-x-2">
                <span
                  className={`w-3 h-3 rounded-full ${
                    agent.status === 'active' ? 'bg-green-500 animate-pulse' : 'bg-gray-400'
                  }`}
                />
                <span className="text-sm text-gray-500 capitalize">{agent.status}</span>
              </div>
            </div>
            <p className="mt-4 text-sm text-gray-600">{getAgentDescription(agent.name)}</p>
            <div className="mt-4 pt-4 border-t border-gray-100">
              <div className="flex justify-between text-sm">
                <span className="text-gray-500">Last Run</span>
                <span className="text-gray-900">
                  {agent.last_run ? new Date(agent.last_run).toLocaleString() : 'Never'}
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Agent Workflow Diagram */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Agent Collaboration Flow</h2>
        <div className="flex flex-col items-center space-y-4">
          <div className="flex items-center space-x-8">
            <div className="text-center">
              <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center text-2xl">
                📥
              </div>
              <p className="mt-2 text-sm font-medium">Data Input</p>
            </div>
            <div className="text-2xl text-gray-400">→</div>
            <div className="text-center">
              <div className="w-16 h-16 bg-purple-100 rounded-full flex items-center justify-center text-2xl">
                🔄
              </div>
              <p className="mt-2 text-sm font-medium">Coordinator</p>
            </div>
          </div>

          <div className="text-2xl text-gray-400">↓</div>

          <div className="grid grid-cols-4 gap-4">
            {['gemini', 'chatgpt', 'claude', 'ml'].map((name) => (
              <div key={name} className="text-center">
                <div className="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center text-xl mx-auto">
                  {getAgentIcon(name)}
                </div>
                <p className="mt-1 text-xs font-medium capitalize">{name}</p>
              </div>
            ))}
          </div>

          <div className="text-2xl text-gray-400">↓</div>

          <div className="flex items-center space-x-8">
            <div className="text-center">
              <div className="w-16 h-16 bg-yellow-100 rounded-full flex items-center justify-center text-2xl">
                📊
              </div>
              <p className="mt-2 text-sm font-medium">Analysis</p>
            </div>
            <div className="text-2xl text-gray-400">→</div>
            <div className="text-center">
              <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center text-2xl">
                💹
              </div>
              <p className="mt-2 text-sm font-medium">Trading Signal</p>
            </div>
          </div>
        </div>
      </div>

      {/* API Keys Status */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">API Configuration Status</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { name: 'OpenAI', env: 'OPENAI_API_KEY' },
            { name: 'Anthropic', env: 'ANTHROPIC_API_KEY' },
            { name: 'Google', env: 'GOOGLE_API_KEY' },
            { name: 'Korea Investment', env: 'KIS_APP_KEY' },
            { name: 'Kiwoom', env: 'KIWOOM_USER_ID' },
            { name: 'DART', env: 'DART_API_KEY' },
            { name: 'News API', env: 'NEWS_API_KEY' },
            { name: 'Slack', env: 'SLACK_WEBHOOK_URL' },
          ].map((api) => (
            <div key={api.name} className="p-3 bg-gray-50 rounded-lg">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">{api.name}</span>
                <span className="w-2 h-2 rounded-full bg-gray-400" />
              </div>
              <p className="text-xs text-gray-500 mt-1">{api.env}</p>
            </div>
          ))}
        </div>
        <p className="mt-4 text-sm text-gray-500">
          Configure API keys in .env file to enable each service.
        </p>
      </div>
    </div>
  );
}

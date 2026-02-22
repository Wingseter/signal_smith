import { useState, useEffect, useRef, useCallback } from 'react';
import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { useCouncilStore } from '../store/councilStore';
import { councilWebSocket, newsMonitorWebSocket } from '../services/api';
import clsx from 'clsx';

// 핵심 네비게이션 - AI 토론 중심으로 재구성
const navItems = [
  { path: '/', label: 'Dashboard', icon: '📊', description: 'AI 투자 현황' },
  { path: '/council', label: 'AI Council', icon: '🏛️', description: '실시간 AI 토론', highlight: true },
  { path: '/news-monitor', label: 'News', icon: '📰', description: '뉴스 모니터링' },
  { path: '/analysis', label: 'Analysis', icon: '🔍', description: 'AI 종합 분석' },
  { path: '/signals', label: 'Signals', icon: '📡', description: '투자 시그널' },
  { path: '/quant-signals', label: 'Quant', icon: '🔬', description: '퀀트 시그널' },
  { path: '/portfolio', label: 'Portfolio', icon: '💼', description: '포트폴리오' },
  { path: '/trading', label: 'Trading', icon: '💹', description: '자동매매' },
  { path: '/backtest', label: 'Backtest', icon: '⏱️', description: '전략 검증' },
  { path: '/performance', label: 'Performance', icon: '📉', description: '성과 분석' },
];

const moreItems = [
  { path: '/stocks', label: 'Stocks', icon: '📈' },
  { path: '/optimizer', label: 'Optimizer', icon: '⚖️' },
  { path: '/sectors', label: 'Sectors', icon: '🏭' },
  { path: '/reports', label: 'Reports', icon: '📄' },
  { path: '/agents', label: 'AI Agents', icon: '🤖' },
  { path: '/settings/notifications', label: 'Alerts', icon: '🔔' },
];

// AI 상태 표시 컴포넌트
function AIStatusIndicator() {
  const { isCouncilRunning, pendingSignals, unreadCount } = useCouncilStore();

  return (
    <div className="flex items-center space-x-3">
      {/* Council 실행 상태 */}
      <div
        className={clsx(
          'flex items-center space-x-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all',
          isCouncilRunning
            ? 'bg-green-100 text-green-700 border border-green-300'
            : 'bg-gray-100 text-gray-500 border border-gray-200'
        )}
      >
        <span
          className={clsx(
            'w-2 h-2 rounded-full',
            isCouncilRunning ? 'bg-green-500 animate-pulse' : 'bg-gray-400'
          )}
        />
        <span>{isCouncilRunning ? 'AI 활성' : 'AI 대기'}</span>
      </div>

      {/* 대기 시그널 */}
      {pendingSignals.length > 0 && (
        <Link
          to="/council"
          className="flex items-center space-x-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-700 border border-yellow-300 hover:bg-yellow-200 transition-all"
        >
          <span>📋</span>
          <span>{pendingSignals.length}개 시그널 대기</span>
        </Link>
      )}

      {/* 미확인 트리거 */}
      {unreadCount > 0 && (
        <span className="flex items-center justify-center w-6 h-6 bg-red-500 text-white text-xs font-bold rounded-full animate-bounce">
          {unreadCount}
        </span>
      )}
    </div>
  );
}


// 트리거 히스토리 드롭다운
function TriggerHistoryDropdown() {
  const [isOpen, setIsOpen] = useState(false);
  const navigate = useNavigate();
  const { triggers, unreadCount, markAsRead, clearTriggers } = useCouncilStore();
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleOpen = () => {
    setIsOpen(!isOpen);
    if (!isOpen && unreadCount > 0) {
      markAsRead();
    }
  };

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={handleOpen}
        className={clsx(
          'relative p-2 rounded-lg transition-all',
          unreadCount > 0
            ? 'bg-red-100 text-red-600 hover:bg-red-200'
            : 'text-gray-600 hover:bg-gray-100'
        )}
      >
        <span className="text-xl">🔔</span>
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 text-white text-xs font-bold rounded-full flex items-center justify-center">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-2 w-96 bg-white rounded-xl shadow-2xl border overflow-hidden z-50">
          <div className="p-3 bg-gradient-to-r from-indigo-600 to-purple-600 flex justify-between items-center">
            <span className="font-bold text-white">🔔 AI 트리거 알림</span>
            {triggers.length > 0 && (
              <button
                onClick={clearTriggers}
                className="text-white/70 hover:text-white text-xs"
              >
                모두 지우기
              </button>
            )}
          </div>

          <div className="max-h-96 overflow-y-auto">
            {triggers.length === 0 ? (
              <div className="p-8 text-center text-gray-500">
                <span className="text-4xl mb-2 block">📭</span>
                <p>알림이 없습니다</p>
                <p className="text-xs mt-1">뉴스 트리거가 감지되면 여기에 표시됩니다</p>
              </div>
            ) : (
              triggers.map((trigger) => (
                <div
                  key={trigger.id}
                  onClick={() => {
                    navigate('/council');
                    setIsOpen(false);
                  }}
                  className="p-3 border-b hover:bg-gray-50 cursor-pointer transition-colors"
                >
                  <div className="flex items-start space-x-3">
                    <div className="w-10 h-10 bg-indigo-100 rounded-lg flex items-center justify-center text-lg">
                      {trigger.type === 'news_trigger' ? '📰' :
                        trigger.type === 'meeting_started' ? '🏛️' :
                        trigger.type === 'signal_created' ? '📡' : '✅'}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center space-x-2">
                        <span className="font-medium text-gray-900">{trigger.company_name}</span>
                        <span className="text-xs text-gray-400">{trigger.symbol}</span>
                      </div>
                      <p className="text-sm text-gray-600 truncate">{trigger.news_title}</p>
                      <div className="flex items-center space-x-2 mt-1">
                        <span className="text-xs text-yellow-600">⭐ {trigger.news_score}/10</span>
                        <span className="text-xs text-gray-400">
                          {new Date(trigger.timestamp).toLocaleTimeString('ko-KR', {
                            hour: '2-digit',
                            minute: '2-digit',
                          })}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>

          {triggers.length > 0 && (
            <div className="p-3 bg-gray-50 border-t">
              <button
                onClick={() => {
                  navigate('/council');
                  setIsOpen(false);
                }}
                className="w-full py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 transition-all"
              >
                AI Council에서 전체 보기 →
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function Layout() {
  const location = useLocation();
  const { user, logout } = useAuthStore();
  const {
    addTrigger,
    setCouncilRunning,
    setPendingSignals,
    setActiveMeeting,
  } = useCouncilStore();
  const [showMoreMenu, setShowMoreMenu] = useState(false);

  // Council WebSocket 연결
  const councilWsRef = useRef<WebSocket | null>(null);
  const newsWsRef = useRef<WebSocket | null>(null);

  const connectWebSockets = useCallback(() => {
    // Council WebSocket
    if (!councilWsRef.current || councilWsRef.current.readyState === WebSocket.CLOSED) {
      try {
        const councilWs = councilWebSocket.connect();
        councilWsRef.current = councilWs;

        councilWs.onmessage = (event) => {
          const data = JSON.parse(event.data);

          if (data.type === 'connected') {
            setCouncilRunning(data.status?.running || false);
          } else if (data.type === 'status_update') {
            setCouncilRunning(data.running || false);
            if (data.pending_signals !== undefined) {
              // 형식 변환이 필요할 수 있음
            }
          } else if (data.type === 'meeting_started' || data.type === 'meeting_update') {
            const meeting = data.meeting;
            if (meeting) {
              setActiveMeeting(meeting.id);
              if (data.type === 'meeting_started') {
                addTrigger({
                  id: `meeting-${meeting.id}`,
                  symbol: meeting.symbol,
                  company_name: meeting.company_name,
                  news_title: meeting.news_title,
                  news_score: meeting.news_score,
                  timestamp: new Date().toISOString(),
                  type: 'meeting_started',
                });
              }
            }
          } else if (data.type === 'signal_created') {
            const signal = data.signal;
            if (signal) {
              addTrigger({
                id: `signal-${signal.id}`,
                symbol: signal.symbol,
                company_name: signal.company_name,
                news_title: `${signal.action} 시그널: ${signal.consensus_reason?.slice(0, 50)}...`,
                news_score: Math.round(signal.confidence * 10),
                timestamp: new Date().toISOString(),
                type: 'signal_created',
              });
            }
          }
        };

        councilWs.onclose = () => {
          setTimeout(connectWebSockets, 3000);
        };
      } catch (error) {
        console.error('Council WebSocket 연결 실패:', error);
      }
    }

    // News Monitor WebSocket
    if (!newsWsRef.current || newsWsRef.current.readyState === WebSocket.CLOSED) {
      try {
        const newsWs = newsMonitorWebSocket.connect();
        newsWsRef.current = newsWs;

        newsWs.onmessage = (event) => {
          const data = JSON.parse(event.data);

          // 뉴스 분석 결과는 로그만 남기고 알림은 보내지 않음
          // 사용자 알림은 Council 회의가 시작될 때만 (meeting_started 이벤트)
          if (data.type === 'analyzed' && data.data) {
            console.log('뉴스 분석 완료:', data.data.news_title?.slice(0, 50));
          }
        };

        newsWs.onclose = () => {
          setTimeout(connectWebSockets, 3000);
        };
      } catch (error) {
        console.error('News WebSocket 연결 실패:', error);
      }
    }
  }, [addTrigger, setCouncilRunning, setActiveMeeting, setPendingSignals]);

  useEffect(() => {
    connectWebSockets();

    // Ping intervals
    const pingInterval = setInterval(() => {
      if (councilWsRef.current?.readyState === WebSocket.OPEN) {
        councilWebSocket.ping(councilWsRef.current);
      }
      if (newsWsRef.current?.readyState === WebSocket.OPEN) {
        newsMonitorWebSocket.ping(newsWsRef.current);
      }
    }, 30000);

    return () => {
      clearInterval(pingInterval);
      councilWsRef.current?.close();
      newsWsRef.current?.close();
    };
  }, [connectWebSockets]);

  return (
    <div className="min-h-screen bg-gray-50">
      {/* 트리거 알림 모달 - 제거됨 (전체화면 알림 비활성화) */}

      {/* Header */}
      <header className="bg-white shadow-sm border-b border-gray-200 sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            {/* 로고 */}
            <div className="flex items-center space-x-4">
              <Link to="/" className="flex items-center space-x-2">
                <span className="text-2xl">🤖</span>
                <span className="text-xl font-bold bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">
                  Signal Smith
                </span>
              </Link>
              <span className="hidden sm:inline-block px-2 py-0.5 bg-indigo-100 text-indigo-700 text-xs font-medium rounded-full">
                AI 자동매매
              </span>
            </div>

            {/* AI 상태 표시 */}
            <div className="hidden lg:flex">
              <AIStatusIndicator />
            </div>

            {/* 우측 메뉴 */}
            <div className="flex items-center space-x-3">
              <TriggerHistoryDropdown />
              <span className="text-sm text-gray-600 hidden sm:inline">{user?.email}</span>
              <button
                onClick={logout}
                className="text-sm text-gray-600 hover:text-gray-900 px-3 py-1.5 rounded-lg hover:bg-gray-100 transition-all"
              >
                로그아웃
              </button>
            </div>
          </div>
        </div>

        {/* 주요 네비게이션 */}
        <nav className="border-t border-gray-100 bg-white">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex items-center space-x-1 overflow-x-auto py-2">
              {navItems.map((item) => (
                <Link
                  key={item.path}
                  to={item.path}
                  className={clsx(
                    'flex items-center space-x-1.5 px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-all',
                    location.pathname === item.path
                      ? 'bg-indigo-100 text-indigo-700'
                      : item.highlight
                        ? 'text-purple-600 hover:bg-purple-50'
                        : 'text-gray-600 hover:bg-gray-100'
                  )}
                >
                  <span>{item.icon}</span>
                  <span>{item.label}</span>
                  {item.highlight && location.pathname !== item.path && (
                    <span className="w-2 h-2 bg-purple-500 rounded-full animate-pulse" />
                  )}
                </Link>
              ))}

              {/* More 메뉴 */}
              <div className="relative">
                <button
                  onClick={() => setShowMoreMenu(!showMoreMenu)}
                  className="flex items-center space-x-1.5 px-4 py-2 rounded-lg text-sm font-medium text-gray-600 hover:bg-gray-100 transition-all"
                >
                  <span>⋯</span>
                  <span>더보기</span>
                </button>

                {showMoreMenu && (
                  <div className="absolute right-0 mt-1 w-48 bg-white rounded-lg shadow-lg border z-50">
                    {moreItems.map((item) => (
                      <Link
                        key={item.path}
                        to={item.path}
                        onClick={() => setShowMoreMenu(false)}
                        className={clsx(
                          'flex items-center space-x-2 px-4 py-2.5 text-sm transition-colors',
                          location.pathname === item.path
                            ? 'bg-indigo-50 text-indigo-700'
                            : 'text-gray-700 hover:bg-gray-50'
                        )}
                      >
                        <span>{item.icon}</span>
                        <span>{item.label}</span>
                      </Link>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </nav>
      </header>

      {/* Main content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <Outlet />
      </main>

      {/* Footer */}
      <footer className="bg-white border-t mt-auto">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex flex-col sm:flex-row justify-between items-center text-sm text-gray-500">
            <div className="flex items-center space-x-2">
              <span>🤖</span>
              <span>Signal Smith - AI 기반 자동매매 시스템</span>
            </div>
            <div className="flex items-center space-x-4 mt-2 sm:mt-0">
              <span className="flex items-center space-x-1">
                <span>📰</span>
                <span>Gemini</span>
              </span>
              <span className="flex items-center space-x-1">
                <span>📊</span>
                <span>GPT</span>
              </span>
              <span className="flex items-center space-x-1">
                <span>📈</span>
                <span>Claude</span>
              </span>
            </div>
          </div>
        </div>
      </footer>

      {/* CSS 애니메이션 */}
      <style>{`
        @keyframes slide-down {
          from {
            opacity: 0;
            transform: translateY(-20px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
        .animate-slide-down {
          animation: slide-down 0.3s ease-out;
        }
      `}</style>
    </div>
  );
}

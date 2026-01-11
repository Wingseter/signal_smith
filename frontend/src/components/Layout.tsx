import { Outlet, Link, useLocation } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import clsx from 'clsx';

const navItems = [
  { path: '/', label: 'Dashboard', icon: '📊' },
  { path: '/analysis', label: 'Analysis', icon: '🔍' },
  { path: '/signals', label: 'Signals', icon: '📡' },
  { path: '/stocks', label: 'Stocks', icon: '📈' },
  { path: '/portfolio', label: 'Portfolio', icon: '💼' },
  { path: '/trading', label: 'Trading', icon: '💹' },
  { path: '/backtest', label: 'Backtest', icon: '⏱️' },
  { path: '/performance', label: 'Performance', icon: '📉' },
  { path: '/agents', label: 'AI Agents', icon: '🤖' },
  { path: '/settings/notifications', label: 'Alerts', icon: '🔔' },
];

export default function Layout() {
  const location = useLocation();
  const { user, logout } = useAuthStore();

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center">
              <Link to="/" className="text-xl font-bold text-primary-600">
                Signal Smith
              </Link>
            </div>
            <nav className="hidden md:flex space-x-4">
              {navItems.map((item) => (
                <Link
                  key={item.path}
                  to={item.path}
                  className={clsx(
                    'px-3 py-2 rounded-md text-sm font-medium transition-colors',
                    location.pathname === item.path
                      ? 'bg-primary-100 text-primary-700'
                      : 'text-gray-600 hover:bg-gray-100'
                  )}
                >
                  <span className="mr-1">{item.icon}</span>
                  {item.label}
                </Link>
              ))}
            </nav>
            <div className="flex items-center space-x-4">
              <span className="text-sm text-gray-600">{user?.email}</span>
              <button
                onClick={logout}
                className="text-sm text-gray-600 hover:text-gray-900"
              >
                Logout
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Mobile nav */}
      <nav className="md:hidden bg-white border-b border-gray-200 overflow-x-auto">
        <div className="flex px-4 py-2 space-x-2">
          {navItems.map((item) => (
            <Link
              key={item.path}
              to={item.path}
              className={clsx(
                'px-3 py-2 rounded-md text-sm font-medium whitespace-nowrap',
                location.pathname === item.path
                  ? 'bg-primary-100 text-primary-700'
                  : 'text-gray-600'
              )}
            >
              <span className="mr-1">{item.icon}</span>
              {item.label}
            </Link>
          ))}
        </div>
      </nav>

      {/* Main content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <Outlet />
      </main>
    </div>
  );
}

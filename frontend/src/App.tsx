import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuthStore } from './store/authStore';
import Layout from './components/Layout';
import LoginPage from './components/Auth/LoginPage';
import Dashboard from './components/Dashboard/Dashboard';
import StockList from './components/Charts/StockList';
import StockDetail from './components/Charts/StockDetail';
import Portfolio from './components/Portfolio/Portfolio';
import Trading from './components/Trading/Trading';
import TradingSignals from './components/Trading/TradingSignals';
import AgentMonitor from './components/AgentMonitor/AgentMonitor';
import AnalysisPanel from './components/Analysis/AnalysisPanel';
import NotificationSettings from './components/Settings/NotificationSettings';
import Backtest from './components/Backtest/Backtest';
import PerformanceDashboard from './components/Performance/PerformanceDashboard';
import PortfolioOptimizer from './components/Optimizer/PortfolioOptimizer';
import SectorAnalysis from './components/Sectors/SectorAnalysis';

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" />;
}

function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <PrivateRoute>
            <Layout />
          </PrivateRoute>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="stocks" element={<StockList />} />
        <Route path="stocks/:symbol" element={<StockDetail />} />
        <Route path="portfolio" element={<Portfolio />} />
        <Route path="trading" element={<Trading />} />
        <Route path="signals" element={<TradingSignals />} />
        <Route path="agents" element={<AgentMonitor />} />
        <Route path="analysis" element={<AnalysisPanel />} />
        <Route path="backtest" element={<Backtest />} />
        <Route path="performance" element={<PerformanceDashboard />} />
        <Route path="optimizer" element={<PortfolioOptimizer />} />
        <Route path="sectors" element={<SectorAnalysis />} />
        <Route path="settings/notifications" element={<NotificationSettings />} />
      </Route>
    </Routes>
  );
}

export default App;

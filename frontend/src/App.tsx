import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuthStore } from './store/authStore';
import Layout from './components/Layout';
import LoginPage from './components/Auth/LoginPage';
import Dashboard from './components/Dashboard/Dashboard';
import StockList from './components/Charts/StockList';
import StockDetail from './components/Charts/StockDetail';
import Portfolio from './components/Portfolio/Portfolio';
import Trading from './components/Trading/Trading';
import AgentMonitor from './components/AgentMonitor/AgentMonitor';

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
        <Route path="agents" element={<AgentMonitor />} />
      </Route>
    </Routes>
  );
}

export default App;

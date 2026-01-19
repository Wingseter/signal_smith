import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { reportsApi, stocksApi, portfolioApi } from '../../services/api';
import clsx from 'clsx';

type ReportType = 'stock_analysis' | 'portfolio_review' | 'trading_summary' | 'market_overview';

interface ReportTypeInfo {
  id: ReportType;
  name: string;
  description: string;
  icon: string;
}

const reportTypes: ReportTypeInfo[] = [
  {
    id: 'stock_analysis',
    name: 'Stock Analysis',
    description: 'Comprehensive AI analysis of a single stock',
    icon: '📊',
  },
  {
    id: 'portfolio_review',
    name: 'Portfolio Review',
    description: 'Full portfolio performance and risk analysis',
    icon: '💼',
  },
  {
    id: 'trading_summary',
    name: 'Trading Summary',
    description: 'Trading activity and performance summary',
    icon: '📈',
  },
  {
    id: 'market_overview',
    name: 'Market Overview',
    description: 'Market indices, sectors, and top movers',
    icon: '🌐',
  },
];

export default function ReportGenerator() {
  const [selectedType, setSelectedType] = useState<ReportType>('stock_analysis');
  const [selectedSymbol, setSelectedSymbol] = useState<string>('');
  const [periodDays, setPeriodDays] = useState<number>(30);
  const [includeAiInsights, setIncludeAiInsights] = useState(true);
  const [includeRiskMetrics, setIncludeRiskMetrics] = useState(true);
  const [includeSectors, setIncludeSectors] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);

  // Fetch stocks for dropdown
  const { data: stocksData } = useQuery({
    queryKey: ['stocks'],
    queryFn: () => stocksApi.list({ limit: 100 }),
  });

  // Fetch portfolios
  const { data: portfoliosData } = useQuery({
    queryKey: ['portfolios'],
    queryFn: portfolioApi.list,
  });

  const downloadPdf = (blob: Blob, filename: string) => {
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  };

  const handleGenerateReport = async () => {
    setIsGenerating(true);
    try {
      let blob: Blob;
      let filename: string;
      const dateStr = new Date().toISOString().split('T')[0].replace(/-/g, '');

      switch (selectedType) {
        case 'stock_analysis':
          if (!selectedSymbol) {
            alert('Please select a stock');
            return;
          }
          blob = await reportsApi.generateStockReport(selectedSymbol, includeAiInsights);
          filename = `stock_report_${selectedSymbol}_${dateStr}.pdf`;
          break;

        case 'portfolio_review':
          blob = await reportsApi.generatePortfolioReport(undefined, includeRiskMetrics);
          filename = `portfolio_report_${dateStr}.pdf`;
          break;

        case 'trading_summary':
          blob = await reportsApi.generateTradingReport(periodDays);
          filename = `trading_report_${dateStr}.pdf`;
          break;

        case 'market_overview':
          blob = await reportsApi.generateMarketReport(includeSectors);
          filename = `market_report_${dateStr}.pdf`;
          break;

        default:
          return;
      }

      downloadPdf(blob, filename);
    } catch (error) {
      console.error('Failed to generate report:', error);
      alert('Failed to generate report. Please try again.');
    } finally {
      setIsGenerating(false);
    }
  };

  const renderOptions = () => {
    switch (selectedType) {
      case 'stock_analysis':
        return (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Select Stock
              </label>
              <select
                value={selectedSymbol}
                onChange={(e) => setSelectedSymbol(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
              >
                <option value="">-- Select a stock --</option>
                {stocksData?.stocks?.map((stock: { symbol: string; name: string }) => (
                  <option key={stock.symbol} value={stock.symbol}>
                    {stock.symbol} - {stock.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex items-center">
              <input
                type="checkbox"
                id="includeAiInsights"
                checked={includeAiInsights}
                onChange={(e) => setIncludeAiInsights(e.target.checked)}
                className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
              />
              <label htmlFor="includeAiInsights" className="ml-2 text-sm text-gray-700">
                Include AI Insights
              </label>
            </div>
          </div>
        );

      case 'portfolio_review':
        return (
          <div className="space-y-4">
            <div className="flex items-center">
              <input
                type="checkbox"
                id="includeRiskMetrics"
                checked={includeRiskMetrics}
                onChange={(e) => setIncludeRiskMetrics(e.target.checked)}
                className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
              />
              <label htmlFor="includeRiskMetrics" className="ml-2 text-sm text-gray-700">
                Include Risk Metrics (Sharpe, VaR, etc.)
              </label>
            </div>
            {portfoliosData?.length > 0 && (
              <p className="text-sm text-gray-500">
                Report will be generated for your default portfolio.
              </p>
            )}
          </div>
        );

      case 'trading_summary':
        return (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Period (Days)
              </label>
              <select
                value={periodDays}
                onChange={(e) => setPeriodDays(Number(e.target.value))}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
              >
                <option value={7}>Last 7 days</option>
                <option value={14}>Last 14 days</option>
                <option value={30}>Last 30 days</option>
                <option value={60}>Last 60 days</option>
                <option value={90}>Last 90 days</option>
              </select>
            </div>
          </div>
        );

      case 'market_overview':
        return (
          <div className="space-y-4">
            <div className="flex items-center">
              <input
                type="checkbox"
                id="includeSectors"
                checked={includeSectors}
                onChange={(e) => setIncludeSectors(e.target.checked)}
                className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
              />
              <label htmlFor="includeSectors" className="ml-2 text-sm text-gray-700">
                Include Sector Performance
              </label>
            </div>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">AI Analysis Reports</h1>
        <p className="text-gray-600 mt-1">Generate comprehensive PDF reports with AI insights</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Report Type Selection */}
        <div className="lg:col-span-2">
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Select Report Type</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {reportTypes.map((type) => (
                <button
                  key={type.id}
                  onClick={() => setSelectedType(type.id)}
                  className={clsx(
                    'p-4 rounded-lg border-2 text-left transition-all',
                    selectedType === type.id
                      ? 'border-primary-500 bg-primary-50'
                      : 'border-gray-200 hover:border-gray-300 bg-white'
                  )}
                >
                  <div className="flex items-start gap-3">
                    <span className="text-2xl">{type.icon}</span>
                    <div>
                      <h3 className="font-medium text-gray-900">{type.name}</h3>
                      <p className="text-sm text-gray-500 mt-1">{type.description}</p>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Report Options */}
        <div className="lg:col-span-1">
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Report Options</h2>
            {renderOptions()}

            <div className="mt-6">
              <button
                onClick={handleGenerateReport}
                disabled={isGenerating || (selectedType === 'stock_analysis' && !selectedSymbol)}
                className={clsx(
                  'w-full py-3 px-4 rounded-lg font-medium transition-colors flex items-center justify-center gap-2',
                  isGenerating || (selectedType === 'stock_analysis' && !selectedSymbol)
                    ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                    : 'bg-primary-600 text-white hover:bg-primary-700'
                )}
              >
                {isGenerating ? (
                  <>
                    <svg
                      className="animate-spin h-5 w-5"
                      xmlns="http://www.w3.org/2000/svg"
                      fill="none"
                      viewBox="0 0 24 24"
                    >
                      <circle
                        className="opacity-25"
                        cx="12"
                        cy="12"
                        r="10"
                        stroke="currentColor"
                        strokeWidth="4"
                      />
                      <path
                        className="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                      />
                    </svg>
                    Generating...
                  </>
                ) : (
                  <>
                    <svg
                      className="w-5 h-5"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                      />
                    </svg>
                    Generate PDF Report
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Report Preview / Info */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Report Contents</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {selectedType === 'stock_analysis' && (
            <>
              <ContentCard title="Price Overview" items={['Current price', 'Price change', 'Volume', 'Market cap']} />
              <ContentCard title="Valuation" items={['P/E Ratio', 'P/B Ratio', 'Dividend yield']} />
              <ContentCard title="AI Scores" items={['Technical score', 'Fundamental score', 'Sentiment score', 'Overall rating']} />
              <ContentCard title="Recommendation" items={['Investment suggestion', 'Price target', 'Support/Resistance levels']} />
            </>
          )}
          {selectedType === 'portfolio_review' && (
            <>
              <ContentCard title="Summary" items={['Total value', 'Total P&L', 'Cash balance']} />
              <ContentCard title="Holdings" items={['Position details', 'Individual P&L', 'Weight allocation']} />
              <ContentCard title="Risk Metrics" items={['Sharpe Ratio', 'Max Drawdown', 'VaR (95%)']} />
              <ContentCard title="Allocation" items={['Sector breakdown', 'Concentration analysis']} />
            </>
          )}
          {selectedType === 'trading_summary' && (
            <>
              <ContentCard title="Overview" items={['Total trades', 'Win rate', 'Total P&L']} />
              <ContentCard title="Performance" items={['Avg profit/loss', 'Largest win/loss']} />
              <ContentCard title="Signals" items={['Signals generated', 'Execution rate']} />
              <ContentCard title="Trade History" items={['Recent trades', 'Per-trade details']} />
            </>
          )}
          {selectedType === 'market_overview' && (
            <>
              <ContentCard title="Indices" items={['KOSPI', 'KOSDAQ', 'Index changes']} />
              <ContentCard title="Sentiment" items={['Market mood', 'Volatility index', 'Trading volume']} />
              <ContentCard title="Sectors" items={['Performance by sector', 'Period returns']} />
              <ContentCard title="Movers" items={['Top gainers', 'Top losers']} />
            </>
          )}
        </div>
      </div>

      {/* Recent Reports */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Quick Actions</h2>
        <div className="flex flex-wrap gap-3">
          <QuickActionButton
            label="Download Portfolio Report"
            icon="💼"
            onClick={async () => {
              setIsGenerating(true);
              try {
                const blob = await reportsApi.generatePortfolioReport();
                const dateStr = new Date().toISOString().split('T')[0].replace(/-/g, '');
                downloadPdf(blob, `portfolio_report_${dateStr}.pdf`);
              } catch (e) {
                console.error(e);
              } finally {
                setIsGenerating(false);
              }
            }}
            disabled={isGenerating}
          />
          <QuickActionButton
            label="Download Market Report"
            icon="🌐"
            onClick={async () => {
              setIsGenerating(true);
              try {
                const blob = await reportsApi.generateMarketReport();
                const dateStr = new Date().toISOString().split('T')[0].replace(/-/g, '');
                downloadPdf(blob, `market_report_${dateStr}.pdf`);
              } catch (e) {
                console.error(e);
              } finally {
                setIsGenerating(false);
              }
            }}
            disabled={isGenerating}
          />
          <QuickActionButton
            label="Download Trading Summary (30d)"
            icon="📈"
            onClick={async () => {
              setIsGenerating(true);
              try {
                const blob = await reportsApi.generateTradingReport(30);
                const dateStr = new Date().toISOString().split('T')[0].replace(/-/g, '');
                downloadPdf(blob, `trading_report_${dateStr}.pdf`);
              } catch (e) {
                console.error(e);
              } finally {
                setIsGenerating(false);
              }
            }}
            disabled={isGenerating}
          />
        </div>
      </div>
    </div>
  );
}

function ContentCard({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="bg-gray-50 rounded-lg p-4">
      <h3 className="font-medium text-gray-900 mb-2">{title}</h3>
      <ul className="text-sm text-gray-600 space-y-1">
        {items.map((item, i) => (
          <li key={i} className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 bg-primary-500 rounded-full" />
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}

function QuickActionButton({
  label,
  icon,
  onClick,
  disabled,
}: {
  label: string;
  icon: string;
  onClick: () => void;
  disabled: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={clsx(
        'inline-flex items-center gap-2 px-4 py-2 rounded-lg border transition-colors',
        disabled
          ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
          : 'bg-white border-gray-300 text-gray-700 hover:bg-gray-50 hover:border-gray-400'
      )}
    >
      <span>{icon}</span>
      <span className="text-sm font-medium">{label}</span>
    </button>
  );
}

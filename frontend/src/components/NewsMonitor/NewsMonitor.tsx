import { useState, useEffect, useRef, useCallback } from 'react';
import { newsMonitorApi, newsMonitorWebSocket } from '../../services/api';
import clsx from 'clsx';

interface CrawledNews {
  title: string;
  url: string;
  source: string;
  symbol: string | null;
  company_name: string | null;
  category: string;
  keywords: string[];
  crawled_at: string;
  is_trigger: boolean;
}

interface AnalysisResult {
  news_title: string;
  symbol: string | null;
  company_name: string | null;
  score: number;
  sentiment: string;
  trading_signal: string;
  confidence: number;
  analysis_reason: string;
  analyzer: string;
  analyzed_at: string;
}

interface MonitorStatus {
  monitor_running: boolean;
  stats: {
    total_crawled: number;
    total_analyzed: number;
    total_triggers: number;
    last_crawl_at: string | null;
    last_analysis_at: string | null;
    crawled_count: number;
    analysis_count: number;
  };
  poll_interval: number;
  seen_urls_count: number;
}

export default function NewsMonitor() {
  const [status, setStatus] = useState<MonitorStatus | null>(null);
  const [crawledNews, setCrawledNews] = useState<CrawledNews[]>([]);
  const [analysisHistory, setAnalysisHistory] = useState<AnalysisResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [testCrawling, setTestCrawling] = useState(false);
  const [testTitle, setTestTitle] = useState('');
  const [testSymbol, setTestSymbol] = useState('');
  const [testAnalyzing, setTestAnalyzing] = useState(false);
  const [testResult, setTestResult] = useState<any>(null);
  const [wsConnected, setWsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  // Fetch initial data
  const fetchData = useCallback(async () => {
    try {
      const [statusRes, crawledRes, analysisRes] = await Promise.all([
        newsMonitorApi.getStatus(),
        newsMonitorApi.getCrawledNews(50),
        newsMonitorApi.getAnalysisHistory(50),
      ]);
      setStatus(statusRes);
      setCrawledNews(crawledRes.news || []);
      setAnalysisHistory(analysisRes.analysis || []);
    } catch (error) {
      console.error('Failed to fetch news monitor data:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  // WebSocket connection
  useEffect(() => {
    const connectWebSocket = () => {
      try {
        const ws = newsMonitorWebSocket.connect();
        wsRef.current = ws;

        ws.onopen = () => {
          console.log('News Monitor WebSocket connected');
          setWsConnected(true);
        };

        ws.onmessage = (event) => {
          const data = JSON.parse(event.data);

          if (data.type === 'connected') {
            setStatus({
              monitor_running: data.status.monitor_running,
              stats: data.status.stats,
              poll_interval: 60,
              seen_urls_count: 0,
            });
            setCrawledNews(data.recent_crawled || []);
            setAnalysisHistory(data.recent_analysis || []);
          } else if (data.type === 'crawled') {
            // New crawled news
            setCrawledNews(prev => [data.data, ...prev.slice(0, 49)]);
          } else if (data.type === 'analyzed') {
            // New analysis result
            setAnalysisHistory(prev => [data.data, ...prev.slice(0, 49)]);
          } else if (data.type === 'status') {
            setStatus(prev => prev ? { ...prev, ...data.status } : null);
          }
        };

        ws.onclose = () => {
          console.log('News Monitor WebSocket disconnected');
          setWsConnected(false);
          // Reconnect after 3 seconds
          setTimeout(connectWebSocket, 3000);
        };

        ws.onerror = (error) => {
          console.error('News Monitor WebSocket error:', error);
        };
      } catch (error) {
        console.error('Failed to connect WebSocket:', error);
        setTimeout(connectWebSocket, 3000);
      }
    };

    fetchData();
    connectWebSocket();

    // Ping interval
    const pingInterval = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        newsMonitorWebSocket.ping(wsRef.current);
      }
    }, 30000);

    return () => {
      clearInterval(pingInterval);
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [fetchData]);

  // Test crawl
  const handleTestCrawl = async () => {
    setTestCrawling(true);
    try {
      const result = await newsMonitorApi.testCrawl();
      alert(`${result.crawled_count}건의 뉴스를 크롤링했습니다.`);
      await fetchData();
    } catch (error) {
      console.error('Test crawl failed:', error);
      alert('크롤링 테스트 실패');
    } finally {
      setTestCrawling(false);
    }
  };

  // Test analyze
  const handleTestAnalyze = async () => {
    if (!testTitle.trim()) {
      alert('뉴스 제목을 입력하세요');
      return;
    }
    setTestAnalyzing(true);
    setTestResult(null);
    try {
      const result = await newsMonitorApi.testAnalyze(testTitle, testSymbol || undefined);
      setTestResult(result);
    } catch (error) {
      console.error('Test analyze failed:', error);
      alert('분석 테스트 실패');
    } finally {
      setTestAnalyzing(false);
    }
  };

  // Format time
  const formatTime = (isoString: string) => {
    const date = new Date(isoString);
    return date.toLocaleTimeString('ko-KR', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  // Get sentiment color
  const getSentimentColor = (sentiment: string) => {
    switch (sentiment) {
      case 'very_positive': return 'text-green-600 bg-green-100';
      case 'positive': return 'text-green-500 bg-green-50';
      case 'neutral': return 'text-gray-600 bg-gray-100';
      case 'negative': return 'text-red-500 bg-red-50';
      case 'very_negative': return 'text-red-600 bg-red-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  // Get signal color
  const getSignalColor = (signal: string) => {
    switch (signal) {
      case 'BUY': return 'text-green-600 bg-green-100';
      case 'SELL': return 'text-red-600 bg-red-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  // Get score color
  const getScoreColor = (score: number) => {
    if (score >= 8) return 'text-green-600';
    if (score >= 6) return 'text-green-500';
    if (score >= 4) return 'text-gray-600';
    if (score >= 2) return 'text-red-500';
    return 'text-red-600';
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">News Monitor</h1>
          <p className="text-gray-600">Gemini 뉴스 분석 현황</p>
        </div>
        <div className="flex items-center gap-4">
          <div className={clsx(
            'flex items-center gap-2 px-3 py-1 rounded-full text-sm',
            wsConnected ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
          )}>
            <span className={clsx(
              'w-2 h-2 rounded-full',
              wsConnected ? 'bg-green-500 animate-pulse' : 'bg-red-500'
            )}></span>
            {wsConnected ? 'WebSocket 연결됨' : 'WebSocket 끊김'}
          </div>
        </div>
      </div>

      {/* Status Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white p-4 rounded-lg shadow-sm border">
          <div className="text-sm text-gray-500">모니터링 상태</div>
          <div className={clsx(
            'text-xl font-semibold mt-1',
            status?.monitor_running ? 'text-green-600' : 'text-gray-400'
          )}>
            {status?.monitor_running ? '실행 중' : '중지됨'}
          </div>
        </div>
        <div className="bg-white p-4 rounded-lg shadow-sm border">
          <div className="text-sm text-gray-500">크롤링 건수</div>
          <div className="text-xl font-semibold mt-1 text-blue-600">
            {status?.stats.total_crawled || 0}
          </div>
        </div>
        <div className="bg-white p-4 rounded-lg shadow-sm border">
          <div className="text-sm text-gray-500">분석 건수</div>
          <div className="text-xl font-semibold mt-1 text-purple-600">
            {status?.stats.total_analyzed || 0}
          </div>
        </div>
        <div className="bg-white p-4 rounded-lg shadow-sm border">
          <div className="text-sm text-gray-500">트리거 감지</div>
          <div className="text-xl font-semibold mt-1 text-orange-600">
            {status?.stats.total_triggers || 0}
          </div>
        </div>
      </div>

      {/* Test Section */}
      <div className="bg-white p-4 rounded-lg shadow-sm border">
        <h2 className="text-lg font-semibold mb-4">테스트</h2>
        <div className="flex flex-wrap gap-4">
          <button
            onClick={handleTestCrawl}
            disabled={testCrawling}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {testCrawling ? '크롤링 중...' : '수동 크롤링'}
          </button>

          <div className="flex-1 flex gap-2 items-center">
            <input
              type="text"
              placeholder="뉴스 제목 입력"
              value={testTitle}
              onChange={(e) => setTestTitle(e.target.value)}
              className="flex-1 px-3 py-2 border rounded-lg"
            />
            <input
              type="text"
              placeholder="종목코드 (선택)"
              value={testSymbol}
              onChange={(e) => setTestSymbol(e.target.value)}
              className="w-32 px-3 py-2 border rounded-lg"
            />
            <button
              onClick={handleTestAnalyze}
              disabled={testAnalyzing}
              className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50"
            >
              {testAnalyzing ? '분석 중...' : 'Gemini 분석'}
            </button>
          </div>
        </div>

        {/* Test Result */}
        {testResult && (
          <div className="mt-4 p-4 bg-gray-50 rounded-lg">
            <h3 className="font-medium mb-2">분석 결과</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div>
                <span className="text-gray-500">점수:</span>
                <span className={clsx('ml-2 font-semibold', getScoreColor(testResult.score))}>
                  {testResult.score}/10
                </span>
              </div>
              <div>
                <span className="text-gray-500">감성:</span>
                <span className={clsx('ml-2 px-2 py-0.5 rounded text-xs', getSentimentColor(testResult.sentiment))}>
                  {testResult.sentiment}
                </span>
              </div>
              <div>
                <span className="text-gray-500">신호:</span>
                <span className={clsx('ml-2 px-2 py-0.5 rounded text-xs font-semibold', getSignalColor(testResult.trading_signal))}>
                  {testResult.trading_signal}
                </span>
              </div>
              <div>
                <span className="text-gray-500">신뢰도:</span>
                <span className="ml-2 font-medium">{(testResult.confidence * 100).toFixed(0)}%</span>
              </div>
            </div>
            <div className="mt-2 text-sm text-gray-600">
              <span className="text-gray-500">분석 근거:</span> {testResult.reason}
            </div>
          </div>
        )}
      </div>

      {/* Main Content - Two Columns */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Crawled News */}
        <div className="bg-white rounded-lg shadow-sm border">
          <div className="p-4 border-b flex justify-between items-center">
            <h2 className="text-lg font-semibold">크롤링된 뉴스</h2>
            <span className="text-sm text-gray-500">{crawledNews.length}건</span>
          </div>
          <div className="max-h-[500px] overflow-y-auto">
            {crawledNews.length === 0 ? (
              <div className="p-8 text-center text-gray-500">
                크롤링된 뉴스가 없습니다
              </div>
            ) : (
              <div className="divide-y">
                {crawledNews.map((news, index) => (
                  <div key={index} className={clsx(
                    'p-4 hover:bg-gray-50',
                    news.is_trigger && 'bg-yellow-50'
                  )}>
                    <div className="flex justify-between items-start gap-2">
                      <a
                        href={news.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm font-medium text-gray-900 hover:text-blue-600 line-clamp-2"
                      >
                        {news.title}
                      </a>
                      {news.is_trigger && (
                        <span className="px-2 py-0.5 bg-yellow-200 text-yellow-800 text-xs rounded">
                          트리거
                        </span>
                      )}
                    </div>
                    <div className="mt-2 flex flex-wrap gap-2 text-xs">
                      <span className="text-gray-500">{news.source}</span>
                      {news.company_name && (
                        <span className="px-1.5 py-0.5 bg-blue-100 text-blue-700 rounded">
                          {news.company_name}
                        </span>
                      )}
                      <span className="px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded">
                        {news.category}
                      </span>
                      <span className="text-gray-400 ml-auto">
                        {formatTime(news.crawled_at)}
                      </span>
                    </div>
                    {news.keywords.length > 0 && (
                      <div className="mt-1 flex flex-wrap gap-1">
                        {news.keywords.slice(0, 5).map((kw, i) => (
                          <span key={i} className="text-xs text-orange-600">
                            #{kw}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Analysis History */}
        <div className="bg-white rounded-lg shadow-sm border">
          <div className="p-4 border-b flex justify-between items-center">
            <h2 className="text-lg font-semibold">Gemini 분석 결과</h2>
            <span className="text-sm text-gray-500">{analysisHistory.length}건</span>
          </div>
          <div className="max-h-[500px] overflow-y-auto">
            {analysisHistory.length === 0 ? (
              <div className="p-8 text-center text-gray-500">
                분석 결과가 없습니다
              </div>
            ) : (
              <div className="divide-y">
                {analysisHistory.map((analysis, index) => (
                  <div key={index} className="p-4 hover:bg-gray-50">
                    <div className="flex justify-between items-start gap-2">
                      <div className="text-sm font-medium text-gray-900 line-clamp-2">
                        {analysis.news_title}
                      </div>
                      <div className="flex gap-1 shrink-0">
                        <span className={clsx(
                          'px-2 py-0.5 text-xs font-semibold rounded',
                          getScoreColor(analysis.score)
                        )}>
                          {analysis.score}/10
                        </span>
                        <span className={clsx(
                          'px-2 py-0.5 text-xs font-semibold rounded',
                          getSignalColor(analysis.trading_signal)
                        )}>
                          {analysis.trading_signal}
                        </span>
                      </div>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-2 text-xs">
                      {analysis.company_name && (
                        <span className="px-1.5 py-0.5 bg-blue-100 text-blue-700 rounded">
                          {analysis.company_name}
                        </span>
                      )}
                      <span className={clsx('px-1.5 py-0.5 rounded', getSentimentColor(analysis.sentiment))}>
                        {analysis.sentiment}
                      </span>
                      <span className="text-gray-500">
                        신뢰도 {(analysis.confidence * 100).toFixed(0)}%
                      </span>
                      <span className="text-gray-400 ml-auto">
                        {formatTime(analysis.analyzed_at)}
                      </span>
                    </div>
                    <div className="mt-2 text-xs text-gray-600 line-clamp-2">
                      {analysis.analysis_reason}
                    </div>
                    <div className="mt-1 text-xs text-gray-400">
                      분석기: {analysis.analyzer}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

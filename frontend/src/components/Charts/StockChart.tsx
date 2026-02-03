import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

interface StockChartProps {
  symbol: string;
  data?: Array<{
    date: string;
    close: number;
  }>;
}

// Sample data for demo
const sampleData = [
  { date: '2024-01-01', close: 2600 },
  { date: '2024-01-02', close: 2620 },
  { date: '2024-01-03', close: 2615 },
  { date: '2024-01-04', close: 2635 },
  { date: '2024-01-05', close: 2640 },
  { date: '2024-01-08', close: 2625 },
  { date: '2024-01-09', close: 2650 },
  { date: '2024-01-10', close: 2645 },
  { date: '2024-01-11', close: 2660 },
  { date: '2024-01-12', close: 2655 },
];

export default function StockChart({ symbol: _symbol, data = sampleData }: StockChartProps) {
  void _symbol; // Symbol is received for API use but chart uses data directly
  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 12 }}
            tickFormatter={(value) => value.slice(5)}
          />
          <YAxis
            domain={['dataMin - 20', 'dataMax + 20']}
            tick={{ fontSize: 12 }}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: 'white',
              border: '1px solid #e5e7eb',
              borderRadius: '8px',
            }}
          />
          <Line
            type="monotone"
            dataKey="close"
            stroke="#3b82f6"
            strokeWidth={2}
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

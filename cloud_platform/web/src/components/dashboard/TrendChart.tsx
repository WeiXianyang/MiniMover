import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';
import { MOCK_HOURLY_DATA } from '../../mock';

export default function TrendChart() {
  const data = MOCK_HOURLY_DATA;
  const maxCount = Math.max(...data.map(d => d.count), 1);

  return (
    <div className="panel p-4">
      <div className="mb-3">
        <h3 className="text-[15px] font-semibold text-text">24 小时趋势</h3>
        <p className="text-[12px] text-muted-2">按小时聚合的告警数量</p>
      </div>

      <div className="h-[200px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 4, bottom: 0, left: -20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(147,164,186,0.08)" vertical={false} />
            <XAxis
              dataKey="hour"
              axisLine={{ stroke: '#263241' }}
              tickLine={false}
              tick={{ fill: '#667386', fontSize: 11 }}
            />
            <YAxis
              axisLine={false}
              tickLine={false}
              tick={{ fill: '#667386', fontSize: 11 }}
            />
            <Tooltip
              contentStyle={{
                background: '#1b2633',
                border: '1px solid #263241',
                borderRadius: 8,
                fontSize: 12,
                color: '#eef4ff',
              }}
              cursor={{ fill: 'rgba(232,139,69,0.06)' }}
            />
            <defs>
              <linearGradient id="barGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#e88b45" />
                <stop offset="100%" stopColor="rgba(91,174,199,0.3)" />
              </linearGradient>
            </defs>
            <Bar
              dataKey="count"
              fill="url(#barGrad)"
              radius={[4, 4, 0, 0]}
              maxBarSize={32}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

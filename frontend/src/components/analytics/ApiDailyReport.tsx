import { useId, useState } from 'react';
import { Activity } from 'lucide-react';
import {
  CartesianGrid,
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { chartTheme } from './chartTheme';
import { AnalyticsTable } from './AnalyticsTable';
import { ReportPanelHeader } from './ReportPanelHeader';

type Day = { day: string; requests: number; errors: number };
export function ApiDailyReport({
  days,
  period,
}: {
  days: Day[];
  period: string;
}) {
  const fillId = `requests-fill-${useId().replace(/:/g, '')}`;
  const [metric, setMetric] = useState<'requests' | 'errors'>('requests');
  const labels = {
    requests: 'API requests',
    errors: 'Server errors',
  };
  return (
    <section className="analytics-panel analytics-comparison-panel">
      <ReportPanelHeader title="Daily requests" icon={Activity} />
      <label className="analytics-table-tools">
        Chart metric
        <select
          aria-label="API chart metric"
          value={metric}
          onChange={(event) => setMetric(event.target.value as typeof metric)}
        >
          {Object.entries(labels).map(([key, label]) => (
            <option key={key} value={key}>
              {label}
            </option>
          ))}
        </select>
      </label>
      <div
        className="analytics-comparison-chart"
        role="img"
        aria-label={`${labels[metric]} by UTC day for ${period}. Exact values follow.`}
      >
        <ResponsiveContainer
          width="100%"
          height="100%"
          minWidth={0}
          initialDimension={{ width: 1000, height: 288 }}
        >
          <AreaChart
            data={days}
            margin={{ top: 16, right: 8, left: -20, bottom: 0 }}
            accessibilityLayer
          >
            <defs>
              <linearGradient id={fillId} x1="0" y1="0" x2="0" y2="1">
                <stop
                  offset="0%"
                  stopColor={chartTheme.fill.color}
                  stopOpacity={chartTheme.fill.startOpacity}
                />
                <stop
                  offset="100%"
                  stopColor={chartTheme.fill.color}
                  stopOpacity={chartTheme.fill.endOpacity}
                />
              </linearGradient>
            </defs>
            <CartesianGrid {...chartTheme.grid} />
            <XAxis
              dataKey="day"
              axisLine={false}
              tickLine={false}
              tick={chartTheme.tick}
              minTickGap={35}
              tickFormatter={(day) =>
                new Date(`${day}T00:00:00Z`).toLocaleDateString('en-US', {
                  month: 'short',
                  day: 'numeric',
                  timeZone: 'UTC',
                })
              }
            />
            <YAxis
              axisLine={false}
              tickLine={false}
              tick={chartTheme.tick}
              allowDecimals={false}
              width={80}
              tickFormatter={(value: number) => value.toLocaleString('en-US')}
            />
            <Tooltip
              cursor={chartTheme.cursor}
              contentStyle={chartTheme.tooltip}
              labelStyle={chartTheme.tooltipLabel}
              labelFormatter={(day) =>
                new Date(`${day}T00:00:00Z`).toLocaleDateString('en-US', {
                  month: 'short',
                  day: 'numeric',
                  timeZone: 'UTC',
                })
              }
              formatter={(value: number) => value.toLocaleString('en-US')}
            />
            <Area
              type="linear"
              dataKey={metric}
              name={labels[metric]}
              {...chartTheme.series}
              fill={`url(#${fillId})`}
              dot={false}
              isAnimationActive={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <details>
        <summary>Daily values</summary>
        <AnalyticsTable className="analytics-comparison-table">
          <caption className="sr-only">{period} daily requests</caption>
          <thead>
            <tr>
              <th scope="col">Date</th>
              <th scope="col">API requests</th>
              <th scope="col">Server errors</th>
            </tr>
          </thead>
          <tbody>
            {days.map((day) => (
              <tr key={day.day}>
                <th scope="row">{day.day}</th>
                <td>{day.requests.toLocaleString('en-US')}</td>
                <td>{day.errors.toLocaleString('en-US')}</td>
              </tr>
            ))}
          </tbody>
        </AnalyticsTable>
      </details>
    </section>
  );
}

import { useState } from 'react';
import { Activity } from 'lucide-react';
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
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
  const [metric, setMetric] = useState<'requests' | 'errors'>('requests');
  const labels = {
    requests: 'API requests',
    errors: 'Zero-result requests',
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
          <LineChart data={days}>
            <CartesianGrid strokeDasharray="2 6" />
            <XAxis
              dataKey="day"
              minTickGap={35}
              tickFormatter={(day) =>
                new Date(`${day}T00:00:00Z`).toLocaleDateString('en-US', {
                  month: 'short',
                  day: 'numeric',
                  timeZone: 'UTC',
                })
              }
            />
            <YAxis />
            <Tooltip />
            <Line
              type="linear"
              dataKey={metric}
              name={labels[metric]}
              stroke="#003c5b"
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
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
              <th scope="col">Zero-result requests</th>
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

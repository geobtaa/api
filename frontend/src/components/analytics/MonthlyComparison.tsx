import { september } from '../../data/analytics/september2026';
import { ReportSectionHeading } from './ReportSectionHeading';
import { AnalyticsTable } from './AnalyticsTable';
import { Activity, BarChart3 } from 'lucide-react';
import { ReportPanelHeader } from './ReportPanelHeader';
import { useState } from 'react';
import {
  CartesianGrid,
  Bar,
  BarChart,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import {
  JULY_2026_SUMMARY,
  dailyActivity as julyDailyActivity,
} from '../../data/analytics/july2026';
import {
  AUGUST_2026_SUMMARY,
  augustDailyActivity,
} from '../../data/analytics/august2026';
import { comparisonChange } from '../../utils/analyticsComparison';

const number = new Intl.NumberFormat('en-US');
const summaryMetrics = [
  ['requests', 'API requests'],
  ['searches', 'Searches'],
  ['impressions', 'Search impressions'],
  ['events', 'Tracked interactions'],
  ['resourceViews', 'Resource views'],
  ['resultClicks', 'Result clicks'],
  ['downloadClicks', 'Download clicks'],
  ['uniqueEngagedVisits', 'Engaged visits'],
  ['zeroResultSearches', 'Zero-result searches'],
  ['serverErrors', 'Server errors'],
  ['medianResponseMs', 'Median response time (ms)'],
  ['p95ResponseMs', '95th percentile response time (ms)'],
] as const;
const dailyMetrics = {
  events: 'Tracked interactions',
  searches: 'Searches',
  requests: 'API requests',
};
export function MonthlyComparison() {
  const [dailyMetric, setDailyMetric] =
    useState<keyof typeof dailyMetrics>('events');
  const dailyData = augustDailyActivity.map((point, index) => ({
    day: index + 1,
    July: julyDailyActivity[index][dailyMetric],
    August: point[dailyMetric],
    September: september.dailyActivity[index]?.[dailyMetric] ?? null,
  }));

  return (
    <section
      id="comparison"
      className="analytics-section"
      aria-labelledby="comparison-title"
    >
      <ReportSectionHeading
        id="comparison-title"
        title="September compared with August"
        description="Three complete months in 2026. September has 30 days; July and August have 31. Changes compare September with August."
      />
      <div className="analytics-panel analytics-comparison-panel">
        <ReportPanelHeader
          title="Portal totals"
          icon={BarChart3}
        ></ReportPanelHeader>
        <div
          className="analytics-comparison-scroll"
          tabIndex={0}
          role="region"
          aria-label="Portal comparison table"
        >
          <AnalyticsTable className="analytics-comparison-table">
            <caption className="sr-only">
              July, August, and September 2026 portal totals and changes
            </caption>
            <thead>
              <tr>
                <th scope="col">Metric</th>
                <th scope="col">July 2026</th>
                <th scope="col">August 2026</th>
                <th scope="col">September 2026</th>
                <th scope="col">Change</th>
                <th scope="col">Change %</th>
              </tr>
            </thead>
            <tbody>
              {summaryMetrics.map(([key, label]) => {
                const july = JULY_2026_SUMMARY[key];
                const august = AUGUST_2026_SUMMARY[key];
                const latest = september.summary[key];
                const delta = latest - august;
                return (
                  <tr key={key}>
                    <th scope="row">{label}</th>
                    <td>{number.format(july)}</td>
                    <td>{number.format(august)}</td>
                    <td>{number.format(latest)}</td>
                    <td>
                      {delta > 0 ? '+' : ''}
                      {number.format(delta)}
                    </td>
                    <td>{comparisonChange(august, latest)}</td>
                  </tr>
                );
              })}
            </tbody>
          </AnalyticsTable>
        </div>
        <p className="analytics-comparison-note">
          API requests include bots and probes. Engaged visits are distinct
          visit tokens with a tracked interaction, not unique people. Download
          counts measure link clicks. A positive change indicates an increase,
          including for errors and response times.
        </p>
      </div>
      <div className="analytics-panel analytics-comparison-panel">
        <ReportPanelHeader title="Daily comparison" icon={Activity}>
          <label>
            Daily metric{' '}
            <select
              value={dailyMetric}
              onChange={(event) =>
                setDailyMetric(event.target.value as keyof typeof dailyMetrics)
              }
            >
              {Object.entries(dailyMetrics).map(([key, label]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </select>
          </label>
        </ReportPanelHeader>
        <p className="analytics-comparison-note">
          Compare July, August, and September side by side for each day of the
          month. Bar heights use the same scale; dates are not aligned by
          weekday.
        </p>
        <div
          className="analytics-comparison-chart"
          role="img"
          aria-label={`${dailyMetrics[dailyMetric]} for July, August, and September as grouped bars for each day of month. Exact values are available in the daily values table below.`}
        >
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={dailyData} barGap={2} barCategoryGap="20%">
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="day" tickLine={false} />
              <YAxis
                width={65}
                tickFormatter={(value) => number.format(value)}
              />
              <Tooltip
                labelFormatter={(value) => `Day ${value}`}
                formatter={(value) => number.format(Number(value))}
                cursor={{ fill: '#f1f5f9' }}
              />
              <Legend />
              <Bar
                dataKey="July"
                name="July 2026"
                fill="#6d28d9"
                isAnimationActive={false}
              />
              <Bar
                dataKey="August"
                name="August 2026"
                fill="#0f766e"
                isAnimationActive={false}
              />
              <Bar
                dataKey="September"
                name="September 2026"
                fill="#2563eb"
                isAnimationActive={false}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <details>
          <summary>Daily values: {dailyMetrics[dailyMetric]}</summary>
          <div
            className="analytics-comparison-scroll"
            tabIndex={0}
            role="region"
            aria-label="Daily comparison table"
          >
            <AnalyticsTable className="analytics-comparison-table">
              <caption className="sr-only">
                Daily {dailyMetrics[dailyMetric].toLowerCase()} in July and
                August, and September 2026
              </caption>
              <thead>
                <tr>
                  <th scope="col">Day of month</th>
                  <th scope="col">July</th>
                  <th scope="col">August</th>
                  <th scope="col">September</th>
                  <th scope="col">Change</th>
                  <th scope="col">Change %</th>
                </tr>
              </thead>
              <tbody>
                {dailyData.map((row) => (
                  <tr key={row.day}>
                    <th scope="row">{row.day}</th>
                    <td>{number.format(row.July)}</td>
                    <td>{number.format(row.August)}</td>
                    <td>
                      {row.September === null
                        ? '—'
                        : number.format(row.September)}
                    </td>
                    <td>
                      {row.September === null
                        ? '—'
                        : `${row.September > row.August ? '+' : ''}${number.format(row.September - row.August)}`}
                    </td>
                    <td>
                      {row.September === null
                        ? '—'
                        : comparisonChange(row.August, row.September)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </AnalyticsTable>
          </div>
        </details>
      </div>
      <p className="analytics-comparison-note">
        September covers September 1–30, 2026 (UTC), exported{' '}
        {september.summary.exportedAt}. July uses the preserved August 20
        export. Monthly rankings and campus reports for all three months are
        available from the report navigation.
      </p>
    </section>
  );
}

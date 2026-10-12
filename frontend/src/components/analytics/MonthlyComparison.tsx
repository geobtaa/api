import { publishedMonths, monthLabel } from '../../config/analyticsPeriods';
import { monthlySnapshots } from '../../data/analytics/september2026';
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
  const months = publishedMonths.map((period) => ({
    period,
    label: monthLabel(period),
    short: monthLabel(period).replace(/ \d{4}$/, ''),
    ...(period === '2026-07'
      ? { summary: JULY_2026_SUMMARY, dailyActivity: julyDailyActivity }
      : period === '2026-08'
        ? { summary: AUGUST_2026_SUMMARY, dailyActivity: augustDailyActivity }
        : monthlySnapshots[period]),
  }));
  const latest = months.at(-1)!;
  const previous = months.at(-2)!;
  const monthNames = new Intl.ListFormat('en-US').format(
    months.map((m) => m.short)
  );
  const dailyData = Array.from(
    { length: Math.max(...months.map((m) => m.dailyActivity.length)) },
    (_, index) => ({
      day: index + 1,
      ...Object.fromEntries(
        months.map((m) => [
          m.period,
          m.dailyActivity[index]?.[dailyMetric] ?? null,
        ])
      ),
    })
  ) as Array<Record<string, number | null> & { day: number }>;

  return (
    <section
      id="comparison"
      className="analytics-section"
      aria-labelledby="comparison-title"
    >
      <ReportSectionHeading
        id="comparison-title"
        title={`${latest.short} compared with ${previous.short}`}
        description={`${months.length} published months. Changes compare ${latest.label} with ${previous.label}; month lengths may differ.`}
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
              {monthNames} portal totals and changes
            </caption>
            <thead>
              <tr>
                <th scope="col">Metric</th>
                {months.map((m) => (
                  <th scope="col" key={m.period}>
                    {m.label}
                  </th>
                ))}
                <th scope="col">Change</th>
                <th scope="col">Change %</th>
              </tr>
            </thead>
            <tbody>
              {summaryMetrics.map(([key, label]) => {
                const baseline = previous.summary[key];
                const current = latest.summary[key];
                const delta = current - baseline;
                return (
                  <tr key={key}>
                    <th scope="row">{label}</th>
                    {months.map((m) => (
                      <td key={m.period}>
                        {m.summary[key] === null
                          ? 'Not available'
                          : number.format(m.summary[key])}
                      </td>
                    ))}
                    <td>
                      {delta > 0 ? '+' : ''}
                      {number.format(delta)}
                    </td>
                    <td>{comparisonChange(baseline, current)}</td>
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
          Compare {monthNames} side by side for each day of the month. Bar
          heights use the same scale; dates are not aligned by weekday.
        </p>
        <div
          className="analytics-comparison-chart"
          role="img"
          aria-label={`${dailyMetrics[dailyMetric]} for ${monthNames} as grouped bars for each day of month. Exact values are available in the daily values table below.`}
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
              {months.map((m, index) => (
                <Bar
                  key={m.period}
                  dataKey={m.period}
                  name={m.label}
                  fill={['#6d28d9', '#0f766e', '#2563eb', '#b45309'][index % 4]}
                  isAnimationActive={false}
                />
              ))}
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
                Daily {dailyMetrics[dailyMetric].toLowerCase()} in {monthNames}
              </caption>
              <thead>
                <tr>
                  <th scope="col">Day of month</th>
                  {months.map((m) => (
                    <th scope="col" key={m.period}>
                      {m.label}
                    </th>
                  ))}
                  <th scope="col">Change</th>
                  <th scope="col">Change %</th>
                </tr>
              </thead>
              <tbody>
                {dailyData.map((row) => (
                  <tr key={row.day}>
                    <th scope="row">{row.day}</th>
                    {months.map((m) => (
                      <td key={m.period}>
                        {row[m.period] === null
                          ? '—'
                          : number.format(row[m.period]!)}
                      </td>
                    ))}
                    <td>
                      {row[latest.period] === null ||
                      row[previous.period] === null
                        ? '—'
                        : number.format(
                            row[latest.period]! - row[previous.period]!
                          )}
                    </td>
                    <td>
                      {row[latest.period] === null ||
                      row[previous.period] === null
                        ? '—'
                        : comparisonChange(
                            row[previous.period]!,
                            row[latest.period]!
                          )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </AnalyticsTable>
          </div>
        </details>
      </div>
      <p className="analytics-comparison-note">
        Monthly rankings and campus reports for every published month are
        available from the report navigation. The latest export is{' '}
        {latest.summary.exportedAt}.
      </p>
    </section>
  );
}

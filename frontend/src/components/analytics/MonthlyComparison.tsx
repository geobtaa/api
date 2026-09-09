import { useState } from 'react';
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import {
  JULY_2026_SUMMARY,
  dailyActivity as julyDailyActivity,
  memberPerformance,
} from '../../data/analytics/july2026';
import {
  AUGUST_2026_SUMMARY,
  augustDailyActivity,
  augustMemberPerformance,
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
const memberMetrics = {
  resourceViews: 'Resource views',
  downloadClicks: 'Download clicks',
  impressions: 'Search impressions',
  sourceClicks: 'Source-site clicks',
};

const csvRows = [
  ['Metric', 'July 2026', 'August 2026', 'Change', 'Percent change'],
  ...summaryMetrics.map(([key, label]) => [
    label,
    JULY_2026_SUMMARY[key],
    AUGUST_2026_SUMMARY[key],
    AUGUST_2026_SUMMARY[key] - JULY_2026_SUMMARY[key],
    comparisonChange(JULY_2026_SUMMARY[key], AUGUST_2026_SUMMARY[key]),
  ]),
  ...memberPerformance.flatMap((member) => {
    const august = augustMemberPerformance.find(
      (row) => row.code === member.code
    )!;
    return Object.entries(memberMetrics).map(([key, label]) => {
      const metric = key as keyof typeof memberMetrics;
      return [
        `${member.name}: ${label}`,
        member[metric],
        august[metric],
        august[metric] - member[metric],
        comparisonChange(member[metric], august[metric]),
      ];
    });
  }),
];
const csvHref = `data:text/csv;charset=utf-8,${encodeURIComponent(
  csvRows
    .map((row) =>
      row.map((cell) => `"${String(cell).replaceAll('"', '""')}"`).join(',')
    )
    .join('\r\n')
)}`;

export function MonthlyComparison() {
  const [dailyMetric, setDailyMetric] =
    useState<keyof typeof dailyMetrics>('events');
  const [memberMetric, setMemberMetric] =
    useState<keyof typeof memberMetrics>('resourceViews');
  const dailyData = augustDailyActivity.map((point, index) => ({
    day: index + 1,
    July: julyDailyActivity[index][dailyMetric],
    August: point[dailyMetric],
  }));

  return (
    <section
      id="comparison"
      className="analytics-section"
      aria-labelledby="comparison-title"
    >
      <div className="analytics-section-heading">
        <p>Month-to-month reporting</p>
        <div>
          <h2 id="comparison-title">August compared with July</h2>
          <span>
            Two complete 31-day periods in 2026. Changes use July as the
            baseline.
          </span>
        </div>
      </div>
      <div className="analytics-panel analytics-comparison-panel">
        <div className="analytics-comparison-toolbar">
          <h3>Portal totals</h3>
          <a href={csvHref} download="analytics-july-august-2026.csv">
            Download comparison CSV
          </a>
        </div>
        <div
          className="analytics-comparison-scroll"
          tabIndex={0}
          role="region"
          aria-label="Portal comparison table"
        >
          <table className="analytics-comparison-table">
            <caption className="sr-only">
              July and August 2026 portal totals and changes
            </caption>
            <thead>
              <tr>
                <th scope="col">Metric</th>
                <th scope="col">July 2026</th>
                <th scope="col">August 2026</th>
                <th scope="col">Change</th>
                <th scope="col">Change %</th>
              </tr>
            </thead>
            <tbody>
              {summaryMetrics.map(([key, label]) => {
                const july = JULY_2026_SUMMARY[key];
                const august = AUGUST_2026_SUMMARY[key];
                const delta = august - july;
                return (
                  <tr key={key}>
                    <th scope="row">{label}</th>
                    <td>{number.format(july)}</td>
                    <td>{number.format(august)}</td>
                    <td>
                      {delta > 0 ? '+' : ''}
                      {number.format(delta)}
                    </td>
                    <td>{comparisonChange(july, august)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="analytics-comparison-note">
          API requests include bots and probes. Engaged visits are distinct
          visit tokens with a tracked interaction, not unique people. Download
          counts measure link clicks. A positive change indicates an increase,
          including for errors and response times.
        </p>
      </div>
      <div className="analytics-panel analytics-comparison-panel">
        <div className="analytics-comparison-toolbar">
          <h3>Daily comparison</h3>
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
        </div>
        <p className="analytics-comparison-note">
          Aligned by day of month. July is the dashed purple line; August is the
          solid teal line.
        </p>
        <div
          className="analytics-comparison-chart"
          role="img"
          aria-label={`${dailyMetrics[dailyMetric]} for July and August, aligned by day of month. Exact values are available in the daily values table below.`}
        >
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={dailyData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="day" />
              <YAxis width={65} />
              <Tooltip />
              <Line
                type="monotone"
                dataKey="July"
                stroke="#6d28d9"
                strokeDasharray="5 4"
                strokeWidth={2}
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="August"
                stroke="#0f766e"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
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
            <table className="analytics-comparison-table">
              <caption className="sr-only">
                Daily {dailyMetrics[dailyMetric].toLowerCase()} in July and
                August 2026
              </caption>
              <thead>
                <tr>
                  <th scope="col">Day of month</th>
                  <th scope="col">July</th>
                  <th scope="col">August</th>
                </tr>
              </thead>
              <tbody>
                {dailyData.map((row) => (
                  <tr key={row.day}>
                    <th scope="row">{row.day}</th>
                    <td>{number.format(row.July)}</td>
                    <td>{number.format(row.August)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      </div>
      <div className="analytics-panel analytics-comparison-panel">
        <div className="analytics-comparison-toolbar">
          <h3>Member comparison</h3>
          <label>
            Member metric{' '}
            <select
              value={memberMetric}
              onChange={(event) =>
                setMemberMetric(
                  event.target.value as keyof typeof memberMetrics
                )
              }
            >
              {Object.entries(memberMetrics).map(([key, label]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div
          className="analytics-comparison-scroll"
          tabIndex={0}
          role="region"
          aria-label="Member comparison table"
        >
          <table className="analytics-comparison-table">
            <caption className="sr-only">
              Member {memberMetrics[memberMetric].toLowerCase()} in July and
              August 2026
            </caption>
            <thead>
              <tr>
                <th scope="col">Member</th>
                <th scope="col">July 2026</th>
                <th scope="col">August 2026</th>
                <th scope="col">Change %</th>
              </tr>
            </thead>
            <tbody>
              {memberPerformance.map((member) => {
                const august = augustMemberPerformance.find(
                  (row) => row.code === member.code
                )!;
                return (
                  <tr key={member.code}>
                    <th scope="row">{member.name}</th>
                    <td>{number.format(member[memberMetric])}</td>
                    <td>{number.format(august[memberMetric])}</td>
                    <td>
                      {comparisonChange(
                        member[memberMetric],
                        august[memberMetric]
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="analytics-comparison-note">
          Member attribution follows contribution-code prefixes for published,
          unsuppressed catalog records at each export. Catalog changes between
          snapshots can affect member comparisons. A zero July baseline is shown
          as “N/A” when August has activity.
        </p>
      </div>
      <p className="analytics-comparison-note">
        August covers August 1–31, 2026 (UTC), exported{' '}
        {AUGUST_2026_SUMMARY.exportedAt}. July uses the preserved August 20
        export. Detailed July rankings and campus reports are available from the
        report navigation.
      </p>
    </section>
  );
}

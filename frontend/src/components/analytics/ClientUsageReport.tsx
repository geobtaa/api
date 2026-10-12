import { useAnalyticsData } from './AnalyticsData';

import {
  monthLabel,
  periodRange,
  allTimeRange,
} from '../../config/analyticsPeriods';

import { AnalyticsTable } from './AnalyticsTable';
import { Activity, KeyRound, Network, Server, Users } from 'lucide-react';
import { ReportPanelHeader } from './ReportPanelHeader';

const number = new Intl.NumberFormat('en-US');

export function ClientUsageReport({ month }: { month: string }) {
  const analytics = useAnalyticsData();
  const monthly = analytics['monthlySnapshots.json'].default;
  const allTime = analytics['allTimeCurrent.json'].default;
  const clientSnapshots = analytics['clients2026'].clientSnapshots;
  const combineClientSnapshots =
    analytics['clients2026'].combineClientSnapshots;

  const snapshot =
    month === 'all'
      ? combineClientSnapshots(
          allTime.publishedMonths.map(
            (month) => clientSnapshots[month as keyof typeof clientSnapshots]
          )
        )
      : clientSnapshots[month];
  const period = month === 'all' ? 'All time' : monthLabel(month);
  const range = month === 'all' ? allTimeRange : periodRange(month);
  const requests = snapshot.clients.reduce((sum, row) => sum + row.requests, 0);
  const namedRequests = snapshot.clients
    .filter((row) => row.name !== 'Not declared')
    .reduce((sum, row) => sum + row.requests, 0);
  const mcpRequests = snapshot.surfaces.find(
    (row) => row.label === 'MCP endpoints'
  )!.requests;
  const qgisDeclared = snapshot.clients
    .filter((row) => row.channel === 'qgis' || row.name === 'qgis-plugin')
    .reduce((sum, row) => sum + row.requests, 0);

  return (
    <section
      className="analytics-section"
      aria-label={`${period} client and API key usage`}
    >
      <aside
        className="analytics-panel analytics-client-coverage-note"
        role="note"
        aria-label="Historical attribution gaps"
      >
        <ReportPanelHeader
          title="Historical attribution is incomplete"
          icon={Activity}
          level={2}
        />
        <p>
          These snapshots cannot measure total Geoportal usage by API key.
          Requests using the configured unlimited Geoportal key could bypass
          usage logging, and many recorded requests omitted client identity
          headers.
        </p>
        <p>
          “Not declared” means no client label was recorded—not anonymous access
          or a specific application. Missing requests are absent from these
          totals. The small declared SSR count is not the total number of
          Geoportal server requests.
        </p>
        <p>
          Client names and channels are caller-supplied labels, separate from
          verified API-key identity. The logging correction applies to newly
          collected data after deployment; it does not repair these historical
          snapshots.
        </p>
      </aside>
      <div className="analytics-client-highlights">
        <article className="analytics-panel analytics-comparison-panel">
          <h2>
            <Activity aria-hidden="true" />
            Recorded API requests
          </h2>
          <strong>{number.format(requests)}</strong>
          <p>Recorded requests only; historical gaps apply</p>
        </article>
        <article className="analytics-panel analytics-comparison-panel">
          <h2>
            <Users aria-hidden="true" />
            Requests with a client name
          </h2>
          <strong>{number.format(namedRequests)}</strong>
          <p>
            {((namedRequests / requests) * 100).toFixed(2)}% attribution
            coverage
          </p>
        </article>
        <article className="analytics-panel analytics-comparison-panel">
          <h2>
            <KeyRound aria-hidden="true" />
            Known Geoportal API key
          </h2>
          <strong>#129</strong>
          <p>Production frontend BFF · unlimited</p>
        </article>
      </div>
      <article className="analytics-panel analytics-comparison-panel">
        <ReportPanelHeader
          title="Declared clients and channels"
          icon={Users}
          level={2}
        ></ReportPanelHeader>
        <div
          className="analytics-comparison-scroll"
          role="region"
          aria-label="Client usage table"
          tabIndex={0}
        >
          <AnalyticsTable className="analytics-comparison-table analytics-client-table">
            <caption className="sr-only">
              {period} declared client usage
            </caption>
            <thead>
              <tr>
                <th scope="col">Client name</th>
                <th scope="col">Channel</th>
                <th scope="col">API requests</th>
                <th scope="col">Request share</th>
                <th scope="col">Tracked searches</th>
                <th scope="col">Tracked interactions</th>
              </tr>
            </thead>
            <tbody>
              {snapshot.clients.map((row) => (
                <tr key={`${row.name}:${row.channel}`}>
                  <th scope="row">{row.name}</th>
                  <td>{row.channel}</td>
                  <td>{number.format(row.requests)}</td>
                  <td>{((row.requests / requests) * 100).toFixed(2)}%</td>
                  <td>{number.format(row.searches)}</td>
                  <td>{number.format(row.events)}</td>
                </tr>
              ))}
            </tbody>
          </AnalyticsTable>
        </div>
        <p className="analytics-comparison-note">
          Client names and channels are declared by callers. “Not declared”
          means the log has no client identity; it does not identify a
          particular application. API requests, tracked searches, and
          interactions are separate measures. A single API request can carry
          multiple events, and most HTTP requests have no declared client.
        </p>
      </article>
      <article className="analytics-panel analytics-comparison-panel">
        <ReportPanelHeader
          title="API key attribution"
          icon={KeyRound}
          level={2}
        />
        <div className="analytics-comparison-scroll">
          <table
            className="analytics-comparison-table"
            aria-label="Known Geoportal key usage"
          >
            <thead>
              <tr>
                <th scope="col">Known key</th>
                <th scope="col">Access</th>
                <th scope="col">Requests in this period</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <th scope="row">#129 · Production frontend BFF</th>
                <td>Unlimited Geoportal access</td>
                <td>Not recorded</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p className="analytics-comparison-note">
          Production verification on October 12, 2026 matched the configured BFF
          credential to active key #129. BFF key use is known, even though its
          unlimited-access path skipped request logging. Its missing request
          count is not zero and is not included in the recorded totals below.
        </p>
        <div
          className="analytics-comparison-scroll"
          role="region"
          aria-label="API key attribution table"
          tabIndex={0}
        >
          <AnalyticsTable className="analytics-comparison-table">
            <caption className="sr-only">
              {period} API key attribution coverage
            </caption>
            <thead>
              <tr>
                <th scope="col">Attribution</th>
                <th scope="col">Requests</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <th scope="row">Linked to a recorded API key</th>
                <td>{number.format(snapshot.keyAttributedRequests)}</td>
              </tr>
              <tr>
                <th scope="row">No API key attribution recorded</th>
                <td>{number.format(snapshot.unattributedKeyRequests)}</td>
              </tr>
            </tbody>
          </AnalyticsTable>
        </div>
        <p className="analytics-comparison-note">
          These recorded-request totals do not include the omitted BFF requests.
          “Not declared” identifies missing caller labels and is not a
          substitute for BFF usage. Key values and hashes are never included in
          this report.
        </p>
      </article>
      <article className="analytics-panel analytics-comparison-panel">
        <ReportPanelHeader
          title="MCP and QGIS signals"
          icon={Network}
          level={2}
        />
        <div
          className="analytics-comparison-scroll"
          role="region"
          aria-label="MCP and QGIS signals table"
          tabIndex={0}
        >
          <AnalyticsTable className="analytics-comparison-table">
            <caption className="sr-only">
              {period} MCP and QGIS request signals
            </caption>
            <thead>
              <tr>
                <th scope="col">Signal</th>
                <th scope="col">Requests</th>
                <th scope="col">What it measures</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <th scope="row">MCP endpoint traffic</th>
                <td>{number.format(mcpRequests)}</td>
                <td>Logged HTTP requests to MCP routes</td>
              </tr>
              <tr>
                <th scope="row">Declared QGIS client</th>
                <td>{number.format(qgisDeclared)}</td>
                <td>Client name qgis-plugin or channel qgis</td>
              </tr>
              <tr>
                <th scope="row">QGIS user-agent match</th>
                <td>
                  {snapshot.qgisUserAgentRequests === null
                    ? 'Not available'
                    : number.format(snapshot.qgisUserAgentRequests)}
                </td>
                <td>
                  {snapshot.qgisUserAgentRequests === null
                    ? 'July raw request logs are no longer retained'
                    : 'Raw requests with QGIS in the user-agent string'}
                </td>
              </tr>
            </tbody>
          </AnalyticsTable>
        </div>
        <p className="analytics-comparison-note">
          These signals can overlap with declared clients. MCP endpoint requests
          are not a count of successful tool calls or WebSocket messages. QGIS
          can use OGC or other endpoints without declaring its identity. Zero
          matching signatures does not establish zero QGIS usage.
        </p>
      </article>
      <article className="analytics-panel analytics-comparison-panel">
        <ReportPanelHeader
          title="API request surfaces"
          icon={Server}
          level={2}
        />
        <div
          className="analytics-comparison-scroll"
          role="region"
          aria-label="API request surfaces table"
          tabIndex={0}
        >
          <AnalyticsTable className="analytics-comparison-table">
            <caption className="sr-only">
              {period} requests by endpoint category
            </caption>
            <thead>
              <tr>
                <th scope="col">Endpoint category</th>
                <th scope="col">Requests</th>
                <th scope="col">Share</th>
              </tr>
            </thead>
            <tbody>
              {snapshot.surfaces.map((row) => (
                <tr key={row.label}>
                  <th scope="row">{row.label}</th>
                  <td>{number.format(row.requests)}</td>
                  <td>{((row.requests / requests) * 100).toFixed(2)}%</td>
                </tr>
              ))}
            </tbody>
          </AnalyticsTable>
        </div>
        <p className="analytics-comparison-note">
          Endpoint categories explain which API surfaces were requested; they do
          not identify the calling application. OGC traffic may come from QGIS,
          browsers, or other GIS clients. Each logged request belongs to one
          category.
        </p>
      </article>
      <p className="analytics-comparison-note">
        {range} (UTC) · Exported{' '}
        {month === '2026-07' || month === '2026-08'
          ? 'September 9, 2026'
          : month === 'all'
            ? allTime.exportedAt.slice(0, 10)
            : (monthly as Record<string, { summary: { exportedAt: string } }>)[
                month
              ].summary.exportedAt}
        . Request figures use retained daily rollups covering the complete
        selected period and reconcile with the dashboard totals. Search and
        interaction counts use their respective event records. Available
        user-agent matching uses the retained raw request logs.
      </p>
    </section>
  );
}

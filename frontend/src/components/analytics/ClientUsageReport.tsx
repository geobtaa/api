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
        aria-label="Missing application activity"
      >
        <ReportPanelHeader
          title="Some application activity is missing"
          icon={Activity}
          level={2}
        />
        <p>
          These records do not show all Geoportal use by application or access
          key. Some requests from the Geoportal website were not logged, and
          many recorded requests did not identify the application making them.
        </p>
        <p>
          “Not declared” means the application was not identified; it does not
          mean anonymous use. Missing requests are not included in these totals.
          The row labeled SSR covers only identified server requests, not all
          activity from the Geoportal website.
        </p>
        <p>
          Application names are self-reported, not verified identities.
          Improvements to activity recording affect future data; they do not
          fill gaps in these historical reports.
        </p>
      </aside>
      <div className="analytics-client-highlights">
        <article className="analytics-metric-card">
          <h2>
            <Activity aria-hidden="true" />
            Recorded API requests
          </h2>
          <strong>{number.format(requests)}</strong>
          <p>Recorded requests only; historical gaps apply</p>
        </article>
        <article className="analytics-metric-card">
          <h2>
            <Users aria-hidden="true" />
            Requests identifying an application
          </h2>
          <strong>{number.format(namedRequests)}</strong>
          <p>
            {((namedRequests / requests) * 100).toFixed(2)}% of recorded
            requests
          </p>
        </article>
        <article className="analytics-metric-card">
          <h2>
            <KeyRound aria-hidden="true" />
            Known Geoportal API key
          </h2>
          <strong>#129</strong>
          <p>Geoportal website · unlimited access</p>
        </article>
      </div>
      <article className="analytics-panel analytics-comparison-panel">
        <ReportPanelHeader
          title="Reported applications and access methods"
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
                <th scope="col">Application name</th>
                <th scope="col">Access method</th>
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
          Applications supply their own names and access methods. “Not declared”
          means that information was not recorded. Requests, searches, and
          interactions are separate measures: one request can record several
          actions. Most requests do not identify an application.
        </p>
      </article>
      <article className="analytics-panel analytics-comparison-panel">
        <ReportPanelHeader
          title="Requests linked to access keys"
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
                <th scope="row">#129 · Geoportal website</th>
                <td>Unlimited Geoportal access</td>
                <td>Not recorded</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p className="analytics-comparison-note">
          A check on October 12, 2026 confirmed that the Geoportal website uses
          access key #129. Requests using this unlimited-access key were not
          logged. Its request count is therefore unknown, not zero, and is
          absent from the totals below.
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
          These totals exclude the unrecorded website requests. The “Not
          declared” category cannot be used to estimate that missing activity.
          This report does not expose access-key credentials.
        </p>
      </article>
      <article className="analytics-panel analytics-comparison-panel">
        <ReportPanelHeader
          title="AI-tool and mapping-application activity"
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
                <th scope="row">AI-tool connection requests (MCP)</th>
                <td>{number.format(mcpRequests)}</td>
                <td>Recorded requests to the AI-tool connection service</td>
              </tr>
              <tr>
                <th scope="row">Requests identifying themselves as QGIS</th>
                <td>{number.format(qgisDeclared)}</td>
                <td>Requests labeled as QGIS by the application</td>
              </tr>
              <tr>
                <th scope="row">
                  Requests with QGIS in their software identifier
                </th>
                <td>
                  {snapshot.qgisUserAgentRequests === null
                    ? 'Not available'
                    : number.format(snapshot.qgisUserAgentRequests)}
                </td>
                <td>
                  {snapshot.qgisUserAgentRequests === null
                    ? 'July raw request logs are no longer retained'
                    : 'Requests whose software identification includes QGIS'}
                </td>
              </tr>
            </tbody>
          </AnalyticsTable>
        </div>
        <p className="analytics-comparison-note">
          These counts can overlap with the application table above. Model
          Context Protocol (MCP) connects AI tools to the service; its request
          count does not measure completed tool actions. QGIS is a mapping
          application and can access the service without identifying itself. No
          matching records does not prove that QGIS was unused.
        </p>
      </article>
      <article className="analytics-panel analytics-comparison-panel">
        <ReportPanelHeader title="Services requested" icon={Server} level={2} />
        <div
          className="analytics-comparison-scroll"
          role="region"
          aria-label="Services requested table"
          tabIndex={0}
        >
          <AnalyticsTable className="analytics-comparison-table">
            <caption className="sr-only">
              {period} requests by endpoint category
            </caption>
            <thead>
              <tr>
                <th scope="col">Service category</th>
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
          These categories describe which service was requested, not which
          application made the request. Open Geospatial Consortium (OGC)
          services can be used by QGIS, web browsers, or other mapping software.
          Each recorded request belongs to one category.
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
        . Request figures use saved daily counts for the selected period and
        match the dashboard totals. Searches and interactions are counted
        separately. Software identification is available only where detailed
        request records were retained.
      </p>
    </section>
  );
}

import {
  Activity,
  KeyRound,
  Network,
  Server,
  Users,
  Download,
} from 'lucide-react';
import { ReportPanelHeader } from './ReportPanelHeader';
import { clientSnapshots } from '../../data/analytics/clients2026';

const number = new Intl.NumberFormat('en-US');

export function ClientUsageReport({ month }: { month: '2026-07' | '2026-08' }) {
  const snapshot = clientSnapshots[month];
  const period = month === '2026-08' ? 'August' : 'July';
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
  const csv = [
    [
      'Client',
      'Channel',
      'API requests',
      'Tracked searches',
      'Tracked interactions',
    ],
    ...snapshot.clients.map((row) => [
      row.name,
      row.channel,
      row.requests,
      row.searches,
      row.events,
    ]),
  ]
    .map((row) =>
      row.map((cell) => `"${String(cell).replaceAll('"', '""')}"`).join(',')
    )
    .join('\r\n');

  return (
    <section
      className="analytics-section"
      aria-label={`${period} client and API key usage`}
    >
      <div className="analytics-client-highlights">
        <article className="analytics-panel analytics-comparison-panel">
          <h2>
            <Activity aria-hidden="true" />
            Recorded API requests
          </h2>
          <strong>{number.format(requests)}</strong>
          <p>All logged HTTP traffic</p>
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
            API keys identified in logs
          </h2>
          <strong>{snapshot.recordedKeys}</strong>
          <p>Historical key attribution is missing</p>
        </article>
      </div>
      <article className="analytics-panel analytics-comparison-panel">
        <ReportPanelHeader
          title="Declared clients and channels"
          icon={Users}
          level={2}
        >
          <a
            download={`api-clients-${month}.csv`}
            href={`data:text/csv;charset=utf-8,${encodeURIComponent(csv)}`}
          >
            <Download aria-hidden="true" /> Download client CSV
          </a>
        </ReportPanelHeader>
        <div
          className="analytics-comparison-scroll"
          role="region"
          aria-label="Client usage table"
          tabIndex={0}
        >
          <table className="analytics-comparison-table analytics-client-table">
            <caption className="sr-only">
              {period} 2026 declared client usage
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
          </table>
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
        <div
          className="analytics-comparison-scroll"
          role="region"
          aria-label="API key attribution table"
          tabIndex={0}
        >
          <table className="analytics-comparison-table">
            <caption className="sr-only">
              {period} 2026 API key attribution coverage
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
          </table>
        </div>
        <p className="analytics-comparison-note">
          No API-key IDs were recorded for this month, so per-key usage cannot
          be reconstructed from these logs. This does not mean that no keys were
          configured or used. A key such as <code>btaa_geoportal</code> cannot
          be assigned request counts without a recorded link. Key values and
          hashes are never included in this report.
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
          <table className="analytics-comparison-table">
            <caption className="sr-only">
              {period} 2026 MCP and QGIS request signals
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
          </table>
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
          <table className="analytics-comparison-table">
            <caption className="sr-only">
              {period} 2026 requests by endpoint category
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
          </table>
        </div>
        <p className="analytics-comparison-note">
          Endpoint categories explain which API surfaces were requested; they do
          not identify the calling application. OGC traffic may come from QGIS,
          browsers, or other GIS clients. Each logged request belongs to one
          category.
        </p>
      </article>
      <p className="analytics-comparison-note">
        {period} 1–31, 2026 (UTC) · Exported September 9, 2026. Request figures
        use retained daily rollups covering all 31 days and reconcile with the
        dashboard totals. Search and interaction counts use their respective
        event records. August user-agent matching uses the retained raw request
        logs.
      </p>
    </section>
  );
}

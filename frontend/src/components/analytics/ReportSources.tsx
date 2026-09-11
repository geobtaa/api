import type { AnalyticsReport } from '../../config/analyticsReports';

const definitions: Record<
  AnalyticsReport,
  { source: string; grouping: string; limits: string }
> = {
  overview: {
    source:
      'Recorded API requests, searches, search impressions, and interaction events, exported from the production analytics database into checked-in monthly snapshots.',
    grouping:
      'Totals cover the entire portal. Daily series group timestamps by UTC calendar day. Interactions count event rows. Tracked visits deduplicate tokens across searches and events; engaged visits use events only. These are tab-scoped tokens, not unique people.',
    limits:
      'API traffic includes bots and probes. Visits are not unique people, and download clicks are not completed downloads.',
  },
  comparison: {
    source:
      'The preserved July and August snapshots used by the other reports; this page does not query live analytics.',
    grouping:
      'Portal figures cover all recorded traffic. Member figures use contribution-code prefixes 01–17, not Provider. Changes use July as the baseline; both periods contain 31 UTC days.',
    limits:
      'Member attribution uses each export’s catalog: August 20 for July and September 9 for August. Records outside university code groups are excluded from member comparisons but remain in portal totals. A zero baseline is shown as N/A.',
  },
  content: {
    source:
      'Interaction events and recorded search constraints joined to catalog metadata at export. July rankings were exported August 20; August rankings September 9.',
    grouping:
      'Resources rank by resource-view events; downloads by download-click events. Collections count searches carrying collection inclusion filters, deduplicated per search and collection. Momentum compares days 16–31 with days 1–15. Source-site totals and the independently ranked outlink list count visit_source_click events across all recorded resource IDs; their catalog labels were exported September 10.',
    limits:
      'Rankings are not restricted to university providers or published, unsuppressed records. Missing catalog records cannot be ranked by title. Multi-collection searches count in each collection; download clicks do not confirm file transfer.',
  },
  members: {
    source:
      'Resource views, download/source-link clicks, and search impressions joined by resource ID to the catalog snapshot. Only published, unsuppressed records are eligible.',
    grouping:
      'Contribution codes describe acquisition responsibility and can include outside agencies. Provider describes the institution or agency named in the Provider facet. These are different ways to attribute the same activity.',
    limits:
      'Catalog counts are point-in-time inventory, not month-end totals. Historical activity is attributed using metadata available at export. Portal totals also include records outside the eligible member catalog.',
  },
  discovery: {
    source:
      'Recorded searches and their saved query, view, constraints, and zero-results flag. Query rankings were exported September 10 and facet aggregates September 9 for both months.',
    grouping:
      'Top 50 searches group all recorded searches by trimmed, non-empty query text, preserving case and combining filters/views. Zero-result rankings show up to 100 terms with no minimum-frequency cutoff, ordered by count then query using database collation. Facets count distinct searches per category across inclusion, exclusion, and legacy filter formats.',
    limits:
      'Expand recorded search context to inspect saved filters, pagination, and result totals. Plain query links repeat text only; context links repeat the exported parameters. The historical zero-result flag can include an empty page despite a positive total. Facet counts describe filters present in searches, not clicks, and categories overlap. Map bounds and year ranges are included.',
  },
  clients: {
    source:
      'Daily API request rollups plus searches and interaction events, exported September 9. August user-agent evidence comes from retained request logs; July raw request logs had expired.',
    grouping:
      'Client names and channels are caller-declared. API requests, searches, and interactions are counted separately. Endpoint categories classify routes; MCP requests do not measure tool invocations, and OGC requests are not automatically QGIS.',
    limits:
      'Neither month contains recorded API key IDs, so per-key attribution is unavailable. Missing client names are labeled Not declared. Missing July user-agent evidence is unavailable, not zero.',
  },
  platform: {
    source:
      'Monthly API request-log aggregates exported August 20 for July and September 9 for August, using requested-at timestamps and response times.',
    grouping:
      'Requests group by route and UTC date. The monthly mix separates API docs, Turnstile status checks, analytics event capture, and other routes. Peak-day categories use the busiest date. Server errors are HTTP status 500 or higher.',
    limits:
      'Includes automated traffic and health probes, not just visitors. Response percentiles summarize logged requests. Endpoint categories differ from the broader route families in Clients & API keys.',
  },
};

export function ReportSources({
  report,
  month,
}: {
  report: AnalyticsReport;
  month: string;
}) {
  const info = definitions[report];
  return (
    <section
      className="analytics-panel analytics-report-sources"
      aria-label="Sources and grouping"
    >
      <h2>Sources and grouping</h2>
      <p>
        <strong>Period:</strong>{' '}
        {report === 'comparison'
          ? 'July 1–31 and August 1–31, 2026'
          : `${month} 1–31, 2026`}{' '}
        (UTC). Static aggregate snapshots, not live traffic.
      </p>
      <dl>
        <div>
          <dt>Source</dt>
          <dd>{info.source}</dd>
        </div>
        <div>
          <dt>Grouping</dt>
          <dd>{info.grouping}</dd>
        </div>
        <div>
          <dt>Reading the figures</dt>
          <dd>{info.limits}</dd>
        </div>
      </dl>
    </section>
  );
}

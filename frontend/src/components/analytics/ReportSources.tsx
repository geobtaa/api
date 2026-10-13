import { ReportProvenance } from './ReportProvenance';
import { useAnalyticsData } from './AnalyticsData';
import { BookOpen } from 'lucide-react';
import { ReportPanelHeader } from './ReportPanelHeader';
import { comparisonLabel } from '../../config/analyticsPeriods';

import manifest from '../../../private-analytics-reports/manifest.json';
import type { AnalyticsReport } from '../../config/analyticsReports';

const definitions: Record<
  AnalyticsReport,
  { source: string; grouping: string; limits: string }
> = {
  overview: {
    source:
      'Saved monthly records of service requests, searches, resource appearances in results, and clicks.',
    grouping:
      'Totals cover the whole Geoportal. Days use Coordinated Universal Time (UTC). Visits are tracked within browser tabs across searches and clicks; a person using several tabs can count more than once. Visits with activity count tabs with a recorded action.',
    limits:
      'Service requests include automated traffic and system checks. Visits are not individual people, and download clicks do not confirm completed downloads.',
  },
  comparison: {
    source:
      'The same saved monthly reports used throughout this dashboard, rather than live activity.',
    grouping:
      'Figures cover the whole Geoportal. Changes compare the latest published month with the previous month. Use daily averages when comparing months of different lengths.',
    limits:
      'A percentage change cannot be calculated when the earlier value is zero; it is shown as N/A. Service requests include automated traffic.',
  },
  content: {
    source:
      'Saved resource activity linked to the catalog information available when the report was prepared.',
    grouping:
      'Resources and collections are ranked by views; download lists are ranked by download-link clicks. Collection totals count views of resources belonging to each collection. Changes compare the previous calendar month. Source-site clicks count links to the websites hosting resources; that list is ranked separately from resource views.',
    limits:
      'These lists include resources beyond member institutions. Records missing catalog information may be absent from title-based rankings. A resource in several collections contributes views to each. Catalog labels may have been refreshed separately from the activity records. Download clicks do not confirm completed downloads.',
  },
  members: {
    source:
      'Views, download clicks, source-site clicks, and appearances in search results linked to published, publicly visible catalog records.',
    grouping:
      'BTAA contributing institution groups resources by responsibility for adding them to the Geoportal, including resources from outside agencies. Catalog provider uses the institution or agency named in the catalog. These groupings answer different questions about the same activity.',
    limits:
      'Catalog counts reflect the date shown, not necessarily the end of the month. Activity is assigned using the catalog information saved with the report. Geoportal-wide totals can include resources not included in the member report.',
  },
  discovery: {
    source:
      'Saved searches, including search terms, filters, results view, and whether the displayed page had any results.',
    grouping:
      'The top 50 search terms combine searches with the same text, including searches using different filters or views. Capitalization is preserved and spaces at the beginning and end are ignored. Up to 100 terms without results are shown, subject to the reporting period’s privacy rules. Filter counts measure searches using each category, not clicks on filter controls; categories can overlap.',
    limits:
      'A search with no displayed results does not necessarily indicate a collection gap: filters or the selected results page may explain it. Expand the saved search details before drawing conclusions. Search-term links repeat only the words; links with saved settings also apply the recorded filters and page settings.',
  },
  clients: {
    source:
      'Saved daily service-request totals, searches, and clicks. Application-identification details come from retained request logs; those detailed logs are no longer available for July.',
    grouping:
      'Application names and access methods are supplied by the applications themselves. Service requests, searches, and clicks are separate measures. Requests to AI-tool connections (MCP) are not counts of completed tool actions. Requests to geospatial services (OGC) do not identify which mapping application was used.',
    limits:
      'The published periods contain no recorded API key identifiers, so requests cannot be assigned to individual access keys. “Not declared” means the application did not identify itself. Missing historical detail is unavailable, not zero.',
  },
  platform: {
    source:
      'Saved service-request records, including request times, response times, and errors.',
    grouping:
      'Requests are grouped by service address and day in UTC. Categories include API documentation, security checks, activity recording, and other services. The busiest-day breakdown uses the date with the most requests. Server errors are responses with HTTP status 500 or higher.',
    limits:
      'Traffic includes automated requests and system checks, not just visits. Response-time statistics describe the requests that were recorded.',
  },
};

export function ReportSources({
  report,
  month,
  period,
  snapshotPeriod,
}: {
  report: AnalyticsReport;
  month: string;
  period?: string;
  snapshotPeriod?: string;
}) {
  const analytics = useAnalyticsData();
  const outcomes = analytics['outcomes'].outcomes;

  const info = definitions[report];
  const archive = manifest.periods.find(
    (entry) => entry.id === (report === 'comparison' ? 'all' : snapshotPeriod)
  );
  return (
    <>
      <section
        className="analytics-panel analytics-report-sources"
        id="report-sources"
        aria-label="About this report"
      >
        <ReportPanelHeader
          title="About this report"
          icon={BookOpen}
          level={2}
        />
        <p>
          <strong>Period:</strong>{' '}
          {report === 'comparison'
            ? comparisonLabel
            : (period ?? `${month} 1–31, 2026`)}{' '}
          (UTC). Saved report data, not live activity.
        </p>
        {report === 'content' && (
          <p>
            Resource titles and Provider fields refreshed{' '}
            {new Date(outcomes.contentCatalogCapturedAt).toLocaleDateString(
              'en-US',
              {
                month: 'long',
                day: 'numeric',
                year: 'numeric',
                timeZone: 'UTC',
              }
            )}
            , independently of campus inventory eligibility. “Provider not
            recorded” means the Provider field is empty; “Provider metadata
            unavailable” means no metadata could be retrieved.
          </p>
        )}
        <div className="analytics-sources-table-wrap">
          <table className="analytics-sources-table">
            <caption className="sr-only">About this report definitions</caption>
            <tbody>
              <tr>
                <th scope="row">Data used</th>
                <td>{info.source}</td>
              </tr>
              <tr>
                <th scope="row">How it is counted</th>
                <td>{info.grouping}</td>
              </tr>
              <tr>
                <th scope="row">Reading the figures</th>
                <td>{info.limits}</td>
              </tr>
            </tbody>
          </table>
        </div>
        {archive && (
          <p className="analytics-source-download">
            <a
              className="analytics-snapshot-download"
              href={`/analytics-reports/${archive.id}/${archive.revision}/tables.zip`}
              download
            >
              Download report data (CSV and JSON)
            </a>
          </p>
        )}
      </section>
      {archive && (
        <ReportProvenance
          report={archive}
          downloadUrl={
            archive.evidence
              ? `/analytics-reports/${archive.id}/${archive.revision}/evidence-${archive.evidence.checksum}.zip`
              : undefined
          }
        />
      )}
    </>
  );
}

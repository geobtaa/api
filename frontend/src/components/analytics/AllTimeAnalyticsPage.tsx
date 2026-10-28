import { RecordAccessPatterns } from './RecordAccessPatterns';
import { ReportProvenance } from './ReportProvenance';
import { useAnalyticsData } from './AnalyticsData';
import { allTimeRange } from '../../config/analyticsPeriods';
import manifest from '../../../private-analytics-reports/manifest.json';
import { ReportingPeriodPicker } from './ReportingPeriodPicker';
import { ReportContentLayout } from './ReportContentLayout';

import { PopularContentReport } from './PopularContentReport';
import { OutlinkedResources } from './DiscoveryOutcomes';

import { Seo } from '../Seo';
import { useSearchParams } from 'react-router';

import {
  analyticsReports,
  type AnalyticsReport,
} from '../../config/analyticsReports';
import { AnalyticsHeader } from './AnalyticsHeader';

const range = allTimeRange;

export function AllTimeAnalyticsPage({
  reportId,
}: {
  reportId: AnalyticsReport;
}) {
  const analytics = useAnalyticsData();
  const collectionViews = analytics['collectionViewsCurrent.json'].default;
  const outcomes = analytics['outcomes'].outcomes;
  const data = analytics['allTimeCurrent.json'].default;
  const archive = manifest.periods.find((entry) => entry.id === 'all')!;

  const [params, setParams] = useSearchParams();
  const report = analyticsReports.find((entry) => entry.id === reportId)!;
  return (
    <div className="analytics-page min-h-screen bg-gray-50">
      <Seo
        title={`${report.label} — All time — Analytics`}
        description="Academic-year analytics across published months beginning July 1, 2026."
      />
      <AnalyticsHeader activeReport={reportId} />
      <main id="analytics-main" tabIndex={-1}>
        <div className="analytics-shell analytics-report-intro">
          <div className="analytics-report-title">
            <p>All time · Academic year to date</p>
            <h1>{report.label}</h1>
            <span>
              {range}. Includes published months since the academic year began
              July 1.
            </span>
          </div>
          <ReportingPeriodPicker
            id="all-time-period"
            value="all"
            label="Reporting period"
            onChange={(value) => {
              const next = new URLSearchParams(params);
              next.set('month', value);
              setParams(next);
            }}
          />
        </div>
        <ReportContentLayout report={report.label}>
          <div className="analytics-shell analytics-content analytics-all-time">
            {reportId === 'content' && (
              <>
                <PopularContentReport
                  title="Top resources and collections across all months"
                  topResources={data.resources.map((row) => ({
                    id: row.id,
                    title: row.title ?? row.id,
                    provider: row.provider ?? 'Missing provider',
                    resourceClass: row.resourceClass,
                    resourceType: row.resourceType,
                    views: row.views,
                    actions: null,
                    firstHalfEvents: 0,
                    secondHalfEvents: 0,
                  }))}
                  topCollections={collectionViews.all}
                  collectionNote="Ranked by views of member resources across all published months, using each month's saved collection membership. Resources in multiple collections contribute views to each; resources without recorded membership are excluded."
                  topDownloadedResources={outcomes.periods.all.downloads.map(
                    (row) => ({
                      id: row.id,
                      title: row.title ?? row.id,
                      provider: row.provider ?? 'Missing provider',
                      resourceClass: '',
                      formatLabel: '',
                      clicks: row.clicks,
                      engagedVisits: null,
                    })
                  )}
                  downloadClicks={outcomes.periods.all.totals.downloads}
                  downloadNote="Ranked across all published months."
                />
                <OutlinkedResources period="all" />
                <RecordAccessPatterns period="all" />
              </>
            )}
            <section
              id="report-sources"
              className="analytics-report-sources"
              aria-label="About this report"
            >
              <h2>About this report</h2>
              <p>
                All time begins at the academic-year start, July 1, and includes
                published monthly reports: {range} (UTC). Daily dates retain
                their month. Searches and resource rankings use records from the
                full period, rather than adding monthly top lists. Appearances
                in search results use saved daily counts. Resource counts and
                institution assignments use the catalog saved for each month;
                latest catalog date {data.catalogDate}. Resource titles and
                Provider fields refreshed{' '}
                {new Date(outcomes.contentCatalogCapturedAt).toLocaleDateString(
                  'en-US',
                  { timeZone: 'UTC' }
                )}
                , independently of campus eligibility.
              </p>
              <p>
                Exported{' '}
                {new Date(data.exportedAt).toLocaleDateString('en-US', {
                  timeZone: 'UTC',
                })}
                . Tables are sortable and filterable.
              </p>
              <p>
                <a
                  href={`/analytics-reports/all/${archive.revision}/tables.zip`}
                  download
                >
                  Download report data (CSV and JSON)
                </a>
              </p>
            </section>
            {reportId === 'content' && (
              <p>
                The most-viewed ranking uses preserved monthly catalog metadata.
                Source-site and download-click rankings include all recorded
                resources, even when catalog information is missing. Collection
                rankings are ranked by views of resources in each collection
                across all saved months before selecting the top 50.
              </p>
            )}
            <ReportProvenance
              report={archive}
              downloadUrl={
                archive.evidence
                  ? `/analytics-reports/all/${archive.revision}/evidence-${archive.evidence.checksum}.zip`
                  : undefined
              }
            />
          </div>
        </ReportContentLayout>
      </main>
    </div>
  );
}

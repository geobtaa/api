import { ReportingPeriodPicker } from './ReportingPeriodPicker';
import { ReportContentLayout } from './ReportContentLayout';
import collectionSearches from '../../data/analytics/collectionSearchesAllTime2026.json';
import type { CollectionChartEntry } from '../../data/analytics/july2026';
import { PopularContentReport } from './PopularContentReport';
import { AccessSummary, OutlinkedResources } from './DiscoveryOutcomes';
import { outcomes } from '../../data/analytics/outcomes';
import { Seo } from '../Seo';
import { useSearchParams } from 'react-router';
import data from '../../data/analytics/allTime2026.json';

import {
  analyticsReports,
  type AnalyticsReport,
} from '../../config/analyticsReports';
import { AnalyticsHeader } from './AnalyticsHeader';

const range = 'July 1–August 31, 2026';
export function AllTimeAnalyticsPage({
  reportId,
}: {
  reportId: AnalyticsReport;
}) {
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
              July 1. September joins once its monthly report is published.
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
                  title="All time’s top resources and collections"
                  topResources={data.resources.map((row) => ({
                    id: row.id,
                    title: row.title ?? row.id,
                    provider: row.provider ?? 'Missing provider',
                    resourceClass: '',
                    resourceType: '',
                    views: row.views,
                    actions: null,
                    firstHalfEvents: 0,
                    secondHalfEvents: 0,
                  }))}
                  topCollections={(
                    collectionSearches.collections as CollectionChartEntry[]
                  ).slice(0, 10)}
                  collectionNote={collectionSearches.method}
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
              </>
            )}
            {reportId === 'content' && <AccessSummary period="all" />}
            <section
              id="report-sources"
              className="analytics-report-sources"
              aria-label="Sources and grouping"
            >
              <h2>Sources and grouping</h2>
              <p>
                All time begins at the academic-year start, July 1, and includes
                published monthly reports: {range} (UTC). Daily dates retain
                their month. Searches and content rankings are recomputed from
                full-period records, not combined top lists. Resource
                impressions use durable daily aggregates; inventory and
                attribution use the catalog on {data.catalogDate}.
              </p>
              <p>
                Exported{' '}
                {new Date(data.exportedAt).toLocaleDateString('en-US', {
                  timeZone: 'UTC',
                })}
                . Tables are sortable and filterable.
              </p>
            </section>
            {reportId === 'content' && (
              <p>
                The most-viewed ranking uses current published, unsuppressed
                catalog metadata. Outlink and download rankings include all
                recorded resource IDs, retaining missing catalog records.
                Collection rankings are rebuilt from preserved monthly search
                dimensions before selecting the top ten. Half-month momentum
                remains in monthly reports.
              </p>
            )}
          </div>
        </ReportContentLayout>
      </main>
    </div>
  );
}

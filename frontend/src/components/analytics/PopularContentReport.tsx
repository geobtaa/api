import { useAnalyticsData } from './AnalyticsData';

import { RankingRow } from './RankingRow';
import { ReportSectionHeading } from './ReportSectionHeading';
import { useRanking } from './useRanking';
import { Download, Flame, Layers3, Trophy } from 'lucide-react';
import type {
  ResourceChartEntry,
  DownloadChartEntry,
} from '../../data/analytics/july2026';
import { ResourceThumbnail } from './ResourceThumbnail';

export type PopularResource = Omit<ResourceChartEntry, 'actions'> & {
  actions: number | null;
  previousMonthViews?: number | null;
};
export type PopularDownload = Omit<DownloadChartEntry, 'engagedVisits'> & {
  engagedVisits: number | null;
};
const wholeNumber = new Intl.NumberFormat('en-US');

export type CollectionViewsEntry = { id: string; title: string; views: number };

function collectionHref(collection: CollectionViewsEntry) {
  return `/resources/${encodeURIComponent(collection.id)}`;
}

function ResourceRankingRow({
  resource,
  rank,
  month,
  maxViews,
}: {
  resource: PopularResource;
  rank: number;
  maxViews: number;
  month?: string;
}) {
  return (
    <RankingRow
      rank={rank}
      title={resource.title}
      href={`/resources/${encodeURIComponent(resource.id)}`}
      thumbnail={<ResourceThumbnail resource={resource} eager={rank === 1} />}
      kicker={
        <>
          {resource.resourceClass && <span>{resource.resourceClass}</span>}
          {resource.year && <span>{resource.year}</span>}
        </>
      }
      description={
        resource.provider +
        (resource.resourceType ? ` · ${resource.resourceType}` : '')
      }
      value={resource.views}
      label="views"
      maximum={maxViews}
      previousValue={month ? (resource.previousMonthViews ?? null) : undefined}
    />
  );
}

export function PopularContentReport({
  title,
  reportMonth,
  reportPeriod,
  topResources,
  topCollections,
  collectionNote,
  topDownloadedResources,
  downloadClicks,
  downloadNote,
}: {
  title: string;
  reportMonth?: string;
  reportPeriod?: string;
  topResources: PopularResource[];
  topCollections: CollectionViewsEntry[] | null;
  collectionNote: string;
  topDownloadedResources: PopularDownload[];
  downloadClicks: number;
  downloadNote: string;
}) {
  const analytics = useAnalyticsData();
  const previousRankingValue =
    analytics['popularMomentum'].previousRankingValue;

  const resources = useRanking(
    topResources,
    (row) => row.views,
    'Top resources'
  );
  const downloads = useRanking(
    topDownloadedResources,
    (row) => row.clicks,
    'Top downloaded resources'
  );
  const maxCollectionViews = Math.max(
    1,
    ...(topCollections ?? []).map((row) => row.views)
  );
  const maxDownloadClicks = Math.max(
    1,
    ...topDownloadedResources.map((row) => row.clicks)
  );
  return (
    <section id="charts" className="analytics-section" data-nav-exclude>
      <ReportSectionHeading
        title={title}
        description={
          reportMonth
            ? `Ranked by resource detail views. Momentum compares each ranking’s metric with the previous calendar month; totals are not adjusted for month length.`
            : 'Ranked by resource detail views across all published months.'
        }
      />

      <div className="analytics-charts-grid">
        <div
          id="top-resources"
          className="analytics-panel analytics-panel--ranking"
        >
          <div className="analytics-panel-header">
            <div>
              <Flame className="h-5 w-5" aria-hidden />
              <h3>Top resources</h3>
            </div>
            <div className="analytics-ranking-legend" aria-hidden="true">
              <span>Views</span>
              {reportMonth && <span>Momentum</span>}
            </div>
          </div>
          {resources.controls}
          <div className="analytics-ranking-list">
            {resources.visible.map(({ row: resource, rank }) => (
              <ResourceRankingRow
                key={resource.id}
                resource={resource}
                rank={rank}
                maxViews={Math.max(1, ...topResources.map((row) => row.views))}
                month={reportMonth}
              />
            ))}
          </div>
        </div>
      </div>

      <div className="analytics-taxonomy-grid">
        {(['resourceClass', 'resourceType'] as const).map((field) => {
          const counts = new Map<string, number>();
          const priorCounts = new Map<string, number | null>();
          topResources.forEach((resource) => {
            const labels = [
              ...new Set(
                (resource[field] || 'Not recorded')
                  .split(',')
                  .map((value) => value.trim())
                  .filter(Boolean)
              ),
            ];
            labels.forEach((label) => {
              counts.set(label, (counts.get(label) || 0) + resource.views);
              const prior = priorCounts.get(label);
              priorCounts.set(
                label,
                prior === null || resource.previousMonthViews == null
                  ? null
                  : (prior ?? 0) + resource.previousMonthViews
              );
            });
          });
          const rows = [...counts]
            .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
            .slice(0, 10);
          return (
            <article className="analytics-panel" key={field}>
              <div className="analytics-panel-header">
                <div>
                  <Layers3 size={20} aria-hidden />
                  <h3>
                    {field === 'resourceClass'
                      ? 'Top resource classes'
                      : 'Top resource types'}
                  </h3>
                </div>
                <small>resource views</small>
              </div>
              <p className="analytics-download-note">
                Within the {topResources.length} resources ranked above.
                Resources with multiple classifications contribute to each;
                missing metadata is shown as Not recorded.
                {reportMonth &&
                  ' Momentum compares the same resources and classifications in both months.'}
              </p>
              <div className="analytics-ranking-list">
                {rows.map(([label, views], index) => (
                  <RankingRow
                    key={label}
                    rank={index + 1}
                    title={label}
                    value={views}
                    label="views"
                    maximum={rows[0][1]}
                    previousValue={
                      reportMonth ? (priorCounts.get(label) ?? null) : undefined
                    }
                  />
                ))}
              </div>
            </article>
          );
        })}
      </div>
      <aside
        id="collections"
        className="analytics-panel analytics-panel--collections"
      >
        <div className="analytics-panel-header">
          <div>
            <Trophy className="h-5 w-5" aria-hidden />
            <h3>Top collections</h3>
          </div>
          <small>resource views</small>
        </div>
        {topCollections === null && (
          <p className="analytics-download-note">
            Collection rankings are unavailable in the saved All time snapshot.
            Monthly top lists cannot reconstruct a complete combined ranking.
          </p>
        )}
        <div className="analytics-ranking-list">
          {topCollections?.map((collection, index) => (
            <RankingRow
              key={`${collection.title}-${collection.id ?? index}`}
              rank={index + 1}
              title={collection.title}
              href={collectionHref(collection)}
              thumbnail={
                <ResourceThumbnail
                  resource={{
                    id: collection.id,
                    title: collection.title,
                    resourceClass: 'Collections',
                  }}
                  href={collectionHref(collection)}
                />
              }
              description="Views of member resources"
              value={collection.views}
              label="views"
              maximum={maxCollectionViews}
              previousValue={
                reportMonth
                  ? (previousRankingValue(
                      reportPeriod,
                      'collections',
                      collection.id
                    ) ?? null)
                  : undefined
              }
            />
          ))}
        </div>
        <div className="analytics-chart-note">
          <Layers3 className="h-5 w-5" aria-hidden />
          <p>{collectionNote}</p>
        </div>
      </aside>
      <article
        id="downloads"
        className="analytics-panel analytics-download-chart"
      >
        <div className="analytics-panel-header">
          <div>
            <Download className="h-5 w-5" aria-hidden />
            <h3>Top downloaded resources</h3>
          </div>
          <small>
            {wholeNumber.format(downloadClicks)} across all resources
          </small>
        </div>
        {downloads.controls}
        <div className="analytics-ranking-list">
          {downloads.visible.map(({ row: resource, rank }) => (
            <RankingRow
              key={resource.id}
              rank={rank}
              title={resource.title}
              href={`/resources/${encodeURIComponent(resource.id)}`}
              thumbnail={
                <ResourceThumbnail resource={resource} eager={rank === 1} />
              }
              kicker={
                resource.resourceClass && <span>{resource.resourceClass}</span>
              }
              description={
                resource.provider +
                (resource.formatLabel ? ` · ${resource.formatLabel}` : '')
              }
              value={resource.clicks}
              label="download clicks"
              maximum={maxDownloadClicks}
              previousValue={
                reportMonth
                  ? (previousRankingValue(
                      reportPeriod,
                      'downloads',
                      resource.id
                    ) ?? null)
                  : undefined
              }
              secondary={{ value: resource.engagedVisits, label: 'visits' }}
            />
          ))}
        </div>
        <p className="analytics-download-note">
          {downloadNote} A click records selection of a catalog download link;
          completion on an external provider site cannot be verified.
          {reportMonth
            ? ' Visits are distinct tracked visit tokens.'
            : ' Distinct download visits are unavailable in this snapshot; monthly distinct counts are not added together.'}
        </p>
      </article>
    </section>
  );
}

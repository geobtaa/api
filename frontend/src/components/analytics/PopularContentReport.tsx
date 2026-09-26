import { ReportSectionHeading } from './ReportSectionHeading';
import { useId, useState } from 'react';
import { Link } from 'react-router';
import {
  ArrowDownRight,
  ArrowUpRight,
  Download,
  Flame,
  Layers3,
  Trophy,
} from 'lucide-react';
import type {
  ResourceChartEntry,
  CollectionChartEntry,
  DownloadChartEntry,
} from '../../data/analytics/july2026';
import { ResourceThumbnail } from './ResourceThumbnail';

export type PopularResource = Omit<ResourceChartEntry, 'actions'> & {
  actions: number | null;
};
export type PopularDownload = Omit<DownloadChartEntry, 'engagedVisits'> & {
  engagedVisits: number | null;
};
const wholeNumber = new Intl.NumberFormat('en-US');

function collectionHref(collection: CollectionChartEntry) {
  if (collection.id) return `/resources/${encodeURIComponent(collection.id)}`;

  const params = new URLSearchParams();
  params.append(
    `include_filters[${collection.filterField}][]`,
    collection.title
  );
  return `/search?${params.toString()}`;
}

function resourceMomentum(resource: PopularResource) {
  if (resource.firstHalfEvents === 0) {
    return { label: 'New', direction: 'up' as const };
  }

  const change = Math.round(
    ((resource.secondHalfEvents - resource.firstHalfEvents) /
      resource.firstHalfEvents) *
      100
  );

  if (change > 0) {
    return { label: `${change}%`, direction: 'up' as const };
  }

  if (change < 0) {
    return { label: `${Math.abs(change)}%`, direction: 'down' as const };
  }

  return { label: 'Even', direction: 'flat' as const };
}

function MomentumBadge({
  resource,
  month,
}: {
  resource: PopularResource;
  month?: string;
}) {
  const momentum = resourceMomentum(resource);

  return (
    <span
      className={`analytics-momentum analytics-momentum--${momentum.direction}`}
      title={`All tracked interactions in ${month} 16–31 compared with ${month} 1–15`}
    >
      {momentum.direction === 'up' && (
        <ArrowUpRight className="h-3.5 w-3.5" aria-hidden />
      )}
      {momentum.direction === 'down' && (
        <ArrowDownRight className="h-3.5 w-3.5" aria-hidden />
      )}
      {momentum.label}
    </span>
  );
}

function ResourceRankingRow({
  resource,
  rank,
  month,
}: {
  resource: PopularResource;
  rank: number;
  month?: string;
}) {
  const isLeader = rank === 1;

  return (
    <article
      className={`analytics-ranking-row${isLeader ? ' analytics-ranking-row--leader' : ''}`}
    >
      <div className="analytics-rank-number" aria-label={`Rank ${rank}`}>
        <span>#</span>
        {rank}
      </div>
      <ResourceThumbnail resource={resource} eager={isLeader} />
      <div className="analytics-ranking-copy">
        <div className="analytics-ranking-kicker">
          {resource.resourceClass && <span>{resource.resourceClass}</span>}
          {resource.year && <span>{resource.year}</span>}
        </div>
        <h3>
          <Link to={`/resources/${encodeURIComponent(resource.id)}`}>
            {resource.title}
          </Link>
        </h3>
        <p>
          {resource.provider}
          {resource.resourceType ? ` · ${resource.resourceType}` : ''}
        </p>
      </div>
      <div className="analytics-ranking-stat">
        <strong>{wholeNumber.format(resource.views)}</strong>
        <span>views</span>
      </div>
      <div className="analytics-ranking-stat analytics-ranking-stat--actions">
        <strong>
          {resource.actions === null
            ? '—'
            : wholeNumber.format(resource.actions)}
        </strong>
        <span>actions</span>
      </div>
      <div className="analytics-ranking-trend">
        {month ? (
          <>
            <MomentumBadge resource={resource} month={month} />
            <span>2H pulse</span>
          </>
        ) : (
          <>
            <span>—</span>
            <span>Monthly only</span>
          </>
        )}
      </div>
      <Link
        to={`/resources/${encodeURIComponent(resource.id)}`}
        className="analytics-row-action"
        aria-label={`Open ${resource.title}`}
      >
        <ArrowUpRight className="h-4 w-4" aria-hidden />
      </Link>
    </article>
  );
}

function useRanking<T extends { title: string; provider: string }>(
  rows: T[],
  count: (row: T) => number,
  label: string
) {
  const id = useId();
  const [query, setQuery] = useState('');
  const [order, setOrder] = useState('count');
  const terms = query.toLowerCase().trim().split(/\s+/).filter(Boolean);
  const visible = rows
    .map((row, index) => ({ row, rank: index + 1 }))
    .filter(({ row }) =>
      terms.every((term) =>
        `${row.title} ${row.provider}`.toLowerCase().includes(term)
      )
    )
    .sort((a, b) =>
      order === 'title'
        ? a.row.title.localeCompare(b.row.title)
        : order === 'provider'
          ? a.row.provider.localeCompare(b.row.provider)
          : count(b.row) - count(a.row)
    );
  return {
    visible,
    controls: (
      <div className="analytics-table-tools analytics-table-tools--inset">
        <label htmlFor={id}>
          Filter resources
          <input
            id={id}
            type="search"
            aria-label={`Filter ${label}`}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search titles or providers…"
          />
        </label>
        <label>
          Sort by
          <select
            aria-label={`Sort ${label}`}
            value={order}
            onChange={(event) => setOrder(event.target.value)}
          >
            <option value="count">
              Most {label === 'Top resources' ? 'views' : 'clicks'}
            </option>
            <option value="title">Title</option>
            <option value="provider">Provider</option>
          </select>
        </label>
        <span role="status">
          {visible.length} of {rows.length} resources
        </span>
      </div>
    ),
  };
}

export function PopularContentReport({
  title,
  reportMonth,
  topResources,
  topCollections,
  collectionNote,
  topDownloadedResources,
  downloadClicks,
  downloadNote,
}: {
  title: string;
  reportMonth?: string;
  topResources: PopularResource[];
  topCollections: CollectionChartEntry[] | null;
  collectionNote: string;
  topDownloadedResources: PopularDownload[];
  downloadClicks: number;
  downloadNote: string;
}) {
  const resources = useRanking(
    topResources,
    (row) => row.views,
    'Top resources'
  );
  const downloads = useRanking(
    topDownloadedResources,
    (row) => row.clicks,
    'Top download clicks'
  );
  const maxCollectionSearches = Math.max(
    1,
    ...(topCollections ?? []).map((row) => row.searches)
  );
  const maxDownloadClicks = Math.max(
    1,
    ...topDownloadedResources.map((row) => row.clicks)
  );
  return (
    <section id="charts" className="analytics-section">
      <ReportSectionHeading
        title={title}
        description={
          reportMonth
            ? `Ranked by resource detail views. Momentum compares all tracked interactions in the first and second halves of ${reportMonth}.`
            : 'Ranked by resource detail views across all published months. Half-month momentum applies only to monthly reports.'
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
              <span>Top resources</span>
            </div>
            <div className="analytics-ranking-legend" aria-hidden="true">
              <span>Views</span>
              <span>Actions</span>
              <span>Momentum</span>
            </div>
          </div>
          {resources.controls}
          <div className="analytics-ranking-list">
            {resources.visible.map(({ row: resource, rank }) => (
              <ResourceRankingRow
                key={resource.id}
                resource={resource}
                rank={rank}
                month={reportMonth}
              />
            ))}
          </div>
        </div>

        <aside
          id="collections"
          className="analytics-panel analytics-panel--collections"
        >
          <div className="analytics-panel-header">
            <div>
              <Trophy className="h-5 w-5" aria-hidden />
              <span>Collection chart</span>
            </div>
            <small>filtered searches</small>
          </div>
          {topCollections === null && (
            <p className="analytics-download-note">
              Collection rankings are unavailable in the saved All time
              snapshot. Monthly top lists cannot reconstruct a complete combined
              ranking.
            </p>
          )}
          <ol className="analytics-collection-list">
            {topCollections?.map((collection, index) => (
              <li key={`${collection.title}-${collection.id ?? index}`}>
                <span className="analytics-collection-rank">
                  {String(index + 1).padStart(2, '0')}
                </span>
                <div className="analytics-resource-cell">
                  <ResourceThumbnail
                    resource={{
                      id: collection.id,
                      title: collection.title,
                      resourceClass: 'Collections',
                    }}
                    href={collectionHref(collection)}
                    compact
                  />
                  <div className="analytics-collection-copy">
                    <Link to={collectionHref(collection)}>
                      {collection.title}
                    </Link>
                    <span>{collection.kind}</span>
                    <div
                      className="analytics-collection-track"
                      aria-hidden="true"
                    >
                      <i
                        style={{
                          width: `${(collection.searches / maxCollectionSearches) * 100}%`,
                        }}
                      />
                    </div>
                  </div>
                </div>
                <strong>{collection.searches}</strong>
              </li>
            ))}
          </ol>
          <div className="analytics-chart-note">
            <Layers3 className="h-5 w-5" aria-hidden />
            <p>{collectionNote}</p>
          </div>
        </aside>
      </div>

      <article
        id="downloads"
        className="analytics-panel analytics-download-chart"
      >
        <div className="analytics-panel-header">
          <div>
            <Download className="h-5 w-5" aria-hidden />
            <span>Top download clicks</span>
          </div>
          <small>
            {wholeNumber.format(downloadClicks)} across all resources
          </small>
        </div>
        <div className="analytics-download-legend" aria-hidden="true">
          <span>Resource</span>
          <span>Clicks</span>
          <span>Visits</span>
        </div>
        {downloads.controls}
        <ol className="analytics-download-list">
          {downloads.visible.map(({ row: resource, rank }) => (
            <li key={resource.id}>
              <span className="analytics-download-rank">
                {String(rank).padStart(2, '0')}
              </span>
              <div className="analytics-resource-cell">
                <ResourceThumbnail resource={resource} compact />
                <div className="analytics-download-copy">
                  <div>
                    {resource.resourceClass && (
                      <span>{resource.resourceClass}</span>
                    )}
                    <Link to={`/resources/${encodeURIComponent(resource.id)}`}>
                      {resource.title}
                    </Link>
                  </div>
                  <p>
                    {resource.provider}
                    {resource.formatLabel ? ` · ${resource.formatLabel}` : ''}
                  </p>
                  <div className="analytics-download-track" aria-hidden>
                    <i
                      style={{
                        width: `${(resource.clicks / maxDownloadClicks) * 100}%`,
                      }}
                    />
                  </div>
                </div>
              </div>
              <strong>{resource.clicks}</strong>
              <span>{resource.engagedVisits ?? '—'}</span>
              <Link
                to={`/resources/${encodeURIComponent(resource.id)}`}
                className="analytics-row-action"
                aria-label={`Open ${resource.title}`}
              >
                <ArrowUpRight className="h-4 w-4" aria-hidden />
              </Link>
            </li>
          ))}
        </ol>
        <p className="analytics-download-note">
          {downloadNote} A click records selection of a catalog download link;
          completion on an external provider site cannot be verified.
          {reportMonth
            ? ' Visits are distinct tracked visit tokens.'
            : ' Distinct download visits and complete per-resource action totals are unavailable in this snapshot; monthly distinct counts are not added together.'}
        </p>
      </article>
    </section>
  );
}

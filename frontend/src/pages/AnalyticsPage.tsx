import { searchSnapshots } from '../data/analytics/searches2026';
import { FACET_LABELS } from '../utils/facetLabels';
import { ClientUsageReport } from '../components/analytics/ClientUsageReport';
import * as augustReports from '../data/analytics/reportsAugust2026';
import { augustDailyActivity } from '../data/analytics/august2026';
import {
  Activity,
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  BarChart3,
  CalendarDays,
  CheckCircle2,
  CircleGauge,
  Download,
  Eye,
  Flame,
  Layers3,
  Map,
  Search,
  Trophy,
  Zap,
} from 'lucide-react';
import { Link, useSearchParams } from 'react-router';
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { useState } from 'react';
import {
  augustTopResources,
  augustTopCollections,
  augustTopDownloadedResources,
  augustDownloadSummary,
} from '../data/analytics/popularAugust2026';
import {
  analyticsMonth,
  selectedAnalyticsReport,
} from '../config/analyticsReports';
import { AUGUST_2026_SUMMARY } from '../data/analytics/august2026';
import { MonthlyComparison } from '../components/analytics/MonthlyComparison';
import { Footer } from '../components/layout/Footer';
import { AnalyticsHeader } from '../components/analytics/AnalyticsHeader';
import {
  analyticsReports,
  analyticsReportHref,
} from '../config/analyticsReports';
import { Seo } from '../components/Seo';
import { BTAA_PARTNER_INSTITUTIONS } from '../constants/partnerInstitutions';
import {
  JULY_2026_SUMMARY,
  MEMBER_JULY_SUMMARY as julyMEMBER_JULY_SUMMARY,
  dailyActivity as julyDailyActivity,
  discoveryViews as julyDiscoveryViews,
  memberPerformance as julyMemberPerformance,
  peakApiTrafficBreakdown as julyPeakApiTrafficBreakdown,
  requestMix as julyRequestMix,
  resourceClassFilters as julyResourceClassFilters,
  topCollections as julyTopCollections,
  topDownloadedResources as julyTopDownloadedResources,
  topResources as julyTopResources,
  topSearchTerms as julyTopSearchTerms,
  type CollectionChartEntry,
  type ResourceChartEntry,
} from '../data/analytics/july2026';
import {
  memberDailySeries as julyMemberDailySeries,
  memberTopContent as julyMemberTopContent,
  type MemberContentEntry,
} from '../data/analytics/memberJuly2026';
import { getResourceIcon } from '../utils/resourceIcons';
import '../styles/analytics.css';

const compactNumber = new Intl.NumberFormat('en-US', {
  notation: 'compact',
  maximumFractionDigits: 1,
});

const wholeNumber = new Intl.NumberFormat('en-US');

function formatCompact(value: number) {
  return compactNumber.format(value);
}

function collectionHref(collection: CollectionChartEntry) {
  if (collection.id) return `/resources/${encodeURIComponent(collection.id)}`;

  const params = new URLSearchParams();
  params.append(
    `include_filters[${collection.filterField}][]`,
    collection.title
  );
  return `/search?${params.toString()}`;
}

function memberSearchHref(code: string) {
  const params = new URLSearchParams();
  params.append('include_filters[b1g_code_s][]', code);
  return `/search?${params.toString()}`;
}

function resourceMomentum(resource: ResourceChartEntry) {
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
  resource: ResourceChartEntry;
  month: string;
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

function RankingThumbnail({
  resource,
  eager,
}: {
  resource: ResourceChartEntry;
  eager: boolean;
}) {
  const [imageFailed, setImageFailed] = useState(false);
  const resourceHref = `/resources/${encodeURIComponent(resource.id)}`;

  return (
    <Link
      to={resourceHref}
      className="analytics-cover"
      aria-label={`View ${resource.title}`}
    >
      {imageFailed ? (
        <span
          className="analytics-cover-placeholder"
          data-testid={`analytics-thumbnail-fallback-${resource.id}`}
        >
          {getResourceIcon(resource.resourceClass, {
            className: 'h-10 w-10',
          })}
        </span>
      ) : (
        <img
          src={`${resourceHref}/thumbnail`}
          alt=""
          loading={eager ? 'eager' : 'lazy'}
          decoding="async"
          data-testid={`analytics-thumbnail-${resource.id}`}
          onError={() => setImageFailed(true)}
        />
      )}
    </Link>
  );
}

function ResourceRankingRow({
  resource,
  rank,
  month,
}: {
  resource: ResourceChartEntry;
  rank: number;
  month: string;
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
      <RankingThumbnail resource={resource} eager={isLeader} />
      <div className="analytics-ranking-copy">
        <div className="analytics-ranking-kicker">
          <span>{resource.resourceClass}</span>
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
        <strong>{wholeNumber.format(resource.actions)}</strong>
        <span>actions</span>
      </div>
      <div className="analytics-ranking-trend">
        <MomentumBadge resource={resource} month={month} />
        <span>2H pulse</span>
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

function SectionHeading({
  eyebrow,
  title,
  description,
}: {
  eyebrow: string;
  title: string;
  description: string;
}) {
  return (
    <div className="analytics-section-heading">
      <p>{eyebrow}</p>
      <div>
        <h2>{title}</h2>
        <span>{description}</span>
      </div>
    </div>
  );
}

function MemberContentList({
  title,
  items,
  metric,
  emptyMessage,
}: {
  title: string;
  items: MemberContentEntry[];
  metric: 'views' | 'downloads';
  emptyMessage: string;
}) {
  return (
    <div className="analytics-member-content-list">
      <h4>{title}</h4>
      {items.length > 0 ? (
        <ol>
          {items.map((item, index) => (
            <li key={item.id}>
              <span>{String(index + 1).padStart(2, '0')}</span>
              <Link to={`/resources/${encodeURIComponent(item.id)}`}>
                {item.title}
              </Link>
              <strong>{wholeNumber.format(item[metric])}</strong>
            </li>
          ))}
        </ol>
      ) : (
        <p>{emptyMessage}</p>
      )}
    </div>
  );
}

export function AnalyticsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const report = selectedAnalyticsReport(searchParams);
  const reportMonth = analyticsMonth(searchParams);
  const isAugust = reportMonth === 'August';
  const topResources = isAugust ? augustTopResources : julyTopResources;
  const topCollections = isAugust ? augustTopCollections : julyTopCollections;
  const topDownloadedResources = isAugust
    ? augustTopDownloadedResources
    : julyTopDownloadedResources;
  const contentSummary = isAugust ? AUGUST_2026_SUMMARY : JULY_2026_SUMMARY;
  const downloadResourceCount = isAugust
    ? augustDownloadSummary.resources
    : 695;
  const topDownloadClicks = topDownloadedResources.reduce(
    (sum, row) => sum + row.clicks,
    0
  );
  const summary = isAugust ? AUGUST_2026_SUMMARY : JULY_2026_SUMMARY;
  const memberSummary = isAugust
    ? augustReports.augustMemberSummary
    : julyMEMBER_JULY_SUMMARY;
  const memberPerformance = isAugust
    ? augustReports.augustMembers
    : julyMemberPerformance;
  const memberDailySeries = isAugust
    ? augustReports.augustMemberDailySeries
    : julyMemberDailySeries;
  const memberTopContent = isAugust
    ? augustReports.augustMemberTopContent
    : julyMemberTopContent;
  const monthShort = isAugust ? 'Aug' : 'Jul';
  const dailyActivity = isAugust
    ? augustDailyActivity.map((row, index) => ({
        ...row,
        day: `Aug ${index + 1}`,
      }))
    : julyDailyActivity;
  const discoveryViews = isAugust
    ? augustReports.augustDiscoveryViews
    : julyDiscoveryViews;
  const resourceClassFilters = isAugust
    ? augustReports.augustResourceClassFilters
    : julyResourceClassFilters;
  const topSearchTerms = isAugust
    ? augustReports.augustTopSearchTerms
    : julyTopSearchTerms;
  const searchSnapshot = searchSnapshots[isAugust ? '2026-08' : '2026-07'];
  const topZeroResultQueries = searchSnapshot.zeroQueries;
  const facetLabels: Record<string, string> = {
    ...FACET_LABELS,
    geo: 'Map bounds',
    year_range: 'Year range',
    b1g_code_s: 'BTAA member',
    dct_issued_s: 'Date issued',
    dct_provenance_s: 'Provenance',
    'dct:isSourceOf_agg': 'Is source of',
    'dct:sourceOf_agg': 'Source of',
    h3_res2: 'Map cells (resolution 2)',
    h3_res4: 'Map cells (resolution 4)',
    h3_res5: 'Map cells (resolution 5)',
    h3_res7: 'Map cells (resolution 7)',
  };
  const requestMix = isAugust ? augustReports.augustRequestMix : julyRequestMix;
  const peakApiTrafficBreakdown = isAugust
    ? augustReports.augustPeakApiTrafficBreakdown
    : julyPeakApiTrafficBreakdown;
  const inventoryDate = isAugust ? 'September 9, 2026' : 'August 20, 2026';
  const zeroQueries = isAugust
    ? augustReports.augustZeroResultBreakdown
    : { with_query: 758, without_query: 340 };
  const peakActivity = dailyActivity.reduce((peak, row) =>
    row.events > peak.events ? row : peak
  );
  const peakTraffic = dailyActivity.reduce((peak, row) =>
    row.requests > peak.requests ? row : peak
  );
  const viewLeader = [...memberPerformance].sort(
    (a, b) => b.resourceViews - a.resourceViews
  )[0];
  const downloadLeader = [...memberPerformance].sort(
    (a, b) => b.downloadClicks - a.downloadClicks
  )[0];
  const reachLeader = [...memberPerformance].sort(
    (a, b) => b.activeResources - a.activeResources
  )[0];
  const mapView = discoveryViews.find((row) => row.label === 'Map')!;
  let viewPercent = 0;
  const discoveryGradient = `conic-gradient(${discoveryViews
    .map((row) => {
      const start = viewPercent;
      viewPercent += (row.count / summary.searches) * 100;
      return `${row.color} ${start}% ${viewPercent}%`;
    })
    .join(',')})`;
  const changeMonth = (value: string) => {
    const params = new URLSearchParams(searchParams);
    params.set('month', value);
    setSearchParams(params);
  };
  const memberSelectorEntries = BTAA_PARTNER_INSTITUTIONS.flatMap(
    (institution) => {
      const member = memberPerformance.find(
        (entry) => entry.slug === institution.slug
      );
      return member ? [member] : [];
    }
  );

  const allMemberDailySeries = {
    views: Array.from({ length: 31 }, (_, index) =>
      memberPerformance.reduce(
        (total, member) => total + memberDailySeries[member.code].views[index],
        0
      )
    ),
    downloads: Array.from({ length: 31 }, (_, index) =>
      memberPerformance.reduce(
        (total, member) =>
          total + memberDailySeries[member.code].downloads[index],
        0
      )
    ),
  };

  const allMemberTopContent = {
    viewed: memberPerformance
      .flatMap((member) => memberTopContent[member.code].viewed)
      .sort((a, b) => b.views - a.views)
      .slice(0, 3),
    downloaded: memberPerformance
      .flatMap((member) => memberTopContent[member.code].downloaded)
      .sort((a, b) => b.downloads - a.downloads)
      .slice(0, 3),
  };

  const activeReport = report.id;
  const [selectedMemberCode, setSelectedMemberCode] = useState('all');
  const zeroResultRate = (summary.zeroResultSearches / summary.searches) * 100;
  const requestReliability =
    ((summary.requests - summary.serverErrors) / summary.requests) * 100;
  const maxCollectionSearches = topCollections[0].searches;
  const maxDownloadClicks = topDownloadedResources[0].clicks;
  const maxClassFilters = resourceClassFilters[0].count;
  const membersByViews = [...memberPerformance].sort(
    (a, b) => b.resourceViews - a.resourceViews
  );
  const memberImpressionShare =
    (memberSummary.impressions / summary.impressions) * 100;
  const memberViewShare =
    (memberSummary.resourceViews / summary.resourceViews) * 100;
  const memberDownloadShare =
    (memberSummary.downloadClicks / summary.downloadClicks) * 100;
  const selectedMember =
    selectedMemberCode === 'all'
      ? null
      : (memberPerformance.find(
          (member) => member.code === selectedMemberCode
        ) ?? null);
  const selectedDailySeries = selectedMember
    ? memberDailySeries[selectedMember.code]
    : allMemberDailySeries;
  const selectedTopContent = selectedMember
    ? memberTopContent[selectedMember.code]
    : allMemberTopContent;
  const selectedDailyActivity = selectedDailySeries.views.map(
    (views, index) => ({
      day: `${monthShort} ${index + 1}`,
      views,
      downloads: selectedDailySeries.downloads[index],
    })
  );
  const selectedCatalogRecords =
    selectedMember?.catalogRecords ?? memberSummary.catalogRecords;
  const selectedActiveResources =
    selectedMember?.activeResources ?? memberSummary.activeResources;
  const selectedImpressions =
    selectedMember?.impressions ?? memberSummary.impressions;
  const selectedResourceViews =
    selectedMember?.resourceViews ?? memberSummary.resourceViews;
  const selectedDownloadClicks =
    selectedMember?.downloadClicks ?? memberSummary.downloadClicks;
  const selectedSourceClicks =
    selectedMember?.sourceClicks ?? memberSummary.sourceClicks;
  const activeResourceRate =
    (selectedActiveResources / selectedCatalogRecords) * 100;
  const peakMemberDay = selectedDailyActivity.reduce((peak, day) =>
    day.views > peak.views ? day : peak
  );

  return (
    <div className="analytics-page min-h-screen bg-gray-50">
      <Seo
        title={`${report.label} — Analytics — ${report.period}`}
        description="Compare July and August 2026 API traffic and discovery activity, with monthly resource, member, discovery, and reliability reports."
      />
      <AnalyticsHeader activeReport={activeReport} />

      <main id="analytics-main" tabIndex={-1}>
        {activeReport === 'overview' ? (
          <>
            <section
              className="analytics-hero"
              aria-labelledby="analytics-title"
            >
              <div className="analytics-grid-overlay" aria-hidden="true" />
              <div
                className="analytics-orb analytics-orb--one"
                aria-hidden="true"
              />
              <div
                className="analytics-orb analytics-orb--two"
                aria-hidden="true"
              />

              <div className="analytics-shell analytics-hero-inner">
                <div className="analytics-hero-topline">
                  <div
                    className="analytics-month-picker"
                    aria-label="Dashboard month"
                  >
                    <CalendarDays className="h-4 w-4" aria-hidden />
                    <label htmlFor="overview-month" className="sr-only">
                      Reporting month
                    </label>
                    <select
                      id="overview-month"
                      value={isAugust ? '2026-08' : '2026-07'}
                      onChange={(event) => changeMonth(event.target.value)}
                    >
                      <option value="2026-08">August 2026</option>
                      <option value="2026-07">July 2026</option>
                    </select>
                  </div>
                </div>

                <div className="analytics-hero-copy">
                  <div>
                    <p className="analytics-overline">
                      API + discovery analytics
                    </p>
                    <h1 id="analytics-title">Monthly analytics dashboard</h1>
                  </div>
                  <div className="analytics-hero-note">
                    <p>
                      A combined view of raw API traffic and visitor discovery
                      activity. Infrastructure requests are separated from
                      product engagement throughout.
                    </p>
                  </div>
                </div>

                <div
                  className="analytics-hero-stats"
                  aria-label={`${reportMonth} 2026 highlights`}
                >
                  <div>
                    <span>01</span>
                    <strong>{formatCompact(summary.requests)}</strong>
                    <p>{reportMonth} API requests recorded</p>
                    <small>Includes bots, probes, and browser traffic</small>
                  </div>
                  <div>
                    <span>02</span>
                    <strong>{formatCompact(summary.resourceViews)}</strong>
                    <p>resource views</p>
                    <small>
                      {formatCompact(summary.impressions)} discoveries shown
                    </small>
                  </div>
                  <div>
                    <span>03</span>
                    <strong>{formatCompact(summary.searches)}</strong>
                    <p>searches launched</p>
                    <small>{reportMonth} 1–31, 2026</small>
                  </div>
                  <div>
                    <span>04</span>
                    <strong>
                      {wholeNumber.format(summary.downloadClicks)}
                    </strong>
                    <p>download clicks</p>
                    <small>
                      Plus {wholeNumber.format(summary.resultClicks)} result
                      opens
                    </small>
                  </div>
                </div>
              </div>
            </section>
          </>
        ) : (
          <div className="analytics-shell analytics-report-intro">
            <p>{report.period} · Monthly analytics</p>
            <h1>{report.label}</h1>
            <span>{report.description}</span>
            {activeReport !== 'comparison' && (
              <div className="analytics-content-month">
                <label htmlFor="report-month">Reporting month</label>
                <select
                  id="report-month"
                  value={isAugust ? '2026-08' : '2026-07'}
                  onChange={(event) => {
                    const params = new URLSearchParams(searchParams);
                    params.set('month', event.target.value);
                    setSearchParams(params);
                  }}
                >
                  <option value="2026-08">August 2026</option>
                  <option value="2026-07">July 2026</option>
                </select>
              </div>
            )}
          </div>
        )}

        <div className="analytics-shell analytics-content">
          {activeReport === 'comparison' && <MonthlyComparison />}
          {activeReport === 'clients' && (
            <ClientUsageReport month={isAugust ? '2026-08' : '2026-07'} />
          )}
          {activeReport === 'content' && (
            <section id="charts" className="analytics-section">
              <SectionHeading
                eyebrow="Popularity charts"
                title={`${reportMonth}’s top resources and collections`}
                description={`Ranked by resource detail views. Momentum compares all tracked interactions in the first and second halves of ${reportMonth}.`}
              />

              <div className="analytics-charts-grid">
                <div className="analytics-panel analytics-panel--ranking">
                  <div className="analytics-panel-header">
                    <div>
                      <Flame className="h-5 w-5" aria-hidden />
                      <span>Top resources</span>
                    </div>
                    <div
                      className="analytics-ranking-legend"
                      aria-hidden="true"
                    >
                      <span>Views</span>
                      <span>Actions</span>
                      <span>Momentum</span>
                    </div>
                  </div>
                  <div className="analytics-ranking-list">
                    {topResources.map((resource, index) => (
                      <ResourceRankingRow
                        key={resource.id}
                        resource={resource}
                        rank={index + 1}
                        month={reportMonth}
                      />
                    ))}
                  </div>
                </div>

                <aside className="analytics-panel analytics-panel--collections">
                  <div className="analytics-panel-header">
                    <div>
                      <Trophy className="h-5 w-5" aria-hidden />
                      <span>Collection chart</span>
                    </div>
                    <small>filtered searches</small>
                  </div>
                  <ol className="analytics-collection-list">
                    {topCollections.map((collection, index) => (
                      <li key={`${collection.title}-${collection.id ?? index}`}>
                        <span className="analytics-collection-rank">
                          {String(index + 1).padStart(2, '0')}
                        </span>
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
                        <strong>{collection.searches}</strong>
                      </li>
                    ))}
                  </ol>
                  <div className="analytics-chart-note">
                    <Layers3 className="h-5 w-5" aria-hidden />
                    <p>
                      {isAugust
                        ? `${topCollections[0].title} led August with ${topCollections[0].searches} filtered searches.`
                        : 'Urban Base Layers held the top spot, while historical maps claimed five positions in the collection top 10.'}
                    </p>
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
                    {wholeNumber.format(contentSummary.downloadClicks)} across
                    all resources
                  </small>
                </div>
                <div className="analytics-download-legend" aria-hidden="true">
                  <span>Resource</span>
                  <span>Clicks</span>
                  <span>Visits</span>
                </div>
                <ol className="analytics-download-list">
                  {topDownloadedResources.map((resource, index) => (
                    <li key={resource.id}>
                      <span className="analytics-download-rank">
                        {String(index + 1).padStart(2, '0')}
                      </span>
                      <div className="analytics-download-copy">
                        <div>
                          <span>{resource.resourceClass}</span>
                          <Link
                            to={`/resources/${encodeURIComponent(resource.id)}`}
                          >
                            {resource.title}
                          </Link>
                        </div>
                        <p>
                          {resource.provider} · {resource.formatLabel}
                        </p>
                        <div className="analytics-download-track" aria-hidden>
                          <i
                            style={{
                              width: `${(resource.clicks / maxDownloadClicks) * 100}%`,
                            }}
                          />
                        </div>
                      </div>
                      <strong>{resource.clicks}</strong>
                      <span>{resource.engagedVisits}</span>
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
                  The top {topDownloadedResources.length} account for{' '}
                  {topDownloadClicks} of {contentSummary.downloadClicks} clicks
                  (
                  {(
                    (topDownloadClicks / contentSummary.downloadClicks) *
                    100
                  ).toFixed(1)}
                  %), across {downloadResourceCount} resources with download
                  clicks. A click records selection of a catalog download link;
                  completion on an external provider site cannot be verified.
                  Visits are distinct tracked visit tokens.
                </p>
              </article>
              <p className="analytics-comparison-note">
                {reportMonth} 1–31, 2026 (UTC) · Exported{' '}
                {contentSummary.exportedAt}. Rankings use recorded interactions
                and catalog metadata at export. Actions are tracked events other
                than resource views; momentum compares days 16–31 with days
                1–15.
              </p>
            </section>
          )}

          {activeReport === 'members' && (
            <section id="members" className="analytics-section">
              <SectionHeading
                eyebrow="Member overview"
                title="How BTAA member content performed"
                description={`Start with the full alliance, then choose any campus to follow its catalog footprint, daily attention, downloads, and leading content across ${reportMonth}.`}
              />

              <div className="analytics-panel analytics-campus-selector">
                <div className="analytics-campus-selector-header">
                  <div>
                    <Map className="h-5 w-5" aria-hidden />
                    <span>Filter the member report</span>
                  </div>
                  <p>Choose the alliance or a campus contribution stream</p>
                </div>
                <fieldset>
                  <legend className="sr-only">
                    Select a BTAA member report
                  </legend>
                  <div className="analytics-campus-filter-grid">
                    <button
                      type="button"
                      className={`analytics-campus-filter${selectedMemberCode === 'all' ? ' analytics-campus-filter--active' : ''}`}
                      aria-pressed={selectedMemberCode === 'all'}
                      onClick={() => setSelectedMemberCode('all')}
                    >
                      <span className="analytics-campus-filter-mark analytics-campus-filter-mark--btaa">
                        <img src="/btaa-logo.png" alt="" />
                      </span>
                      <span>All BTAA</span>
                    </button>
                    {memberSelectorEntries.map((member) => (
                      <button
                        key={member.code}
                        type="button"
                        className={`analytics-campus-filter${selectedMemberCode === member.code ? ' analytics-campus-filter--active' : ''}`}
                        aria-label={`Show ${member.name} ${reportMonth} report`}
                        aria-pressed={selectedMemberCode === member.code}
                        title={member.name}
                        onClick={() => setSelectedMemberCode(member.code)}
                      >
                        <span className="analytics-campus-filter-mark">
                          <img
                            src={`/icons/${member.iconSlug}.svg`}
                            alt=""
                            loading="lazy"
                          />
                        </span>
                        <span>{member.shortName}</span>
                      </button>
                    ))}
                  </div>
                </fieldset>
              </div>

              <div className="analytics-member-selection" aria-live="polite">
                <div className="analytics-member-selection-brand">
                  <span>
                    <img
                      src={
                        selectedMember
                          ? `/icons/${selectedMember.iconSlug}.svg`
                          : '/btaa-logo.png'
                      }
                      alt=""
                    />
                  </span>
                  <div>
                    <p>{selectedMember ? 'Campus segment' : 'Alliance view'}</p>
                    <h3>{selectedMember?.name ?? 'All BTAA member content'}</h3>
                    <small>
                      {selectedMember
                        ? `Contribution stream ${selectedMember.code} · ${reportMonth} 1–31, 2026`
                        : `17 member contribution streams · ${reportMonth} 1–31, 2026`}
                    </small>
                  </div>
                </div>
                {selectedMember && (
                  <Link to={memberSearchHref(selectedMember.code)}>
                    Browse {selectedMember.shortName} content
                    <ArrowRight className="h-4 w-4" aria-hidden />
                  </Link>
                )}
              </div>

              <div className="analytics-member-kpi-grid">
                <article>
                  <span>Catalog footprint</span>
                  <strong>{wholeNumber.format(selectedCatalogRecords)}</strong>
                  <p>published catalog inventory as of {inventoryDate}</p>
                </article>
                <article>
                  <span>{reportMonth} reach</span>
                  <strong>{wholeNumber.format(selectedActiveResources)}</strong>
                  <p>
                    {activeResourceRate.toFixed(1)}% of the catalog appeared in
                    a search or received an action
                  </p>
                </article>
                <article>
                  <span>Resource attention</span>
                  <strong>{wholeNumber.format(selectedResourceViews)}</strong>
                  <p>
                    {selectedMember
                      ? `${wholeNumber.format(selectedImpressions)} search impressions`
                      : `${memberViewShare.toFixed(1)}% of portal views · ${memberImpressionShare.toFixed(1)}% of search impressions`}
                  </p>
                </article>
                <article>
                  <span>Download intent</span>
                  <strong>{wholeNumber.format(selectedDownloadClicks)}</strong>
                  <p>
                    {wholeNumber.format(selectedSourceClicks)} source-site
                    clicks
                    {selectedMember
                      ? ''
                      : ` · ${memberDownloadShare.toFixed(1)}% of all download clicks`}
                  </p>
                </article>
              </div>

              <div className="analytics-member-detail-grid">
                <figure className="analytics-panel analytics-member-trend">
                  <div className="analytics-panel-header">
                    <div>
                      <Activity className="h-5 w-5" aria-hidden />
                      <span>Daily member-content engagement</span>
                    </div>
                    <div className="analytics-chart-key" aria-hidden="true">
                      <span>
                        <i className="analytics-key-events" />
                        Views
                      </span>
                      <span>
                        <i className="analytics-key-downloads" />
                        Downloads
                      </span>
                    </div>
                  </div>
                  <div
                    className="analytics-member-rechart"
                    role="img"
                    aria-label={`${selectedMember?.name ?? 'All BTAA member content'} daily resource views and download clicks from ${reportMonth} 1 through ${reportMonth} 31, 2026. Views peaked at ${peakMemberDay.views} on ${peakMemberDay.day}.`}
                  >
                    <ResponsiveContainer
                      width="100%"
                      height="100%"
                      minWidth={0}
                      minHeight={300}
                      initialDimension={{ width: 800, height: 300 }}
                    >
                      <AreaChart
                        data={selectedDailyActivity}
                        margin={{ top: 16, right: 8, left: -24, bottom: 0 }}
                        accessibilityLayer
                      >
                        <defs>
                          <linearGradient
                            id="memberViewsFill"
                            x1="0"
                            y1="0"
                            x2="0"
                            y2="1"
                          >
                            <stop
                              offset="0%"
                              stopColor="#2563EB"
                              stopOpacity={0.22}
                            />
                            <stop
                              offset="100%"
                              stopColor="#2563EB"
                              stopOpacity={0}
                            />
                          </linearGradient>
                        </defs>
                        <CartesianGrid
                          stroke="#E5E7EB"
                          strokeDasharray="2 6"
                          vertical={false}
                        />
                        <XAxis
                          dataKey="day"
                          axisLine={false}
                          tickLine={false}
                          tick={{ fill: '#6B7280', fontSize: 11 }}
                          interval={4}
                        />
                        <YAxis
                          axisLine={false}
                          tickLine={false}
                          tick={{ fill: '#6B7280', fontSize: 11 }}
                          allowDecimals={false}
                        />
                        <Tooltip
                          cursor={{ stroke: '#2563EB', strokeDasharray: '3 3' }}
                          contentStyle={{
                            background: '#FFFFFF',
                            border: '1px solid #D1D5DB',
                            borderRadius: 8,
                            color: '#111827',
                          }}
                          labelStyle={{ color: '#111827', fontWeight: 600 }}
                        />
                        <Area
                          type="linear"
                          dataKey="views"
                          name="Resource views"
                          stroke="#2563EB"
                          strokeWidth={3}
                          fill="url(#memberViewsFill)"
                          isAnimationActive={false}
                        />
                        <Line
                          type="linear"
                          dataKey="downloads"
                          name="Download clicks"
                          stroke="#047857"
                          strokeWidth={2}
                          dot={false}
                          activeDot={{ r: 4, fill: '#047857' }}
                          isAnimationActive={false}
                        />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                  <figcaption>
                    <span>{selectedMember?.shortName ?? 'All members'}</span>
                    <strong>
                      Peak: {wholeNumber.format(peakMemberDay.views)} views ·{' '}
                      {peakMemberDay.day}
                    </strong>
                  </figcaption>
                </figure>

                <aside className="analytics-panel analytics-member-content-card">
                  <div className="analytics-panel-header">
                    <div>
                      <Trophy className="h-5 w-5" aria-hidden />
                      <span>Leading content</span>
                    </div>
                    <small>{selectedMember?.shortName ?? 'All members'}</small>
                  </div>
                  <MemberContentList
                    title="Most viewed"
                    items={selectedTopContent.viewed}
                    metric="views"
                    emptyMessage="No resource views were recorded."
                  />
                  <MemberContentList
                    title="Most downloaded"
                    items={selectedTopContent.downloaded}
                    metric="downloads"
                    emptyMessage={`No direct download-link clicks were recorded; ${wholeNumber.format(selectedSourceClicks)} source-site clicks were still captured.`}
                  />
                </aside>
              </div>

              {!selectedMember && (
                <div className="analytics-member-standouts">
                  <article className="analytics-panel">
                    <div>
                      <Eye className="h-5 w-5" aria-hidden />
                      <span>Attention leader</span>
                    </div>
                    <strong>{viewLeader.shortName}</strong>
                    <p>
                      {wholeNumber.format(viewLeader.resourceViews)} resource
                      views and {wholeNumber.format(viewLeader.sourceClicks)}{' '}
                      source-site clicks—the month’s leading member by resource
                      views.
                    </p>
                  </article>
                  <article className="analytics-panel">
                    <div>
                      <Download className="h-5 w-5" aria-hidden />
                      <span>Download leader</span>
                    </div>
                    <strong>{downloadLeader.shortName}</strong>
                    <p>
                      {wholeNumber.format(downloadLeader.downloadClicks)}{' '}
                      download clicks, the most among member contributions.
                    </p>
                  </article>
                  <article className="analytics-panel">
                    <div>
                      <Layers3 className="h-5 w-5" aria-hidden />
                      <span>Broadest {reportMonth} reach</span>
                    </div>
                    <strong>{reachLeader.shortName}</strong>
                    <p>
                      {wholeNumber.format(reachLeader.activeResources)} distinct
                      records appeared in a search or received a tracked action.
                    </p>
                  </article>
                </div>
              )}

              {!selectedMember && (
                <article className="analytics-panel analytics-member-report">
                  <div className="analytics-panel-header">
                    <div>
                      <Trophy className="h-5 w-5" aria-hidden />
                      <span>Member performance report</span>
                    </div>
                    <small>
                      17 contributing institutions · ranked by views
                    </small>
                  </div>
                  <div className="analytics-member-table-wrap">
                    <table>
                      <caption className="sr-only">
                        {reportMonth} 2026 performance for BTAA
                        member-contributed catalog content
                      </caption>
                      <thead>
                        <tr>
                          <th scope="col">Rank</th>
                          <th scope="col">Member</th>
                          <th scope="col">Catalog</th>
                          <th scope="col">{reportMonth} active</th>
                          <th scope="col">Impressions</th>
                          <th scope="col">Views</th>
                          <th scope="col">Downloads</th>
                          <th scope="col">Source clicks</th>
                          <th scope="col">Top-viewed content</th>
                        </tr>
                      </thead>
                      <tbody>
                        {membersByViews.map((member, index) => (
                          <tr key={member.code}>
                            <td>
                              <span className="analytics-member-rank">
                                {String(index + 1).padStart(2, '0')}
                              </span>
                            </td>
                            <th scope="row">
                              <div className="analytics-member-school">
                                <span className="analytics-member-logo">
                                  <img
                                    src={`/icons/${member.iconSlug}.svg`}
                                    alt=""
                                    loading="lazy"
                                  />
                                </span>
                                <div>
                                  <Link to={memberSearchHref(member.code)}>
                                    {member.shortName}
                                  </Link>
                                  {member.name !== member.shortName && (
                                    <span>{member.name}</span>
                                  )}
                                </div>
                              </div>
                            </th>
                            <td>{wholeNumber.format(member.catalogRecords)}</td>
                            <td>
                              {wholeNumber.format(member.activeResources)}
                            </td>
                            <td>{wholeNumber.format(member.impressions)}</td>
                            <td>
                              <strong>
                                {wholeNumber.format(member.resourceViews)}
                              </strong>
                            </td>
                            <td>{wholeNumber.format(member.downloadClicks)}</td>
                            <td>{wholeNumber.format(member.sourceClicks)}</td>
                            <td>
                              <Link
                                className="analytics-member-top-resource"
                                to={`/resources/${encodeURIComponent(member.topResource.id)}`}
                              >
                                {member.topResource.title}
                              </Link>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </article>
              )}

              <p className="analytics-member-method analytics-panel">
                Activity period: {reportMonth} 1–31, 2026. Catalog inventory:
                published, unsuppressed records as of {inventoryDate}, when this
                report was exported. The inventory is a point-in-time count, not
                an activity total or month-end count. “{reportMonth} active”
                means a distinct record with at least one search impression or
                tracked action during {reportMonth}. School attribution follows
                the BTAA contribution code rather than the provider label, which
                often names an originating public agency. Downloads and
                source-site visits are link clicks, not verified completions.
              </p>
            </section>
          )}

          {activeReport === 'overview' && (
            <section id="pulse" className="analytics-section">
              <SectionHeading
                eyebrow="Monthly trends"
                title="Day by day"
                description={`Daily interactions and searches across ${reportMonth}. ${peakActivity.day} recorded the most interactions.`}
              />

              <div className="analytics-pulse-grid">
                <figure className="analytics-panel analytics-activity-chart">
                  <div className="analytics-panel-header">
                    <div>
                      <Activity className="h-5 w-5" aria-hidden />
                      <span>Interactions and searches</span>
                    </div>
                    <div className="analytics-chart-key" aria-hidden="true">
                      <span>
                        <i className="analytics-key-events" />
                        Interactions
                      </span>
                      <span>
                        <i className="analytics-key-searches" />
                        Searches
                      </span>
                    </div>
                  </div>
                  <div
                    className="analytics-rechart"
                    role="img"
                    aria-label={`Daily interactions and searches from ${reportMonth} 1 through ${reportMonth} 31, 2026. Interactions peaked at ${peakActivity.events} on ${peakActivity.day}.`}
                  >
                    <ResponsiveContainer
                      width="100%"
                      height="100%"
                      minWidth={0}
                      minHeight={352}
                      initialDimension={{ width: 1_000, height: 352 }}
                    >
                      <AreaChart
                        data={dailyActivity}
                        margin={{ top: 16, right: 8, left: -24, bottom: 0 }}
                        accessibilityLayer
                      >
                        <defs>
                          <linearGradient
                            id="eventsFill"
                            x1="0"
                            y1="0"
                            x2="0"
                            y2="1"
                          >
                            <stop
                              offset="0%"
                              stopColor="#2563EB"
                              stopOpacity={0.24}
                            />
                            <stop
                              offset="100%"
                              stopColor="#2563EB"
                              stopOpacity={0}
                            />
                          </linearGradient>
                        </defs>
                        <CartesianGrid
                          stroke="#E5E7EB"
                          strokeDasharray="2 6"
                          vertical={false}
                        />
                        <XAxis
                          dataKey="day"
                          axisLine={false}
                          tickLine={false}
                          tick={{ fill: '#6B7280', fontSize: 11 }}
                          interval={4}
                        />
                        <YAxis
                          axisLine={false}
                          tickLine={false}
                          tick={{ fill: '#6B7280', fontSize: 11 }}
                        />
                        <Tooltip
                          cursor={{ stroke: '#2563EB', strokeDasharray: '3 3' }}
                          contentStyle={{
                            background: '#FFFFFF',
                            border: '1px solid #D1D5DB',
                            borderRadius: 8,
                            color: '#111827',
                          }}
                          labelStyle={{ color: '#111827', fontWeight: 600 }}
                        />
                        <Area
                          type="linear"
                          dataKey="events"
                          name="Interactions"
                          stroke="#2563EB"
                          strokeWidth={3}
                          fill="url(#eventsFill)"
                          isAnimationActive={false}
                        />
                        <Line
                          type="linear"
                          dataKey="searches"
                          name="Searches"
                          stroke="#003C5B"
                          strokeWidth={2}
                          dot={false}
                          activeDot={{ r: 5, fill: '#003C5B' }}
                          isAnimationActive={false}
                        />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                  <figcaption>
                    <span>{monthShort} 1</span>
                    <strong>
                      Peak: {wholeNumber.format(peakActivity.events)}{' '}
                      interactions · {peakActivity.day}
                    </strong>
                    <span>{monthShort} 31</span>
                  </figcaption>
                </figure>

                <aside className="analytics-signal-stack">
                  <div className="analytics-signal-card analytics-signal-card--bright">
                    <div>
                      <Zap className="h-5 w-5" aria-hidden />
                      <span>Peak API traffic</span>
                    </div>
                    <strong>{wholeNumber.format(peakTraffic.requests)}</strong>
                    <p>
                      raw HTTP requests on {peakTraffic.day}, including bots and
                      automated health probes
                    </p>
                  </div>
                  <div className="analytics-signal-card">
                    <div>
                      <Eye className="h-5 w-5" aria-hidden />
                      <span>Discovery surface</span>
                    </div>
                    <strong>{formatCompact(summary.impressions)}</strong>
                    <p>resource cards appeared across search result views</p>
                  </div>
                  <div className="analytics-signal-card">
                    <div>
                      <CheckCircle2 className="h-5 w-5" aria-hidden />
                      <span>Engaged visits</span>
                    </div>
                    <strong>
                      {wholeNumber.format(summary.uniqueEngagedVisits)}
                    </strong>
                    <p>
                      distinct visit tokens generated a tracked product event
                    </p>
                  </div>
                </aside>
              </div>
            </section>
          )}

          {activeReport === 'overview' && (
            <section
              className="analytics-report-directory"
              aria-labelledby="reports-title"
            >
              <h2 id="reports-title">Explore the reports</h2>
              <p>
                Choose a focused report. Each report shows its available
                reporting period.
              </p>
              <div className="analytics-report-cards">
                {analyticsReports
                  .filter((entry) => entry.id !== 'overview')
                  .map((entry) => (
                    <Link
                      key={entry.id}
                      to={analyticsReportHref(
                        entry.id,
                        searchParams.get('month')
                      )}
                      className="analytics-panel analytics-report-card"
                    >
                      <span>
                        {entry.id === 'comparison'
                          ? entry.period
                          : `${reportMonth} 2026`}
                      </span>
                      <h3>
                        {entry.label} <span aria-hidden="true">→</span>
                      </h3>
                      <p>{entry.description}</p>
                    </Link>
                  ))}
              </div>
            </section>
          )}

          {activeReport === 'discovery' && (
            <section id="discovery" className="analytics-section">
              <SectionHeading
                eyebrow="Search patterns"
                title="What visitors looked for"
                description={`Search views, query terms, filters, and zero-result searches recorded during ${reportMonth}.`}
              />

              <div className="analytics-insights-grid">
                <article className="analytics-panel analytics-donut-card">
                  <div className="analytics-panel-header">
                    <div>
                      <Map className="h-5 w-5" aria-hidden />
                      <span>Search view mix</span>
                    </div>
                  </div>
                  <div className="analytics-donut-layout">
                    <div
                      className="analytics-donut"
                      role="img"
                      aria-label={discoveryViews
                        .map(
                          (row) => `${row.label} view ${row.percent} percent`
                        )
                        .join(', ')}
                      style={{ background: discoveryGradient }}
                    >
                      <div>
                        <strong>{Math.round(mapView.percent)}%</strong>
                        <span>map view</span>
                      </div>
                    </div>
                    <ul>
                      {discoveryViews.map((view) => (
                        <li key={view.label}>
                          <i
                            style={{ backgroundColor: view.color }}
                            aria-hidden="true"
                          />
                          <span>{view.label}</span>
                          <strong>{view.percent}%</strong>
                        </li>
                      ))}
                    </ul>
                  </div>
                  <p className="analytics-card-footnote">
                    The map generated {wholeNumber.format(mapView.count)} of{' '}
                    {wholeNumber.format(summary.searches)} rendered searches.
                  </p>
                </article>

                <article className="analytics-panel analytics-search-card">
                  <div className="analytics-panel-header">
                    <div>
                      <Search className="h-5 w-5" aria-hidden />
                      <span>Top search terms</span>
                    </div>
                    <small>non-empty queries</small>
                  </div>
                  <ol>
                    {topSearchTerms.map((query, index) => (
                      <li key={query.term}>
                        <span>{String(index + 1).padStart(2, '0')}</span>
                        <Link
                          to={`/search?q=${encodeURIComponent(query.term)}`}
                        >
                          {query.term}
                        </Link>
                        <strong>{query.count}</strong>
                      </li>
                    ))}
                  </ol>
                </article>

                <article className="analytics-panel analytics-format-card">
                  <div className="analytics-panel-header">
                    <div>
                      <BarChart3 className="h-5 w-5" aria-hidden />
                      <span>Resource class demand</span>
                    </div>
                    <small>filters applied</small>
                  </div>
                  <ul>
                    {resourceClassFilters.map((item) => (
                      <li key={item.label}>
                        <div>
                          <span>{item.label}</span>
                          <strong>{item.count}</strong>
                        </div>
                        <div
                          className="analytics-format-track"
                          aria-hidden="true"
                        >
                          <i
                            style={{
                              width: `${(item.count / maxClassFilters) * 100}%`,
                              backgroundColor: item.color,
                            }}
                          />
                        </div>
                      </li>
                    ))}
                  </ul>
                </article>

                <article className="analytics-panel analytics-format-card analytics-facet-card">
                  <div className="analytics-panel-header">
                    <div>
                      <BarChart3 className="h-5 w-5" aria-hidden />
                      <h3>Most-used facet categories</h3>
                    </div>
                    <small>searches using each category</small>
                  </div>
                  <div
                    className="analytics-search-scroll"
                    role="region"
                    aria-label="Facet category usage chart"
                    tabIndex={0}
                  >
                    <ul>
                      {searchSnapshot.facets.map((facet) => (
                        <li key={facet.field}>
                          <div>
                            <span>
                              {facetLabels[facet.field] ?? facet.field}
                            </span>
                            <strong>{wholeNumber.format(facet.count)}</strong>
                          </div>
                          <div
                            className="analytics-format-track"
                            aria-hidden="true"
                          >
                            <i
                              style={{
                                width: `${(facet.count / searchSnapshot.facets[0].count) * 100}%`,
                                backgroundColor: '#2563EB',
                              }}
                            />
                          </div>
                        </li>
                      ))}
                    </ul>
                  </div>
                  <p className="analytics-card-footnote">
                    Each search counts once per category, including exclusion
                    filters and legacy filter formats. Searches can use several
                    categories. Map bounds and year ranges are included; these
                    counts describe filters present in searches, not facet
                    clicks.
                  </p>
                </article>

                <article className="analytics-panel analytics-opportunity-card">
                  <div className="analytics-opportunity-summary">
                    <div className="analytics-opportunity-heading">
                      <div className="analytics-opportunity-icon">
                        <CircleGauge className="h-7 w-7" aria-hidden />
                      </div>
                      <p>Search opportunity</p>
                    </div>
                    <strong>{zeroResultRate.toFixed(1)}%</strong>
                    <h3>of searches returned zero results</h3>
                    <span>
                      That’s {wholeNumber.format(summary.zeroResultSearches)}{' '}
                      moments to improve metadata, spelling support, or query
                      guidance.
                    </span>
                    <Link to="/feedback">
                      Share a discovery idea
                      <ArrowRight className="h-4 w-4" aria-hidden />
                    </Link>
                  </div>

                  <div className="analytics-zero-query-list">
                    <div className="analytics-zero-query-header">
                      <div>
                        <Search className="h-5 w-5" aria-hidden />
                        <h3>Top zero-result queries</h3>
                      </div>
                      <small>searches</small>
                    </div>
                    <p>
                      Showing up to 50 queries with at least 3 zero-result
                      searches, ranked by frequency.
                    </p>
                    <div
                      className="analytics-search-scroll"
                      role="region"
                      aria-label="Zero-result queries"
                      tabIndex={0}
                    >
                      <ol>
                        {topZeroResultQueries.map((query, index) => (
                          <li key={query.term}>
                            <span>{String(index + 1).padStart(2, '0')}</span>
                            <Link
                              to={`/search?q=${encodeURIComponent(query.term)}`}
                            >
                              {query.term}
                            </Link>
                            <strong>{query.count}</strong>
                          </li>
                        ))}
                      </ol>
                    </div>
                    <p>
                      {wholeNumber.format(zeroQueries.with_query)} zero-result
                      searches included query text;{' '}
                      {wholeNumber.format(zeroQueries.without_query)} were
                      filter-only searches with no query.
                    </p>
                  </div>
                </article>
              </div>
            </section>
          )}

          {activeReport === 'platform' && (
            <section
              id="platform"
              className="analytics-section analytics-platform-section"
            >
              <SectionHeading
                eyebrow="API analytics"
                title="API requests and reliability"
                description="Raw HTTP traffic includes browsers, crawlers, health probes, images, and analytics capture. It should not be read as a count of searches or visitors."
              />

              <div className="analytics-platform-grid">
                <article className="analytics-panel analytics-reliability-card">
                  <div className="analytics-reliability-top">
                    <div>
                      <p>Requests without a server error</p>
                      <strong>{requestReliability.toFixed(3)}%</strong>
                    </div>
                    <div className="analytics-reliability-badge">
                      <CheckCircle2 className="h-5 w-5" aria-hidden />
                      Healthy
                    </div>
                  </div>
                  <div
                    className="analytics-reliability-track"
                    aria-hidden="true"
                  >
                    <i />
                  </div>
                  <div className="analytics-performance-stats">
                    <div>
                      <span>Median response</span>
                      <strong>{summary.medianResponseMs} ms</strong>
                    </div>
                    <div>
                      <span>95th percentile</span>
                      <strong>{summary.p95ResponseMs} ms</strong>
                    </div>
                    <div>
                      <span>Server errors</span>
                      <strong>{summary.serverErrors}</strong>
                    </div>
                  </div>
                </article>

                <article className="analytics-panel analytics-request-card">
                  <div className="analytics-panel-header">
                    <div>
                      <CircleGauge className="h-5 w-5" aria-hidden />
                      <span>Request mix</span>
                    </div>
                    <small>{formatCompact(summary.requests)} total</small>
                  </div>
                  <div className="analytics-request-bar" aria-hidden="true">
                    {requestMix.map((item) => (
                      <i
                        key={item.label}
                        style={{
                          width: `${item.percent}%`,
                          backgroundColor: item.color,
                        }}
                      />
                    ))}
                  </div>
                  <ul>
                    {requestMix.map((item) => (
                      <li key={item.label}>
                        <i
                          style={{ backgroundColor: item.color }}
                          aria-hidden="true"
                        />
                        <span>{item.label}</span>
                        <strong>{formatCompact(item.count)}</strong>
                      </li>
                    ))}
                  </ul>
                </article>

                <article className="analytics-panel analytics-api-breakdown-card">
                  <div className="analytics-panel-header">
                    <div>
                      <Activity className="h-5 w-5" aria-hidden />
                      <span>{peakTraffic.day} API traffic separation</span>
                    </div>
                    <small>
                      {wholeNumber.format(peakTraffic.requests)} raw HTTP
                      requests
                    </small>
                  </div>
                  <div className="analytics-api-table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th scope="col">Traffic type</th>
                          <th scope="col">Requests</th>
                          <th scope="col">Share</th>
                          <th scope="col">What it represents</th>
                        </tr>
                      </thead>
                      <tbody>
                        {peakApiTrafficBreakdown.map((item) => (
                          <tr key={item.label}>
                            <th scope="row">{item.label}</th>
                            <td>{wholeNumber.format(item.count)}</td>
                            <td>{item.percent}%</td>
                            <td>{item.detail}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <p>
                    Turnstile status checks and API documentation probes made up
                    {(
                      ((peakApiTrafficBreakdown[0].count +
                        peakApiTrafficBreakdown[1].count) /
                        peakTraffic.requests) *
                      100
                    ).toFixed(1)}
                    % of the peak. The table describes infrastructure load, not
                    visitor search demand.
                  </p>
                </article>
              </div>
            </section>
          )}

          {activeReport !== 'comparison' &&
            activeReport !== 'content' &&
            activeReport !== 'clients' && (
              <section
                className="analytics-method-note"
                aria-label="Data notes"
              >
                <div>
                  <Download className="h-5 w-5" aria-hidden />
                  <strong>Verified {reportMonth} snapshot</strong>
                </div>
                <p>
                  Built from reconciled API, search, impression, and event
                  exports covering {reportMonth} 1–31, 2026 (UTC). Exported{' '}
                  {summary.exportedAt}. Raw request records remain outside this
                  application; this page contains aggregate metrics and public
                  catalog metadata only.
                </p>
                <span>
                  7 analytics tables · 1 catalog snapshot · 31 complete days
                </span>
              </section>
            )}
        </div>
      </main>

      <Footer />
    </div>
  );
}

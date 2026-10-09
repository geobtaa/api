import { ReportingPeriodPicker } from '../components/analytics/ReportingPeriodPicker';
import { ApiDailyReport } from '../components/analytics/ApiDailyReport';
import reliabilityEndpoints from '../data/analytics/reliabilityEndpoints2026.json';
import { SearchDailyReport } from '../components/analytics/SearchDailyReport';
import zeroSnapshots from '../data/analytics/zeroResultQueries2026.json';
import {
  allTimeMembers,
  allTimeMemberSummary,
  allTimeMemberDaily,
  allTimeMemberContent,
  allTimeProviderSnapshot,
  memberDays,
  memberRange,
  memberCatalogDate,
  memberPortalTotals,
} from '../data/analytics/memberAllTime';
import allTimeData from '../data/analytics/allTime2026.json';
import { ReportContentLayout } from '../components/analytics/ReportContentLayout';
import { ReportSectionHeading as SectionHeading } from '../components/analytics/ReportSectionHeading';
import { PopularContentReport } from '../components/analytics/PopularContentReport';
import {
  AccessSummary,
  AudienceReport,
  OutlinkedResources,
} from '../components/analytics/DiscoveryOutcomes';
import { outcomes } from '../data/analytics/outcomes';
import { ZeroResultReport } from '../components/analytics/ZeroResultReport';
import { AllTimeAnalyticsPage } from '../components/analytics/AllTimeAnalyticsPage';
import {
  queryCategory,
  queryCategoryMethod,
} from '../data/analytics/queryCategories';
import topSearches from '../data/analytics/topSearches2026.json';
import { AnalyticsTable } from '../components/analytics/AnalyticsTable';
import { CodeCoverage } from '../components/analytics/CodeCoverage';
import { ProviderReport } from '../components/analytics/ProviderReport';
import { ReportSources } from '../components/analytics/ReportSources';
import { searchSnapshots } from '../data/analytics/searches2026';
import { FACET_LABELS } from '../utils/facetLabels';
import { ClientUsageReport } from '../components/analytics/ClientUsageReport';
import * as augustReports from '../data/analytics/reportsAugust2026';
import { augustDailyActivity } from '../data/analytics/august2026';
import {
  Activity,
  ArrowRight,
  BarChart3,
  CheckCircle2,
  CircleGauge,
  Download,
  Eye,
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
} from '../data/analytics/july2026';
import {
  memberDailySeries as julyMemberDailySeries,
  memberTopContent as julyMemberTopContent,
  type MemberContentEntry,
} from '../data/analytics/memberJuly2026';
import '../styles/analytics.css';

const compactNumber = new Intl.NumberFormat('en-US', {
  notation: 'compact',
  maximumFractionDigits: 1,
});

const wholeNumber = new Intl.NumberFormat('en-US');

function formatCompact(value: number) {
  return compactNumber.format(value);
}

function memberSearchHref(code: string) {
  const params = new URLSearchParams();
  params.append('include_filters[b1g_code_s][]', code);
  return `/search?${params.toString()}`;
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
  const isAllTime = searchParams.get('month') === 'all';
  const reportMonth = isAllTime ? 'All time' : analyticsMonth(searchParams);
  const isAugust = analyticsMonth(searchParams) === 'August';
  const periodRange = isAllTime ? memberRange : `${reportMonth} 1–31, 2026`;
  const selectedPeriod = isAllTime ? 'all' : isAugust ? '2026-08' : '2026-07';
  const memberGrouping =
    searchParams.get('grouping') === 'provider' ? 'provider' : 'code';
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
  const summary = isAllTime
    ? {
        ...AUGUST_2026_SUMMARY,
        ...memberPortalTotals,
        zeroResultSearches: allTimeData.searchTotals.zeroResults,
        searches: allTimeData.daily.reduce((n, row) => n + row.searches, 0),
        requests: allTimeData.daily.reduce((n, row) => n + row.requests, 0),
        serverErrors: allTimeData.daily.reduce((n, row) => n + row.errors, 0),
        events: allTimeData.daily.reduce((n, row) => n + row.events, 0),
        resultClicks:
          JULY_2026_SUMMARY.resultClicks + AUGUST_2026_SUMMARY.resultClicks,
        exportedAt: 'September 11, 2026',
      }
    : isAugust
      ? AUGUST_2026_SUMMARY
      : JULY_2026_SUMMARY;
  const memberSummary = isAllTime
    ? allTimeMemberSummary
    : isAugust
      ? augustReports.augustMemberSummary
      : julyMEMBER_JULY_SUMMARY;
  const memberPerformance = isAllTime
    ? allTimeMembers
    : isAugust
      ? augustReports.augustMembers
      : julyMemberPerformance;
  const memberDailySeries = isAllTime
    ? allTimeMemberDaily
    : isAugust
      ? augustReports.augustMemberDailySeries
      : julyMemberDailySeries;
  const memberTopContent = isAllTime
    ? allTimeMemberContent
    : isAugust
      ? augustReports.augustMemberTopContent
      : julyMemberTopContent;
  const monthShort = isAugust ? 'Aug' : 'Jul';
  const dailyActivity = isAllTime
    ? allTimeData.daily.map((row) => ({
        ...row,
        day: new Date(`${row.day}T00:00:00Z`).toLocaleDateString('en-US', {
          month: 'short',
          day: 'numeric',
          timeZone: 'UTC',
        }),
      }))
    : isAugust
      ? augustDailyActivity.map((row, index) => ({
          ...row,
          day: `Aug ${index + 1}`,
        }))
      : julyDailyActivity;
  const discoveryViews = isAllTime
    ? allTimeData.searchViews.map((row) => ({
        label: row.label.charAt(0).toUpperCase() + row.label.slice(1),
        count: row.count,
        percent: Number(
          ((row.count / allTimeData.searchTotals.searches) * 100).toFixed(1)
        ),
        color:
          julyDiscoveryViews.find(
            (view) => view.label.toLowerCase() === row.label
          )?.color ?? '#003C5B',
      }))
    : isAugust
      ? augustReports.augustDiscoveryViews
      : julyDiscoveryViews;
  const resourceClassFilters = isAllTime
    ? julyResourceClassFilters
        .map((row) => ({
          ...row,
          count:
            row.count +
            (augustReports.augustResourceClassFilters.find(
              (item) => item.label === row.label
            )?.count ?? 0),
        }))
        .sort((a, b) => b.count - a.count)
    : isAugust
      ? augustReports.augustResourceClassFilters
      : julyResourceClassFilters;
  const topSearchSnapshot = isAllTime
    ? {
        ...allTimeData.searchTotals,
        queries: allTimeData.queries,
        rankedSearches: allTimeData.queries.reduce(
          (n, row) => n + row.count,
          0
        ),
      }
    : topSearches.months[isAugust ? '2026-08' : '2026-07'];
  const topSearchTerms = topSearchSnapshot.queries.map((query, index) => ({
    ...query,
    rank: index + 1,
    category: queryCategory(query.term),
  }));
  const [selectedQueryCategory, setQueryCategoryFilter] = useState('all');
  const snapshotMonth = isAugust ? '2026-08' : '2026-07';
  const [overviewMetric, setOverviewMetric] = useState<
    'events' | 'visits' | 'views' | 'searches'
  >('events');
  const overviewMetricLabels = {
    events: 'Interactions',
    searches: 'Searches',
    visits: 'Tracked visits',
    views: 'Resource views',
  };
  const overviewDaily = dailyActivity.map((row, index) => {
    const audience = isAllTime
      ? outcomes.periods.all.daily.find(
          (day) => day.day === allTimeData.daily[index].day
        )
      : outcomes.periods[snapshotMonth].daily.find(
          (day) =>
            Number(day.day.slice(-2)) === Number(row.day.split(' ').at(-1))
        );
    return {
      ...row,
      visits: audience?.visits ?? null,
      views: audience?.views ?? null,
    };
  });

  const overviewPeak = overviewDaily.reduce((peak, row) =>
    (row[overviewMetric] ?? 0) > (peak[overviewMetric] ?? 0) ? row : peak
  );

  const queryCategoryCounts = Array.from(
    new Set(topSearchTerms.map((query) => query.category))
  )
    .sort()
    .map((category) => ({
      category,
      queries: topSearchTerms.filter((query) => query.category === category)
        .length,
      searches: topSearchTerms
        .filter((query) => query.category === category)
        .reduce((sum, query) => sum + query.count, 0),
    }));
  const queryCategoryFilter = queryCategoryCounts.some(
    ({ category }) => category === selectedQueryCategory
  )
    ? selectedQueryCategory
    : 'all';
  const visibleSearchTerms = topSearchTerms.filter(
    (query) =>
      queryCategoryFilter === 'all' || query.category === queryCategoryFilter
  );
  const allTimeFacets = new globalThis.Map<string, number>();
  for (const month of allTimeData.publishedMonths) {
    for (const facet of searchSnapshots[month as keyof typeof searchSnapshots]
      .facets) {
      allTimeFacets.set(
        facet.field,
        (allTimeFacets.get(facet.field) ?? 0) + facet.count
      );
    }
  }
  const searchSnapshot = isAllTime
    ? {
        zeroQueries: allTimeData.zeroQueries,
        facets: [...allTimeFacets]
          .map(([field, count]) => ({ field, count }))
          .sort((a, b) => b.count - a.count),
      }
    : searchSnapshots[isAugust ? '2026-08' : '2026-07'];
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
  const requestMix = isAllTime
    ? julyRequestMix.map((row) => {
        const count =
          row.count +
          (augustReports.augustRequestMix.find(
            (item) => item.label === row.label
          )?.count ?? 0);
        return { ...row, count, percent: (count / summary.requests) * 100 };
      })
    : isAugust
      ? augustReports.augustRequestMix
      : julyRequestMix;
  const peakApiTrafficBreakdown = isAugust
    ? augustReports.augustPeakApiTrafficBreakdown
    : julyPeakApiTrafficBreakdown;
  const inventoryDate = isAllTime
    ? memberCatalogDate
    : isAugust
      ? 'September 9, 2026'
      : 'August 20, 2026';
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
    views: Array.from(
      { length: isAllTime ? memberDays.length : 31 },
      (_, index) =>
        memberPerformance.reduce(
          (total, member) =>
            total + memberDailySeries[member.code].views[index],
          0
        )
    ),
    downloads: Array.from(
      { length: isAllTime ? memberDays.length : 31 },
      (_, index) =>
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
  const requestReliability =
    ((summary.requests - summary.serverErrors) / summary.requests) * 100;
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
      day: isAllTime
        ? new Date(`${memberDays[index]}T00:00:00Z`).toLocaleDateString(
            'en-US',
            { month: 'short', day: 'numeric', timeZone: 'UTC' }
          )
        : `${monthShort} ${index + 1}`,
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

  if (
    isAllTime &&
    ![
      'comparison',
      'members',
      'overview',
      'discovery',
      'clients',
      'platform',
    ].includes(activeReport)
  ) {
    return <AllTimeAnalyticsPage reportId={activeReport} />;
  }

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
                  <ReportingPeriodPicker
                    id="overview-month"
                    value={selectedPeriod}
                    onChange={changeMonth}
                  />
                </div>

                <div className="analytics-hero-copy">
                  <div>
                    <p className="analytics-overline">
                      API + discovery analytics
                    </p>
                    <h1 id="analytics-title">Analytics dashboard</h1>
                  </div>
                  <div className="analytics-hero-note">
                    <p>
                      How people search for resources, view records, and follow
                      source or download links. Explore audience coverage and
                      access outcomes below.
                    </p>
                  </div>
                </div>

                <div
                  className="analytics-hero-stats"
                  aria-label={`${reportMonth} 2026 highlights`}
                >
                  <div>
                    <span>01</span>
                    <strong>{formatCompact(summary.searches)}</strong>
                    <p>Search result pages</p>
                    <small>
                      {periodRange} · includes filter changes and pagination
                    </small>
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
                    <strong>
                      {wholeNumber.format(
                        outcomes.periods[selectedPeriod].totals.sources
                      )}
                    </strong>
                    <p>Source-site clicks</p>
                    <small>Clicks to authoritative source links</small>
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
            <div className="analytics-report-title">
              <p>{report.period} · Analytics</p>
              <h1>{report.label}</h1>
              <span>{report.description}</span>
            </div>
            <ReportingPeriodPicker
              id="report-month"
              value={selectedPeriod}
              onChange={changeMonth}
              comparison={activeReport === 'comparison'}
            />
          </div>
        )}

        <ReportContentLayout report={report.label}>
          <div className="analytics-shell analytics-content">
            {activeReport === 'comparison' && <MonthlyComparison />}
            {activeReport === 'clients' && (
              <ClientUsageReport month={selectedPeriod} />
            )}
            {activeReport === 'content' && (
              <PopularContentReport
                title={`${reportMonth}’s top resources and collections`}
                reportMonth={reportMonth}
                topResources={topResources}
                topCollections={topCollections}
                collectionNote={
                  isAugust
                    ? `${topCollections[0].title} led August with ${topCollections[0].searches} filtered searches.`
                    : 'Urban Base Layers held the top spot, while historical maps claimed five positions in the collection top 10.'
                }
                topDownloadedResources={topDownloadedResources}
                downloadClicks={contentSummary.downloadClicks}
                downloadNote={`The top ${topDownloadedResources.length} account for ${topDownloadClicks} of ${contentSummary.downloadClicks} clicks (${((topDownloadClicks / contentSummary.downloadClicks) * 100).toFixed(1)}%), across ${downloadResourceCount} resources with download clicks.`}
              />
            )}

            {activeReport === 'content' && (
              <OutlinkedResources period={snapshotMonth} />
            )}

            {activeReport === 'members' && (
              <div className="analytics-grouping-controls">
                <label htmlFor="member-grouping">Group records by</label>
                <select
                  id="member-grouping"
                  value={memberGrouping}
                  onChange={(event) => {
                    const params = new URLSearchParams(searchParams);
                    params.set('grouping', event.target.value);
                    setSearchParams(params);
                  }}
                >
                  <option value="code">BTAA contribution code</option>
                  <option value="provider">Provider facet</option>
                </select>
                <p>
                  Contribution codes include agency content gathered through a
                  member’s stream. Provider uses the named institution or agency
                  on the record.
                </p>
              </div>
            )}
            {activeReport === 'members' && memberGrouping === 'provider' && (
              <ProviderReport
                key={selectedPeriod}
                month={isAllTime ? memberRange : snapshotMonth}
                snapshot={isAllTime ? allTimeProviderSnapshot : undefined}
              />
            )}

            {activeReport === 'members' && memberGrouping === 'code' && (
              <section id="members" className="analytics-section">
                <SectionHeading
                  title="How BTAA member content performed"
                  description={`Start with the full alliance, then choose any campus to follow its catalog footprint, daily attention, downloads, and leading content across the selected period.`}
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
                      <p>
                        {selectedMember ? 'Campus segment' : 'Alliance view'}
                      </p>
                      <h3>
                        {selectedMember?.name ?? 'All BTAA member content'}
                      </h3>
                      <small>
                        {selectedMember
                          ? `Contribution stream ${selectedMember.code} · ${periodRange}`
                          : `17 member contribution streams · ${periodRange}`}
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
                    <strong>
                      {wholeNumber.format(selectedCatalogRecords)}
                    </strong>
                    <p>published catalog inventory as of {inventoryDate}</p>
                  </article>
                  <article>
                    <span>{reportMonth} reach</span>
                    <strong>
                      {wholeNumber.format(selectedActiveResources)}
                    </strong>
                    <p>
                      {activeResourceRate.toFixed(1)}% of the catalog appeared
                      in a search or received an action
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
                    <strong>
                      {wholeNumber.format(selectedDownloadClicks)}
                    </strong>
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
                      aria-label={`${selectedMember?.name ?? 'All BTAA member content'} daily resource views and download clicks from ${periodRange}. Views peaked at ${peakMemberDay.views} on ${peakMemberDay.day}.`}
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
                            interval={isAllTime ? 9 : 4}
                          />
                          <YAxis
                            axisLine={false}
                            tickLine={false}
                            tick={{ fill: '#6B7280', fontSize: 11 }}
                            allowDecimals={false}
                          />
                          <Tooltip
                            cursor={{
                              stroke: '#2563EB',
                              strokeDasharray: '3 3',
                            }}
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
                      <small>
                        {selectedMember?.shortName ?? 'All members'}
                      </small>
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
                        source-site clicks—the month’s leading member by
                        resource views.
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
                        {wholeNumber.format(reachLeader.activeResources)}{' '}
                        distinct records appeared in a search or received a
                        tracked action.
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
                      <AnalyticsTable>
                        <caption className="sr-only">
                          {report.period} performance for BTAA
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
                              <td>
                                {wholeNumber.format(member.catalogRecords)}
                              </td>
                              <td>
                                {wholeNumber.format(member.activeResources)}
                              </td>
                              <td>{wholeNumber.format(member.impressions)}</td>
                              <td>
                                <strong>
                                  {wholeNumber.format(member.resourceViews)}
                                </strong>
                              </td>
                              <td>
                                {wholeNumber.format(member.downloadClicks)}
                              </td>
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
                      </AnalyticsTable>
                    </div>
                  </article>
                )}

                <CodeCoverage
                  month={selectedPeriod}
                  snapshot={isAllTime ? allTimeProviderSnapshot : undefined}
                />
                <section
                  className="analytics-panel analytics-report-sources"
                  aria-label="Outside the university code groups"
                  data-nav-label="Outside university groups"
                >
                  <h3>What is outside these university totals?</h3>
                  <p>
                    {wholeNumber.format(
                      summary.resourceViews - memberSummary.resourceViews
                    )}{' '}
                    resource views,{' '}
                    {wholeNumber.format(
                      summary.impressions - memberSummary.impressions
                    )}{' '}
                    search impressions, and{' '}
                    {wholeNumber.format(
                      summary.downloadClicks - memberSummary.downloadClicks
                    )}{' '}
                    download clicks in the portal totals are outside this
                    eligible 01–17 member cohort.
                  </p>
                  <p>
                    This remainder is not an “Other institutions” total: it can
                    also include unpublished, suppressed, missing, or unmatched
                    catalog records. Federal sources, standalone items, and
                    BTAA-curated content need their actual contribution codes or
                    Provider values checked before assigning them to a group.
                  </p>
                  <p>
                    The{' '}
                    <a href="https://gin.btaa.org/harvest-operations/latest/institutions/">
                      harvest-operations institution report
                    </a>{' '}
                    groups harvest records and includes OpenGeoMetadata,
                    licensed databases, BTAA-GIN curated datasets, and Other.
                    Its grouping is not equivalent to this catalog-level prefix
                    grouping.
                  </p>
                </section>

                {isAllTime && (
                  <p className="analytics-comparison-note" role="note">
                    All time uses preserved attribution captured September 11,
                    2026. Its explicit code mapping keeps four-digit federal
                    codes such as 1000 outside Wisconsin’s stream 10; the
                    original monthly snapshots used a broader prefix match. July
                    resource-level impressions were unavailable when this
                    archive was built; preserved aggregates retain available
                    evidence, but cannot recover missing historical detail.
                    Inventory and active records are counted across the full
                    period, not added from monthly totals.
                  </p>
                )}
                <p className="analytics-member-method analytics-panel">
                  Activity period: {periodRange}. Catalog inventory: published,
                  unsuppressed records as of {inventoryDate}, when this report
                  was exported. The inventory is a point-in-time count, not an
                  activity total or month-end count. “{reportMonth} active”
                  means a distinct record with at least one search impression or
                  tracked action during the selected period. Only code prefixes
                  01–17 are included here. Other prefixes and missing codes are
                  excluded, even if their records appear in portal totals. The
                  coverage table retains other and missing code groups. Their
                  inclusion depends on the stored code, not their title or
                  Provider. School attribution follows the BTAA contribution
                  code rather than the provider label, which often names an
                  originating public agency. Downloads and source-site visits
                  are link clicks, not verified completions.
                </p>
              </section>
            )}

            {activeReport === 'overview' && (
              <section id="pulse" className="analytics-section">
                <SectionHeading
                  title="Day by day"
                  description={`Daily interactions and searches across the selected period. ${peakActivity.day} recorded the most interactions.`}
                />

                <div className="analytics-pulse-grid">
                  <figure className="analytics-panel analytics-activity-chart">
                    <div className="analytics-panel-header">
                      <div>
                        <Activity className="h-5 w-5" aria-hidden />
                        <span>Daily discovery</span>
                      </div>
                      <div className="analytics-chart-key" aria-hidden="true">
                        <span>
                          <i className="analytics-key-events" />
                          {overviewMetricLabels[overviewMetric]}
                        </span>
                      </div>
                    </div>
                    <label className="analytics-table-tools analytics-table-tools--inset">
                      Chart metric
                      <select
                        aria-label="Overview chart metric"
                        value={overviewMetric}
                        onChange={(event) =>
                          setOverviewMetric(
                            event.target.value as typeof overviewMetric
                          )
                        }
                      >
                        {Object.entries(overviewMetricLabels).map(
                          ([key, label]) => (
                            <option key={key} value={key}>
                              {label}
                            </option>
                          )
                        )}
                      </select>
                    </label>
                    <div
                      className="analytics-rechart"
                      role="img"
                      aria-label={`Daily ${overviewMetricLabels[overviewMetric].toLowerCase()} from ${periodRange}. Peak: ${overviewPeak[overviewMetric]} on ${overviewPeak.day}.`}
                    >
                      <ResponsiveContainer
                        width="100%"
                        height="100%"
                        minWidth={0}
                        minHeight={352}
                        initialDimension={{ width: 1_000, height: 352 }}
                      >
                        <AreaChart
                          data={overviewDaily}
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
                            interval={isAllTime ? 9 : 4}
                          />
                          <YAxis
                            axisLine={false}
                            tickLine={false}
                            tick={{ fill: '#6B7280', fontSize: 11 }}
                          />
                          <Tooltip
                            cursor={{
                              stroke: '#2563EB',
                              strokeDasharray: '3 3',
                            }}
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
                            dataKey={overviewMetric}
                            name={overviewMetricLabels[overviewMetric]}
                            stroke="#2563EB"
                            strokeWidth={3}
                            fill="url(#eventsFill)"
                            isAnimationActive={false}
                          />
                        </AreaChart>
                      </ResponsiveContainer>
                    </div>
                    <figcaption>
                      <span>{overviewDaily[0].day}</span>
                      <strong>
                        Peak:{' '}
                        {wholeNumber.format(overviewPeak[overviewMetric] ?? 0)}{' '}
                        {overviewMetricLabels[overviewMetric].toLowerCase()} ·{' '}
                        {overviewPeak.day}
                      </strong>
                      <span>{overviewDaily.at(-1)?.day}</span>
                    </figcaption>
                  </figure>

                  <aside className="analytics-signal-stack">
                    <div className="analytics-signal-card analytics-signal-card--bright">
                      <div>
                        <Zap className="h-5 w-5" aria-hidden />
                        <span>Peak API traffic</span>
                      </div>
                      <strong>
                        {wholeNumber.format(peakTraffic.requests)}
                      </strong>
                      <p>
                        raw HTTP requests on {peakTraffic.day}, including bots
                        and automated health probes
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
                        <span>Tracked visits</span>
                      </div>
                      <strong>
                        {wholeNumber.format(
                          outcomes.periods[selectedPeriod].audience
                            .trackedVisits
                        )}
                      </strong>
                      <p>
                        distinct visit tokens recorded in searches or events;
                        not unique people
                      </p>
                    </div>
                  </aside>
                </div>
                <div
                  data-nav-label="Daily audience values"
                  className="analytics-panel analytics-overview-details"
                >
                  <AudienceReport period={selectedPeriod} embedded />
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
                            : report.period}
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
                  title="Top 50 searches"
                  description={`The most frequently recorded queries during ${periodRange}. ${wholeNumber.format(topSearchSnapshot.withQuery)} searches included query text, across ${wholeNumber.format(topSearchSnapshot.distinctQueries)} distinct queries.`}
                />
                <article className="analytics-panel analytics-top-searches">
                  <div className="analytics-panel-header">
                    <div>
                      <Search className="h-5 w-5" aria-hidden />
                      <span>Most frequent queries</span>
                    </div>
                    <small>
                      {wholeNumber.format(topSearchSnapshot.rankedSearches)}{' '}
                      searches across these 50 queries
                    </small>
                  </div>
                  <div className="analytics-top-searches-body">
                    <div className="analytics-query-category-filter">
                      <label htmlFor="query-category">Query category</label>
                      <select
                        id="query-category"
                        value={queryCategoryFilter}
                        onChange={(event) =>
                          setQueryCategoryFilter(event.target.value)
                        }
                      >
                        <option value="all">All categories · 50 queries</option>
                        {queryCategoryCounts.map(
                          ({ category, queries, searches }) => (
                            <option key={category} value={category}>
                              {category} · {queries}{' '}
                              {queries === 1 ? 'query' : 'queries'} · {searches}{' '}
                              searches
                            </option>
                          )
                        )}
                      </select>
                      <p>
                        Suggested from query text; each query has one primary
                        category. Counts in the menu cover these top 50 queries
                        only.
                      </p>
                    </div>
                    <div
                      className="analytics-top-searches-table"
                      role="region"
                      aria-label="Top 50 searches"
                      tabIndex={0}
                    >
                      <AnalyticsTable className="analytics-comparison-table">
                        <caption className="sr-only">
                          {report.period} top 50 searches
                        </caption>
                        <thead>
                          <tr>
                            <th scope="col">Rank</th>
                            <th scope="col">Query</th>
                            <th scope="col">Category</th>
                            <th scope="col">Searches</th>
                          </tr>
                        </thead>
                        <tbody>
                          {visibleSearchTerms.map((query) => (
                            <tr key={query.term}>
                              <td>{query.rank}</td>
                              <th scope="row">
                                <Link
                                  to={`/search?q=${encodeURIComponent(query.term)}`}
                                >
                                  {query.term}
                                </Link>
                              </th>
                              <td>{query.category}</td>
                              <td>{wholeNumber.format(query.count)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </AnalyticsTable>
                    </div>
                    <p className="analytics-card-footnote">
                      {queryCategoryMethod} Counts include successful and
                      zero-result searches, grouped by trimmed query text with
                      case preserved. Filters and views are combined; links
                      repeat the query text only. Empty queries are excluded.
                      Exported{' '}
                      {new Date(topSearches.exportedAt).toLocaleDateString(
                        'en-US',
                        {
                          timeZone: 'UTC',
                          month: 'long',
                          day: 'numeric',
                          year: 'numeric',
                        }
                      )}
                      .
                    </p>
                  </div>
                </article>
                <SearchDailyReport
                  period={report.period}
                  days={allTimeData.daily.filter(
                    (row) => isAllTime || row.day.startsWith(selectedPeriod)
                  )}
                />
                <SectionHeading
                  title="Views, filters, and zero results"
                  description={`How searches were viewed and refined during the selected period.`}
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
                      filters and legacy filter formats. Searches can use
                      several categories. Map bounds and year ranges are
                      included; these counts describe filters present in
                      searches, not facet clicks.
                    </p>
                  </article>

                  <ZeroResultReport
                    periodKey={selectedPeriod}
                    key={selectedPeriod}
                    period={report.period}
                    searches={summary.searches}
                    zeroResults={summary.zeroResultSearches}
                    withQuery={
                      isAllTime
                        ? allTimeData.publishedMonths.reduce(
                            (sum, month) =>
                              sum +
                              zeroSnapshots.months[
                                month as keyof typeof zeroSnapshots.months
                              ].withQuery,
                            0
                          )
                        : zeroQueries.with_query
                    }
                    queries={topZeroResultQueries}
                  />
                </div>
              </section>
            )}

            {activeReport === 'platform' && (
              <section
                id="platform"
                className="analytics-section analytics-platform-section"
              >
                <SectionHeading
                  title="API requests and reliability"
                  description="Raw HTTP traffic includes browsers, crawlers, health probes, images, and analytics capture. It should not be read as a count of searches or visitors."
                />

                <div className="analytics-platform-grid">
                  <article
                    className="analytics-panel analytics-reliability-card"
                    data-nav-label="Reliability summary"
                  >
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
                        <strong>
                          {isAllTime
                            ? 'Not available'
                            : `${summary.medianResponseMs} ms`}
                        </strong>
                      </div>
                      <div>
                        <span>95th percentile</span>
                        <strong>
                          {isAllTime
                            ? 'Not available'
                            : `${summary.p95ResponseMs} ms`}
                        </strong>
                      </div>
                      <div>
                        <span>Server errors</span>
                        <strong>{summary.serverErrors}</strong>
                      </div>
                    </div>
                    {isAllTime && (
                      <p className="analytics-comparison-note">
                        Full-period response-time percentiles cannot be
                        reconstructed from monthly percentiles. Request and
                        server-error totals cover the complete period.
                      </p>
                    )}
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
                        <span>Peak-day API traffic</span>
                      </div>
                      <small>
                        {wholeNumber.format(peakTraffic.requests)} raw HTTP
                        requests · {peakTraffic.day}
                      </small>
                    </div>
                    <div className="analytics-api-table-wrap">
                      <AnalyticsTable label="API traffic breakdown">
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
                      </AnalyticsTable>
                    </div>
                    <p>
                      Turnstile status checks and API documentation probes made
                      up
                      {(
                        ((peakApiTrafficBreakdown[0].count +
                          peakApiTrafficBreakdown[1].count) /
                          peakTraffic.requests) *
                        100
                      ).toFixed(1)}
                      % of the peak. The table describes infrastructure load,
                      not visitor search demand.
                    </p>
                  </article>
                </div>
                <ApiDailyReport
                  period={report.period}
                  days={allTimeData.daily.filter(
                    (row) => isAllTime || row.day.startsWith(selectedPeriod)
                  )}
                />
                <section
                  className="analytics-panel analytics-comparison-panel"
                  data-nav-label="API endpoints"
                >
                  <h3>API endpoints</h3>
                  <AnalyticsTable className="analytics-comparison-table">
                    <caption className="sr-only">
                      {report.period} API endpoints
                    </caption>
                    <thead>
                      <tr>
                        <th scope="col">Endpoint</th>
                        <th scope="col">Requests</th>
                        <th scope="col">Server errors</th>
                      </tr>
                    </thead>
                    <tbody>
                      {reliabilityEndpoints.periods[selectedPeriod].map(
                        (row) => (
                          <tr key={row.label}>
                            <th scope="row">{row.label}</th>
                            <td>{wholeNumber.format(row.requests)}</td>
                            <td>{wholeNumber.format(row.errors)}</td>
                          </tr>
                        )
                      )}
                    </tbody>
                  </AnalyticsTable>
                  <p className="analytics-comparison-note">
                    {reliabilityEndpoints.method}
                  </p>
                </section>
              </section>
            )}

            {activeReport === 'content' && (
              <AccessSummary period={snapshotMonth} />
            )}
            <ReportSources
              report={activeReport}
              month={reportMonth}
              period={periodRange}
            />

            {activeReport === 'content' && (
              <p className="analytics-comparison-note">
                {periodRange} (UTC) · Exported {contentSummary.exportedAt}.
                Rankings use recorded interactions and catalog metadata at
                export. Actions are tracked events other than resource views;
                momentum compares days 16–31 with days 1–15.
              </p>
            )}

            {activeReport !== 'comparison' &&
              activeReport !== 'content' &&
              activeReport !== 'clients' && (
                <section
                  className="analytics-method-note"
                  aria-label="Data notes"
                >
                  <div>
                    <strong>{reportMonth} report data</strong>
                  </div>
                  <p>
                    Built from reconciled API, search, impression, and event
                    exports covering {periodRange} (UTC). Exported{' '}
                    {summary.exportedAt}. Raw request records remain outside
                    this application; this page contains aggregate metrics and
                    public catalog metadata only.
                  </p>
                  <span>
                    {isAllTime
                      ? `${memberDays.length} days · Preserved reporting aggregates`
                      : '7 analytics tables · 1 catalog snapshot · 31 complete days'}
                  </span>
                </section>
              )}
          </div>
        </ReportContentLayout>
      </main>

      <Footer />
    </div>
  );
}

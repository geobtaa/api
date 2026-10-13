import manifest from '../../private-analytics-reports/manifest.json';
import { ReportFindings } from '../components/analytics/ReportFindings';
import { CampusBrief } from '../components/analytics/CampusBrief';
import {
  buildFindings,
  previousCalendarMonth,
} from '../utils/analyticsFindings';
import { MemberPerformanceReport } from '../components/analytics/MemberPerformanceReport';
import { useAnalyticsData } from '../components/analytics/AnalyticsData';

import { chartTheme } from '../components/analytics/chartTheme';
import { MetricHeading } from '../components/analytics/MetricHeading';
import { Users } from 'lucide-react';
import { ReportPanelHeader } from '../components/analytics/ReportPanelHeader';
import {
  selectedSnapshotPeriod,
  latestMonth,
  monthDays as daysInMonth,
  periodRange as monthlyRange,
  monthLabel,
} from '../config/analyticsPeriods';

import { ReportingPeriodPicker } from '../components/analytics/ReportingPeriodPicker';
import { ApiDailyReport } from '../components/analytics/ApiDailyReport';

import { MemberContentList } from '../components/analytics/MemberContentList';
import { RankingRow } from '../components/analytics/RankingRow';
import { SearchCategoryChart } from '../components/analytics/SearchCategoryChart';
import { SearchDailyReport } from '../components/analytics/SearchDailyReport';

import { ReportContentLayout } from '../components/analytics/ReportContentLayout';
import { ReportSectionHeading as SectionHeading } from '../components/analytics/ReportSectionHeading';
import { PopularContentReport } from '../components/analytics/PopularContentReport';
import {
  AudienceReport,
  OutlinkedResources,
} from '../components/analytics/DiscoveryOutcomes';

import { ZeroResultReport } from '../components/analytics/ZeroResultReport';
import { AllTimeAnalyticsPage } from '../components/analytics/AllTimeAnalyticsPage';

import { AnalyticsTable } from '../components/analytics/AnalyticsTable';
import { ProviderReport } from '../components/analytics/ProviderReport';
import { ReportSources } from '../components/analytics/ReportSources';

import { FACET_LABELS } from '../utils/facetLabels';
import { ClientUsageReport } from '../components/analytics/ClientUsageReport';

import {
  Activity,
  SlidersHorizontal,
  BarChart3,
  CheckCircle2,
  CircleGauge,
  Download,
  Eye,
  ExternalLink,
  Layers3,
  Map,
  Search,
  Zap,
} from 'lucide-react';
import { Link, useSearchParams, useLocation } from 'react-router';
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
  analyticsMonth,
  selectedAnalyticsReport,
} from '../config/analyticsReports';

import { MonthlyComparison } from '../components/analytics/MonthlyComparison';
import { Footer } from '../components/layout/Footer';
import { AnalyticsHeader } from '../components/analytics/AnalyticsHeader';
import {
  analyticsReports,
  analyticsReportHref,
} from '../config/analyticsReports';
import { Seo } from '../components/Seo';
import { BTAA_PARTNER_INSTITUTIONS } from '../constants/partnerInstitutions';

import '../styles/analytics.css';

const compactNumber = new Intl.NumberFormat('en-US', {
  notation: 'compact',
  maximumFractionDigits: 1,
});

const wholeNumber = new Intl.NumberFormat('en-US');

function formatCompact(value: number) {
  return compactNumber.format(value);
}

export function AnalyticsPage() {
  const analytics = useAnalyticsData();
  const collectionViews = analytics['collectionViewsCurrent.json'].default;
  const monthlySnapshots = analytics['september2026'].monthlySnapshots;
  const reliabilityEndpoints =
    analytics['reliabilityEndpointsCurrent.json'].default;
  const allTimeMembers = analytics['memberAllTime'].allTimeMembers;
  const allTimeMemberSummary = analytics['memberAllTime'].allTimeMemberSummary;
  const allTimeMemberDaily = analytics['memberAllTime'].allTimeMemberDaily;
  const allTimeMemberContent = analytics['memberAllTime'].allTimeMemberContent;
  const allTimeProviderSnapshot =
    analytics['memberAllTime'].allTimeProviderSnapshot;
  const memberDays = analytics['memberAllTime'].memberDays;
  const memberRange = analytics['memberAllTime'].memberRange;
  const memberCatalogDate = analytics['memberAllTime'].memberCatalogDate;
  const memberPortalTotals = analytics['memberAllTime'].memberPortalTotals;
  const allTimeData = analytics['allTimeCurrent.json'].default;
  const outcomes = analytics['outcomes'].outcomes;
  const visitsAreEstimated = analytics['outcomes'].visitsAreEstimated;
  const queryCategory = analytics['queryCategories'].queryCategory;
  const queryCategoryMethod = analytics['queryCategories'].queryCategoryMethod;
  const topSearches = analytics['topSearches2026.json'].default;
  const searchSnapshots = analytics['searches2026'].searchSnapshots;
  const augustReports = analytics['reportsAugust2026'];
  const augustDailyActivity = analytics['august2026'].augustDailyActivity;
  const popularHistory = analytics['popularHistory2026'].popularHistory;
  const AUGUST_2026_SUMMARY = analytics['august2026'].AUGUST_2026_SUMMARY;
  const JULY_2026_SUMMARY = analytics['july2026'].JULY_2026_SUMMARY;
  const julyMEMBER_JULY_SUMMARY = analytics['july2026'].MEMBER_JULY_SUMMARY;
  const julyDailyActivity = analytics['july2026'].dailyActivity;
  const julyDiscoveryViews = analytics['july2026'].discoveryViews;
  const julyMemberPerformance = analytics['july2026'].memberPerformance;
  const julyPeakApiTrafficBreakdown =
    analytics['july2026'].peakApiTrafficBreakdown;
  const julyRequestMix = analytics['july2026'].requestMix;
  const julyResourceClassFilters = analytics['july2026'].resourceClassFilters;
  const julyMemberDailySeries = analytics['memberJuly2026'].memberDailySeries;
  const julyMemberTopContent = analytics['memberJuly2026'].memberTopContent;

  const [searchParams, setSearchParams] = useSearchParams();
  const { pathname } = useLocation();
  const report = selectedAnalyticsReport(searchParams, pathname);
  const isAllTime = searchParams.get('month') === 'all';
  const reportMonth = isAllTime ? 'All time' : analyticsMonth(searchParams);
  const selectedPeriod = selectedSnapshotPeriod(searchParams.get('month'));
  const activeMonth = isAllTime ? latestMonth : selectedPeriod;
  const selectedSnapshot =
    monthlySnapshots[activeMonth] ?? monthlySnapshots[latestMonth];
  const hasMonthlySnapshot = activeMonth in monthlySnapshots;
  const monthDays = daysInMonth(activeMonth);
  const isAugust = activeMonth === '2026-08';
  const periodRange = isAllTime ? memberRange : monthlyRange(activeMonth);
  const memberGrouping =
    searchParams.get('grouping') === 'provider' ? 'provider' : 'code';
  const popular = hasMonthlySnapshot
    ? selectedSnapshot
    : popularHistory[isAugust ? '2026-08' : '2026-07'];
  const topResources = popular.topResources;
  const topCollections =
    collectionViews[activeMonth as keyof typeof collectionViews] ?? [];
  const topDownloadedResources = popular.topDownloads;
  const contentSummary = hasMonthlySnapshot
    ? selectedSnapshot.summary
    : isAugust
      ? AUGUST_2026_SUMMARY
      : JULY_2026_SUMMARY;
  const downloadResourceCount = popular.downloadResources;
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
        resultClicks: allTimeData.resultClicks,
        exportedAt: monthlySnapshots[latestMonth].summary.exportedAt,
      }
    : hasMonthlySnapshot
      ? selectedSnapshot.summary
      : isAugust
        ? AUGUST_2026_SUMMARY
        : JULY_2026_SUMMARY;
  const memberSummary = isAllTime
    ? allTimeMemberSummary
    : hasMonthlySnapshot
      ? selectedSnapshot.memberSummary
      : isAugust
        ? augustReports.augustMemberSummary
        : julyMEMBER_JULY_SUMMARY;
  const memberPerformance = isAllTime
    ? allTimeMembers
    : hasMonthlySnapshot
      ? selectedSnapshot.members
      : isAugust
        ? augustReports.augustMembers
        : julyMemberPerformance;
  const memberDailySeries = isAllTime
    ? allTimeMemberDaily
    : hasMonthlySnapshot
      ? selectedSnapshot.memberDailySeries
      : isAugust
        ? augustReports.augustMemberDailySeries
        : julyMemberDailySeries;
  const memberTopContent =
    analytics.memberLeadingContent[selectedPeriod] ??
    (isAllTime
      ? allTimeMemberContent
      : hasMonthlySnapshot
        ? selectedSnapshot.memberTopContent
        : isAugust
          ? augustReports.augustMemberTopContent
          : julyMemberTopContent);
  const monthShort = monthLabel(activeMonth, true).split(' ')[0];
  const dailyActivity = isAllTime
    ? allTimeData.daily.map((row) => ({
        ...row,
        day: new Date(`${row.day}T00:00:00Z`).toLocaleDateString('en-US', {
          month: 'short',
          day: 'numeric',
          timeZone: 'UTC',
        }),
      }))
    : hasMonthlySnapshot
      ? selectedSnapshot.dailyActivity.map((row, index) => ({
          ...row,
          day: `${monthShort} ${index + 1}`,
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
    : hasMonthlySnapshot
      ? selectedSnapshot.discoveryViews
      : isAugust
        ? augustReports.augustDiscoveryViews
        : julyDiscoveryViews;
  const resourceClassFilters = isAllTime
    ? allTimeData.resourceClassFilters
    : hasMonthlySnapshot
      ? selectedSnapshot.resourceClassFilters
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
    : hasMonthlySnapshot
      ? selectedSnapshot.topSearches
      : topSearches.months[isAugust ? '2026-08' : '2026-07'];
  const topSearchTerms = topSearchSnapshot.queries.map((query, index) => ({
    ...query,
    rank: index + 1,
    category: queryCategory(query.term),
  }));
  const [selectedQueryCategory, setQueryCategoryFilter] = useState('all');
  const snapshotMonth = selectedPeriod;
  const [overviewMetric, setOverviewMetric] = useState<
    'events' | 'visits' | 'views' | 'searches'
  >('events');
  const overviewMetricLabels = {
    events: 'Interactions',
    searches: 'Searches',
    visits: visitsAreEstimated(selectedPeriod)
      ? 'Tracked visits (estimated)'
      : 'Tracked visits',
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
  const searchSnapshot = isAllTime
    ? { zeroQueries: allTimeData.zeroQueries, facets: allTimeData.facets }
    : hasMonthlySnapshot
      ? selectedSnapshot.searchSnapshot
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
          )?.count ?? 0) +
          Object.values(monthlySnapshots).reduce(
            (sum, month) =>
              sum +
              (month.requestMix.find((item) => item.label === row.label)
                ?.count ?? 0),
            0
          );
        return { ...row, count, percent: (count / summary.requests) * 100 };
      })
    : hasMonthlySnapshot
      ? selectedSnapshot.requestMix
      : isAugust
        ? augustReports.augustRequestMix
        : julyRequestMix;
  const inventoryDate = isAllTime
    ? memberCatalogDate
    : hasMonthlySnapshot
      ? selectedSnapshot.summary.exportedAt
      : isAugust
        ? 'September 9, 2026'
        : 'August 20, 2026';
  const zeroQueries = hasMonthlySnapshot
    ? selectedSnapshot.zeroBreakdown
    : isAugust
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
  const peakMonth = isAllTime
    ? allTimeData.daily
        .reduce((peak, row) => (row.requests > peak.requests ? row : peak))
        .day.slice(0, 7)
    : activeMonth;
  const peakApiTrafficBreakdown =
    monthlySnapshots[peakMonth]?.peakApiTrafficBreakdown ??
    (peakMonth === '2026-08'
      ? augustReports.augustPeakApiTrafficBreakdown
      : julyPeakApiTrafficBreakdown);
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
  const memberSelectorEntries = BTAA_PARTNER_INSTITUTIONS.map((institution) => {
    const member = memberPerformance.find(
      (entry) => entry.slug === institution.slug
    );
    return {
      slug: institution.slug,
      code: member?.code ?? institution.slug,
      name: institution.name,
      shortName:
        member?.shortName ??
        (institution.slug === 'university-of-southern-california'
          ? 'USC'
          : institution.name),
      iconSrc: institution.iconSrc ?? `/icons/${institution.iconSlug}.svg`,
      available: Boolean(member),
    };
  }).sort((a, b) =>
    a.shortName.localeCompare(b.shortName, 'en', { sensitivity: 'base' })
  );

  const allMemberDailySeries = {
    views: Array.from(
      { length: isAllTime ? memberDays.length : monthDays },
      (_, index) =>
        memberPerformance.reduce(
          (total, member) =>
            total + memberDailySeries[member.code].views[index],
          0
        )
    ),
    downloads: Array.from(
      { length: isAllTime ? memberDays.length : monthDays },
      (_, index) =>
        memberPerformance.reduce(
          (total, member) =>
            total + memberDailySeries[member.code].downloads[index],
          0
        )
    ),
  };

  const allMemberTopContent = memberTopContent.all ?? {
    viewed: [],
    downloaded: [],
  };

  const providerSnapshot = isAllTime
    ? allTimeProviderSnapshot
    : hasMonthlySnapshot
      ? selectedSnapshot.provider
      : analytics.providers2026.providerSnapshots[snapshotMonth];
  const activeReport = report.id;
  const selectedMemberCode =
    memberSelectorEntries.find(
      (member) => member.slug === searchParams.get('institution')
    )?.code ?? 'all';
  const setSelectedMemberCode = (code: string) => {
    const params = new URLSearchParams(searchParams);
    const institution = memberSelectorEntries.find(
      (member) => member.code === code
    );
    if (institution) params.set('institution', institution.slug);
    else params.delete('institution');
    setSearchParams(params);
  };
  const [institutionPickerOpen, setInstitutionPickerOpen] = useState(false);
  const unavailableMember = memberSelectorEntries.find(
    (member) => member.code === selectedMemberCode && !member.available
  );
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

  const previousPeriod = previousCalendarMonth(selectedPeriod);
  const previousSnapshot = previousPeriod
    ? monthlySnapshots[previousPeriod]
    : undefined;
  const previousSummary =
    previousSnapshot?.summary ??
    (previousPeriod === '2026-08'
      ? AUGUST_2026_SUMMARY
      : previousPeriod === '2026-07'
        ? JULY_2026_SUMMARY
        : undefined);
  const previousMembers =
    previousSnapshot?.members ??
    (previousPeriod === '2026-08'
      ? augustReports.augustMembers
      : previousPeriod === '2026-07'
        ? julyMemberPerformance
        : undefined);
  const previousMemberSummary =
    previousSnapshot?.memberSummary ??
    (previousPeriod === '2026-08'
      ? augustReports.augustMemberSummary
      : previousPeriod === '2026-07'
        ? julyMEMBER_JULY_SUMMARY
        : undefined);
  const previousMember = selectedMember
    ? previousMembers?.find((member) => member.code === selectedMember.code)
    : previousMemberSummary;
  const archive = manifest.periods.find((entry) => entry.id === selectedPeriod);
  const briefParams = new URLSearchParams(searchParams);
  briefParams.set('month', selectedPeriod);
  briefParams.set('brief', '1');
  const reportParams = new URLSearchParams(briefParams);
  reportParams.delete('brief');
  const memberReportHref = `/analytics/members?${reportParams}`;
  if (
    activeReport === 'members' &&
    memberGrouping === 'code' &&
    searchParams.get('brief') === '1' &&
    !unavailableMember &&
    archive
  ) {
    return (
      <CampusBrief
        name={selectedMember?.name ?? 'All recorded member contributions'}
        iconSrc={
          memberSelectorEntries.find(
            (member) => member.code === selectedMemberCode
          )?.iconSrc
        }
        periodLabel={periodRange}
        inventoryDate={inventoryDate}
        counts={{
          resourceViews: selectedResourceViews,
          downloadClicks: selectedDownloadClicks,
          sourceClicks: selectedSourceClicks,
          impressions: selectedImpressions,
        }}
        catalogRecords={selectedCatalogRecords}
        activeResources={selectedActiveResources}
        previous={previousMember}
        previousLabel={
          previousPeriod ? monthLabel(previousPeriod, true) : undefined
        }
        topContent={selectedTopContent ?? { viewed: [], downloaded: [] }}
        daily={selectedDailyActivity}
        report={archive}
        reportHref={memberReportHref}
      />
    );
  }

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
        description="Explore API traffic and discovery activity with monthly resource, member, discovery, and reliability reports."
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
                  aria-label={`${isAllTime ? reportMonth : monthLabel(activeMonth)} highlights`}
                >
                  <div>
                    <MetricHeading icon={Users}>
                      Tracked visits
                      {visitsAreEstimated(selectedPeriod) ? ' (estimated)' : ''}
                    </MetricHeading>
                    <strong>
                      {visitsAreEstimated(selectedPeriod) ? '≈ ' : ''}
                      {wholeNumber.format(
                        outcomes.periods[selectedPeriod].audience.trackedVisits
                      )}
                    </strong>
                    <small>
                      Distinct browser-tab visits, not unique people
                    </small>
                  </div>
                  <div>
                    <MetricHeading icon={Search}>
                      Search result pages
                    </MetricHeading>
                    <strong>{formatCompact(summary.searches)}</strong>
                    <small>
                      {periodRange} · includes filter changes and pagination
                    </small>
                  </div>
                  <div>
                    <MetricHeading icon={Eye}>Resource views</MetricHeading>
                    <strong>{formatCompact(summary.resourceViews)}</strong>
                    <small>
                      {formatCompact(summary.impressions)} discoveries shown
                    </small>
                  </div>
                  <div>
                    <MetricHeading icon={ExternalLink}>
                      Source-site clicks
                    </MetricHeading>
                    <strong>
                      {wholeNumber.format(
                        outcomes.periods[selectedPeriod].totals.sources
                      )}
                    </strong>
                    <small>Clicks to authoritative source links</small>
                  </div>
                  <div>
                    <MetricHeading icon={Download}>
                      Download clicks
                    </MetricHeading>
                    <strong>
                      {wholeNumber.format(summary.downloadClicks)}
                    </strong>
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
              <span>
                {activeReport === 'platform'
                  ? 'Inspect HTTP traffic and service reliability, including browsers, crawlers, health probes, images, and analytics capture. Request counts are not searches or visitors.'
                  : activeReport === 'comparison'
                    ? 'Compare portal totals and daily trends. Use daily averages to account for different month lengths.'
                    : report.description}
              </span>
            </div>
            <div
              className={
                activeReport === 'members'
                  ? 'analytics-member-filter-panel'
                  : 'analytics-filter-passthrough'
              }
              role={activeReport === 'members' ? 'region' : undefined}
              aria-label={
                activeReport === 'members' ? 'Filter this report' : undefined
              }
            >
              {activeReport === 'members' && (
                <div className="analytics-filter-heading sr-only">
                  <h2>
                    <SlidersHorizontal size={18} aria-hidden />
                    Filter this report
                  </h2>
                </div>
              )}
              <div className="analytics-report-controls">
                <div
                  className={
                    activeReport === 'members'
                      ? 'analytics-period-control'
                      : undefined
                  }
                >
                  {activeReport === 'members' && (
                    <label htmlFor="report-month">Reporting period</label>
                  )}
                  <ReportingPeriodPicker
                    id="report-month"
                    value={selectedPeriod}
                    onChange={changeMonth}
                    comparison={activeReport === 'comparison'}
                  />
                </div>
                {activeReport === 'members' && (
                  <div className="analytics-grouping-controls">
                    <label htmlFor="member-grouping">Group records by</label>
                    <select
                      id="member-grouping"
                      aria-describedby="member-grouping-help"
                      value={memberGrouping}
                      onChange={(event) => {
                        const params = new URLSearchParams(searchParams);
                        params.set('grouping', event.target.value);
                        params.delete('institution');
                        params.delete('provider');
                        setSearchParams(params);
                      }}
                    >
                      <option value="code">BTAA contribution code</option>
                      <option value="provider">Provider facet</option>
                    </select>
                    <p id="member-grouping-help" className="sr-only">
                      Contribution codes include agency content gathered through
                      a member’s stream. Provider uses the named institution or
                      agency on the record.
                    </p>
                  </div>
                )}
                {activeReport === 'members' &&
                  memberGrouping === 'provider' && (
                    <div className="analytics-grouping-controls">
                      <label htmlFor="analytics-provider">Provider</label>
                      <select
                        id="analytics-provider"
                        value={
                          providerSnapshot?.groups.some(
                            (row) => row.id === searchParams.get('provider')
                          )
                            ? searchParams.get('provider')!
                            : 'all'
                        }
                        onChange={(event) => {
                          const params = new URLSearchParams(searchParams);
                          if (event.target.value === 'all')
                            params.delete('provider');
                          else params.set('provider', event.target.value);
                          setSearchParams(params);
                        }}
                      >
                        <option value="all">All providers</option>
                        {[...(providerSnapshot?.groups ?? [])]
                          .sort((a, b) =>
                            (a.provider ?? 'Missing provider').localeCompare(
                              b.provider ?? 'Missing provider'
                            )
                          )
                          .map((row) => (
                            <option key={row.id} value={row.id}>
                              {row.provider ?? 'Missing provider'}
                            </option>
                          ))}
                      </select>
                    </div>
                  )}
                {activeReport === 'members' && memberGrouping === 'code' && (
                  <div className="analytics-institution-control">
                    <span>Institution</span>
                    <button
                      type="button"
                      aria-expanded={institutionPickerOpen}
                      aria-controls="institution-picker"
                      onClick={() =>
                        setInstitutionPickerOpen(!institutionPickerOpen)
                      }
                    >
                      {memberSelectorEntries.find(
                        (member) => member.code === selectedMemberCode
                      )?.shortName ?? 'All BTAA'}{' '}
                      <span>
                        {institutionPickerOpen ? 'Close' : 'Change institution'}
                      </span>
                    </button>
                  </div>
                )}
              </div>
              {activeReport === 'members' && memberGrouping === 'code' && (
                <section
                  id="institution-picker"
                  hidden={!institutionPickerOpen}
                  className="analytics-header-institutions"
                  aria-label="Institution filter"
                >
                  <div className="analytics-member-picker-heading">
                    <h2>Institution</h2>
                    <button
                      type="button"
                      className={`analytics-campus-filter analytics-all-members-button${selectedMemberCode === 'all' ? ' analytics-campus-filter--active' : ''}`}
                      aria-pressed={selectedMemberCode === 'all'}
                      onClick={() => {
                        setSelectedMemberCode('all');
                        setInstitutionPickerOpen(false);
                      }}
                    >
                      <span className="analytics-campus-filter-mark analytics-campus-filter-mark--btaa">
                        <img src="/btaa-logo.png" alt="" />
                      </span>
                      <span>All BTAA</span>
                    </button>
                  </div>

                  <div className="analytics-campus-selector">
                    <fieldset>
                      <legend className="sr-only">
                        Select a BTAA member report
                      </legend>
                      <div className="analytics-campus-filter-grid">
                        {memberSelectorEntries.map((member) => (
                          <button
                            key={member.code}
                            type="button"
                            className={`analytics-campus-filter${selectedMemberCode === member.code ? ' analytics-campus-filter--active' : ''}`}
                            aria-label={`Show ${member.name} ${reportMonth} report`}
                            aria-pressed={selectedMemberCode === member.code}
                            title={member.name}
                            onClick={() => {
                              setSelectedMemberCode(member.code);
                              setInstitutionPickerOpen(false);
                            }}
                          >
                            <span className="analytics-campus-filter-mark">
                              <img src={member.iconSrc} alt="" loading="lazy" />
                            </span>
                            <span>{member.shortName}</span>
                          </button>
                        ))}
                      </div>
                    </fieldset>
                  </div>
                </section>
              )}
            </div>
          </div>
        )}

        <ReportContentLayout report={report.label}>
          <div className="analytics-shell analytics-content">
            {activeReport === 'overview' && (
              <ReportFindings
                findings={buildFindings({
                  period: selectedPeriod,
                  summary,
                  previous: previousSummary,
                  members: memberPerformance,
                  previousMembers,
                  leader: isAllTime
                    ? allTimeData.resources[0]
                    : topResources[0],
                })}
                periodLabel={periodRange}
                cumulative={isAllTime}
              />
            )}
            {activeReport === 'members' &&
              memberGrouping === 'code' &&
              !unavailableMember &&
              archive && (
                <div className="analytics-brief-invitation">
                  <div>
                    <p className="analytics-eyebrow">
                      Bring the story to your next meeting
                    </p>
                    <h2>
                      {selectedMember
                        ? `${selectedMember.shortName} at a glance`
                        : 'Member contributions at a glance'}
                    </h2>
                    <p>
                      A printable brief with activity, leading resources and
                      reporting context.
                    </p>
                  </div>
                  <Link to={`/analytics/members?${briefParams}`}>
                    Open {selectedMember ? 'campus' : 'member'} brief{' '}
                    <ExternalLink size={17} aria-hidden="true" />
                  </Link>
                </div>
              )}
            {activeReport === 'comparison' && <MonthlyComparison />}
            {activeReport === 'clients' && (
              <ClientUsageReport month={selectedPeriod} />
            )}
            {activeReport === 'content' && (
              <PopularContentReport
                title={`${reportMonth}’s top resources and collections`}
                reportMonth={reportMonth}
                reportPeriod={snapshotMonth}
                topResources={topResources}
                topCollections={topCollections}
                collectionNote={`The top ${topCollections.length} collections ranked by views of their member resources in ${reportMonth}. Resources belonging to multiple collections contribute views to each; resources without recorded collection membership are excluded.`}
                topDownloadedResources={topDownloadedResources}
                downloadClicks={contentSummary.downloadClicks}
                downloadNote={`The top ${topDownloadedResources.length} account for ${topDownloadClicks} of ${contentSummary.downloadClicks} clicks (${((topDownloadClicks / contentSummary.downloadClicks) * 100).toFixed(1)}%), across ${downloadResourceCount} resources with download clicks.`}
              />
            )}

            {activeReport === 'content' && (
              <OutlinkedResources period={snapshotMonth} />
            )}

            {activeReport === 'members' && memberGrouping === 'provider' && (
              <ProviderReport
                key={selectedPeriod}
                month={isAllTime ? memberRange : snapshotMonth}
                snapshot={
                  isAllTime
                    ? allTimeProviderSnapshot
                    : hasMonthlySnapshot
                      ? selectedSnapshot.provider
                      : undefined
                }
              />
            )}

            {activeReport === 'members' && memberGrouping === 'code' && (
              <section
                id="members"
                className="analytics-section"
                data-nav-exclude
              >
                {unavailableMember ? (
                  <section
                    className="analytics-panel analytics-member-unavailable"
                    aria-label={`${unavailableMember.name} report`}
                  >
                    <img src={unavailableMember.iconSrc} alt="" />
                    <h3>{unavailableMember.name}</h3>
                    <p>Analytics data unavailable for this period.</p>
                    <p>
                      The saved report does not include a contribution stream
                      for this institution. This does not mean it had zero
                      activity. Alliance totals include only the{' '}
                      {memberPerformance.length} recorded member streams.
                    </p>
                  </section>
                ) : (
                  <>
                    <div className="analytics-member-kpi-grid">
                      <article>
                        <MetricHeading icon={Layers3}>
                          Catalog footprint
                        </MetricHeading>
                        <strong>
                          {wholeNumber.format(selectedCatalogRecords)}
                        </strong>
                        <p>published catalog inventory as of {inventoryDate}</p>
                      </article>
                      <article>
                        <MetricHeading icon={Activity}>
                          {reportMonth} reach
                        </MetricHeading>
                        <strong>
                          {wholeNumber.format(selectedActiveResources)}
                        </strong>
                        <p>
                          {activeResourceRate.toFixed(1)}% of the catalog
                          appeared in a search or received an action
                        </p>
                      </article>
                      <article>
                        <MetricHeading icon={Eye}>
                          Resource attention
                        </MetricHeading>
                        <strong>
                          {wholeNumber.format(selectedResourceViews)}
                        </strong>
                        <p>
                          {selectedMember
                            ? `${wholeNumber.format(selectedImpressions)} search impressions`
                            : `${memberViewShare.toFixed(1)}% of portal views · ${memberImpressionShare.toFixed(1)}% of search impressions`}
                        </p>
                      </article>
                      <article>
                        <MetricHeading icon={Download}>
                          Download intent
                        </MetricHeading>
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
                          <div
                            className="analytics-chart-key"
                            aria-hidden="true"
                          >
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
                              margin={{
                                top: 16,
                                right: 8,
                                left: -24,
                                bottom: 0,
                              }}
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
                              <CartesianGrid {...chartTheme.grid} />
                              <XAxis
                                dataKey="day"
                                axisLine={false}
                                tickLine={false}
                                tick={chartTheme.tick}
                                interval={isAllTime ? 9 : 4}
                              />
                              <YAxis
                                axisLine={false}
                                tickLine={false}
                                tick={chartTheme.tick}
                                allowDecimals={false}
                              />
                              <Tooltip
                                cursor={chartTheme.cursor}
                                contentStyle={chartTheme.tooltip}
                                labelStyle={chartTheme.tooltipLabel}
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
                          <span>
                            {selectedMember?.shortName ?? 'All members'}
                          </span>
                          <strong>
                            Peak: {wholeNumber.format(peakMemberDay.views)}{' '}
                            views · {peakMemberDay.day}
                          </strong>
                        </figcaption>
                      </figure>
                    </div>

                    {!selectedMember && (
                      <MemberPerformanceReport members={membersByViews} />
                    )}

                    <div className="analytics-member-leading-content">
                      <MemberContentList
                        title={
                          selectedMember
                            ? `Most viewed - ${selectedMember.name}`
                            : 'Most viewed'
                        }
                        items={selectedTopContent.viewed}
                        metric="views"
                        emptyMessage="No resource views were recorded."
                      />
                      <MemberContentList
                        title={
                          selectedMember
                            ? `Most downloaded - ${selectedMember.name}`
                            : 'Most downloaded'
                        }
                        items={selectedTopContent.downloaded}
                        metric="downloads"
                        emptyMessage={`No direct download-link clicks were recorded; ${wholeNumber.format(selectedSourceClicks)} source-site clicks were still captured.`}
                      />
                    </div>

                    {!selectedMember && (
                      <div className="analytics-member-standouts">
                        <article className="analytics-panel">
                          <div>
                            <Eye className="h-5 w-5" aria-hidden />
                            <span>Attention leader</span>
                          </div>
                          <strong>
                            {wholeNumber.format(viewLeader.resourceViews)}
                          </strong>
                          <p>
                            {viewLeader.shortName} resource views and{' '}
                            {wholeNumber.format(viewLeader.sourceClicks)}{' '}
                            source-site clicks—the month’s leading member by
                            resource views.
                          </p>
                        </article>
                        <article className="analytics-panel">
                          <div>
                            <Download className="h-5 w-5" aria-hidden />
                            <span>Download leader</span>
                          </div>
                          <strong>
                            {wholeNumber.format(downloadLeader.downloadClicks)}
                          </strong>
                          <p>
                            {downloadLeader.shortName} download clicks, the most
                            among member contributions.
                          </p>
                        </article>
                        <article className="analytics-panel">
                          <div>
                            <Layers3 className="h-5 w-5" aria-hidden />
                            <span>Broadest {reportMonth} reach</span>
                          </div>
                          <strong>
                            {wholeNumber.format(reachLeader.activeResources)}
                          </strong>
                          <p>
                            {reachLeader.shortName} records appeared in a search
                            or received a tracked action.
                          </p>
                        </article>
                      </div>
                    )}

                    <section
                      className="analytics-panel analytics-member-scope"
                      aria-label="Outside the university code groups"
                      data-nav-label="Outside university groups"
                    >
                      <ReportPanelHeader
                        title="Outside university groups"
                        icon={Layers3}
                      />
                      <div className="analytics-member-scope-body">
                        <p className="analytics-member-scope-intro">
                          Portal activity beyond the 17 member contribution
                          streams included in this report.
                        </p>
                        <dl className="analytics-member-scope-stats">
                          <div>
                            <dt>
                              <Eye size={18} aria-hidden />
                              Resource views
                            </dt>
                            <dd>
                              {wholeNumber.format(
                                summary.resourceViews -
                                  memberSummary.resourceViews
                              )}
                            </dd>
                          </div>
                          <div>
                            <dt>
                              <Search size={18} aria-hidden />
                              Search impressions
                            </dt>
                            <dd>
                              {wholeNumber.format(
                                summary.impressions - memberSummary.impressions
                              )}
                            </dd>
                          </div>
                          <div>
                            <dt>
                              <Download size={18} aria-hidden />
                              Download clicks
                            </dt>
                            <dd>
                              {wholeNumber.format(
                                summary.downloadClicks -
                                  memberSummary.downloadClicks
                              )}
                            </dd>
                          </div>
                        </dl>
                        <p className="analytics-member-scope-note">
                          These figures can include unpublished, suppressed,
                          missing, or unmatched catalog records. They should not
                          be interpreted as an “Other institutions” total.
                        </p>
                        <details className="analytics-member-scope-details">
                          <summary>How these totals are calculated</summary>
                          <div>
                            <h4>Attribution and grouping</h4>
                            <p>
                              Only contribution code prefixes 01–17 are included
                              in the university totals. Other prefixes and
                              missing codes are excluded, even when their
                              records appear in portal totals. School
                              attribution follows the BTAA contribution code
                              rather than the provider label. Federal sources,
                              standalone items, and BTAA-curated content require
                              their actual contribution codes or Provider values
                              to be checked before assigning them to a group.
                            </p>
                            <h4>Reporting period and catalog</h4>
                            <p>
                              Activity period: {periodRange}. Published,
                              unsuppressed catalog inventory as of{' '}
                              {inventoryDate}. Inventory is a point-in-time
                              count, not an activity total or month-end count. “
                              {reportMonth} active” means a distinct record with
                              at least one search impression or tracked action
                              during the selected period. Downloads and
                              source-site visits are link clicks, not verified
                              completions.
                            </p>
                            {isAllTime && (
                              <>
                                <h4>Historical data</h4>
                                <p>
                                  All time uses preserved attribution captured
                                  September 11, 2026. Its explicit code mapping
                                  keeps four-digit federal codes such as 1000
                                  outside Wisconsin’s stream 10; the original
                                  monthly snapshots used a broader prefix match.
                                  July resource-level impressions were
                                  unavailable when this archive was built.
                                  Preserved aggregates retain available evidence
                                  but cannot recover missing historical detail.
                                  Inventory and active records are counted
                                  across the full period, not added from monthly
                                  totals.
                                </p>
                              </>
                            )}
                            <h4>Related reporting</h4>
                            <p>
                              The{' '}
                              <a href="https://gin.btaa.org/harvest-operations/latest/institutions/">
                                harvest-operations institution report
                              </a>{' '}
                              groups harvest records, including OpenGeoMetadata,
                              licensed databases, BTAA-GIN curated datasets, and
                              Other. Its grouping differs from this
                              catalog-level contribution-code report.
                            </p>
                          </div>
                        </details>
                      </div>
                    </section>
                  </>
                )}
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
                        <h3>Daily discovery</h3>
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
                          <CartesianGrid {...chartTheme.grid} />
                          <XAxis
                            dataKey="day"
                            axisLine={false}
                            tickLine={false}
                            tick={chartTheme.tick}
                            interval={isAllTime ? 9 : 4}
                          />
                          <YAxis
                            axisLine={false}
                            tickLine={false}
                            tick={chartTheme.tick}
                          />
                          <Tooltip
                            cursor={chartTheme.cursor}
                            contentStyle={chartTheme.tooltip}
                            labelStyle={chartTheme.tooltipLabel}
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
                        <span>
                          Tracked visits
                          {visitsAreEstimated(selectedPeriod)
                            ? ' (estimated)'
                            : ''}
                        </span>
                      </div>
                      <strong>
                        {visitsAreEstimated(selectedPeriod) ? '≈ ' : ''}
                        {wholeNumber.format(
                          outcomes.periods[selectedPeriod].audience
                            .trackedVisits
                        )}
                      </strong>
                      <p>
                        {visitsAreEstimated(selectedPeriod)
                          ? 'Estimated distinct'
                          : 'Distinct'}{' '}
                        browser-tab visits recorded in searches or events; not
                        unique people
                      </p>
                    </div>
                  </aside>
                </div>
                <div
                  data-nav-label="Daily audience values"
                  className="analytics-panel analytics-overview-details"
                >
                  <ReportPanelHeader
                    title="Audience and discovery"
                    icon={Users}
                    level={2}
                  />
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
              <section
                id="discovery"
                className="analytics-section"
                data-nav-exclude
              >
                <div className="analytics-search-chart-grid">
                  <SearchDailyReport
                    period={report.period}
                    days={allTimeData.daily.filter(
                      (row) => isAllTime || row.day.startsWith(selectedPeriod)
                    )}
                  />
                  <SearchCategoryChart categories={queryCategoryCounts} />
                </div>

                <SectionHeading
                  title="Top 50 searches"
                  description={`The most frequently recorded queries during ${periodRange}. ${wholeNumber.format(topSearchSnapshot.withQuery)} searches included query text, across ${wholeNumber.format(topSearchSnapshot.distinctQueries)} distinct queries.`}
                />
                <article className="analytics-panel analytics-top-searches analytics-panel--ranking">
                  <div className="analytics-panel-header">
                    <div>
                      <Search className="h-5 w-5" aria-hidden />
                      <h3>Most frequent queries</h3>
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
                      className="analytics-ranking-list"
                      aria-label="Top 50 searches"
                    >
                      {visibleSearchTerms.map((query) => (
                        <RankingRow
                          key={query.term}
                          rank={query.rank}
                          title={query.term}
                          href={`/search?q=${encodeURIComponent(query.term)}`}
                          description={query.category}
                          value={query.count}
                          label="searches"
                          maximum={Math.max(
                            1,
                            ...topSearchTerms.map((row) => row.count)
                          )}
                        />
                      ))}
                    </div>
                    <p className="analytics-card-footnote">
                      {queryCategoryMethod} Counts include successful and
                      zero-result searches, grouped by trimmed query text with
                      case preserved. Filters and views are combined; links
                      repeat the query text only. Empty queries are excluded.
                      Exported{' '}
                      {new Date(
                        hasMonthlySnapshot || isAllTime
                          ? selectedSnapshot.provider.exportedAt.slice(0, 10)
                          : topSearches.exportedAt
                      ).toLocaleDateString('en-US', {
                        timeZone: 'UTC',
                        month: 'long',
                        day: 'numeric',
                        year: 'numeric',
                      })}
                      .
                    </p>
                  </div>
                </article>
                <SectionHeading
                  title="Views, filters, and zero results"
                  description={`How searches were viewed and refined during the selected period.`}
                />

                <div className="analytics-insights-grid">
                  <article className="analytics-panel analytics-donut-card">
                    <div className="analytics-panel-header">
                      <div>
                        <Map className="h-5 w-5" aria-hidden />
                        <h3>Search view mix</h3>
                      </div>
                    </div>
                    <div className="analytics-donut-layout">
                      <div
                        className="analytics-donut"
                        role="img"
                        aria-label={discoveryViews
                          .map(
                            (row) =>
                              `${row.label} view ${Math.round(row.percent)} percent`
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
                            <strong>{Math.round(view.percent)}%</strong>
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
                        <h3>Resource class demand</h3>
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
                        ? allTimeData.zeroWithQuery
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
                <div className="analytics-platform-grid">
                  <article
                    className="analytics-panel analytics-reliability-card"
                    data-nav-label="Reliability summary"
                  >
                    <h3>Reliability summary</h3>
                    <div className="analytics-reliability-top">
                      <div>
                        <MetricHeading icon={CheckCircle2}>
                          Requests without a server error
                        </MetricHeading>
                        <strong>{requestReliability.toFixed(3)}%</strong>
                        <p>
                          Share of recorded requests without an HTTP 5xx
                          response
                        </p>
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
                        <MetricHeading icon={CircleGauge}>
                          Median response
                        </MetricHeading>
                        <strong>
                          {isAllTime
                            ? 'Not available'
                            : `${summary.medianResponseMs} ms`}
                        </strong>
                        <p>Half of requests responded within this time</p>
                      </div>
                      <div>
                        <MetricHeading icon={CircleGauge}>
                          95th percentile
                        </MetricHeading>
                        <strong>
                          {isAllTime
                            ? 'Not available'
                            : `${summary.p95ResponseMs} ms`}
                        </strong>
                        <p>95% of requests responded within this time</p>
                      </div>
                      <div>
                        <MetricHeading icon={Activity}>
                          Server errors
                        </MetricHeading>
                        <strong>{summary.serverErrors}</strong>
                        <p>Requests returning a server error</p>
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
                        <h3>Request mix</h3>
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
                        <h3>Peak-day API traffic</h3>
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
                      {(
                        reliabilityEndpoints.periods as Record<
                          string,
                          { label: string; requests: number; errors: number }[]
                        >
                      )[selectedPeriod].map((row) => (
                        <tr key={row.label}>
                          <th scope="row">{row.label}</th>
                          <td>{wholeNumber.format(row.requests)}</td>
                          <td>{wholeNumber.format(row.errors)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </AnalyticsTable>
                  <p className="analytics-comparison-note">
                    {reliabilityEndpoints.method}
                  </p>
                </section>
              </section>
            )}

            <ReportSources
              report={activeReport}
              month={reportMonth}
              period={periodRange}
              snapshotPeriod={selectedPeriod}
            />

            {activeReport === 'content' && (
              <p className="analytics-comparison-note">
                {periodRange} (UTC) · Exported {contentSummary.exportedAt}.
                Rankings use recorded interactions and catalog metadata at
                export. Momentum compares each ranking’s metric with the
                previous calendar month.
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
                      : `7 analytics tables · 1 catalog snapshot · ${monthDays} complete days`}
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

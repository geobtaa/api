import {
  AUGUST_2026_SUMMARY,
  augustDailyActivity,
  augustMemberPerformance,
} from '../../data/analytics/august2026';
import {
  augustMembers,
  augustMemberSummary,
  augustMemberDailySeries,
  augustMemberTopContent,
  augustDiscoveryViews,
  augustRequestMix,
  augustPeakApiTrafficBreakdown,
  augustZeroResultBreakdown,
} from '../../data/analytics/reportsAugust2026';
import {
  augustTopResources,
  augustTopCollections,
  augustTopDownloadedResources,
  augustDownloadSummary,
} from '../../data/analytics/popularAugust2026';
import { selectedAnalyticsReport } from '../../config/analyticsReports';

describe('August analytics reconciliation', () => {
  it('reconciles member daily series, totals, and comparison figures', () => {
    expect(augustMembers).toHaveLength(17);
    for (const key of [
      'catalogRecords',
      'activeResources',
      'impressions',
      'resourceViews',
      'downloadClicks',
      'sourceClicks',
    ] as const) {
      expect(augustMembers.reduce((sum, row) => sum + row[key], 0)).toBe(
        augustMemberSummary[key]
      );
    }
    for (const member of augustMembers) {
      const series = augustMemberDailySeries[member.code];
      expect(series.views).toHaveLength(31);
      expect(series.downloads).toHaveLength(31);
      expect(series.views.reduce((sum, n) => sum + n, 0)).toBe(
        member.resourceViews
      );
      expect(series.downloads.reduce((sum, n) => sum + n, 0)).toBe(
        member.downloadClicks
      );
      expect(member).toMatchObject(
        augustMemberPerformance.find((row) => row.code === member.code)!
      );
      expect(augustMemberTopContent[member.code].viewed[0].id).toBe(
        member.topResource.id
      );
    }
  });

  it('reconciles discovery and API category totals', () => {
    expect(augustDiscoveryViews.reduce((sum, row) => sum + row.count, 0)).toBe(
      AUGUST_2026_SUMMARY.searches
    );
    expect(augustRequestMix.reduce((sum, row) => sum + row.count, 0)).toBe(
      AUGUST_2026_SUMMARY.requests
    );
    expect(
      augustPeakApiTrafficBreakdown.reduce((sum, row) => sum + row.count, 0)
    ).toBe(Math.max(...augustDailyActivity.map((row) => row.requests)));
    expect(
      augustZeroResultBreakdown.with_query +
        augustZeroResultBreakdown.without_query
    ).toBe(AUGUST_2026_SUMMARY.zeroResultSearches);
  });

  it('validates popular content totals and descending ranks', () => {
    expect(augustDownloadSummary.clicks).toBe(
      AUGUST_2026_SUMMARY.downloadClicks
    );
    expect(
      augustTopDownloadedResources.reduce((sum, row) => sum + row.clicks, 0)
    ).toBe(55);
    for (const row of augustTopResources)
      expect(row.firstHalfEvents + row.secondHalfEvents).toBe(
        row.views + row.actions
      );
    for (const counts of [
      augustTopResources.map((row) => row.views),
      augustTopCollections.map((row) => row.searches),
      augustTopDownloadedResources.map((row) => row.clicks),
    ]) {
      expect(counts).toHaveLength(10);
      expect(counts).toEqual([...counts].sort((a, b) => b - a));
    }
  });

  it('resolves report periods for server metadata and client navigation', () => {
    for (const report of [
      'overview',
      'content',
      'members',
      'activity',
      'discovery',
      'platform',
    ]) {
      expect(
        selectedAnalyticsReport(new URLSearchParams({ report })).period
      ).toBe('August 2026');
      expect(
        selectedAnalyticsReport(
          new URLSearchParams({ report, month: '2026-07' })
        ).period
      ).toBe('July 2026');
      expect(
        selectedAnalyticsReport(
          new URLSearchParams({ report, month: 'invalid' })
        ).period
      ).toBe('August 2026');
    }
    expect(
      selectedAnalyticsReport(
        new URLSearchParams({ report: 'comparison', month: '2026-07' })
      ).period
    ).toBe('July–August 2026');
  });
});

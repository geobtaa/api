import { describe, expect, it } from 'vitest';
import { analyticsSnapshot } from '../../../app/lib/analytics-data.server';
import {
  buildAnalyticsSummary,
  summaryWindow,
  resourceAccessPatterns,
  groupAccessMonths,
} from '../../utils/analyticsSummary';

describe('access chart grouping', () => {
  function months(count: number, startMonth = 0) {
    return Array.from({ length: count }, (_, index) => {
      const period = new Date(Date.UTC(2026, startMonth + index, 1))
        .toISOString()
        .slice(0, 7);
      return { period, label: period, sources: 1, downloads: 2 };
    });
  }
  it.each([1, 3, 12])('keeps %i months as monthly bars', (count) => {
    const chart = groupAccessMonths(months(count));
    expect(chart.unit).toBe('month');
    expect(chart.rows).toHaveLength(count);
    expect(chart.rows.every((row) => !row.label.includes('partial'))).toBe(
      true
    );
  });
  it('uses calendar quarters and labels a partial quarter', () => {
    const chart = groupAccessMonths(months(13));
    expect(chart.unit).toBe('quarter');
    expect(chart.rows).toHaveLength(5);
    expect(chart.rows[0]).toMatchObject({
      label: 'Q1 2026',
      sources: 3,
      downloads: 6,
    });
    expect(chart.rows.at(-1)).toMatchObject({
      label: 'Q1 2027 (partial)',
      sources: 1,
      downloads: 2,
    });
  });
  it('keeps 36 aligned months in 12 quarters and groups longer histories by years', () => {
    expect(groupAccessMonths(months(36))).toMatchObject({
      unit: 'quarter',
      description: 'Quarterly counts',
    });
    expect(groupAccessMonths(months(36)).rows).toHaveLength(12);
    expect(groupAccessMonths(months(180)).description).toBe(
      'Counts by 2-year period'
    );
  });
  it.each([13, 36, 37, 144, 180, 600])(
    'preserves all %i months within 12 bars',
    (count) => {
      const chart = groupAccessMonths(months(count, 7));
      expect(chart.rows.length).toBeLessThanOrEqual(12);
      expect(chart.rows.reduce((sum, row) => sum + row.sources!, 0)).toBe(
        count
      );
      expect(chart.rows.reduce((sum, row) => sum + row.downloads!, 0)).toBe(
        count * 2
      );
    }
  );
  it('uses yearly bars after 36 months, including partial years', () => {
    const chart = groupAccessMonths(months(37, 6));
    expect(chart.unit).toBe('year');
    expect(chart.description).toBe('Yearly counts');
    expect(chart.rows[0]).toMatchObject({
      label: '2026 (partial)',
      sources: 6,
    });
    expect(chart.rows[1]).toMatchObject({ label: '2027', sources: 12 });
    expect(chart.rows.at(-1)).toMatchObject({
      label: '2029 (partial)',
      sources: 7,
    });
  });
  it('preserves missing counts independently for each metric', () => {
    const rows: Parameters<typeof groupAccessMonths>[0] = months(13);
    rows[0].sources = null;
    const chart = groupAccessMonths(rows);
    expect(chart.rows[0]).toMatchObject({ sources: null, downloads: 6 });
    expect(chart.rows[1].sources).toBe(3);
  });
  it('handles an empty window', () => {
    expect(groupAccessMonths([]).rows).toEqual([]);
  });
});

describe('summary reporting windows', () => {
  it('ranks access-click ratios without treating them as bounded conversion rates', () => {
    const rows = [
      {
        id: 'zero-views',
        title: 'No views',
        views: 0,
        sources: 3,
        downloads: 0,
      },
      {
        id: 'small',
        title: 'Too few views',
        views: 19,
        sources: 20,
        downloads: 0,
      },
      {
        id: 'no-clicks',
        title: 'No clicks',
        views: 100,
        sources: 0,
        downloads: 0,
      },
      {
        id: 'many-clicks',
        title: 'Repeated clicks',
        views: 20,
        sources: 10,
        downloads: 20,
      },
      {
        id: 'some-clicks',
        title: 'Some clicks',
        views: 80,
        sources: 2,
        downloads: 2,
      },
      {
        id: 'few-clicks',
        title: 'Few clicks',
        views: 200,
        sources: 1,
        downloads: 1,
      },
    ];
    const result = resourceAccessPatterns(rows);
    expect(result.fewerClicks.map((row) => row.id)).toEqual([
      'no-clicks',
      'few-clicks',
      'some-clicks',
      'many-clicks',
    ]);
    expect(result.moreClicks.map((row) => row.id)).toEqual([
      'many-clicks',
      'some-clicks',
      'few-clicks',
    ]);
    expect(result.moreClicks[0]).toMatchObject({
      clicks: 30,
      clicksPer100Views: 150,
    });
  });
  it('uses only resource counts for the exact selected window', () => {
    const sample =
      buildAnalyticsSummary(analyticsSnapshot).recordAccessPatterns;
    expect(sample?.fewerClicks).toHaveLength(5);
    expect(sample?.moreClicks).toHaveLength(5);
    expect(sample?.moreClicks[0]).toMatchObject({
      title: 'Rivers, Nepal, 2013',
      views: 57,
      clicks: 26,
    });
    expect(
      buildAnalyticsSummary(analyticsSnapshot, '2026-09', 'month')
        .recordAccessPatterns
    ).toBeNull();
  });
  it('compares catalog capture dates independently of activity months', () => {
    const catalog = buildAnalyticsSummary(analyticsSnapshot).catalog;
    expect(catalog).toMatchObject({
      total: 148196,
      date: '2026-10-09',
      previousTotal: 147665,
      previousDate: '2026-09-10',
      change: 531,
    });
    expect(catalog?.percentChange).toBeCloseTo(0.3596, 4);
    expect(
      buildAnalyticsSummary(analyticsSnapshot, '2026-08', 'month').catalog
    ).toMatchObject({
      total: 147665,
      date: '2026-09-10',
      previousDate: null,
      change: null,
    });
  });
  it('allows decreases and does not divide by a zero baseline', () => {
    const snapshot = structuredClone(analyticsSnapshot);
    snapshot['monthlySnapshots.json'].default[
      '2026-09'
    ].provider.totals.catalogRecords = 147000;
    expect(buildAnalyticsSummary(snapshot).catalog?.change).toBe(-665);
    for (const period of ['2026-07', '2026-08'])
      snapshot.providers2026.providerSnapshots[period].totals.catalogRecords =
        0;
    expect(buildAnalyticsSummary(snapshot).catalog).toMatchObject({
      change: 147000,
      percentChange: null,
    });
  });
  it('uses monthly aggregates for selected-month search and resource rankings', () => {
    const data = buildAnalyticsSummary(analyticsSnapshot, '2026-07', 'month');
    expect(data.window.months).toEqual(['2026-07']);
    expect(data.daily).toHaveLength(31);
    expect(data.queries).toEqual(
      analyticsSnapshot['topSearches2026.json'].default.months['2026-07']
        .queries
    );
    expect(data.zeroQueries).toEqual(
      analyticsSnapshot.searches2026.searchSnapshots['2026-07'].zeroQueries
    );
    expect(data.outlinks).toEqual(
      analyticsSnapshot.outcomes.outcomes.periods['2026-07'].outlinks
    );
    expect(data.searches).toBe(
      data.daily.reduce((sum, row) => sum + row.searches, 0)
    );
    expect(data.sources).toBe(1129);
    expect(data.views).toBe(12200);
  });
  it('uses all published days and the complete rankings for all time', () => {
    const data = buildAnalyticsSummary(analyticsSnapshot, '2026-09', 'all');
    expect(data.daily).toHaveLength(92);
    expect(data.searches).toBe(19538);
    expect(data.queries).toEqual(
      analyticsSnapshot['allTimeCurrent.json'].default.queries
    );
  });
  it('uses the complete three-month window for discovery chart totals', () => {
    const data = buildAnalyticsSummary(analyticsSnapshot);
    expect(data.window).toEqual({
      start: '2026-07-01',
      end: '2026-09-30',
      endExclusive: '2026-10-01',
      months: ['2026-07', '2026-08', '2026-09'],
    });
    expect(data.daily).toHaveLength(92);
    expect(data.searches).toBe(19538);
    expect(data.visits).toBe(27892);
    expect(data.views).toBe(
      Object.entries(analyticsSnapshot.outcomes.outcomes.periods)
        .filter(([period]) => /^2026-(07|08|09)$/.test(period))
        .reduce((total, [, period]) => total + period.totals.views, 0)
    );
    expect(data.sources).toBe(2869);
    expect(data.downloads).toBe(2621);
    expect(data.estimatedVisits).toBe(true);
  });
  it('handles year boundaries and leap years in UTC', () => {
    expect(summaryWindow('2027-01').months).toEqual([
      '2026-11',
      '2026-12',
      '2027-01',
    ]);
    expect(summaryWindow('2024-02')).toMatchObject({
      start: '2023-12-01',
      endExclusive: '2024-03-01',
    });
  });
  it('keeps missing measurements unavailable instead of returning a partial total', () => {
    const snapshot = structuredClone(analyticsSnapshot);
    delete snapshot.outcomes.outcomes.periods['2026-08'];
    const data = buildAnalyticsSummary(snapshot);
    expect(data.searches).toBeNull();
    expect(data.views).toBeNull();
    expect(data.sources).toBeNull();
    expect(data.downloads).toBeNull();
    expect(data.dailyComplete).toBe(false);
  });
  it('keeps chart totals within the selected calendar window', () => {
    const snapshot = structuredClone(analyticsSnapshot);
    const template = snapshot.outcomes.outcomes.periods['2026-07'];
    snapshot.outcomes.outcomes.periods = {};
    for (let index = 0; index < 90; index++) {
      const day = new Date(Date.UTC(2027, 0, 31 + index))
        .toISOString()
        .slice(0, 10);
      const period = day.slice(0, 7);
      snapshot.outcomes.outcomes.periods[period] ??= { ...template, daily: [] };
      snapshot.outcomes.outcomes.periods[period].daily.push({
        ...template.daily[0],
        day,
        searches: 1,
      });
    }
    const data = buildAnalyticsSummary(snapshot, '2027-04');
    expect(data.daily).toHaveLength(89);
    expect(data.searches).toBe(89);
  });
  it('does not sum monthly top-N rankings or reuse an aggregate with different dates', () => {
    const snapshot = structuredClone(analyticsSnapshot);
    snapshot['allTimeCurrent.json'].default.start = '2026-06-01';
    snapshot.outcomes.outcomes.periods.all.start = '2026-06-01';
    const data = buildAnalyticsSummary(snapshot);
    expect(data.queries).toBeNull();
    expect(data.zeroQueries).toBeNull();
    expect(data.outlinks).toBeNull();
    expect(data.topDownloads).toBeNull();
    expect(data.visits).toBeNull();
    expect(data.searches).not.toBeNull();
  });
});

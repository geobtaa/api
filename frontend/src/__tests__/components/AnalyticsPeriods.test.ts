import { describe, expect, it } from 'vitest';
import {
  monthDays,
  monthLabel,
  publishedMonths,
  latestMonth,
  selectedSnapshotPeriod,
  selectedSummaryPeriod,
  summaryHasThreeMonths,
} from '../../config/analyticsPeriods';
import { monthlySnapshots } from '../../data/analytics/september2026';
import allTime from '../../data/analytics/allTimeCurrent.json';

describe('monthly publication contract', () => {
  it('uses the latest month when all time exceeds the three-month window', () => {
    expect(summaryHasThreeMonths).toBe(false);
    expect(selectedSummaryPeriod(null)).toBe(latestMonth);
    expect(selectedSummaryPeriod('3months')).toBe(latestMonth);
    expect(selectedSummaryPeriod('2026-08')).toBe('2026-08');
    expect(selectedSummaryPeriod('all')).toBe('all');
  });
  it.each([null, '', 'invalid', '2026-13', '2029-01', 'ay-2026'])(
    'uses the latest snapshot for unsupported input %s',
    (input) => {
      expect(selectedSnapshotPeriod(input)).toBe(latestMonth);
    }
  );
  it('preserves published and cumulative snapshot selections', () => {
    expect(selectedSnapshotPeriod('all')).toBe('all');
    for (const month of publishedMonths)
      expect(selectedSnapshotPeriod(month)).toBe(month);
  });
  it('matches the independently counted October source totals', () => {
    expect(monthlySnapshots['2026-10'].summary).toMatchObject({
      requests: 3208142,
      searches: 7973,
      events: 15191,
      resourceViews: 10577,
      downloadClicks: 551,
      impressions: 130889,
      uniqueEngagedVisits: 6390,
    });
    expect(allTime.daily).toHaveLength(123);
    expect(allTime.daily.reduce((sum, row) => sum + row.requests, 0)).toBe(
      4896112
    );
    expect(allTime.daily.reduce((sum, row) => sum + row.searches, 0)).toBe(
      27511
    );
  });
  it('handles year transitions and leap years', () => {
    expect(monthLabel('2027-01')).toBe('January 2027');
    expect(monthDays('2027-02')).toBe(28);
    expect(monthDays('2028-02')).toBe(29);
    expect(monthDays('2026-12')).toBe(31);
  });
  it('supplies every published month without hand-editing selectors', () => {
    expect(latestMonth).toBe(publishedMonths.at(-1));
    expect(allTime.publishedMonths).toEqual(publishedMonths);
    for (const month of publishedMonths.filter((m) => m >= '2026-09')) {
      const snapshot = monthlySnapshots[month];
      expect(snapshot, month).toBeDefined();
      expect(snapshot.summary.month).toBe(monthLabel(month));
      expect(snapshot.dailyActivity).toHaveLength(monthDays(month));
      for (const metric of ['requests', 'searches', 'events'] as const)
        expect(snapshot.dailyActivity.reduce((n, r) => n + r[metric], 0)).toBe(
          snapshot.summary[metric]
        );
    }
  });
});

import { describe, expect, it } from 'vitest';
import {
  monthDays,
  monthLabel,
  publishedMonths,
  latestMonth,
} from '../../config/analyticsPeriods';
import { monthlySnapshots } from '../../data/analytics/september2026';
import allTime from '../../data/analytics/allTimeCurrent.json';

describe('monthly publication contract', () => {
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

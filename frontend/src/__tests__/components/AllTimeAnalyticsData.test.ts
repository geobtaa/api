import { expect, it } from 'vitest';
import data from '../../data/analytics/allTime2026.json';
import { JULY_2026_SUMMARY as july } from '../../data/analytics/july2026';
import { AUGUST_2026_SUMMARY as august } from '../../data/analytics/august2026';

it('reconciles full-period daily counts to published months without losing dates', () => {
  expect(data.start).toBe('2026-07-01');
  expect(data.endExclusive).toBe('2026-09-01');
  expect(data.daily).toHaveLength(62);
  expect(new Set(data.daily.map((day) => day.day)).size).toBe(62);
  expect(data.daily[0].day).toBe('2026-07-01');
  expect(data.daily[61].day).toBe('2026-08-31');
  for (const key of ['requests', 'events', 'searches'] as const)
    expect(data.daily.reduce((n, day) => n + day[key], 0)).toBe(
      july[key] + august[key]
    );
  expect(data.queries).toHaveLength(50);
  expect(data.queries.find((q) => q.term === 'sanborn')?.count).toBe(49);
  expect(data.searchTotals.distinctQueries).toBe(2785);
});

it('reconciles Provider and contribution-code groups across the full period', () => {
  for (const key of [
    'catalogRecords',
    'activeResources',
    'resourceViews',
    'impressions',
    'downloadClicks',
    'sourceClicks',
  ] as const) {
    expect(data.providers.reduce((n, row) => n + row[key], 0)).toBe(
      data.codes.reduce((n, row) => n + row[key], 0)
    );
  }
  expect(data.providers.reduce((n, row) => n + row.catalogRecords, 0)).toBe(
    147665
  );
});

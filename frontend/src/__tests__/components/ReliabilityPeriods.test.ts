import { expect, it } from 'vitest';
import endpoints from '../../data/analytics/reliabilityEndpoints2026.json';
import allTime from '../../data/analytics/allTime2026.json';
it.each(['2026-07', '2026-08', 'all'] as const)(
  'reconciles endpoint requests and errors for %s',
  (period) => {
    const days = allTime.daily.filter(
      (row) => period === 'all' || row.day.startsWith(period)
    );
    expect(
      endpoints.periods[period].reduce((n, row) => n + row.requests, 0)
    ).toBe(days.reduce((n, row) => n + row.requests, 0));
    expect(
      endpoints.periods[period].reduce((n, row) => n + row.errors, 0)
    ).toBe(days.reduce((n, row) => n + row.errors, 0));
  }
);

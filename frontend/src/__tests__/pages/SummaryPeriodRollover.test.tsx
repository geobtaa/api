import { fireEvent, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { analyticsSnapshot } from '../../../app/lib/analytics-data.server';
import { AnalyticsDataContext } from '../../components/analytics/AnalyticsData';
import { SummaryAnalyticsPage } from '../../components/analytics/SummaryAnalyticsPage';
import {
  selectedSummaryPeriod,
  summaryHasThreeMonths,
} from '../../config/analyticsPeriods';
import { selectedAnalyticsReport } from '../../config/analyticsReports';
import { AnalyticsTestRouter } from '../utils/AnalyticsTestRouter';
import { renderAnalytics } from '../utils/renderAnalytics';

vi.mock(
  '../../../private-analytics-reports/manifest.json',
  async (original) => {
    const { default: manifest } =
      await original<
        typeof import('../../../private-analytics-reports/manifest.json')
      >();
    return {
      default: {
        ...manifest,
        latest: '2026-10',
        throughExclusive: '2026-11-01',
        periods: [
          ...manifest.periods.map((period) =>
            period.id === 'all'
              ? { ...period, endExclusive: '2026-11-01' }
              : period
          ),
          { id: '2026-10', start: '2026-10-01', endExclusive: '2026-11-01' },
        ],
      },
    };
  }
);
vi.mock(
  'recharts',
  async () => (await import('../utils/analyticsCharts')).analyticsCharts
);
vi.mock('../../components/layout/Footer', () => ({ Footer: () => <footer /> }));

function fourthMonthSnapshot() {
  const snapshot = structuredClone(analyticsSnapshot);
  const periods = snapshot.outcomes.outcomes.periods;
  const october = structuredClone(periods['2026-09']);
  october.start = '2026-10-01';
  october.endExclusive = '2026-11-01';
  october.audience.trackedVisits = 4321;
  october.daily = Array.from({ length: 31 }, (_, index) => ({
    ...october.daily[0],
    day: `2026-10-${String(index + 1).padStart(2, '0')}`,
  }));
  periods['2026-10'] = october;
  periods.all.endExclusive = '2026-11-01';
  snapshot['allTimeCurrent.json'].default.endExclusive = '2026-11-01';
  const month = structuredClone(
    snapshot['monthlySnapshots.json'].default['2026-09']
  );
  month.topSearches.queries = [{ term: 'October query', count: 101 }];
  month.searchSnapshot.zeroQueries = [
    { term: 'October no-result query', count: 7 },
  ];
  snapshot['monthlySnapshots.json'].default['2026-10'] = month;
  return snapshot;
}

describe('Summary after a fourth month is published', () => {
  it.each(['', '?month=3months'])(
    'selects a populated month for the default or old shortcut URL %s',
    (query) => {
      const params = new URLSearchParams(query);
      expect(summaryHasThreeMonths).toBe(false);
      expect(selectedSummaryPeriod(params.get('month'))).toBe('2026-10');
      expect(selectedAnalyticsReport(params, '/analytics/summary').period).toBe(
        'October 2026'
      );
      renderAnalytics(
        <AnalyticsDataContext.Provider value={fourthMonthSnapshot()}>
          <AnalyticsTestRouter initialEntries={[`/analytics/summary${query}`]}>
            <SummaryAnalyticsPage />
          </AnalyticsTestRouter>
        </AnalyticsDataContext.Provider>
      );
      const picker = screen.getByRole('combobox', { name: 'Reporting period' });
      expect(picker).toHaveValue('2026-10');
      expect(
        screen.queryByRole('option', { name: 'Past 3 months' })
      ).toBeNull();
      expect(screen.getByText('4,321')).toBeInTheDocument();
      expect(screen.queryByText(/Rankings unavailable/)).toBeNull();
      for (const [heading, term] of [
        ['Most common', 'October query'],
        ['No-result searches', 'October no-result query'],
      ]) {
        const card = screen
          .getByRole('heading', { name: heading })
          .closest('article')!;
        fireEvent.click(
          within(card).getByRole('button', { name: 'Show query terms' })
        );
        expect(within(card).getByText(term)).toBeVisible();
      }
      fireEvent.change(picker, { target: { value: 'all' } });
      expect(picker).toHaveValue('all');
      expect(screen.queryByText(/Rankings unavailable/)).toBeNull();
    }
  );
});

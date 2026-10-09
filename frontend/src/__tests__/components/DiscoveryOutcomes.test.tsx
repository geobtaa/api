import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { describe, expect, it } from 'vitest';
import {
  AccessSummary,
  OutlinkedResources,
} from '../../components/analytics/DiscoveryOutcomes';
import { FailedSearchContext } from '../../components/analytics/FailedSearchContext';
import {
  outcomes,
  replaySearch,
  searchContexts,
} from '../../data/analytics/outcomes';
import zero from '../../data/analytics/zeroResultQueries2026.json';
import all from '../../data/analytics/allTime2026.json';

describe('discovery outcomes', () => {
  it('reconciles access totals, daily history and independently ranked resources', () => {
    expect(outcomes.periods.all.totals.sources).toBe(1987);
    expect(outcomes.periods.all.totals.downloads).toBe(1745);
    for (const period of ['2026-07', '2026-08', 'all'] as const) {
      const report = outcomes.periods[period];
      for (const metric of ['sources', 'downloads', 'views'] as const)
        expect(report.daily.reduce((n, d) => n + d[metric], 0)).toBe(
          report.totals[metric]
        );
      expect(report.daily.reduce((n, d) => n + d.searches, 0)).toBe(
        report.searches
      );
      expect(report.outlinks).toHaveLength(50);
      expect(
        report.outlinks.every(
          (r, i) => i === 0 || report.outlinks[i - 1].clicks >= r.clicks
        )
      ).toBe(true);
      const terms =
        period === 'all' ? all.zeroQueries : zero.months[period].zeroQueries;
      for (const term of terms)
        expect(
          searchContexts(period, term.term).reduce((n, c) => n + c.count, 0)
        ).toBe(term.count);
      expect(report.clients).toEqual([
        {
          client: 'geoportal-web',
          channel: 'browser',
          records: report.audience.activityRecords,
        },
      ]);
    }
  });
  it('deduplicates full-period visits instead of summing monthly distinct counts', () => {
    expect(outcomes.periods.all.audience.trackedVisits).toBe(20735);
    expect(
      outcomes.periods['2026-07'].audience.trackedVisits +
        outcomes.periods['2026-08'].audience.trackedVisits
    ).toBe(20749);
    expect(outcomes.periods.all.audience.recordsWithoutToken).toBe(120);
    expect(outcomes.periods.all.totals.pageViews).toBe(0);
  });
  it('renders both monthly bars and a sortable independent outlink ranking', () => {
    render(
      <MemoryRouter>
        <AccessSummary period="all" />
        <OutlinkedResources period="all" />
      </MemoryRouter>
    );
    expect(screen.getByText('1,987')).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: 'July 2026' })
    ).toBeInTheDocument();
    const table = screen.getByRole('table');
    const highest = outcomes.periods.all.outlinks[0];
    expect(within(table).getAllByRole('row')[1]).toHaveTextContent(
      highest.title
    );
    fireEvent.click(
      within(table).getByRole('button', { name: 'Source-site clicks' })
    );
    expect(within(table).getAllByRole('row')[1]).not.toHaveTextContent(
      highest.title
    );
  });
  it('shows recorded redlining exclusions and replays all their values safely', async () => {
    render(
      <MemoryRouter>
        <FailedSearchContext period="2026-08" term="redlining" />
      </MemoryRouter>
    );
    const details = screen
      .getByText('3 recorded combinations')
      .closest('details')!;
    await act(async () => {
      details.open = true;
      fireEvent(details, new Event('toggle'));
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    expect(await screen.findAllByText('Exclude Resource Class')).toHaveLength(
      3
    );
    expect(
      screen.getAllByRole('link', {
        name: 'Repeat search with recorded parameters',
      })
    ).toHaveLength(3);
    const context = searchContexts('2026-08', 'redlining')[0];
    const params = new URL(
      replaySearch('redlining', context),
      'https://example.org'
    ).searchParams;
    expect(params.getAll('exclude_filters[gbl_resourceClass_sm][]')).toEqual([
      'Datasets',
      'Web services',
    ]);
    expect(params.get('q')).toBe('redlining');
    expect(params.get('view')).toBe('map');
  });
});

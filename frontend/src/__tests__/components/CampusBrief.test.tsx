// @vitest-environment jsdom
import { fireEvent, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';
import { renderAnalytics } from '../utils/renderAnalytics';
import { AnalyticsTestRouter } from '../utils/AnalyticsTestRouter';
import { AnalyticsPage } from '../../pages/AnalyticsPage';
import { analyticsSnapshot } from '../../../app/lib/analytics-data.server';
import manifest from '../../../private-analytics-reports/manifest.json';

vi.mock(
  'recharts',
  async () => (await import('../utils/analyticsCharts')).analyticsCharts
);
const institution = 'the-ohio-state-university';
function open(path: string) {
  return renderAnalytics(
    <AnalyticsTestRouter initialEntries={[path]}>
      <AnalyticsPage />
    </AnalyticsTestRouter>
  );
}

describe('campus brief', () => {
  it('opens from Members with the selected institution and period intact', () => {
    open(`/analytics/members?month=2026-08&institution=${institution}`);
    const link = screen.getByRole('link', { name: 'Open campus brief' });
    expect(link).toHaveAttribute(
      'href',
      `/analytics/members?month=2026-08&institution=${institution}&brief=1`
    );
    fireEvent.click(link);
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
      'The Ohio State University'
    );
    expect(
      screen.getByRole('link', { name: 'Back to Members' })
    ).toHaveAttribute(
      'href',
      `/analytics/members?month=2026-08&institution=${institution}`
    );
  });

  it('uses exact selected-campus counts, rankings, comparison and aggregate revision', async () => {
    const { container } = open(
      `/analytics/members?month=2026-09&institution=${institution}&brief=1`
    );
    const current = analyticsSnapshot.september2026.monthlySnapshots[
      '2026-09'
    ].members.find((row: { slug: string }) => row.slug === institution)!;
    const previous = analyticsSnapshot.reportsAugust2026.augustMembers.find(
      (row: { slug: string }) => row.slug === institution
    )!;
    const metrics = container.querySelector('.analytics-brief-metrics')!;
    expect(metrics).toHaveTextContent(
      current.resourceViews.toLocaleString('en-US')
    );
    expect(metrics).toHaveTextContent(
      `${current.resourceViews - previous.resourceViews > 0 ? '+' : ''}${(current.resourceViews - previous.resourceViews).toLocaleString('en-US')} vs Aug 2026`
    );
    expect(screen.getByText(/Aggregate report revision:/)).toHaveTextContent(
      manifest.periods.find((row) => row.id === '2026-09')!.revision
    );
    expect(screen.getByText(/does not verify this brief/)).toBeInTheDocument();
    expect(screen.getByRole('img')).toHaveAccessibleName(
      /Daily resource views across 30 days/
    );
    expect((await axe(container)).violations).toEqual([]);
    const print = vi.spyOn(window, 'print').mockImplementation(() => {});
    fireEvent.click(screen.getByRole('button', { name: 'Print / save PDF' }));
    expect(print).toHaveBeenCalledOnce();
    print.mockRestore();
  });

  it('keeps cumulative coverage incomplete and never adds monthly comparison percentages', () => {
    open(`/analytics/members?month=all&institution=${institution}&brief=1`);
    expect(
      screen.getByText('Incomplete historical aggregate coverage')
    ).toBeInTheDocument();
    expect(screen.getAllByText('No prior-period comparison')).toHaveLength(4);
    expect(screen.getByRole('img')).toHaveAccessibleName(/across 92 days/);
  });

  it('does not create a brief for unavailable institutions', () => {
    open(
      '/analytics/members?month=2026-09&institution=university-of-southern-california&brief=1'
    );
    expect(
      screen.getByText('Analytics data unavailable for this period.')
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Print / save PDF' })
    ).not.toBeInTheDocument();
  });

  it('exposes three findings with scoped drill-downs on the overview', () => {
    open('/analytics?month=2026-09');
    const findings = within(
      screen.getByRole('region', { name: 'This month in three findings' })
    );
    expect(findings.getAllByRole('article')).toHaveLength(3);
    expect(
      findings.getByRole('link', { name: 'Compare the months' })
    ).toHaveAttribute('href', '/analytics/comparison?month=2026-09#comparison');
    expect(
      findings.getByRole('link', { name: 'Inspect searches without results' })
    ).toHaveAttribute('href', '/analytics/searches?month=2026-09#zero-results');
  });
});

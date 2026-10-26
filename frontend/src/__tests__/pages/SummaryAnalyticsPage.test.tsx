import { fireEvent, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { SummaryAnalyticsPage } from '../../components/analytics/SummaryAnalyticsPage';
import { AnalyticsTestRouter } from '../utils/AnalyticsTestRouter';
import { renderAnalytics } from '../utils/renderAnalytics';
import { axeWithWCAG22 } from '../../test-utils/axe';

vi.mock(
  'recharts',
  async () => (await import('../utils/analyticsCharts')).analyticsCharts
);
vi.mock('../../components/layout/Footer', () => ({ Footer: () => <footer /> }));
function renderSummary(path = '/analytics/summary') {
  return renderAnalytics(
    <AnalyticsTestRouter initialEntries={[path]}>
      <SummaryAnalyticsPage />
    </AnalyticsTestRouter>
  );
}
describe('Summary tab', () => {
  it('expands and collapses each ranking independently', () => {
    renderSummary();
    const titles = [
      'Most common',
      'No-result searches',
      'Top outlinked resources',
      'Top downloaded resources',
    ];
    for (const title of titles) {
      const card = screen
        .getByRole('heading', { name: title })
        .closest('article')!;
      expect(within(card).getAllByRole('listitem')).toHaveLength(5);
      const button = within(card).getByRole('button', { name: /^Show all 20/ });
      expect(button).toHaveAttribute('aria-expanded', 'false');
      fireEvent.click(button);
      expect(within(card).getAllByRole('listitem')).toHaveLength(20);
      expect(button).toHaveAttribute('aria-expanded', 'true');
      expect(
        document.getElementById(button.getAttribute('aria-controls')!)
      ).toBe(within(card).getByRole('list'));
      for (const other of titles.filter((name) => name !== title)) {
        expect(
          within(
            screen.getByRole('heading', { name: other }).closest('article')!
          ).getAllByRole('listitem')
        ).toHaveLength(5);
      }
      fireEvent.click(
        within(card).getByRole('button', { name: /^Show fewer/ })
      );
      expect(within(card).getAllByRole('listitem')).toHaveLength(5);
    }
  });
  it('collapses expanded lists when the reporting period changes', async () => {
    renderSummary();
    fireEvent.click(
      screen.getByRole('button', { name: 'Show all 20 most common' })
    );
    fireEvent.change(
      screen.getByRole('combobox', { name: 'Reporting period' }),
      { target: { value: '2026-07' } }
    );
    const card = (
      await screen.findByRole('heading', { name: 'Most common' })
    ).closest('article')!;
    expect(within(card).getAllByRole('listitem')).toHaveLength(5);
    expect(within(card).getByRole('button')).toHaveAttribute(
      'aria-expanded',
      'false'
    );
  });
  it('shows the requested sections and accurately labels saved-data gaps', () => {
    renderSummary();
    expect(screen.getByRole('link', { name: 'Summary' })).toHaveAttribute(
      'aria-current',
      'page'
    );
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
      'Summary'
    );
    for (const name of [
      'Discovery activity',
      'Top search terms',
      'Successful access',
      'High-value resources',
      'Record access patterns',
      'Collection growth',
    ]) {
      expect(
        screen.getByRole('heading', { level: 2, name })
      ).toBeInTheDocument();
    }
    const patterns = screen
      .getByRole('heading', { name: 'Record access patterns' })
      .closest('section')!;
    const lists = within(patterns).getAllByRole('list');
    expect(lists).toHaveLength(2);
    for (const list of lists)
      expect(within(list).getAllByRole('listitem')).toHaveLength(5);
    expect(within(patterns).getByText('45.6')).toBeInTheDocument();
    expect(within(patterns).getByText('26')).toBeInTheDocument();
    const growth = screen
      .getByRole('heading', { name: 'Collection growth' })
      .closest('section')!;
    expect(within(growth).getByText('148,196')).toBeInTheDocument();
    expect(within(growth).getByText('As of Oct 9, 2026')).toBeInTheDocument();
    expect(within(growth).getByText('+531')).toBeInTheDocument();
    expect(
      within(growth).getByText(/\+0.36% · Since Sep 10, 2026/)
    ).toBeInTheDocument();
    expect(screen.getByText('27,892')).toBeInTheDocument();
    expect(screen.getByText('19,538')).toBeInTheDocument();
    const access = screen
      .getByRole('heading', { name: 'Successful access' })
      .closest('section')!;
    expect(within(access).getByText('2,869')).toBeInTheDocument();
    expect(within(access).getByText('2,621')).toBeInTheDocument();
    expect(
      screen.getByRole('combobox', { name: 'Reporting period' })
    ).toHaveValue('3months');
  });
  it('switches chart totals, access totals, and rankings between periods', () => {
    renderSummary();
    const picker = screen.getByRole('combobox', { name: 'Reporting period' });
    fireEvent.change(picker, { target: { value: '2026-07' } });
    expect(screen.getByText('6,457')).toBeInTheDocument();
    expect(
      screen.getByText(/Combined views and access-click counts are unavailable/)
    ).toBeInTheDocument();
    expect(screen.getByText('7,729')).toBeInTheDocument();
    expect(screen.getByText('147,665')).toBeInTheDocument();
    expect(
      screen.getByText('No earlier catalog snapshot available')
    ).toBeInTheDocument();
    const access = screen
      .getByRole('heading', { name: 'Successful access' })
      .closest('section')!;
    expect(within(access).getAllByText('1,129')).toHaveLength(2);
    expect(
      screen.getByRole('img', { name: /Daily searches/ })
    ).toHaveAccessibleName('Daily searches, Jul 1, 2026 – Jul 31, 2026');
    fireEvent.change(picker, { target: { value: 'all' } });
    expect(screen.getByText('19,538')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Summary' })).toHaveAttribute(
      'href',
      '/analytics/summary?month=all'
    );
    fireEvent.change(picker, { target: { value: '3months' } });
    expect(screen.getByRole('link', { name: 'Summary' })).toHaveAttribute(
      'href',
      '/analytics/summary?month=3months'
    );
    expect(screen.getByRole('link', { name: 'Overview' })).toHaveAttribute(
      'href',
      '/analytics'
    );
  });
  it('restores a month from a shared URL', () => {
    renderSummary('/analytics/summary?month=2026-08');
    expect(
      screen.getByRole('combobox', { name: 'Reporting period' })
    ).toHaveValue('2026-08');
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
      'Summary'
    );
  });
  it('has no WCAG accessibility violations', async () => {
    const { container } = renderSummary();
    expect((await axeWithWCAG22(container)).violations).toEqual([]);
  }, 30_000);
});

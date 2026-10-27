import { fireEvent, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { SummaryAnalyticsPage } from '../../components/analytics/SummaryAnalyticsPage';
import { AnalyticsTestRouter } from '../utils/AnalyticsTestRouter';
import { renderAnalytics } from '../utils/renderAnalytics';
import { axeWithWCAG22 } from '../../test-utils/axe';
import { AnalyticsDataContext } from '../../components/analytics/AnalyticsData';
import { analyticsSnapshot } from '../../../app/lib/analytics-data.server';

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
  it('charts search counts by category for each ranking and follows the period', () => {
    renderAnalytics(
      <AnalyticsDataContext.Provider
        value={{
          ...analyticsSnapshot,
          'allTimeCurrent.json': {
            default: {
              ...analyticsSnapshot['allTimeCurrent.json'].default,
              queries: [
                { term: 'michigan', count: 20 },
                { term: 'siberia russia', count: 10 },
                { term: 'sanborn', count: 5 },
              ],
              zeroQueries: [
                { term: '123 Main street', count: 9 },
                { term: '2020', count: 1 },
              ],
            },
          },
        }}
      >
        <AnalyticsTestRouter initialEntries={['/analytics/summary?month=all']}>
          <SummaryAnalyticsPage />
        </AnalyticsTestRouter>
      </AnalyticsDataContext.Provider>
    );
    const common = screen
      .getByRole('heading', { name: 'Most common' })
      .closest('article')!;
    expect(within(common).getByRole('img')).toHaveAccessibleName(
      'Most common search categories: Places & regions: 30; Maps & imagery: 5'
    );
    expect(within(common).getByText('86%')).toBeInTheDocument();
    expect(
      within(common).getByText(/3 saved leading queries only, not all searches/)
    ).toBeInTheDocument();
    const zero = screen
      .getByRole('heading', { name: 'No-result searches' })
      .closest('article')!;
    expect(within(zero).getByRole('img')).toHaveAccessibleName(
      'No-result searches search categories: Address and street search: 9; Date-only search: 1'
    );
    expect(within(zero).getByText('90%')).toBeInTheDocument();
    expect(
      within(common).queryByRole('list', { name: 'Most common query terms' })
    ).not.toBeInTheDocument();
    fireEvent.click(
      within(common).getByRole('button', { name: 'Show query terms' })
    );
    const commonTerms = within(common).getByRole('list', {
      name: 'Most common query terms',
    });
    expect(within(commonTerms).getAllByRole('listitem')).toHaveLength(3);
    expect(
      within(commonTerms).getByText('michigan').closest('li')
    ).toHaveTextContent('michigan Places & regions20 searches');
    fireEvent.click(
      within(zero).getByRole('button', { name: 'Show query terms' })
    );
    const zeroTerms = within(zero).getByRole('list', {
      name: 'No-result searches query terms',
    });
    expect(
      within(zeroTerms).getByText('123 Main street').closest('li')
    ).toHaveTextContent('123 Main street Address and street search9 searches');
    fireEvent.change(
      screen.getByRole('combobox', { name: 'Reporting period' }),
      {
        target: { value: '2026-07' },
      }
    );
    expect(
      screen.getByRole('img', { name: /^Most common search categories/ })
    ).not.toHaveAccessibleName(
      'Most common search categories: Places & regions: 30; Maps & imagery: 5'
    );
    expect(
      screen.getByRole('img', { name: /^No-result searches search categories/ })
    ).not.toHaveAccessibleName(
      'No-result searches search categories: Address and street search: 9; Date-only search: 1'
    );
  });
  it('expands and collapses each ranking independently', () => {
    renderSummary();
    const titles = ['Top outlinked resources', 'Top downloaded resources'];
    for (const title of titles) {
      const card = screen
        .getByRole('heading', { name: title })
        .closest('article')!;
      expect(
        within(card.querySelector('ol')!).getAllByRole('listitem')
      ).toHaveLength(5);
      const button = within(card).getByRole('button', { name: /^Show all 20/ });
      expect(button).toHaveAttribute('aria-expanded', 'false');
      fireEvent.click(button);
      expect(
        within(card.querySelector('ol')!).getAllByRole('listitem')
      ).toHaveLength(20);
      expect(button).toHaveAttribute('aria-expanded', 'true');
      expect(
        document.getElementById(button.getAttribute('aria-controls')!)
      ).toBe(card.querySelector('ol'));
      for (const other of titles.filter((name) => name !== title)) {
        expect(
          within(
            screen
              .getByRole('heading', { name: other })
              .closest('article')!
              .querySelector('ol')!
          ).getAllByRole('listitem')
        ).toHaveLength(5);
      }
      fireEvent.click(
        within(card).getByRole('button', { name: /^Show fewer/ })
      );
      expect(
        within(card.querySelector('ol')!).getAllByRole('listitem')
      ).toHaveLength(5);
    }
  });
  it('reveals all saved query terms independently and can hide them again', () => {
    renderSummary('/analytics/summary?month=all');
    const common = screen
      .getByRole('heading', { name: 'Most common' })
      .closest('article')!;
    const zero = screen
      .getByRole('heading', { name: 'No-result searches' })
      .closest('article')!;
    for (const [card, count] of [
      [common, analyticsSnapshot['allTimeCurrent.json'].default.queries.length],
      [
        zero,
        analyticsSnapshot['allTimeCurrent.json'].default.zeroQueries.length,
      ],
    ] as const) {
      expect(
        within(card).queryByRole('list', { name: /query terms$/ })
      ).not.toBeInTheDocument();
      const button = within(card).getByRole('button', {
        name: 'Show query terms',
      });
      expect(button).toHaveAttribute('aria-expanded', 'false');
      fireEvent.click(button);
      const list = within(card).getByRole('list', { name: /query terms$/ });
      expect(within(list).getAllByRole('listitem')).toHaveLength(count);
      expect(button).toHaveAttribute('aria-controls', list.id);
      expect(button).toHaveAttribute('aria-expanded', 'true');
      const other = card === common ? zero : common;
      expect(
        within(other).queryByRole('list', { name: /query terms$/ })
      ).not.toBeInTheDocument();
      fireEvent.click(
        within(card).getByRole('button', { name: 'Hide query terms' })
      );
      expect(
        within(card).queryByRole('list', { name: /query terms$/ })
      ).not.toBeInTheDocument();
    }
  });
  it('collapses expanded lists when the reporting period changes', async () => {
    renderSummary();
    fireEvent.click(
      within(
        screen.getByRole('heading', { name: 'Most common' }).closest('article')!
      ).getByRole('button', { name: 'Show query terms' })
    );
    fireEvent.change(
      screen.getByRole('combobox', { name: 'Reporting period' }),
      { target: { value: '2026-07' } }
    );
    const card = (
      await screen.findByRole('heading', { name: 'Most common' })
    ).closest('article')!;
    expect(
      within(card).queryByRole('list', { name: 'Most common query terms' })
    ).not.toBeInTheDocument();
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
    const example = within(patterns)
      .getByRole('link', { name: 'Rivers, Nepal, 2013' })
      .closest('li')!;
    expect(
      within(example)
        .getAllByRole('term')
        .map((element) => element.textContent)
    ).toEqual(['Views', 'Outlinks', 'Downloads', 'Clicks / views']);
    expect(
      within(example)
        .getAllByRole('definition')
        .map((element) => element.textContent)
    ).toEqual(['57', '1', '25', '45.6%']);
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

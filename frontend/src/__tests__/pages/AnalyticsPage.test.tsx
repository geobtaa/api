// @vitest-environment jsdom
import { renderAnalytics as render } from '../utils/renderAnalytics';
import { fireEvent, screen, within } from '@testing-library/react';
import { AnalyticsTestRouter } from '../utils/AnalyticsTestRouter';
import { HelmetProvider } from 'react-helmet-async';
import type { ReactNode } from 'react';
import { vi } from 'vitest';
import { AnalyticsPage } from '../../pages/AnalyticsPage';
import { axeWithWCAG22 } from '../../test-utils/axe';

vi.mock('../../components/layout/Header', () => ({
  Header: () => <div data-testid="header">Header</div>,
}));

vi.mock('../../components/layout/Footer', () => ({
  Footer: () => <div data-testid="footer">Footer</div>,
}));

vi.mock('recharts', async () => ({
  ...(await import('../utils/analyticsCharts')).analyticsCharts,
  Area: () => null,
  AreaChart: ({ data }: { data?: Array<Record<string, unknown>> }) => (
    <div
      data-testid={
        data?.[0] && !('events' in data[0])
          ? 'member-activity-chart'
          : 'activity-chart'
      }
    />
  ),
  LineChart: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  BarChart: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  Bar: () => null,
  Legend: () => null,
  CartesianGrid: () => null,
  Line: () => null,
  ResponsiveContainer: ({ children }: { children: ReactNode }) => (
    <div>{children}</div>
  ),
  Tooltip: () => null,
  XAxis: () => null,
  YAxis: () => null,
}));

// Full snapshot tables and multi-report navigation can exceed Vitest's five-second
// default on shared CI runners. Keep this budget local; WCAG audits retain 60 seconds.
describe('AnalyticsPage', { timeout: 30_000 }, () => {
  function renderPage(report = 'members&month=2026-07') {
    const [id, ...queryParts] = report.split('&');
    const query = queryParts.length ? queryParts.join('&') : undefined;
    const path = ['overview', 'activity'].includes(id)
      ? '/analytics'
      : `/analytics/${id}`;
    window.history.replaceState({}, '', `${path}?${query ?? 'month=2026-08'}`);
    return render(
      <HelmetProvider>
        <AnalyticsTestRouter browser>
          <AnalyticsPage />
        </AnalyticsTestRouter>
      </HelmetProvider>
    );
  }

  function institutionButton(name: string | RegExp) {
    if (!screen.queryByRole('button', { name })) {
      fireEvent.click(
        screen.getByRole('button', { name: /Change institution/ })
      );
    }
    return screen.getByRole('button', { name });
  }

  it.each(['2026-07', '2026-08', '2026-09', 'all'])(
    'preserves search controls and contexts for %s',
    (month) => {
      const { container } = renderPage(`discovery&month=${month}`);
      expect(
        container.querySelector('.analytics-search-categories')
      ).not.toBeNull();
      expect(
        screen.getByRole('heading', { name: 'Most-used search filters' })
      ).toBeInTheDocument();
      const metric = screen.getByRole('combobox', {
        name: 'Search chart metric',
      });
      fireEvent.change(metric, { target: { value: 'zeroResults' } });
      expect(metric).toHaveValue('zeroResults');
      const daily = screen.getByRole('table', {
        name: /daily searches/,
        hidden: true,
      });
      expect(within(daily).getAllByRole('row', { hidden: true }).length).toBe(
        month === 'all' ? 93 : month === '2026-09' ? 31 : 32
      );
      expect(container.querySelector('.analytics-zero-results')).not.toBeNull();
      expect(
        screen.getByRole('combobox', { name: 'Search topic' })
      ).toBeInTheDocument();
    }
  );

  it.each(['members', 'overview', 'discovery', 'clients', 'platform'])(
    'keeps %s sections consistent across reporting periods',
    (report) => {
      const { container } = renderPage(`${report}&month=2026-07`);
      const structure = () =>
        Array.from(
          container.querySelectorAll(
            'h1, h2, .analytics-panel-header > div > span, .analytics-panel-header > span'
          )
        ).map((node) => node.textContent);
      const initial = structure();
      const selector = screen.getByRole('combobox', {
        name: 'Reporting month',
      });
      for (const month of ['2026-08', '2026-09', 'all', '2026-07']) {
        fireEvent.change(selector, { target: { value: month } });
        expect(selector).toHaveValue(month);
        expect(structure()).toEqual(initial);
        if (report === 'members') {
          expect(institutionButton('All BTAA')).toBeInTheDocument();
        } else if (report === 'overview') {
          expect(
            screen.getByRole('combobox', { name: 'Overview chart metric' })
          ).toBeInTheDocument();
          expect(
            container.querySelector('.analytics-overview-details table')
          ).not.toBeNull();
        }
      }
    }
  );

  it.each(['comparison', 'clients', 'platform'])(
    'makes every data table sortable and filterable in %s',
    (report) => {
      const { container } = renderPage(report);
      const tables = container.querySelectorAll('.analytics-data-table table');
      expect(tables.length).toBeGreaterThan(0);
      tables.forEach((table) => {
        expect(
          table.parentElement?.querySelector('input[type="search"]')
        ).not.toBeNull();
        table.querySelectorAll('thead th').forEach((heading) => {
          expect(heading).toHaveAttribute('aria-sort', 'none');
          expect(heading.querySelector('button')).not.toBeNull();
        });
      });
    }
  );

  it('defaults to September and carries All time across reports with monthly switching', () => {
    renderPage('overview&month=');
    const month = screen.getByRole('combobox', { name: 'Reporting month' });
    expect(month).toHaveValue('2026-09');
    fireEvent.change(month, { target: { value: 'all' } });
    expect(screen.getByText('19.5K')).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: 'Analytics dashboard' })
    ).toBeInTheDocument();
    const nav = screen.getByRole('navigation', { name: 'Analytics reports' });
    fireEvent.click(within(nav).getByRole('link', { name: 'Searches' }));
    expect(window.location.pathname).toBe('/analytics/searches');
    expect(window.location.search).toBe('?month=all');
    const table = screen.getByLabelText('Top 50 searches');
    expect(within(table).getAllByRole('article').length).toBe(50);
    expect(
      within(table).getByRole('link', { name: 'sanborn' }).closest('article')
    ).toHaveTextContent('89');
    fireEvent.change(
      screen.getByRole('combobox', { name: 'Reporting month' }),
      { target: { value: '2026-07' } }
    );
    expect(screen.getByLabelText('Top 50 searches')).toBeInTheDocument();
  });

  it.each([
    'overview',
    'content',
    'discovery',
    'members',
    'clients',
    'platform',
  ])(
    'renders All time tables for %s with explicit academic-year coverage',
    (report) => {
      renderPage(`${report}&month=all`);
      expect(
        screen.getByRole('combobox', {
          name: [
            'overview',
            'members',
            'discovery',
            'clients',
            'platform',
          ].includes(report)
            ? 'Reporting month'
            : 'Reporting period',
        })
      ).toHaveValue('all');
      if (
        ['overview', 'members', 'discovery', 'clients', 'platform'].includes(
          report
        )
      ) {
        expect(
          screen.getAllByText(/July 1, 2026 – September 30, 2026/).length
        ).toBeGreaterThan(0);
      } else {
        expect(
          screen.getAllByText(
            /July 1,? ?[–—-].*September 30, 2026|July 1, 2026 – September 30, 2026/
          ).length
        ).toBeGreaterThan(0);
      }
      if (!['members', 'content'].includes(report))
        expect(
          screen.getAllByRole('table', { hidden: true }).length
        ).toBeGreaterThan(0);
      else
        expect(
          screen.getAllByRole('article', { hidden: true }).length
        ).toBeGreaterThan(0);
      expect(
        screen.queryByRole('link', {
          name: 'Download all-time snapshot (JSON)',
        })
      ).not.toBeInTheDocument();
    }
  );

  it.each(['2026-07', '2026-08', '2026-09', 'all'])(
    'combines Overview charts for %s',
    (month) => {
      renderPage(`overview&month=${month}`);
      expect(
        screen.queryByLabelText('Audience chart metric')
      ).not.toBeInTheDocument();
      expect(
        screen.getAllByRole('heading', { name: /^Tracked visits/ })[0]
      ).toBeInTheDocument();
      const select = screen.getByLabelText('Overview chart metric');
      fireEvent.change(select, { target: { value: 'visits' } });
      expect(select).toHaveValue('visits');
      expect(
        screen.getByRole('heading', { name: 'Daily audience values' })
      ).toBeInTheDocument();
    }
  );

  it('shows an overview and navigates between focused reports', () => {
    renderPage('overview');
    expect(
      screen.getByRole('heading', {
        name: 'Analytics dashboard',
        level: 1,
      })
    ).toBeInTheDocument();
    expect(screen.getByText('7.5K')).toBeInTheDocument();
    expect(screen.getByTestId('activity-chart')).toBeInTheDocument();
    expect(
      screen.queryByRole('link', { name: 'Daily activity' })
    ).not.toBeInTheDocument();
    expect(screen.queryByTestId('header')).not.toBeInTheDocument();
    expect(screen.queryByRole('search')).not.toBeInTheDocument();
    expect(
      screen.getAllByRole('heading', { name: /^Tracked visits/ })[0]
    ).toBeInTheDocument();
    const nav = screen.getByRole('navigation', { name: 'Analytics reports' });
    expect(within(nav).getByRole('link', { name: 'Overview' })).toHaveAttribute(
      'aria-current',
      'page'
    );
    fireEvent.click(
      within(nav).getByRole('link', { name: 'Month comparison' })
    );
    expect(window.location.pathname).toBe('/analytics/comparison');
    expect(window.location.search).toBe('?month=2026-08');
    expect(
      screen.getByRole('link', { name: 'Month comparison', current: 'page' })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('table', { name: /portal totals/i })
    ).toBeInTheDocument();
    expect(screen.queryByText('598.9K')).not.toBeInTheDocument();
    expect(
      screen.queryByRole('heading', {
        name: 'How BTAA member content performed',
      })
    ).not.toBeInTheDocument();
    fireEvent.click(within(nav).getByRole('link', { name: 'Overview' }));
    expect(window.location.search).toBe('?month=2026-08');
    expect(
      screen.queryByRole('table', { name: /portal totals/i })
    ).not.toBeInTheDocument();
  });

  it.each(['2026-07', '2026-08', '2026-09', 'all'])(
    'keeps Popular content sections and filtering consistent for %s',
    (month) => {
      const { container } = renderPage(`content&month=${month}`);
      const headers = [
        ...container.querySelectorAll('.analytics-panel-header'),
      ].map((node) => node.textContent ?? '');
      const resources = headers.findIndex((text) =>
        text.includes('Top resources')
      );
      const collections = headers.findIndex((text) =>
        text.includes('Top collections')
      );
      const downloads = headers.findIndex((text) =>
        text.includes('Resources with the most download clicks')
      );
      expect(resources).toBeGreaterThanOrEqual(0);
      expect(collections).toBeGreaterThan(resources);
      expect(downloads).toBeGreaterThan(collections);
      expect(
        container.querySelector('#top-resources .analytics-ranking-item')
      ).toBeInTheDocument();
      fireEvent.change(
        screen.getByRole('searchbox', { name: 'Filter Top resources' }),
        {
          target: { value: 'no matching resource fixture' },
        }
      );
      expect(
        container.querySelector('#top-resources .analytics-ranking-item')
      ).not.toBeInTheDocument();
      if (month === 'all') {
        expect(
          screen.queryByText(/Collection rankings are unavailable/)
        ).not.toBeInTheDocument();
        expect(screen.queryByText('Daily trend')).not.toBeInTheDocument();
        expect(
          screen.getByText('2,621 across all resources')
        ).toBeInTheDocument();
      }
    }
  );

  it('opens popular content directly without unrelated reports', () => {
    renderPage('content&month=2026-07');
    expect(
      screen.getByRole('link', { name: 'Popular content', current: 'page' })
    ).toBeInTheDocument();
    expect(
      screen.getAllByRole('link', { name: 'Emporium, Pennsylvania, 1892' })[0]
    ).toHaveAttribute(
      'href',
      '/resources/95dcf338-fc27-4d3b-8883-967b3223933b'
    );
    expect(
      screen.getByRole('link', { name: 'Urban Base Layers Collection' })
    ).toHaveAttribute('href', '/resources/b1g_urbanBaseLayers');
    expect(screen.queryByTestId('activity-chart')).not.toBeInTheDocument();
    expect(
      screen.queryByTestId('member-activity-chart')
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('heading', { name: 'API requests and reliability' })
    ).not.toBeInTheDocument();
  });

  it('preserves August popular content and preserves July through the month selector', () => {
    renderPage('content');
    expect(
      screen.getByRole('combobox', { name: 'Reporting month' })
    ).toHaveValue('2026-08');
    expect(
      screen.getByRole('heading', {
        name: 'Top resources',
      })
    ).toBeInTheDocument();
    expect(
      screen.getAllByRole('link', { name: 'Rivers, Nepal, 2013' })[0]
    ).toBeInTheDocument();
    expect(screen.getByText('812 across all resources')).toBeInTheDocument();
    expect(
      screen.getByText(/598 resources with download clicks/)
    ).toBeInTheDocument();
    expect(
      within(document.querySelector('#top-resources')!).getAllByText(
        'vs prior month'
      ).length
    ).toBe(50);
    fireEvent.change(
      screen.getByRole('combobox', { name: 'Reporting month' }),
      { target: { value: '2026-07' } }
    );
    expect(window.location.pathname).toBe('/analytics/content');
    expect(window.location.search).toBe('?month=2026-07');
    expect(
      screen.getByRole('heading', {
        name: 'Top resources',
      })
    ).toBeInTheDocument();
    expect(screen.getByText('933 across all resources')).toBeInTheDocument();
    fireEvent.change(
      screen.getByRole('combobox', { name: 'Reporting month' }),
      { target: { value: '2026-08' } }
    );
    expect(
      screen.getByRole('heading', {
        name: 'Top resources',
      })
    ).toBeInTheDocument();
  });

  it('uses August in every detailed report and keeps month selection between tabs', () => {
    renderPage('members');
    expect(
      screen.getByRole('combobox', { name: 'Reporting month' })
    ).toHaveValue('2026-08');
    expect(screen.getByText(/Activity period: August 1–31/)).toHaveTextContent(
      'September 9, 2026'
    );
    expect(screen.getAllByText('10,850').length).toBeGreaterThan(0);
    const nav = screen.getByRole('navigation', { name: 'Analytics reports' });
    fireEvent.click(within(nav).getByRole('link', { name: 'Overview' }));
    expect(screen.getByText('49,258')).toBeInTheDocument();
    fireEvent.click(within(nav).getByRole('link', { name: 'Searches' }));
    expect(screen.getByRole('link', { name: 'wetlands' })).toBeInTheDocument();
    expect(screen.getByText(/5,744 of 7,545/)).toBeInTheDocument();
    fireEvent.click(within(nav).getByRole('link', { name: 'API reliability' }));
    expect(screen.getByText('127 ms')).toBeInTheDocument();
    expect(
      screen.getByText('Peak-day API traffic', {
        selector: '.analytics-panel-header h3',
      })
    ).toBeInTheDocument();
    fireEvent.change(
      screen.getByRole('combobox', { name: 'Reporting month' }),
      { target: { value: '2026-07' } }
    );
    expect(screen.getByText('29 ms')).toBeInTheDocument();
    fireEvent.click(within(nav).getByRole('link', { name: 'Searches' }));
    expect(window.location.pathname).toBe('/analytics/searches');
    expect(window.location.search).toBe('?month=2026-07');
    expect(
      screen.getByRole('link', { name: 'turkey maps' })
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('link', { name: 'wetlands' })
    ).not.toBeInTheDocument();
  });

  it('opens client reporting from navigation and switches its reporting month', () => {
    renderPage('overview');
    fireEvent.click(
      within(
        screen.getByRole('navigation', { name: 'Analytics reports' })
      ).getByRole('link', { name: 'Applications & API access' })
    );
    expect(
      screen.getByRole('link', {
        name: 'Applications & API access',
        current: 'page',
      })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('table', { name: 'August 2026 declared client usage' })
    ).toBeInTheDocument();
    fireEvent.change(
      screen.getByRole('combobox', { name: 'Reporting month' }),
      { target: { value: '2026-07' } }
    );
    expect(
      screen.getByRole('table', { name: 'July 2026 declared client usage' })
    ).toBeInTheDocument();
    expect(screen.getByText('Not available')).toBeInTheDocument();
  });

  it('keeps old daily activity links working with the selected month', () => {
    renderPage('activity&month=2026-07');
    expect(
      screen.getByRole('heading', { name: 'Analytics dashboard' })
    ).toBeInTheDocument();
    expect(screen.getByTestId('activity-chart')).toBeInTheDocument();
    expect(
      screen.getByRole('combobox', { name: 'Reporting month' })
    ).toHaveValue('2026-07');
    expect(
      screen.getByRole('img', {
        name: /Daily interactions from July 1/,
      })
    ).toBeInTheDocument();
  });

  it('leads Searches with 50 ranked queries and preserves original ranks through category filtering', () => {
    renderPage('discovery');
    const heading = screen.getByRole('heading', { name: 'Top 50 searches' });
    expect(
      heading.compareDocumentPosition(
        screen.getByRole('heading', { name: 'Search view mix' })
      ) & Node.DOCUMENT_POSITION_FOLLOWING
    ).toBeTruthy();
    const list = screen.getByLabelText('Top 50 searches');
    expect(within(list).getAllByRole('article').length).toBe(50);
    expect(within(list).getAllByRole('article')[0]).toHaveTextContent(
      'wetlands'
    );
    expect(within(list).getAllByRole('article')[0]).toHaveTextContent('95');
    fireEvent.change(
      screen.getByRole('combobox', { name: 'Reporting month' }),
      { target: { value: '2026-07' } }
    );
    expect(within(list).getAllByRole('article').length).toBe(50);
    expect(
      within(list).getByRole('link', { name: 'turkey maps' })
    ).toHaveAttribute('href', '/search?q=turkey%20%20maps');
  });

  it('filters top searches by inferred category while retaining original ranks', () => {
    renderPage('discovery');
    fireEvent.change(screen.getByRole('combobox', { name: 'Search topic' }), {
      target: { value: 'Mixed or unclear' },
    });
    const table = screen.getByLabelText('Top 50 searches');
    expect(within(table).getAllByRole('article').length).toBe(1);
    expect(within(table).getByText('22')).toBeInTheDocument();
    expect(
      within(table).getByRole('link', {
        name: 'indiana field survey iran hardin i 38l',
      })
    ).toHaveTextContent('indiana field survey iran hardin i 38l');
    fireEvent.change(screen.getByRole('combobox', { name: 'Search topic' }), {
      target: { value: 'People & institutions' },
    });
    fireEvent.change(
      screen.getByRole('combobox', { name: 'Reporting month' }),
      { target: { value: '2026-07' } }
    );
    expect(screen.getByRole('combobox', { name: 'Search topic' })).toHaveValue(
      'all'
    );
    expect(
      within(screen.getByLabelText('Top 50 searches')).getAllByRole('article')
    ).toHaveLength(50);
  });

  it('shows expanded zero-result queries and facet usage for each month', () => {
    renderPage('discovery');
    expect(
      screen.getByRole('link', { name: 'Searches', current: 'page' })
    ).toBeInTheDocument();
    const nav = screen.getByRole('navigation', { name: 'Analytics reports' });
    const labels = within(nav)
      .getAllByRole('link')
      .map((link) => link.textContent);
    expect(labels.indexOf('Searches')).toBe(
      labels.indexOf('Popular content') + 1
    );
    expect(
      within(
        screen.getByRole('region', { name: 'Search terms without results' })
      ).getAllByRole('article')
    ).toHaveLength(100);
    expect(
      screen.getByRole('link', {
        name: 'Carta geologica delle Tre Venezie, Legnago',
      })
    ).toBeInTheDocument();
    expect(
      screen.getByText(/These 100 queries account for 298/)
    ).toBeInTheDocument();
    const chart = screen.getByRole('region', {
      name: 'Facet category usage chart',
    });
    expect(within(chart).getByText('1,515')).toBeInTheDocument();
    expect(within(chart).getByText('Map bounds')).toBeInTheDocument();
    fireEvent.change(
      screen.getByRole('combobox', { name: 'Reporting month' }),
      { target: { value: '2026-07' } }
    );
    expect(
      within(
        screen.getByRole('region', { name: 'Search terms without results' })
      ).getAllByRole('article')
    ).toHaveLength(100);
    expect(screen.getByRole('link', { name: 'Mut' })).toBeInTheDocument();
    expect(
      screen.getByText(/These 100 queries account for 268/)
    ).toBeInTheDocument();
    expect(within(chart).getByText('1,521')).toBeInTheDocument();
  });

  it.each([
    'overview',
    'comparison',
    'content',
    'discovery',
    'members',
    'clients',
    'platform',
  ])(
    'routes report downloads through authenticated endpoints on %s',
    (report) => {
      const { container } = renderPage(report);
      expect(
        screen.getByRole('link', {
          name: 'Download report data (CSV and JSON)',
        })
      ).toHaveAttribute(
        'href',
        expect.stringMatching(/^\/analytics-reports\//)
      );
      expect(
        container.querySelector(
          'a[href^="data:application/json"], a[href^="data:text/csv"]'
        )
      ).toBeNull();
    }
  );

  it('switches grouping with an explicit scope reset and shareable provider selection', () => {
    renderPage('members&month=all&institution=university-of-chicago');
    fireEvent.change(screen.getByLabelText('Group records by'), {
      target: { value: 'provider' },
    });
    expect(new URLSearchParams(window.location.search).has('institution')).toBe(
      false
    );
    expect(
      screen.getByRole('heading', { name: 'Activity by provider' })
    ).toBeInTheDocument();
    const select = screen.getByLabelText('Provider');
    const option = within(select).getAllByRole(
      'option'
    )[1] as HTMLOptionElement;
    fireEvent.change(select, { target: { value: option.value } });
    expect(new URLSearchParams(window.location.search).get('provider')).toBe(
      option.value
    );
    expect(
      screen.getByRole('region', {
        name: 'Most viewed - ' + option.textContent,
      })
    ).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Group records by'), {
      target: { value: 'code' },
    });
    expect(new URLSearchParams(window.location.search).has('provider')).toBe(
      false
    );
    expect(
      screen.getByRole('button', { name: /All BTAA Change institution/ })
    ).toBeInTheDocument();
  });

  it('restores a shared institution filter and clears it for All BTAA', () => {
    renderPage('members&month=all&institution=university-of-chicago');
    expect(
      screen.getByRole('region', {
        name: 'Most viewed - University of Chicago',
      })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('region', {
        name: 'Most download clicks - University of Chicago',
      })
    ).toBeInTheDocument();
    fireEvent.click(
      screen.getByRole('button', { name: /Chicago Change institution/ })
    );
    fireEvent.click(screen.getByRole('button', { name: 'All BTAA' }));
    expect(new URLSearchParams(window.location.search).has('institution')).toBe(
      false
    );
    expect(
      screen.getByRole('region', { name: 'Most viewed' })
    ).toBeInTheDocument();
    fireEvent.click(
      screen.getByRole('button', { name: /All BTAA Change institution/ })
    );
    fireEvent.click(institutionButton(/Show Indiana University/));
    expect(new URLSearchParams(window.location.search).get('institution')).toBe(
      'indiana-university'
    );
    expect(new URLSearchParams(window.location.search).get('month')).toBe(
      'all'
    );
  });

  it('shows top 50 viewed and top 25 downloaded content for the alliance and an institution', () => {
    renderPage('members&month=all');
    expect(
      within(screen.getByRole('region', { name: 'Most viewed' })).getAllByRole(
        'article'
      )
    ).toHaveLength(50);
    expect(
      within(
        screen.getByRole('region', { name: 'Most download clicks' })
      ).getAllByRole('article')
    ).toHaveLength(25);
    fireEvent.click(
      screen.getByRole('button', { name: /All BTAA Change institution/ })
    );
    fireEvent.click(institutionButton(/Show Indiana University/));
    expect(
      within(
        screen.getByRole('region', { name: 'Most viewed - Indiana University' })
      ).getAllByRole('article')
    ).toHaveLength(50);
    expect(
      within(
        screen.getByRole('region', {
          name: 'Most download clicks - Indiana University',
        })
      ).getAllByRole('article')
    ).toHaveLength(25);
  });

  it('keeps institution filters collapsed until requested and closes after selection', () => {
    renderPage('members&month=all');
    expect(
      screen.queryByRole('button', { name: /Show Indiana University/ })
    ).not.toBeInTheDocument();
    fireEvent.click(
      screen.getByRole('button', { name: /All BTAA Change institution/ })
    );
    fireEvent.click(institutionButton(/Show Indiana University/));
    expect(
      screen.getByRole('button', { name: /Indiana Change institution/ })
    ).toHaveAttribute('aria-expanded', 'false');
    expect(
      screen.getByRole('region', { name: 'Most viewed - Indiana University' })
    ).toBeInTheDocument();
  });

  it('includes USC without presenting missing data as alliance totals', () => {
    const { container } = renderPage('members&month=all');
    const controls = container.querySelector('.analytics-report-controls');
    expect(controls).toContainElement(
      screen.getByLabelText('Group records by')
    );
    expect(controls).toContainElement(screen.getByLabelText('Reporting month'));
    const usc = institutionButton(/Show University of Southern California/);
    expect(container.querySelector('.analytics-report-intro')).toContainElement(
      usc
    );
    expect(container.querySelector('.analytics-report-intro')).toContainElement(
      institutionButton('All BTAA')
    );
    fireEvent.click(usc);
    expect(usc).toHaveAttribute('aria-pressed', 'true');
    expect(
      screen.getByRole('region', {
        name: 'University of Southern California report',
      })
    ).toHaveTextContent('Analytics data unavailable');
    expect(
      screen.queryByRole('heading', { name: 'Published resources' })
    ).not.toBeInTheDocument();
    fireEvent.click(institutionButton('All BTAA'));
    expect(
      screen.getByRole('heading', { name: 'Published resources' })
    ).toBeInTheDocument();
  });

  it('switches between verified Provider and historical code groups', () => {
    renderPage('members');
    expect(
      screen.getByRole('region', { name: 'About this report' })
    ).toHaveTextContent('Catalog provider');
    fireEvent.change(screen.getByLabelText('Group records by'), {
      target: { value: 'provider' },
    });
    expect(window.location.search).toContain('grouping=provider');
    expect(
      screen.getByRole('region', { name: 'Provider report' })
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /Show The Ohio State University/ })
    ).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Reporting month'), {
      target: { value: '2026-07' },
    });
    expect(screen.getByLabelText('Group records by')).toHaveValue('provider');
    expect(screen.getByText(/Recovered July export/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Group records by'), {
      target: { value: 'code' },
    });
    expect(
      institutionButton(/Show The Ohio State University/)
    ).toBeInTheDocument();
  });

  it('falls back to overview for an unknown report', () => {
    renderPage('unknown');
    expect(
      screen.getByRole('heading', { name: 'Analytics dashboard' })
    ).toBeInTheDocument();
  });

  it('filters the report to a campus and restores the alliance view', () => {
    renderPage();
    expect(
      screen.getByText(/Activity period: July 1–31, 2026/)
    ).toHaveTextContent('as of August 20, 2026');
    const chicagoFilter = institutionButton(
      'Show University of Chicago July report'
    );
    expect(chicagoFilter).toHaveAttribute('aria-pressed', 'false');
    fireEvent.click(chicagoFilter);
    expect(chicagoFilter).toHaveAttribute('aria-pressed', 'true');
    expect(new URLSearchParams(window.location.search).get('institution')).toBe(
      'university-of-chicago'
    );
    expect(
      screen.getByRole('region', {
        name: 'Most viewed - University of Chicago',
      })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: 'Survey of Egypt: El Bagur' })
    ).toHaveAttribute('href', '/resources/camel-1013673');
    fireEvent.click(institutionButton('All BTAA'));
    expect(new URLSearchParams(window.location.search).has('institution')).toBe(
      false
    );
    expect(
      screen.getByRole('region', { name: 'Most viewed' })
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('region', {
        name: 'Most viewed - University of Chicago',
      })
    ).not.toBeInTheDocument();
  });

  it('explains when a campus had no direct download-link clicks', () => {
    renderPage();

    fireEvent.click(institutionButton('Show University of Oregon July report'));

    expect(
      screen.getByText(
        /No direct download-link clicks were recorded; 9 source-site clicks were still captured/i
      )
    ).toBeInTheDocument();
  });

  it.each([
    'overview',
    'overview&month=all',
    'content&month=all',
    'discovery&month=all',
    'comparison',
    'content',
    'content&month=2026-07',
    'members',
    'activity',
    'discovery',
    'platform',
    'clients',
    'clients&month=2026-07',
    'members&grouping=provider',
    'overview&month=2026-07',
    'members&month=2026-07',
    'activity&month=2026-07',
    'discovery&month=2026-07',
    'platform&month=2026-07',
  ])(
    'has no detectable WCAG violations in %s',
    async (report) => {
      const { container } = renderPage(report);
      expect(
        screen.getByRole('region', { name: 'About this report' })
      ).toBeInTheDocument();
      const results = await axeWithWCAG22(container);

      expect(results.violations).toHaveLength(0);
    },
    60_000
  );

  it('defines historical audience coverage and leads with discovery outcomes', () => {
    renderPage('overview');
    const highlights = screen.getByLabelText('August 2026 highlights');
    expect(highlights.textContent?.indexOf('Search result pages')).toBeLessThan(
      highlights.textContent?.indexOf('Source-site clicks') ?? 0
    );
    const audience = screen.getByLabelText('Audience and discovery coverage');
    expect(within(audience).getByText('13,020')).toBeInTheDocument();
    expect(within(audience).queryByText('Unavailable')).not.toBeInTheDocument();
    expect(
      within(audience).getByText(/71 records lack a visit token/)
    ).toBeInTheDocument();
    expect(
      within(audience).getByRole('table', {
        name: 'August 2026 audience daily values',
      })
    ).toBeInTheDocument();
  });

  it('uses the local thumbnail route and falls back to a resource icon', () => {
    renderPage('content&month=2026-07');

    const thumbnail = screen.getByTestId(
      'analytics-thumbnail-95dcf338-fc27-4d3b-8883-967b3223933b'
    );
    expect(thumbnail).toHaveAttribute(
      'src',
      '/resources/95dcf338-fc27-4d3b-8883-967b3223933b/thumbnail'
    );

    fireEvent.error(thumbnail);

    expect(
      screen.getByTestId(
        'analytics-thumbnail-fallback-95dcf338-fc27-4d3b-8883-967b3223933b'
      )
    ).toBeInTheDocument();
  });
});

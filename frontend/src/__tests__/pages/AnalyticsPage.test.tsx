import { fireEvent, render, screen, within } from '@testing-library/react';
import { BrowserRouter } from 'react-router';
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

vi.mock('recharts', () => ({
  Area: () => null,
  AreaChart: ({ data }: { data?: Array<Record<string, unknown>> }) => (
    <div
      data-testid={
        data?.[0] && 'views' in data[0]
          ? 'member-activity-chart'
          : 'activity-chart'
      }
    />
  ),
  LineChart: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  BarChart: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  Bar: () => null,
  CartesianGrid: () => null,
  Line: () => null,
  ResponsiveContainer: ({ children }: { children: ReactNode }) => (
    <div>{children}</div>
  ),
  Tooltip: () => null,
  XAxis: () => null,
  YAxis: () => null,
}));

describe('AnalyticsPage', () => {
  function renderPage(report = 'members&month=2026-07') {
    window.history.replaceState({}, '', `/analytics?report=${report}`);
    return render(
      <HelmetProvider>
        <BrowserRouter>
          <AnalyticsPage />
        </BrowserRouter>
      </HelmetProvider>
    );
  }

  it.each([
    'comparison',
    'members',
    'clients',
    'platform',
    'members&grouping=provider',
  ])('makes every table sortable and filterable in %s', (report) => {
    const { container } = renderPage(report);
    const tables = container.querySelectorAll('table');
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
  });

  it('defaults to August and carries All time across reports with monthly switching', () => {
    renderPage('overview');
    const month = screen.getByRole('combobox', { name: 'Reporting month' });
    expect(month).toHaveValue('2026-08');
    fireEvent.change(month, { target: { value: 'all' } });
    expect(screen.getByText('14,002')).toBeInTheDocument();
    expect(
      screen.getByText('All time · Academic year to date')
    ).toBeInTheDocument();
    const nav = screen.getByRole('navigation', { name: 'Analytics reports' });
    fireEvent.click(within(nav).getByRole('link', { name: 'Searches' }));
    expect(window.location.search).toBe('?report=discovery&month=all');
    const table = screen.getByRole('table', {
      name: 'Top 50 searches · All time',
    });
    expect(within(table).getAllByRole('row')).toHaveLength(51);
    expect(
      within(table).getByRole('link', { name: 'sanborn' }).closest('tr')
    ).toHaveTextContent('49');
    fireEvent.change(
      screen.getByRole('combobox', { name: 'Reporting period' }),
      { target: { value: '2026-07' } }
    );
    expect(
      screen.getByRole('table', { name: 'July 2026 top 50 searches' })
    ).toBeInTheDocument();
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
        screen.getByRole('combobox', { name: 'Reporting period' })
      ).toHaveValue('all');
      expect(screen.getByText(/September joins once/)).toHaveTextContent(
        'July 1–August 31, 2026'
      );
      expect(
        screen.getAllByRole('table', { hidden: true }).length
      ).toBeGreaterThan(0);
      expect(
        screen.getByRole('link', { name: 'Download all-time snapshot (JSON)' })
      ).toHaveAttribute('download', 'analytics-all-published-months.json');
    }
  );

  it('shows an overview and navigates between focused reports', () => {
    renderPage('overview');
    expect(
      screen.getByRole('heading', {
        name: 'Monthly analytics dashboard',
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
      screen.getByRole('region', { name: 'Audience and discovery coverage' })
    ).toBeInTheDocument();
    const nav = screen.getByRole('navigation', { name: 'Analytics reports' });
    expect(within(nav).getByRole('link', { name: 'Overview' })).toHaveAttribute(
      'aria-current',
      'page'
    );
    fireEvent.click(
      within(nav).getByRole('link', { name: 'Month comparison' })
    );
    expect(window.location.search).toBe('?report=comparison');
    expect(
      screen.getByRole('heading', { name: 'Month comparison', level: 1 })
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
    expect(window.location.search).toBe('');
    expect(
      screen.queryByRole('table', { name: /portal totals/i })
    ).not.toBeInTheDocument();
  });

  it('opens popular content directly without unrelated reports', () => {
    renderPage('content&month=2026-07');
    expect(
      screen.getByRole('heading', { name: 'Popular content', level: 1 })
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

  it('defaults popular content to August and preserves July through the month selector', () => {
    renderPage('content');
    expect(
      screen.getByRole('combobox', { name: 'Reporting month' })
    ).toHaveValue('2026-08');
    expect(
      screen.getByRole('heading', {
        name: 'August’s top resources and collections',
      })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: 'Rivers, Nepal, 2013' })
    ).toBeInTheDocument();
    expect(screen.getByText(/55 of 812 clicks/)).toBeInTheDocument();
    expect(
      screen.getByText(/598 resources with download clicks/)
    ).toBeInTheDocument();
    expect(
      screen.getAllByTitle(
        'All tracked interactions in August 16–31 compared with August 1–15'
      )
    ).toHaveLength(10);
    fireEvent.change(
      screen.getByRole('combobox', { name: 'Reporting month' }),
      { target: { value: '2026-07' } }
    );
    expect(window.location.search).toBe('?report=content&month=2026-07');
    expect(
      screen.getByRole('heading', {
        name: 'July’s top resources and collections',
      })
    ).toBeInTheDocument();
    expect(screen.getByText(/55 of 933 clicks/)).toBeInTheDocument();
    expect(
      screen.queryByRole('link', { name: 'Rivers, Nepal, 2013' })
    ).not.toBeInTheDocument();
    fireEvent.change(
      screen.getByRole('combobox', { name: 'Reporting month' }),
      { target: { value: '2026-08' } }
    );
    expect(
      screen.getByRole('heading', {
        name: 'August’s top resources and collections',
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
      screen.getByText('Aug 1 API traffic separation')
    ).toBeInTheDocument();
    fireEvent.change(
      screen.getByRole('combobox', { name: 'Reporting month' }),
      { target: { value: '2026-07' } }
    );
    expect(screen.getByText('29 ms')).toBeInTheDocument();
    fireEvent.click(within(nav).getByRole('link', { name: 'Searches' }));
    expect(window.location.search).toBe('?report=discovery&month=2026-07');
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
      ).getByRole('link', { name: 'Clients & API keys' })
    );
    expect(
      screen.getByRole('heading', { name: 'Clients & API keys', level: 1 })
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
      screen.getByRole('heading', { name: 'Monthly analytics dashboard' })
    ).toBeInTheDocument();
    expect(screen.getByTestId('activity-chart')).toBeInTheDocument();
    expect(
      screen.getByRole('combobox', { name: 'Reporting month' })
    ).toHaveValue('2026-07');
    expect(
      screen.getByRole('img', {
        name: /Daily interactions and searches from July 1/,
      })
    ).toBeInTheDocument();
  });

  it('leads Searches with 50 ranked, sortable and filterable queries for each month', () => {
    renderPage('discovery');
    const heading = screen.getByRole('heading', { name: 'Top 50 searches' });
    expect(
      heading.compareDocumentPosition(screen.getByText('Search view mix')) &
        Node.DOCUMENT_POSITION_FOLLOWING
    ).toBeTruthy();
    let table = screen.getByRole('table', {
      name: 'August 2026 top 50 searches',
    });
    expect(within(table).getAllByRole('row')).toHaveLength(51);
    expect(within(table).getAllByRole('row')[1]).toHaveTextContent(
      'wetlandsEnvironment & land use95'
    );
    fireEvent.change(
      screen.getByRole('searchbox', {
        name: 'Filter August 2026 top 50 searches',
      }),
      { target: { value: 'wetlands' } }
    );
    expect(within(table).getAllByRole('row')).toHaveLength(2);
    fireEvent.click(
      within(table.parentElement!).getByRole('button', { name: 'Reset' })
    );
    fireEvent.click(within(table).getByRole('button', { name: 'Searches' }));
    expect(within(table).getAllByRole('row')[1]).not.toHaveTextContent(
      'wetlands'
    );
    fireEvent.change(
      screen.getByRole('combobox', { name: 'Reporting month' }),
      { target: { value: '2026-07' } }
    );
    table = screen.getByRole('table', { name: 'July 2026 top 50 searches' });
    expect(within(table).getAllByRole('row')).toHaveLength(51);
    expect(
      within(table).getByRole('link', { name: 'turkey maps' })
    ).toHaveAttribute('href', '/search?q=turkey%20%20maps');
  });

  it('filters top searches by inferred category while retaining original ranks', () => {
    renderPage('discovery');
    fireEvent.change(screen.getByRole('combobox', { name: 'Query category' }), {
      target: { value: 'Mixed or unclear' },
    });
    const table = screen.getByRole('table', {
      name: 'August 2026 top 50 searches',
    });
    expect(within(table).getAllByRole('row')).toHaveLength(2);
    expect(within(table).getByText('22')).toBeInTheDocument();
    expect(within(table).getByRole('link')).toHaveTextContent(
      'indiana field survey iran hardin i 38l'
    );
    fireEvent.change(screen.getByRole('combobox', { name: 'Query category' }), {
      target: { value: 'People & institutions' },
    });
    fireEvent.change(
      screen.getByRole('combobox', { name: 'Reporting month' }),
      { target: { value: '2026-07' } }
    );
    expect(
      screen.getByRole('combobox', { name: 'Query category' })
    ).toHaveValue('all');
    expect(
      within(
        screen.getByRole('table', { name: 'July 2026 top 50 searches' })
      ).getAllByRole('row')
    ).toHaveLength(51);
  });

  it('shows expanded zero-result queries and facet usage for each month', () => {
    renderPage('discovery');
    expect(
      screen.getByRole('heading', { name: 'Searches', level: 1 })
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
        screen.getByRole('region', { name: 'Zero-result queries' })
      ).getAllByRole('row')
    ).toHaveLength(101);
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
        screen.getByRole('region', { name: 'Zero-result queries' })
      ).getAllByRole('row')
    ).toHaveLength(101);
    expect(screen.getByRole('link', { name: 'Mut' })).toBeInTheDocument();
    expect(
      screen.getByText(/These 100 queries account for 268/)
    ).toBeInTheDocument();
    expect(within(chart).getByText('1,521')).toBeInTheDocument();
  });

  it('downloads the selected month report snapshot with provenance and member data', () => {
    renderPage('members');
    const readSnapshot = () => {
      const link = screen.getByRole('link', {
        name: 'Download snapshot (JSON)',
      });
      const href = link.getAttribute('href')!;
      return {
        link,
        data: JSON.parse(decodeURIComponent(href.slice(href.indexOf(',') + 1))),
      };
    };
    const august = readSnapshot();
    expect(august.link).toHaveAttribute('download', 'analytics-2026-08.json');
    expect(august.data.summary.requests).toBe(598931);
    expect(august.data.members.performance).toHaveLength(17);
    expect(august.data.dailyActivity).toHaveLength(31);
    expect(august.data.notes.join(' ')).toContain('not the Provider facet');
    fireEvent.change(
      screen.getByRole('combobox', { name: 'Reporting month' }),
      { target: { value: '2026-07' } }
    );
    const july = readSnapshot();
    expect(july.link).toHaveAttribute('download', 'analytics-2026-07.json');
    expect(july.data.month).toBe('2026-07');
    expect(july.data.summary.requests).toBe(613131);
  });

  it('switches between verified Provider and historical code groups', () => {
    renderPage('members');
    expect(
      screen.getByRole('region', { name: 'Sources and grouping' })
    ).toHaveTextContent('Provider');
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
      screen.getByRole('button', { name: /Show The Ohio State University/ })
    ).toBeInTheDocument();
  });

  it('falls back to overview for an unknown report', () => {
    renderPage('unknown');
    expect(
      screen.getByRole('heading', { name: 'Monthly analytics dashboard' })
    ).toBeInTheDocument();
  });

  it('filters the report to a campus and restores the alliance view', () => {
    renderPage();

    expect(
      screen.getByText(/Activity period: July 1–31, 2026/)
    ).toHaveTextContent('as of August 20, 2026');
    const chicagoFilter = screen.getByRole('button', {
      name: 'Show University of Chicago July report',
    });
    expect(chicagoFilter).toHaveAttribute('aria-pressed', 'false');

    fireEvent.click(chicagoFilter);

    expect(chicagoFilter).toHaveAttribute('aria-pressed', 'true');
    expect(
      screen.getByRole('heading', {
        name: 'University of Chicago',
        level: 3,
      })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: 'Browse Chicago content' })
    ).toHaveAttribute(
      'href',
      '/search?include_filters%5Bb1g_code_s%5D%5B%5D=12'
    );
    expect(
      screen.getByRole('link', { name: 'Survey of Egypt: El Bagur' })
    ).toHaveAttribute('href', '/resources/camel-1013673');
    expect(screen.queryByText(/17 contributing institutions/i)).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: 'All BTAA' }));

    expect(
      screen.getByRole('heading', {
        name: 'All BTAA member content',
        level: 3,
      })
    ).toBeInTheDocument();
    expect(screen.getByText(/17 contributing institutions/i)).toBeVisible();
  });

  it('explains when a campus had no direct download-link clicks', () => {
    renderPage();

    fireEvent.click(
      screen.getByRole('button', {
        name: 'Show University of Oregon July report',
      })
    );

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
        screen.getByRole('region', { name: 'Sources and grouping' })
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
    const audience = screen.getByRole('region', {
      name: 'Audience and discovery coverage',
    });
    expect(within(audience).getByText('13,020')).toBeInTheDocument();
    expect(within(audience).getAllByText('Unavailable')).toHaveLength(2);
    expect(
      within(audience).getByText(/71 records lack a visit token/)
    ).toBeInTheDocument();
    fireEvent.click(within(audience).getByText('Daily audience values'));
    const details = within(audience)
      .getByText('Daily audience values')
      .closest('details')!;
    details.open = true;
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

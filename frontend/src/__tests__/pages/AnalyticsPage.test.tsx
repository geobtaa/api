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
  function renderPage(report = 'members') {
    window.history.replaceState({}, '', `/analytics?report=${report}`);
    return render(
      <HelmetProvider>
        <BrowserRouter>
          <AnalyticsPage />
        </BrowserRouter>
      </HelmetProvider>
    );
  }

  it('shows an overview and navigates between focused reports', () => {
    renderPage('overview');
    expect(
      screen.getByRole('heading', {
        name: 'Monthly analytics dashboard',
        level: 1,
      })
    ).toBeInTheDocument();
    expect(screen.getByText('598.9K')).toBeInTheDocument();
    expect(screen.queryByTestId('header')).not.toBeInTheDocument();
    expect(screen.queryByRole('searchbox')).not.toBeInTheDocument();
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
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
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
  });

  it('opens popular content directly without unrelated reports', () => {
    renderPage('content');
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

  it('falls back to overview for an unknown report', () => {
    renderPage('unknown');
    expect(
      screen.getByRole('heading', { name: 'Monthly analytics dashboard' })
    ).toBeInTheDocument();
  });

  it('filters the report to a campus and restores the alliance view', () => {
    renderPage();

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
    'comparison',
    'content',
    'members',
    'activity',
    'discovery',
    'platform',
  ])(
    'has no detectable WCAG violations in %s',
    async (report) => {
      const { container } = renderPage(report);
      const results = await axeWithWCAG22(container);

      expect(results.violations).toHaveLength(0);
    },
    15_000
  );

  it('uses the local thumbnail route and falls back to a resource icon', () => {
    renderPage('content');

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

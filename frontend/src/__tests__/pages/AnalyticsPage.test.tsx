import { fireEvent, render, screen } from '@testing-library/react';
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
  function renderPage() {
    return render(
      <HelmetProvider>
        <BrowserRouter>
          <AnalyticsPage />
        </BrowserRouter>
      </HelmetProvider>
    );
  }

  it('renders the July dashboard and ranked catalog links', () => {
    renderPage();

    expect(
      screen.getByRole('heading', {
        name: /monthly analytics dashboard/i,
        level: 1,
      })
    ).toBeInTheDocument();
    expect(screen.getByText('613.1K')).toBeInTheDocument();
    expect(
      screen.getAllByRole('link', {
        name: 'Emporium, Pennsylvania, 1892',
      })[0]
    ).toHaveAttribute(
      'href',
      '/resources/95dcf338-fc27-4d3b-8883-967b3223933b'
    );
    expect(
      screen.getByRole('link', { name: 'Urban Base Layers Collection' })
    ).toHaveAttribute('href', '/resources/b1g_urbanBaseLayers');
    expect(screen.getByTestId('activity-chart')).toBeInTheDocument();
    expect(screen.getByTestId('member-activity-chart')).toBeInTheDocument();
    expect(screen.getByText('99.997%')).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: 'Top zero-result queries' })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: '14.271281, 44.702708' })
    ).toHaveAttribute('href', '/search?q=14.271281%2C%2044.702708');
    expect(
      screen.getByText(/758 zero-result searches included query text/i)
    ).toBeInTheDocument();
    expect(
      screen.getAllByRole('link', {
        name: "Map of Home Owners' Loan Corporation [Los Angeles, California] {1939}",
      })[0]
    ).toHaveAttribute(
      'href',
      '/resources/2f3c06da-21a0-410f-b230-be07165aeb89'
    );
    expect(
      screen.getByRole('heading', { name: 'API requests and reliability' })
    ).toBeInTheDocument();
    expect(screen.getByText('Turnstile status checks')).toBeInTheDocument();
    expect(screen.getByText(/84.1% of the peak/i)).toBeInTheDocument();
    expect(
      screen.getByRole('heading', {
        name: 'How BTAA member content performed',
      })
    ).toBeInTheDocument();
    expect(
      screen.getByText(/69\.4% of search impressions/i)
    ).toBeInTheDocument();
    expect(screen.getByText(/64\.8% of portal views/i)).toBeInTheDocument();
    expect(
      screen.getByText(/63\.1% of all download clicks/i)
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Chicago' })).toHaveAttribute(
      'href',
      '/search?include_filters%5Bb1g_code_s%5D%5B%5D=12'
    );
    expect(
      screen.getAllByRole('link', {
        name: /KH-4a: Declassified Satellite Imagery/i,
      })[0]
    ).toHaveAttribute('href', '/resources/camel-1022954');
    expect(screen.getByText(/17 contributing institutions/i)).toBeVisible();
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

  it('has no detectable WCAG 2.2 A or AA violations', async () => {
    const { container } = renderPage();
    const results = await axeWithWCAG22(container);

    expect(results.violations).toHaveLength(0);
  }, 15_000);

  it('uses the local thumbnail route and falls back to a resource icon', () => {
    renderPage();

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

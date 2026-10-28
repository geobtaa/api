import { renderAnalytics as render } from '../utils/renderAnalytics';
import { screen } from '@testing-library/react';
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

// Navigation observers have their own component and accessibility coverage.
// Keep page/report audits independent of DOM measurement side effects.
vi.mock('../../components/analytics/ReportContentLayout', () => ({
  ReportContentLayout: ({ children }: { children: ReactNode }) => (
    <div>{children}</div>
  ),
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

describe('AnalyticsPage accessibility', () => {
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
});

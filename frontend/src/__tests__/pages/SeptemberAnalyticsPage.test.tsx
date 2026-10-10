import { fireEvent, render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router';
import { HelmetProvider } from 'react-helmet-async';
import type { ReactNode } from 'react';
import { vi } from 'vitest';
import { AnalyticsPage } from '../../pages/AnalyticsPage';

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

import { september } from '../../data/analytics/september2026';
import cumulative from '../../data/analytics/allTimeThroughSeptember2026.json';

describe(
  'September in the established dashboard design',
  { timeout: 30000 },
  () => {
    function page(report = 'overview', month = '2026-09') {
      window.history.replaceState(
        {},
        '',
        `/analytics?report=${report}&month=${month}`
      );
      return render(
        <HelmetProvider>
          <BrowserRouter>
            <AnalyticsPage />
          </BrowserRouter>
        </HelmetProvider>
      );
    }
    it('retains the overview layout, metric control, and report download', () => {
      const { container } = page();
      expect(
        screen.getByRole('heading', { name: 'Analytics dashboard' })
      ).toBeInTheDocument();
      expect(
        screen.getByLabelText('September 2026 highlights')
      ).toHaveTextContent('10.5K');
      expect(screen.getByLabelText('Reporting month')).toHaveValue('2026-09');
      expect(
        screen.getByLabelText('Overview chart metric')
      ).toBeInTheDocument();
      expect(
        container.querySelector('.analytics-overview-details table')
      ).not.toBeNull();
      expect(
        screen.getByRole('link', {
          name: 'Download full report (CSV and JSON)',
        })
      ).toHaveAttribute('href', expect.stringContaining('/2026-09/'));
    });
    it.each(['members', 'content', 'discovery', 'clients', 'platform'])(
      'renders the existing %s report for September',
      (report) => {
        const { container } = page(report);
        expect(container.querySelector('.analytics-panel')).not.toBeNull();
        expect(container.querySelector('table')).not.toBeNull();
        expect(container.textContent).not.toContain('NaN');
        expect(container.textContent).not.toContain('September 31');
        if (report === 'members') {
          expect(
            screen.getByRole('button', { name: 'All BTAA' })
          ).toBeInTheDocument();
          expect(september.members).toHaveLength(17);
        }
        if (report === 'content')
          expect(container.querySelector('img')).not.toBeNull();
      }
    );
    it('switches to cumulative coverage without replacing the overview', () => {
      const { container } = page();
      fireEvent.change(screen.getByLabelText('Reporting month'), {
        target: { value: 'all' },
      });
      expect(
        screen.getByRole('heading', { name: 'Analytics dashboard' })
      ).toBeInTheDocument();
      expect(container.textContent).toContain('September 30, 2026');
      expect(
        screen.getByLabelText('Overview chart metric')
      ).toBeInTheDocument();
    });
    it('reconciles all daily totals and includes exactly 30 September dates', () => {
      expect(september.dailyActivity).toHaveLength(30);
      expect(september.dailyActivity.at(-1)?.day).toBe('2026-09-30');
      for (const metric of ['requests', 'searches', 'events'] as const) {
        expect(
          september.dailyActivity.reduce((sum, day) => sum + day[metric], 0)
        ).toBe(september.summary[metric]);
      }
      expect(cumulative.daily).toHaveLength(92);
      expect(cumulative.daily.reduce((sum, day) => sum + day.requests, 0)).toBe(
        1687970
      );
      expect(cumulative.daily.reduce((sum, day) => sum + day.searches, 0)).toBe(
        19538
      );
      expect(
        september.requestMix.reduce((sum, row) => sum + row.count, 0)
      ).toBe(475908);
      expect(september.summary.uniqueEngagedVisits).toBe(7101);
      for (const member of september.members) {
        expect(
          september.memberDailySeries[member.code].views.reduce(
            (a, b) => a + b,
            0
          )
        ).toBe(member.resourceViews);
        expect(
          september.memberDailySeries[member.code].downloads.reduce(
            (a, b) => a + b,
            0
          )
        ).toBe(member.downloadClicks);
      }
    });
  }
);

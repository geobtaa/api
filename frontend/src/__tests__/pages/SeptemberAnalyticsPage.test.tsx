// @vitest-environment jsdom
// Large analytics DOMs make happy-dom role queries exceed the CI timeout.
import { renderAnalytics as render } from '../utils/renderAnalytics';
import { fireEvent, screen, within } from '@testing-library/react';
import { AnalyticsTestRouter as BrowserRouter } from '../utils/AnalyticsTestRouter';
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
        `/analytics${report === 'overview' ? '' : `/${report}`}?month=${month}`
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
          name: 'Download report data (CSV and JSON)',
        })
      ).toHaveAttribute('href', expect.stringContaining('/2026-09/'));
    });
    it('shows the real PennPilot title and labels its empty Provider field precisely', () => {
      const { container } = page('content');
      const resource = Array.from(
        container.querySelectorAll('#top-resources .analytics-ranking-item')
      ).find((row) =>
        row.textContent?.includes(
          'PennPilot (Historical Aerial Photo Library) [Pennsylvania]'
        )
      );
      expect(resource).toBeDefined();
      expect(resource).toHaveTextContent('Provider not recorded');
      expect(resource).not.toHaveTextContent('Unmapped');
      expect(resource?.querySelector('h3 a')).toHaveAttribute(
        'href',
        '/resources/pasda-1078'
      );
    });
    it.each(['members', 'content', 'discovery', 'clients', 'platform'])(
      'renders the existing %s report for September',
      (report) => {
        const { container } = page(report);
        expect(container.querySelector('.analytics-panel')).not.toBeNull();
        if (report !== 'members')
          expect(container.querySelector('table')).not.toBeNull();
        expect(container.textContent).not.toContain('NaN');
        expect(container.textContent).not.toContain('September 31');
        if (report === 'members') {
          expect(
            screen.getByRole('button', { name: /All BTAA Change institution/ })
          ).toBeInTheDocument();
          expect(september.members).toHaveLength(17);
        }
        if (report === 'content')
          expect(container.querySelector('img')).not.toBeNull();
      }
    );
    it('shows views and access clicks after the content rankings and follows the period', () => {
      const { container } = page('content', 'all');
      const section = screen
        .getByRole('heading', { name: 'Views and access clicks' })
        .closest('section')!;
      expect(within(section).getByText('Experimental')).toBeInTheDocument();
      expect(
        within(section).getByText('Temporary disclaimer')
      ).toBeInTheDocument();
      const lists = within(section).getAllByRole('list');
      expect(lists).toHaveLength(2);
      for (const list of lists)
        expect(within(list).getAllByRole('listitem')).toHaveLength(5);
      const example = within(section)
        .getByRole('link', { name: 'Rivers, Nepal, 2013' })
        .closest('li')!;
      expect(
        within(example)
          .getAllByRole('definition')
          .map((row) => row.textContent)
      ).toEqual(['57', '1', '25', '45.6%']);
      const outlinks = container.querySelector('#outlinked-resources');
      expect(outlinks).not.toBeNull();
      expect(
        outlinks!.compareDocumentPosition(section) &
          Node.DOCUMENT_POSITION_FOLLOWING
      ).toBeTruthy();
      fireEvent.change(
        screen.getByRole('combobox', { name: 'Reporting period' }),
        { target: { value: '2026-09' } }
      );
      expect(
        screen.getByRole('heading', { name: 'Views and access clicks' })
      ).toBeInTheDocument();
      expect(
        screen.getByText(
          /Combined views and access-click counts are unavailable/
        )
      ).toBeInTheDocument();
      expect(
        screen.queryByRole('heading', { name: 'More access clicks per view' })
      ).not.toBeInTheDocument();
    });
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
    it.each([
      ['2026-07', 50],
      ['2026-08', 50],
      ['2026-09', 50],
      ['all', 50],
    ] as const)(
      'shows the Top 50 in all Popular content sections for %s',
      (month, collections) => {
        const { container } = page('content', month);
        expect(
          container.querySelectorAll('#top-resources .analytics-ranking-item')
            .length
        ).toBe(50);
        expect(
          container.querySelectorAll('#collections .analytics-ranking-item')
            .length
        ).toBe(collections);
        expect(
          container.querySelectorAll('#downloads .analytics-ranking-item')
            .length
        ).toBe(50);
        expect(
          container.querySelectorAll(
            '#outlinked-resources .analytics-ranking-item'
          ).length
        ).toBe(50);
      }
    );
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

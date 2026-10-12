import { render, screen, within } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import type { ReactNode } from 'react';

vi.mock(
  '../../../public/analytics-reports/manifest.json',
  async (importOriginal) => {
    const { default: original } = await importOriginal<{
      default: typeof import('../../../public/analytics-reports/manifest.json');
    }>();
    return {
      default: {
        ...original,
        latest: '2026-10',
        periods: [...original.periods, { id: '2026-10' }],
      },
    };
  }
);
vi.mock(
  '../../data/analytics/monthlySnapshots.json',
  async (importOriginal) => {
    const { default: original } = await importOriginal<{
      default: typeof import('../../data/analytics/monthlySnapshots.json');
    }>();
    const october = {
      ...original['2026-09'],
      summary: { ...original['2026-09'].summary, month: 'October 2026' },
      dailyActivity: [
        ...original['2026-09'].dailyActivity,
        { day: '2026-10-31', requests: 0, searches: 0, events: 0 },
      ],
    };
    return { default: { ...original, '2026-10': october } };
  }
);
vi.mock('recharts', () => ({
  Bar: () => null,
  Legend: () => null,
  BarChart: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  CartesianGrid: () => null,
  ResponsiveContainer: ({ children }: { children: ReactNode }) => (
    <div>{children}</div>
  ),
  Tooltip: () => null,
  XAxis: () => null,
  YAxis: () => null,
}));
import { ReportingPeriodPicker } from '../../components/analytics/ReportingPeriodPicker';
import { MonthlyComparison } from '../../components/analytics/MonthlyComparison';
import { selectedAnalyticsReport } from '../../config/analyticsReports';

it('adds a fourth month to navigation, defaults, comparisons, and daily columns', () => {
  expect(selectedAnalyticsReport(new URLSearchParams()).period).toBe(
    'October 2026'
  );
  render(
    <>
      <ReportingPeriodPicker id="month" value="2026-10" onChange={() => {}} />
      <MonthlyComparison />
    </>
  );
  expect(
    screen.getByRole('option', { name: 'October 2026' })
  ).toBeInTheDocument();
  expect(
    screen.getByText('October compared with September')
  ).toBeInTheDocument();
  const table = screen.getByRole('table', { name: /portal totals/i });
  expect(
    within(table).getByRole('columnheader', { name: 'October 2026' })
  ).toBeInTheDocument();
  expect(
    within(table).getByRole('columnheader', { name: 'September 2026' })
  ).toBeInTheDocument();
});

import { fireEvent, render, screen, within } from '@testing-library/react';
import type { ReactNode } from 'react';
import { vi } from 'vitest';
import { MonthlyComparison } from '../../components/analytics/MonthlyComparison';
import {
  AUGUST_2026_SUMMARY,
  augustDailyActivity,
  augustMemberPerformance,
} from '../../data/analytics/august2026';
import { memberPerformance } from '../../data/analytics/july2026';
import { comparisonChange } from '../../utils/analyticsComparison';

vi.mock('recharts', () => ({
  Line: () => null,
  LineChart: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  CartesianGrid: () => null,
  ResponsiveContainer: ({ children }: { children: ReactNode }) => (
    <div>{children}</div>
  ),
  Tooltip: () => null,
  XAxis: () => null,
  YAxis: () => null,
}));

describe('MonthlyComparison', () => {
  it('reports verified totals, changes, and CSV data', () => {
    render(<MonthlyComparison />);
    const table = screen.getByRole('table', { name: /portal totals/i });
    const views = within(table).getByRole('row', { name: /Resource views/ });
    expect(views).toHaveTextContent('12,200');
    expect(views).toHaveTextContent('17,440');
    expect(views).toHaveTextContent('+5,240');
    expect(views).toHaveTextContent('+43.0%');
    expect(
      within(table).getByRole('row', { name: /Download clicks/ })
    ).toHaveTextContent('-13.0%');
    const link = screen.getByRole('link', { name: /Download comparison CSV/ });
    const csv = decodeURIComponent(
      link.getAttribute('href')!.split(',').slice(1).join(',')
    );
    expect(csv).toContain('"Resource views","12200","17440","5240","+43.0%"');
    expect(csv).toContain(
      '"University of Oregon: Download clicks","0","0","0","0.0%"'
    );
    expect(csv.split('\r\n')).toHaveLength(1 + 12 + 17 * 4);
  });

  it('switches daily and member metrics independently', () => {
    render(<MonthlyComparison />);
    fireEvent.change(screen.getByRole('combobox', { name: 'Daily metric' }), {
      target: { value: 'requests' },
    });
    expect(
      screen.getByRole('img', { name: /API requests for July and August/ })
    ).toBeInTheDocument();
    fireEvent.click(screen.getByText('Daily values: API requests'));
    const daily = screen.getByRole('table', { name: /Daily api requests/ });
    expect(within(daily).getAllByRole('row')).toHaveLength(32);
    const dayOne = within(daily).getAllByRole('row')[1];
    expect(dayOne).toHaveTextContent(
      new Intl.NumberFormat('en-US').format(augustDailyActivity[0].requests)
    );
    fireEvent.change(screen.getByRole('combobox', { name: 'Member metric' }), {
      target: { value: 'downloadClicks' },
    });
    const members = screen.getByRole('table', {
      name: /Member download clicks/,
    });
    expect(within(members).getAllByRole('row')).toHaveLength(18);
    expect(
      within(members).getByRole('row', { name: /University of Oregon/ })
    ).toHaveTextContent('0.0%');
    expect(screen.getByRole('combobox', { name: 'Daily metric' })).toHaveValue(
      'requests'
    );
  });

  it('reconciles the snapshot and covers every member and August date', () => {
    expect(augustDailyActivity.map((point) => point.day)).toEqual(
      Array.from(
        { length: 31 },
        (_, index) => `2026-08-${String(index + 1).padStart(2, '0')}`
      )
    );
    for (const metric of ['requests', 'searches', 'events'] as const) {
      expect(
        augustDailyActivity.reduce((sum, point) => sum + point[metric], 0)
      ).toBe(AUGUST_2026_SUMMARY[metric]);
    }
    expect(augustMemberPerformance.map((member) => member.code)).toEqual(
      memberPerformance.map((member) => member.code)
    );
    for (const metric of [
      'resourceViews',
      'downloadClicks',
      'impressions',
    ] as const) {
      expect(
        augustMemberPerformance.reduce((sum, member) => sum + member[metric], 0)
      ).toBeLessThanOrEqual(AUGUST_2026_SUMMARY[metric]);
    }
  });

  it('handles zero baselines without infinite or invented growth', () => {
    expect(comparisonChange(0, 10)).toBe('N/A');
    expect(comparisonChange(0, 0)).toBe('0.0%');
    expect(comparisonChange(10, 0)).toBe('-100.0%');
    expect(comparisonChange(10, 10)).toBe('0.0%');
  });
});

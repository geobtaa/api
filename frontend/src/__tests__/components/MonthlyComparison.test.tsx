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
  Area: () => null,
  Legend: () => null,
  AreaChart: ({ children }: { children: ReactNode }) => <svg>{children}</svg>,
  CartesianGrid: () => null,
  ResponsiveContainer: ({ children }: { children: ReactNode }) => (
    <div>{children}</div>
  ),
  Tooltip: () => null,
  XAxis: () => null,
  YAxis: () => null,
}));

describe('MonthlyComparison', () => {
  it('reports verified totals and changes without export links', () => {
    render(<MonthlyComparison />);
    const table = screen.getByRole('table', { name: /portal totals/i });
    const views = within(table).getByRole('row', { name: /Resource views/ });
    expect(views).toHaveTextContent('12,200');
    expect(views).toHaveTextContent('17,440');
    expect(views).toHaveTextContent('10,497');
    expect(views).toHaveTextContent('-6,943');
    expect(views).toHaveTextContent('-39.8%');
    expect(
      within(table).getByRole('row', { name: /Download clicks/ })
    ).toHaveTextContent('+7.9%');
    expect(
      screen.queryByRole('link', { name: /Download comparison/ })
    ).not.toBeInTheDocument();
    expect(screen.queryByText('Member comparison')).not.toBeInTheDocument();
  });

  it('leads with all-month activity and normalizes by calendar days', () => {
    const { container } = render(<MonthlyComparison />);
    expect(
      screen.getByRole('heading', { name: 'July 2026 – September 2026' })
    ).toBeInTheDocument();
    expect(container.querySelector('.analytics-panel h3')).toHaveTextContent(
      'Monthly activity'
    );
    const chart = screen.getByRole('figure', {
      name: 'Tracked interactions monthly totals',
    });
    expect(chart).toHaveTextContent('21,753');
    fireEvent.change(screen.getByRole('combobox', { name: 'Compare' }), {
      target: { value: 'average' },
    });
    expect(
      screen.getByRole('figure', {
        name: 'Tracked interactions monthly daily averages',
      })
    ).toHaveTextContent('701.7');
    fireEvent.change(
      screen.getByRole('combobox', { name: 'Metric', exact: true }),
      { target: { value: 'requests' } }
    );
    expect(
      screen.getByRole('figure', {
        name: 'API requests monthly daily averages',
      })
    ).toHaveTextContent('19,320.4');
  });

  it('switches daily metrics', () => {
    render(<MonthlyComparison />);
    fireEvent.change(screen.getByRole('combobox', { name: 'Daily metric' }), {
      target: { value: 'requests' },
    });
    expect(
      screen.getByRole('img', {
        name: /API requests for July, August, and September/,
      })
    ).toBeInTheDocument();
    fireEvent.click(screen.getByText('Daily values: API requests'));
    const daily = screen.getByRole('table', { name: /Daily api requests/ });
    expect(within(daily).getAllByRole('row')).toHaveLength(32);
    expect(within(daily).getAllByRole('row')[31]).toHaveTextContent('—');
    const dayOne = within(daily).getAllByRole('row')[1];
    expect(dayOne).toHaveTextContent(
      new Intl.NumberFormat('en-US').format(augustDailyActivity[0].requests)
    );
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

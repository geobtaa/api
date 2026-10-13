import { ArrowDownRight, ArrowUpRight } from 'lucide-react';

export function MomentumBadge({
  value,
  previous,
  label,
}: {
  value: number;
  previous: number | null;
  label: string;
}) {
  const change = previous ? ((value - previous) / previous) * 100 : 0;
  const direction = change > 0 ? 'up' : change < 0 ? 'down' : 'flat';
  const format = new Intl.NumberFormat('en-US');
  return (
    <>
      {previous == null ? (
        <span title="Previous-month history is unavailable">Unavailable</span>
      ) : previous === 0 ? (
        <span title={`No ${label} recorded in the previous month`}>
          No prior activity
        </span>
      ) : (
        <span
          className={`analytics-momentum analytics-momentum--${direction}`}
          title={`${format.format(value)} ${label} this month; ${format.format(previous)} in the previous month. Totals are not adjusted for month length.`}
        >
          {change > 0 ? (
            <ArrowUpRight size={14} aria-hidden />
          ) : change < 0 ? (
            <ArrowDownRight size={14} aria-hidden />
          ) : null}
          {change > 0 ? '+' : ''}
          {change.toFixed(1)}%
        </span>
      )}
      <span>vs prior month</span>
    </>
  );
}

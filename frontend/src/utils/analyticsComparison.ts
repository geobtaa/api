/** Percent change relative to the earlier period; zero has no growth denominator. */
export function comparisonChange(previous: number, current: number): string {
  if (previous === 0) return current === 0 ? '0.0%' : 'N/A';
  const change = ((current - previous) / previous) * 100;
  return `${change > 0 ? '+' : ''}${change.toFixed(1)}%`;
}

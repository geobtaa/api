import manifest from '../../private-analytics-reports/manifest.json';
export const publishedMonths = manifest.periods
  .map((row) => row.id)
  .filter((id) => /^\d{4}-\d{2}$/.test(id))
  .sort();
export const latestMonth = manifest.latest;
const [summaryYear, summaryMonth] = latestMonth.split('-').map(Number);
const summaryStart = new Date(Date.UTC(summaryYear, summaryMonth - 3, 1))
  .toISOString()
  .slice(0, 10);
const summaryEnd = new Date(Date.UTC(summaryYear, summaryMonth, 1))
  .toISOString()
  .slice(0, 10);
// Saved rankings and distinct visits cannot be added across months. The current
// exporter supplies monthly and all-time aggregates, so offer this shortcut only
// while all time matches the latest three calendar months exactly.
export const summaryHasThreeMonths = manifest.periods.some(
  (period) =>
    period.id === 'all' &&
    period.start === summaryStart &&
    period.endExclusive === summaryEnd
);
export function selectedSnapshotPeriod(value: string | null) {
  return value === 'all' || publishedMonths.includes(value ?? '')
    ? value!
    : latestMonth;
}
export function selectedSummaryPeriod(value: string | null) {
  return value && (value === 'all' || publishedMonths.includes(value))
    ? value
    : summaryHasThreeMonths
      ? '3months'
      : latestMonth;
}
export function monthLabel(period: string, short = false) {
  return new Date(`${period}-01T00:00:00Z`).toLocaleDateString('en-US', {
    month: short ? 'short' : 'long',
    year: 'numeric',
    timeZone: 'UTC',
  });
}
export function monthDays(period: string) {
  const [year, month] = period.split('-').map(Number);
  return new Date(Date.UTC(year, month, 0)).getUTCDate();
}
export function periodRange(period: string) {
  return `${monthLabel(period).replace(/ \d{4}$/, '')} 1–${monthDays(period)}, ${period.slice(0, 4)}`;
}
export const comparisonLabel = `${monthLabel(publishedMonths[0])} – ${monthLabel(latestMonth)}`;
export const allTimeRange = `${monthLabel(publishedMonths[0]).replace(/ \d{4}$/, '')} 1, ${publishedMonths[0].slice(0, 4)} – ${monthLabel(latestMonth).replace(/ \d{4}$/, '')} ${monthDays(latestMonth)}, ${latestMonth.slice(0, 4)}`;

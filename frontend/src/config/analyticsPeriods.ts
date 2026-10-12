import manifest from '../../public/analytics-reports/manifest.json';
export const publishedMonths = manifest.periods
  .map((row) => row.id)
  .filter((id) => /^\d{4}-\d{2}$/.test(id))
  .sort();
export const latestMonth = manifest.latest;
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

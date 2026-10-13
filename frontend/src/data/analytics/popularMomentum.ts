import snapshots from './popularMomentumCurrent.json';

type Baseline = Record<
  'collections' | 'downloads' | 'outlinks',
  Record<string, number>
>;
const periods: Record<string, Baseline | null> = snapshots;

export function previousRankingValue(
  period: string | undefined,
  ranking: keyof Baseline,
  id: string | null
) {
  if (!period || period === 'all') return undefined;
  const baseline = periods[period];
  if (!baseline || id == null) return null;
  return baseline[ranking][id] ?? 0;
}

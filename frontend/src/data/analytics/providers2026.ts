import snapshots from './providerSnapshots.json';

export type Counts = {
  catalogRecords: number;
  activeResources: number;
  resourceViews: number;
  downloadClicks: number;
  sourceClicks: number;
  impressions: number;
};
type Top = { id: string; title: string; views: number; downloads: number };
export type ProviderGroup = Counts & {
  id: string;
  provider: string | null;
  daily: { day: number; views: number; downloads: number }[];
  topViews: Top[];
  topDownloads: Top[];
};
export type ProviderSnapshot = {
  month: string;
  catalogSnapshotDate: string;
  exportedAt: string;
  totals: Counts;
  groups: ProviderGroup[];
  codeCoverage: (Counts & { label: string })[];
};
export const providerSnapshots = snapshots as Partial<
  Record<string, ProviderSnapshot>
>;

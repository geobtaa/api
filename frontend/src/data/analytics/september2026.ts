import snapshots from './monthlySnapshots.json';
import type Snapshot from './september2026.json';
import {
  memberPerformance as institutions,
  type CollectionChartEntry,
} from './july2026';
import type { ProviderSnapshot } from './providers2026';
import type { ClientSnapshot } from './clients2026';

export function adaptMonth(snapshot: typeof Snapshot) {
  const groups = snapshot.memberReport.groups.filter(
    (row) => row.grouping === 'code'
  );
  const counts = (row: (typeof groups)[number]) => ({
    catalogRecords: row.inventory,
    activeResources: row.activeResources,
    resourceViews: row.views,
    downloadClicks: row.downloads,
    sourceClicks: row.sourceClicks,
    impressions: row.impressions,
  });
  const members = institutions.map((institution) => {
    const group = groups.find((row) => row.name === institution.name)!;
    return {
      ...institution,
      ...counts(group),
      topResource: group.topViews[0] ?? {
        id: '',
        title: 'No recorded resource views',
      },
    };
  });
  const memberSummary = members.reduce(
    (sum, row) => ({
      catalogRecords: sum.catalogRecords + row.catalogRecords,
      activeResources: sum.activeResources + row.activeResources,
      resourceViews: sum.resourceViews + row.resourceViews,
      downloadClicks: sum.downloadClicks + row.downloadClicks,
      sourceClicks: sum.sourceClicks + row.sourceClicks,
      impressions: sum.impressions + row.impressions,
    }),
    {
      catalogRecords: 0,
      activeResources: 0,
      resourceViews: 0,
      downloadClicks: 0,
      sourceClicks: 0,
      impressions: 0,
    }
  );
  const memberDailySeries = Object.fromEntries(
    institutions.map((institution) => {
      const group = groups.find((row) => row.name === institution.name)!;
      return [
        institution.code,
        {
          views: snapshot.dailyActivity.map(
            (day) => group.daily.find((row) => row.date === day.day)?.views ?? 0
          ),
          downloads: snapshot.dailyActivity.map(
            (day) =>
              group.daily.find((row) => row.date === day.day)?.downloads ?? 0
          ),
        },
      ];
    })
  );
  const memberTopContent = Object.fromEntries(
    institutions.map((institution) => {
      const group = groups.find((row) => row.name === institution.name)!;
      return [
        institution.code,
        { viewed: group.topViews, downloaded: group.topDownloads },
      ];
    })
  );
  return {
    ...snapshot,
    members,
    memberSummary,
    memberDailySeries,
    memberTopContent,
    topCollections: snapshot.topCollections as CollectionChartEntry[],
    provider: snapshot.provider as ProviderSnapshot,
    clients: snapshot.clients as ClientSnapshot,
  };
}
export const monthlySnapshots = Object.fromEntries(
  Object.entries(snapshots).map(([period, snapshot]) => [
    period,
    adaptMonth(snapshot),
  ])
);
export const september = monthlySnapshots['2026-09'];

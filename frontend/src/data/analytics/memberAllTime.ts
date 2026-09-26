import preserved from './memberAllTime2026.json';
import { memberPerformance as institutions } from './july2026';
import type { ProviderSnapshot } from './providers2026';

export const memberDays: string[] = [];
for (
  let date = new Date(`${preserved.start}T00:00:00Z`);
  date < new Date(`${preserved.endExclusive}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + 1)
) {
  memberDays.push(date.toISOString().slice(0, 10));
}
const dateLabel = (date: string) =>
  new Date(`${date}T00:00:00Z`).toLocaleDateString('en-US', {
    month: 'long',
    day: 'numeric',
    year: 'numeric',
    timeZone: 'UTC',
  });
export const memberRange = `${dateLabel(memberDays[0])} – ${dateLabel(memberDays.at(-1)!)}`;
export const memberCatalogDate = dateLabel(
  preserved.catalogCapturedAt.slice(0, 10)
);
const counts = (row: (typeof preserved.groups)[number]) => ({
  catalogRecords: row.inventory,
  activeResources: row.activeResources,
  resourceViews: row.views,
  downloadClicks: row.downloads,
  sourceClicks: row.sourceClicks,
  impressions: row.impressions,
});
const codes = preserved.groups.filter((row) => row.grouping === 'code');
export const allTimeMembers = institutions.map((institution) => {
  const row = codes.find((row) => row.name === institution.name);
  if (!row)
    throw new Error(`Missing preserved member group: ${institution.name}`);
  return {
    ...institution,
    ...counts(row),
    topResource: row.topViews[0] ?? {
      id: '',
      title: 'No recorded resource views',
    },
  };
});
export const allTimeMemberSummary = allTimeMembers.reduce(
  (total, row) => ({
    catalogRecords: total.catalogRecords + row.catalogRecords,
    activeResources: total.activeResources + row.activeResources,
    resourceViews: total.resourceViews + row.resourceViews,
    downloadClicks: total.downloadClicks + row.downloadClicks,
    sourceClicks: total.sourceClicks + row.sourceClicks,
    impressions: total.impressions + row.impressions,
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
export const allTimeMemberDaily = Object.fromEntries(
  institutions.map((institution) => {
    const row = codes.find((row) => row.name === institution.name)!;
    return [
      institution.code,
      {
        views: memberDays.map(
          (date) => row.daily.find((day) => day.date === date)?.views ?? 0
        ),
        downloads: memberDays.map(
          (date) => row.daily.find((day) => day.date === date)?.downloads ?? 0
        ),
      },
    ];
  })
);
export const allTimeMemberContent = Object.fromEntries(
  institutions.map((institution) => {
    const row = codes.find((row) => row.name === institution.name)!;
    return [
      institution.code,
      { viewed: row.topViews, downloaded: row.topDownloads },
    ];
  })
);
const providers = preserved.groups.filter((row) => row.grouping === 'provider');
export const allTimeProviderSnapshot: ProviderSnapshot = {
  month: memberRange,
  catalogSnapshotDate: memberCatalogDate,
  exportedAt: preserved.catalogCapturedAt,
  impressionSource:
    'Preserved period aggregates. A record with multiple Providers contributes to each named Provider, so provider totals overlap. July resource-level impressions were unavailable; preserved attribution and reach cannot recover missing historical evidence.',
  totals: providers.reduce(
    (total, row) => ({
      catalogRecords: total.catalogRecords + row.inventory,
      activeResources: total.activeResources + row.activeResources,
      resourceViews: total.resourceViews + row.views,
      downloadClicks: total.downloadClicks + row.downloads,
      sourceClicks: total.sourceClicks + row.sourceClicks,
      impressions: total.impressions + row.impressions,
    }),
    {
      catalogRecords: 0,
      activeResources: 0,
      resourceViews: 0,
      downloadClicks: 0,
      sourceClicks: 0,
      impressions: 0,
    }
  ),
  groups: providers.map((row) => ({
    ...counts(row),
    id: row.name,
    provider: row.name,
    daily: memberDays.map((date) => ({
      day: date,
      views: row.daily.find((day) => day.date === date)?.views ?? 0,
      downloads: row.daily.find((day) => day.date === date)?.downloads ?? 0,
    })),
    topViews: row.topViews,
    topDownloads: row.topDownloads,
  })),
  codeCoverage: codes.map((row) => ({ ...counts(row), label: row.name })),
};
export const memberPortalTotals = {
  resourceViews: preserved.totals.views,
  downloadClicks: preserved.totals.downloads,
  impressions: preserved.totals.impressions,
  sourceClicks: preserved.totals.sourceClicks,
};

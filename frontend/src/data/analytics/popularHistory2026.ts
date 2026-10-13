import history from './popularHistory2026.json';
import { topResources, topDownloadedResources } from './july2026';
import {
  augustTopResources,
  augustTopDownloadedResources,
} from './popularAugust2026';

// Keep historical detail fields and exact download-visit counts where available,
// while refreshed metadata supplies the resource titles and provider labels.
export const popularHistory = Object.fromEntries(
  Object.entries(history).map(([month, snapshot]) => {
    const resources = month === '2026-07' ? topResources : augustTopResources;
    const downloads =
      month === '2026-07'
        ? topDownloadedResources
        : augustTopDownloadedResources;
    return [
      month,
      {
        ...snapshot,
        topResources: snapshot.topResources.map((row) => ({
          ...resources.find((original) => original.id === row.id),
          ...row,
        })),
        topDownloads: snapshot.topDownloads.map((row) => ({
          ...row,
          engagedVisits:
            downloads.find((original) => original.id === row.id)
              ?.engagedVisits ?? null,
        })),
      },
    ];
  })
);

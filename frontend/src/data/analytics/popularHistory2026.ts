import history from './popularHistory2026.json';
import { topResources, topDownloadedResources } from './july2026';
import {
  augustTopResources,
  augustTopDownloadedResources,
} from './popularAugust2026';

// Retain the original published descriptions and exact download-visit counts
// where available while expanding the rankings from complete preserved inputs.
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
          ...row,
          ...resources.find((original) => original.id === row.id),
        })),
        topDownloads: snapshot.topDownloads.map((row) => ({
          ...row,
          ...downloads.find((original) => original.id === row.id),
        })),
      },
    ];
  })
);

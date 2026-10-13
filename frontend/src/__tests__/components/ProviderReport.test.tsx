import { renderAnalytics as render } from '../utils/renderAnalytics';
import { screen } from '@testing-library/react';
import { AnalyticsTestRouter as MemoryRouter } from '../utils/AnalyticsTestRouter';
import { expect, it, vi } from 'vitest';
import { ProviderReport } from '../../components/analytics/ProviderReport';
import type {
  ProviderGroup,
  ProviderSnapshot,
} from '../../data/analytics/providers2026';
vi.mock(
  'recharts',
  async () => (await import('../utils/analyticsCharts')).analyticsCharts
);
const counts = {
  catalogRecords: 10,
  activeResources: 2,
  resourceViews: 5,
  downloadClicks: 1,
  sourceClicks: 2,
  impressions: 8,
};
const group = (id: string, provider: string | null): ProviderGroup => ({
  ...counts,
  id,
  provider,
  daily: Array.from({ length: 31 }, (_, n) => ({
    day: n + 1,
    views: n === 0 ? 5 : 0,
    downloads: n === 0 ? 1 : 0,
  })),
  topViews: [{ id: 'map-1', title: 'Sample map', views: 5, downloads: 1 }],
  topDownloads: [],
});
const snapshot: ProviderSnapshot = {
  month: '2026-08',
  catalogSnapshotDate: '2026-09-10',
  exportedAt: '2026-09-10',
  totals: {
    catalogRecords: 30,
    activeResources: 6,
    resourceViews: 15,
    downloadClicks: 3,
    sourceClicks: 6,
    impressions: 24,
  },
  groups: [
    group('0', 'The Ohio State University'),
    group('1', 'Franklin County, Ohio'),
    group('2', null),
  ],
  codeCoverage: [],
};
it.each(['all', '0', '2'])(
  'keeps provider scope from the shareable URL: %s',
  (provider) => {
    render(
      <MemoryRouter
        initialEntries={[`/analytics/members?provider=${provider}`]}
      >
        <ProviderReport month="2026-08" snapshot={snapshot} />
      </MemoryRouter>
    );
    if (provider === '0') {
      expect(
        screen.getByRole('link', { name: 'The Ohio State University' })
      ).toHaveAttribute(
        'href',
        '/search?include_filters%5Bschema_provider_s%5D%5B%5D=The+Ohio+State+University'
      );
    } else if (provider === '2') {
      expect(
        screen.queryByRole('link', { name: 'The Ohio State University' })
      ).not.toBeInTheDocument();
    }
    expect(
      screen.queryByRole('link', { name: 'Download provider data' })
    ).not.toBeInTheDocument();
  }
);

it('reconciles every exported provider against coverage and daily counts', async () => {
  const { providerSnapshots } =
    await import('../../data/analytics/providers2026');
  for (const snapshot of Object.values(providerSnapshots)) {
    expect(snapshot).toBeDefined();
    if (!snapshot) continue;
    for (const key of [
      'catalogRecords',
      'resourceViews',
      'downloadClicks',
      'sourceClicks',
      'impressions',
      'activeResources',
    ] as const) {
      if (snapshot.totals[key] === null) {
        expect(snapshot.groups.every((group) => group[key] === null)).toBe(
          true
        );
      } else {
        expect(
          snapshot.groups.reduce((n, group) => n + (group[key] ?? 0), 0)
        ).toBe(snapshot.totals[key]);
        expect(
          snapshot.codeCoverage.reduce((n, group) => n + (group[key] ?? 0), 0)
        ).toBe(snapshot.totals[key]);
      }
    }
    for (const group of snapshot.groups) {
      expect(group.daily.reduce((n, day) => n + day.views, 0)).toBe(
        group.resourceViews
      );
      expect(group.daily.reduce((n, day) => n + day.downloads, 0)).toBe(
        group.downloadClicks
      );
    }
  }
  expect(providerSnapshots['2026-07']?.impressionsAvailable).toBe(true);
  expect(providerSnapshots['2026-07']?.totals.impressions).toBeGreaterThan(0);
  expect(providerSnapshots['2026-07']?.totals.activeResources).toBeGreaterThan(
    0
  );
  expect(
    providerSnapshots['2026-08']?.groups.find(
      (g) => g.provider === 'The Ohio State University'
    )?.catalogRecords
  ).toBe(256);
});

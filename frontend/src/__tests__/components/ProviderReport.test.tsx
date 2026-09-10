import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { expect, it, vi } from 'vitest';
import { ProviderReport } from '../../components/analytics/ProviderReport';
import type {
  ProviderGroup,
  ProviderSnapshot,
} from '../../data/analytics/providers2026';
vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  LineChart: () => <div />,
  CartesianGrid: () => null,
  Line: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
}));
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
it('keeps university, agency, and missing providers separate and exports the selection', () => {
  render(
    <MemoryRouter>
      <ProviderReport month="2026-08" snapshot={snapshot} />
    </MemoryRouter>
  );
  expect(screen.getByLabelText('Provider')).toHaveValue('all');
  fireEvent.change(screen.getByLabelText('Provider'), {
    target: { value: '0' },
  });
  const browse = screen.getByRole('link', { name: 'Browse this provider' });
  expect(browse.getAttribute('href')).toBe(
    '/search?include_filters%5Bschema_provider_s%5D%5B%5D=The+Ohio+State+University'
  );
  const href = screen
    .getByRole('link', { name: 'Download provider data' })
    .getAttribute('href')!;
  const data = JSON.parse(
    decodeURIComponent(href.slice(href.indexOf(',') + 1))
  );
  expect(data.groups).toHaveLength(1);
  expect(data.groups[0].provider).toBe('The Ohio State University');
  expect(data.selectedTotals.resourceViews).toBe(5);
  fireEvent.change(screen.getByLabelText('Provider'), {
    target: { value: '2' },
  });
  expect(
    screen.queryByRole('link', { name: 'Browse this provider' })
  ).not.toBeInTheDocument();
});

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
  expect(providerSnapshots['2026-07']?.totals.impressions).toBeNull();
  expect(
    providerSnapshots['2026-08']?.groups.find(
      (g) => g.provider === 'The Ohio State University'
    )?.catalogRecords
  ).toBe(256);
});

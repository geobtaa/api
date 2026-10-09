import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { afterEach, expect, it, vi } from 'vitest';
import { SnapshotAnalyticsPage } from '../../components/analytics/SnapshotAnalyticsPage';

vi.mock('../../components/analytics/RuntimeAnalyticsPage', () => ({
  RuntimeReportView: ({
    report,
    downloadArchive,
  }: {
    report: { period: string };
    downloadArchive: string;
  }) => <a href={downloadArchive}>Report {report.period}</a>,
}));
const revision = 'a'.repeat(64);
const manifest = {
  schemaVersion: 1,
  latest: '2026-09',
  periods: ['2026-09', 'all'].map((id) => ({ id, revision })),
};
function mockFetch() {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => ({
      ok: true,
      json: async () =>
        url.endsWith('manifest.json')
          ? manifest
          : {
              schemaVersion: 1,
              revision,
              period: url.includes('/all/') ? 'all' : '2026-09',
            },
    }))
  );
}
afterEach(() => vi.unstubAllGlobals());
it('defaults to September, downloads the exact revision, and switches to cumulative totals', async () => {
  mockFetch();
  render(
    <MemoryRouter initialEntries={['/analytics']}>
      <SnapshotAnalyticsPage />
    </MemoryRouter>
  );
  expect(await screen.findByText('Report 2026-09')).toHaveAttribute(
    'href',
    `/analytics-reports/2026-09/${revision}/tables.zip`
  );
  expect(screen.getByRole('combobox')).toHaveValue('2026-09');
  expect(
    screen.getByRole('option', { name: 'August 2026' })
  ).toBeInTheDocument();
  fireEvent.change(screen.getByRole('combobox'), { target: { value: 'all' } });
  expect(await screen.findByText('Report all')).toHaveAttribute(
    'href',
    `/analytics-reports/all/${revision}/tables.zip`
  );
  expect(
    screen.getByText('July 1–September 30, 2026 (UTC)')
  ).toBeInTheDocument();
});
it('compares all three months even when linked from September', async () => {
  mockFetch();
  render(
    <MemoryRouter
      initialEntries={['/analytics?report=comparison&month=2026-09']}
    >
      <SnapshotAnalyticsPage />
    </MemoryRouter>
  );
  expect(await screen.findByText('Report all')).toBeInTheDocument();
  expect(screen.getByText('July–September 2026')).toBeInTheDocument();
});
it('shows an error instead of silently substituting mismatched report data', async () => {
  vi.stubGlobal(
    'fetch',
    vi
      .fn()
      .mockResolvedValueOnce({ ok: true, json: async () => manifest })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          schemaVersion: 1,
          revision: 'wrong',
          period: '2026-09',
        }),
      })
  );
  render(
    <MemoryRouter>
      <SnapshotAnalyticsPage />
    </MemoryRouter>
  );
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Report version mismatch'
  );
});

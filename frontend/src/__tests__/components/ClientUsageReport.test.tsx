import { render, screen, within } from '@testing-library/react';
import { ClientUsageReport } from '../../components/analytics/ClientUsageReport';
import {
  clientSnapshots,
  combineClientSnapshots,
} from '../../data/analytics/clients2026';
import { JULY_2026_SUMMARY } from '../../data/analytics/july2026';
import { AUGUST_2026_SUMMARY } from '../../data/analytics/august2026';

describe('Client usage report', () => {
  it('shows declared clients separately from endpoint signals and missing key attribution', () => {
    render(<ClientUsageReport month="2026-08" />);
    const clients = screen.getByRole('table', {
      name: 'August 2026 declared client usage',
    });
    const web = within(clients).getByRole('row', { name: /geoportal-web/ });
    expect(web).toHaveTextContent('644');
    expect(web).toHaveTextContent('7,545');
    expect(web).toHaveTextContent('21,753');
    expect(screen.getByText('0.14% attribution coverage')).toBeInTheDocument();
    const signals = screen.getByRole('table', {
      name: /MCP and QGIS request signals/,
    });
    expect(
      within(signals).getByRole('row', { name: /MCP endpoint traffic/ })
    ).toHaveTextContent('43');
    expect(
      within(signals).getByRole('row', { name: /QGIS user-agent match/ })
    ).toHaveTextContent('0');
    expect(screen.getByText(/No API-key IDs were recorded/)).toHaveTextContent(
      'does not mean that no keys were configured or used'
    );
    const keyTable = screen.getByRole('table', {
      name: /API key attribution coverage/,
    });
    expect(
      within(keyTable).getByRole('row', {
        name: /No API key attribution recorded/,
      })
    ).toHaveTextContent('598,931');
    expect(
      screen.queryByRole('link', { name: 'Download client CSV' })
    ).not.toBeInTheDocument();
  });

  it('distinguishes unavailable July user-agent evidence from zero observed signals', () => {
    render(<ClientUsageReport month="2026-07" />);
    const signals = screen.getByRole('table', {
      name: /MCP and QGIS request signals/,
    });
    expect(
      within(signals).getByRole('row', { name: /QGIS user-agent match/ })
    ).toHaveTextContent('Not available');
    expect(screen.getByText('codex-research-workbook')).toBeInTheDocument();
    expect(screen.queryByText('geoportal-ssr')).not.toBeInTheDocument();
  });

  it('reconciles each independent breakdown with the preserved monthly totals', () => {
    for (const [month, summary] of [
      ['2026-07', JULY_2026_SUMMARY],
      ['2026-08', AUGUST_2026_SUMMARY],
    ] as const) {
      const snapshot = clientSnapshots[month];
      for (const key of ['requests', 'searches', 'events'] as const) {
        expect(snapshot.clients.reduce((sum, row) => sum + row[key], 0)).toBe(
          summary[key]
        );
      }
      expect(
        snapshot.surfaces.reduce((sum, row) => sum + row.requests, 0)
      ).toBe(summary.requests);
      expect(
        snapshot.keyAttributedRequests + snapshot.unattributedKeyRequests
      ).toBe(summary.requests);
    }
  });
});

it('combines client/channel pairs and surfaces while retaining unavailable evidence', () => {
  const combined = combineClientSnapshots(Object.values(clientSnapshots));
  expect(combined.clients.reduce((n, row) => n + row.requests, 0)).toBe(
    1212062
  );
  expect(combined.surfaces.reduce((n, row) => n + row.requests, 0)).toBe(
    1212062
  );
  expect(
    combined.clients.find((row) => row.name === 'geoportal-web')
  ).toMatchObject({ requests: 1575, searches: 14002, events: 38577 });
  expect(combined.qgisUserAgentRequests).toBeNull();
  expect(combined.recordedKeys).toBe(0);
  expect(
    combineClientSnapshots([{ ...clientSnapshots['2026-08'], recordedKeys: 2 }])
      .recordedKeys
  ).toBeNull();
});

it('shows full-period attribution and unavailable QGIS evidence in the shared tables', () => {
  render(<ClientUsageReport month="all" />);
  expect(screen.getAllByRole('table')).toHaveLength(4);
  const signals = screen.getByRole('table', {
    name: /MCP and QGIS request signals/,
  });
  expect(
    within(signals).getByRole('row', { name: /QGIS user-agent match/ })
  ).toHaveTextContent('Not available');
  const clients = screen.getByRole('table', {
    name: 'All time declared client usage',
  });
  expect(
    within(clients).getByRole('row', { name: /geoportal-web/ })
  ).toHaveTextContent('1,575');
});

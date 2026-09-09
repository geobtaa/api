import { render, screen, within } from '@testing-library/react';
import { ClientUsageReport } from '../../components/analytics/ClientUsageReport';
import { clientSnapshots } from '../../data/analytics/clients2026';
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
    const csvLink = screen.getByRole('link', { name: 'Download client CSV' });
    const csv = decodeURIComponent(
      csvLink.getAttribute('href')!.split(',').slice(1).join(',')
    );
    expect(csv).toContain('"geoportal-ssr","ssr","196","0","0"');
    expect(csvLink).toHaveAttribute('download', 'api-clients-2026-08.csv');
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

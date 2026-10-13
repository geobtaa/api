// @vitest-environment jsdom
import { screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { axe } from 'vitest-axe';
import { renderAnalytics } from '../utils/renderAnalytics';
import { ReportSources } from '../../components/analytics/ReportSources';
import { ReportProvenance } from '../../components/analytics/ReportProvenance';
import manifest from '../../../private-analytics-reports/manifest.json';

describe('report provenance', () => {
  it.each(manifest.periods)(
    'discloses coverage and links the exact evidence revision for $id',
    async (entry) => {
      const { container } = renderAnalytics(
        <ReportSources
          report="overview"
          month="September"
          snapshotPeriod={entry.id}
        />
      );
      const panel = within(
        screen.getByRole('region', { name: 'Data provenance and coverage' })
      );
      expect(
        panel.getByText(
          entry.complete
            ? 'Recorded source coverage is complete.'
            : 'Historical coverage is partial.'
        )
      ).toBeInTheDocument();
      const details = panel
        .getByText('View verification details')
        .closest('details');
      expect(details).not.toHaveAttribute('open');
      details?.setAttribute('open', '');
      expect(
        panel.getByRole('link', { name: 'Download report evidence packet' })
      ).toHaveAttribute(
        'href',
        `/analytics-reports/${entry.id}/${entry.revision}/evidence-${entry.evidence.checksum}.zip`
      );
      expect(
        panel.getByText(/Independent baseline evidence/)
      ).toHaveTextContent('not verified');
      expect(panel.getByText(/detailed rankings/)).toHaveTextContent(
        'require separate evidence'
      );
      expect(
        panel.getByText(/Daily totals reconcile with preserved records/)
      ).toHaveTextContent('6 aggregate metrics');
      expect((await axe(container)).violations).toEqual([]);
    }
  );

  it('uses cumulative evidence on the month comparison page', () => {
    renderAnalytics(
      <ReportSources
        report="comparison"
        month="September"
        snapshotPeriod="2026-09"
      />
    );
    screen
      .getByText('View verification details')
      .closest('details')
      ?.setAttribute('open', '');
    expect(
      screen.getByRole('link', { name: 'Download report evidence packet' })
    ).toHaveAttribute('href', expect.stringContaining('/all/'));
    expect(
      screen.getByText('Historical coverage is partial.')
    ).toBeInTheDocument();
  });

  it('does not invent verification or download links for missing evidence', () => {
    renderAnalytics(
      <ReportProvenance
        report={{
          revision: 'a'.repeat(64),
          start: '2026-09-01',
          endExclusive: '2026-10-01',
          complete: false,
        }}
      />
    );
    expect(
      screen.queryByText(/Daily totals reconcile with preserved records/)
    ).not.toBeInTheDocument();
    expect(screen.queryByRole('link')).not.toBeInTheDocument();
    expect(
      screen.getByText('An evidence packet is not available for this revision.')
    ).toBeInTheDocument();
  });
});

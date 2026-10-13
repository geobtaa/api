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
        screen.getByRole('region', { name: 'Understanding these numbers' })
      );
      expect(
        panel.getByText(
          entry.complete
            ? 'Source records cover the full reporting period.'
            : 'Some historical source records are missing.'
        )
      ).toBeInTheDocument();
      const details = panel
        .getByText('How these numbers were checked')
        .closest('details');
      expect(details).not.toHaveAttribute('open');
      details?.setAttribute('open', '');
      expect(
        panel.getByRole('link', {
          name: 'Download supporting records and checks',
        })
      ).toHaveAttribute(
        'href',
        `/analytics-reports/${entry.id}/${entry.revision}/evidence-${entry.evidence.checksum}.zip`
      );
      expect(panel.getByText(/They do not compare/)).toHaveTextContent(
        'do not compare'
      );
      expect(panel.getByText(/Resource rankings/)).toHaveTextContent(
        'need their own supporting records and checks'
      );
      expect(panel.getByText(/The daily counts add up/)).toHaveTextContent(
        '6 measures'
      );
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
      .getByText('How these numbers were checked')
      .closest('details')
      ?.setAttribute('open', '');
    expect(
      screen.getByRole('link', {
        name: 'Download supporting records and checks',
      })
    ).toHaveAttribute('href', expect.stringContaining('/all/'));
    expect(
      screen.getByText('Some historical source records are missing.')
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
      screen.getByText(/September 1, 2026 through September 30, 2026/)
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/The daily counts add up/)
    ).not.toBeInTheDocument();
    expect(screen.queryByRole('link')).not.toBeInTheDocument();
    expect(
      screen.getByText(
        'Supporting records are not available to download for this report version.'
      )
    ).toBeInTheDocument();
  });
});

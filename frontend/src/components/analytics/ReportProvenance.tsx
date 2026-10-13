import { BookOpen } from 'lucide-react';
import { ReportPanelHeader } from './ReportPanelHeader';

type Evidence = {
  checksum: string;
  preservedInputReplay: string;
  reconciledMetrics: string[];
};

type ProvenanceReport = {
  revision: string;
  start: string;
  endExclusive: string;
  complete: boolean;
  evidence?: Evidence;
};

export function ReportProvenance({
  report,
  downloadUrl,
}: {
  report: ProvenanceReport;
  downloadUrl?: string;
}) {
  const dateFormat = new Intl.DateTimeFormat('en-US', {
    month: 'long',
    day: 'numeric',
    year: 'numeric',
    timeZone: 'UTC',
  });
  const firstDay = dateFormat.format(new Date(`${report.start}T00:00:00Z`));
  const lastDay = dateFormat.format(
    new Date(new Date(`${report.endExclusive}T00:00:00Z`).getTime() - 86400000)
  );
  return (
    <section
      className="analytics-panel analytics-report-sources"
      id="report-provenance"
      aria-label="Understanding these numbers"
    >
      <ReportPanelHeader
        title="Understanding these numbers"
        icon={BookOpen}
        level={2}
      />
      <p>
        <strong>
          {report.complete
            ? 'Source records cover the full reporting period.'
            : 'Some historical source records are missing.'}
        </strong>{' '}
        {report.evidence && 'Report totals match the records we have saved. '}
        {report.complete
          ? 'This does not mean every use of the Geoportal was recorded.'
          : 'We cannot fully verify activity for the portions of the period with missing records.'}
      </p>
      <details>
        <summary>How these numbers were checked</summary>
        <p>
          <strong>Reporting period:</strong> {firstDay} through {lastDay},
          including both dates. Days are measured in Coordinated Universal Time
          (UTC), so activity near midnight may fall on a different date than it
          does locally.
        </p>
        {report.evidence && (
          <p>
            <strong>What we checked:</strong> The daily counts add up to the
            report totals for {report.evidence.reconciledMetrics.length}{' '}
            measures.{' '}
            {report.evidence.preservedInputReplay === 'passed'
              ? 'Recalculating those totals from the saved source records produced the same results.'
              : 'Recalculation from the saved source records has not been verified for this report.'}
          </p>
        )}
        <p>
          <strong>What these checks do not establish:</strong> They do not
          compare the report with an independent record of activity or confirm
          that the live system is saving all the records needed for future
          checks. They apply to the overall totals. Resource rankings, activity
          assigned to institutions, categories of API users and applications,
          and other dashboard figures need their own supporting records and
          checks.
        </p>
        <p>
          <strong>How to interpret the figures:</strong>
        </p>
        <ul>
          <li>
            These counts describe recorded activity, not the total number of
            people served.
          </li>
          <li>
            A download click shows that someone selected a download link; it
            does not confirm that a file was received.
          </li>
          <li>
            Visits are estimates, not counts of individual people. Use the
            estimate for the full reporting period in the downloaded report;
            adding daily estimates can count the same visit more than once.
          </li>
          <li>
            Resources are assigned to institutions using the catalog information
            saved with the report. Those assignments may differ from the catalog
            at the end of the month.
          </li>
        </ul>
        <details>
          <summary>Technical identifiers for this report</summary>
          <p>
            These identifiers help technical staff find the exact report and
            supporting files used for a review. They can reveal whether the
            files have changed, but do not prove the figures are accurate.
          </p>
          <p style={{ overflowWrap: 'anywhere' }}>
            Report version: <code>{report.revision}</code>
          </p>
          {report.evidence && (
            <p style={{ overflowWrap: 'anywhere' }}>
              Supporting-file fingerprint (checksum):{' '}
              <code>{report.evidence.checksum}</code>
            </p>
          )}
        </details>
        {downloadUrl ? (
          <p className="analytics-source-download">
            <a
              className="analytics-snapshot-download"
              href={downloadUrl}
              download
            >
              Download supporting records and checks
            </a>
          </p>
        ) : (
          <p>
            Supporting records are not available to download for this report
            version.
          </p>
        )}
      </details>
    </section>
  );
}

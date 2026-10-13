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
  return (
    <section
      className="analytics-panel analytics-report-sources"
      aria-label="Data provenance and coverage"
    >
      <ReportPanelHeader
        title="Data provenance and coverage"
        icon={BookOpen}
        level={2}
      />
      <p>
        <strong>
          Recorded source coverage:{' '}
          {report.complete ? 'Complete' : 'Incomplete'}.
        </strong>{' '}
        {report.complete
          ? 'This is the report’s coverage declaration, not independent certification that every interaction was captured.'
          : 'Some historical source evidence is unavailable. Preserved totals can still be reported, but the full history cannot be certified.'}
      </p>
      <p>
        UTC reporting window: {report.start} inclusive to {report.endExclusive}{' '}
        exclusive.
      </p>
      {report.evidence && (
        <p>
          Report integrity verified. Daily totals reconcile for{' '}
          {report.evidence.reconciledMetrics.length} aggregate metrics.{' '}
          Preserved-input replay:{' '}
          {report.evidence.preservedInputReplay === 'passed'
            ? 'verified'
            : 'not verified for this packet'}
          .
        </p>
      )}
      <p>
        Independent baseline evidence and deployed preservation are not verified
        by this packet. These checks cover the aggregate report; detailed
        rankings, member attribution, client classifications and supplemental
        dashboard data require separate evidence.
      </p>
      <p>
        Counts describe recorded activity. Download clicks do not confirm file
        transfers. Tracked visits are not unique people; the aggregate download
        estimates visits from merged sketches, so daily estimates must not be
        added. Catalog attribution uses captured metadata and may differ from
        month-end inventory.
      </p>
      <details>
        <summary>Report revision and evidence identifiers</summary>
        <p style={{ overflowWrap: 'anywhere' }}>
          Report revision: <code>{report.revision}</code>
        </p>
        {report.evidence && (
          <p style={{ overflowWrap: 'anywhere' }}>
            Evidence checksum: <code>{report.evidence.checksum}</code>
          </p>
        )}
        <p>
          Checksums identify content and detect changes. They are not
          independent attestations.
        </p>
      </details>
      {downloadUrl ? (
        <p className="analytics-source-download">
          <a
            className="analytics-snapshot-download"
            href={downloadUrl}
            download
          >
            Download report evidence packet
          </a>
        </p>
      ) : (
        <p>An evidence packet is not available for this revision.</p>
      )}
    </section>
  );
}

import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router';
import { AnalyticsHeader } from './AnalyticsHeader';
import { ReportingPeriodPicker } from './ReportingPeriodPicker';
import { ReportContentLayout } from './ReportContentLayout';
import {
  RuntimeReportView,
  type RuntimeReport,
  type ReportingManifest,
} from './RuntimeAnalyticsPage';
import { selectedAnalyticsReport } from '../../config/analyticsReports';

const root = '/analytics-reports';

export function SnapshotAnalyticsPage() {
  const [params, setParams] = useSearchParams();
  const active = selectedAnalyticsReport(params);
  const requested =
    active.id === 'comparison' ? 'all' : (params.get('month') ?? '2026-09');
  const [report, setReport] = useState<RuntimeReport | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    setReport(null);
    setError('');
    async function load() {
      const response = await fetch(`${root}/manifest.json`, {
        signal: controller.signal,
      });
      if (!response.ok)
        throw new Error('Could not load published reporting periods.');
      const manifest: ReportingManifest = await response.json();
      if (manifest.schemaVersion !== 1)
        throw new Error('Unsupported report version.');
      const entry = manifest.periods.find((period) => period.id === requested);
      if (!entry) throw new Error('This reporting period is unavailable.');
      const result = await fetch(
        `${root}/${entry.id}/${entry.revision}/report.json`,
        { signal: controller.signal }
      );
      if (!result.ok) throw new Error('Could not load this report.');
      const data: RuntimeReport = await result.json();
      if (
        data.schemaVersion !== 1 ||
        data.revision !== entry.revision ||
        data.period !== requested
      )
        throw new Error('Report version mismatch.');
      if (!controller.signal.aborted) setReport(data);
    }
    load().catch((failure) => {
      if (!controller.signal.aborted && failure.name !== 'AbortError')
        setError(failure.message);
    });
    return () => controller.abort();
  }, [requested]);
  return (
    <div className="analytics-page">
      <AnalyticsHeader activeReport={active.id} />
      <main id="analytics-main" className="analytics-shell">
        <div className="analytics-report-intro">
          <div className="analytics-report-title">
            <p>
              {requested === 'all' ? 'July–September 2026' : 'September 2026'} ·
              Analytics
            </p>
            <h1>{active.label}</h1>
            <span>{active.description}</span>
          </div>
          {active.id === 'comparison' ? (
            <p>July–September 2026</p>
          ) : (
            <ReportingPeriodPicker
              id="snapshot-period"
              value={requested}
              onChange={(month) => {
                const next = new URLSearchParams(params);
                next.set('month', month);
                setParams(next);
              }}
            />
          )}
        </div>
        {error && <p role="alert">{error}</p>}
        {!error && !report && <p role="status">Loading report…</p>}
        {report && (
          <>
            <p>
              {report.period === '2026-09'
                ? 'September 1–30, 2026'
                : 'July 1–September 30, 2026'}{' '}
              (UTC)
            </p>
            <p>
              Rankings show up to 100 entries; member resource tables show
              leaders by activity. Downloads include the full published rankings
              in CSV and JSON.
            </p>
            <ReportContentLayout report={active.label}>
              <div className="analytics-content">
                <RuntimeReportView
                  key={`${requested}-${active.id}`}
                  report={report}
                  active={active.id}
                  downloadArchive={`${root}/${report.period}/${report.revision}/tables.zip`}
                />
              </div>
            </ReportContentLayout>
          </>
        )}
      </main>
    </div>
  );
}

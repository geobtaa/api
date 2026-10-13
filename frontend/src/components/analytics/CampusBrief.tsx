import { useId, useState } from 'react';
import { Link } from 'react-router';
import { ArrowLeft, Copy, Printer } from 'lucide-react';
import { Seo } from '../Seo';
import type { MemberContentEntry } from '../../data/analytics/memberJuly2026';

export type CampusCounts = {
  resourceViews: number;
  downloadClicks: number;
  sourceClicks: number;
  impressions: number;
};
const number = new Intl.NumberFormat('en-US');
const metrics = [
  ['resourceViews', 'Resource views'],
  ['downloadClicks', 'Download clicks'],
  ['sourceClicks', 'Source-site clicks'],
  ['impressions', 'Search impressions'],
] as const;

export function CampusBrief({
  name,
  periodLabel,
  inventoryDate,
  counts,
  previous,
  previousLabel,
  topContent,
  daily,
  report,
  reportHref,
}: {
  name: string;
  periodLabel: string;
  inventoryDate: string;
  counts: CampusCounts;
  previous?: CampusCounts;
  previousLabel?: string;
  topContent: {
    viewed: readonly MemberContentEntry[];
    downloaded: readonly MemberContentEntry[];
  };
  daily: { day: string; views: number; downloads: number }[];
  report: {
    id: string;
    revision: string;
    complete: boolean;
    evidence?: { checksum: string };
  };
  reportHref: string;
}) {
  const [copyStatus, setCopyStatus] = useState('');
  const titleId = useId();
  const peak = daily.reduce(
    (best, row) => (row.views > (best?.views ?? -1) ? row : best),
    daily[0]
  );
  const maximum = Math.max(1, ...daily.map((row) => row.views));
  const points = daily
    .map(
      (row, i) =>
        `${(i * 600) / Math.max(1, daily.length - 1)},${60 - (row.views / maximum) * 56}`
    )
    .join(' ');
  const evidenceHref = report.evidence
    ? `/analytics-reports/${report.id}/${report.revision}/evidence-${report.evidence.checksum}.zip`
    : undefined;
  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setCopyStatus('Brief link copied. Colleagues will need to sign in.');
    } catch {
      setCopyStatus(
        'Copy the address from your browser to share this brief. Colleagues will need to sign in.'
      );
    }
  };
  return (
    <div className="analytics-page analytics-brief-page">
      <Seo
        title={`${name} — ${periodLabel} — Campus brief`}
        description="A printable summary of recorded resource activity with reporting coverage and provenance."
      />
      <nav className="analytics-brief-toolbar" aria-label="Brief actions">
        <Link to={reportHref}>
          <ArrowLeft size={17} aria-hidden="true" />
          Back to Members
        </Link>
        <div>
          <button type="button" onClick={copyLink}>
            <Copy size={17} aria-hidden="true" />
            Copy brief link
          </button>
          <button type="button" onClick={() => window.print()}>
            <Printer size={17} aria-hidden="true" />
            Print / save PDF
          </button>
        </div>
        <p role="status">{copyStatus}</p>
      </nav>
      <main id="analytics-main" className="analytics-brief-sheet" tabIndex={-1}>
        <header className="analytics-brief-header">
          <p className="analytics-eyebrow">
            Big Ten Academic Alliance · Geoportal
          </p>
          <p className="analytics-brief-kicker">Resource activity brief</p>
          <h1>{name}</h1>
          <p className="analytics-brief-period">
            {periodLabel} <span>UTC</span>
          </p>
        </header>
        <div className="analytics-brief-intro">
          <p>
            Recorded attention and access intent for this contribution stream’s
            published, unsuppressed resources.
          </p>
          <span className="analytics-brief-coverage">
            {report.complete
              ? 'Aggregate coverage declared complete'
              : 'Incomplete historical aggregate coverage'}
          </span>
        </div>
        <dl className="analytics-brief-metrics">
          {metrics.map(([key, label]) => (
            <div key={key}>
              <dt>{label}</dt>
              <dd>{number.format(counts[key])}</dd>
              <dd className="analytics-brief-change">
                {previous && previousLabel
                  ? `${counts[key] - previous[key] > 0 ? '+' : ''}${number.format(counts[key] - previous[key])} vs ${previousLabel}`
                  : 'No prior-period comparison'}
              </dd>
            </div>
          ))}
        </dl>
        <section
          className="analytics-brief-activity"
          aria-label="Daily resource attention"
        >
          <div>
            <h2>When resources drew attention</h2>
            <p>
              {peak && peak.views > 0
                ? `Peak: ${number.format(peak.views)} resource views on ${peak.day}.`
                : 'No resource views recorded in this period.'}
            </p>
          </div>
          <svg viewBox="0 0 600 64" role="img" aria-labelledby={titleId}>
            <title id={titleId}>
              Daily resource views across {daily.length} days;{' '}
              {peak && peak.views > 0
                ? `peak ${peak.views} on ${peak.day}`
                : 'no recorded views'}
            </title>
            <polyline
              points={points}
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              vectorEffect="non-scaling-stroke"
            />
          </svg>
          <p className="analytics-brief-chart-range">
            <span>{daily[0]?.day}</span>
            <span>{daily.at(-1)?.day}</span>
          </p>
        </section>
        <div className="analytics-brief-leaders">
          {(['viewed', 'downloaded'] as const).map((kind) => (
            <section key={kind}>
              <h2>
                {kind === 'viewed'
                  ? 'Resources drawing attention'
                  : 'Resources prompting download clicks'}
              </h2>
              <ol>
                {topContent[kind].slice(0, 3).map((resource) => (
                  <li key={resource.id}>
                    <a
                      href={`/resources/${encodeURIComponent(resource.id)}`}
                      title={resource.title}
                    >
                      {resource.title}
                    </a>
                    <strong>
                      {number.format(
                        kind === 'viewed' ? resource.views : resource.downloads
                      )}{' '}
                      <span>
                        {kind === 'viewed'
                          ? resource.views === 1
                            ? 'view'
                            : 'views'
                          : resource.downloads === 1
                            ? 'click'
                            : 'clicks'}
                      </span>
                    </strong>
                  </li>
                ))}
              </ol>
              {!topContent[kind].length && <p>No ranked activity recorded.</p>}
            </section>
          ))}
        </div>
        <footer className="analytics-brief-evidence">
          <h2>Read and share with confidence</h2>
          <p>
            Views count actions, not people. Download and source-site clicks do
            not confirm transfers. Comparisons use period totals; month lengths
            and captured catalog metadata can differ. Catalog attribution date:{' '}
            {inventoryDate}.
          </p>
          <p>
            {report.complete
              ? 'The underlying aggregate report declares complete source coverage.'
              : 'Some historical source evidence is unavailable.'}{' '}
            Its evidence packet documents aggregate checks; it does not verify
            this brief’s member attribution or rankings. Independent baseline
            authentication and deployed preservation remain unverified.
          </p>
          <p>
            <Link to={`${reportHref}#members`}>
              Open the full member report
            </Link>
            {evidenceHref && (
              <>
                {' '}
                ·{' '}
                <a href={evidenceHref} download>
                  Download aggregate evidence
                </a>
              </>
            )}
          </p>
          <p className="analytics-brief-revision">
            Aggregate report revision: {report.revision}
          </p>
        </footer>
      </main>
    </div>
  );
}

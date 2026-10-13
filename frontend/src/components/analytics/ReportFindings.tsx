import { ArrowUpRight } from 'lucide-react';
import { Link } from 'react-router';
import type { Finding } from '../../utils/analyticsFindings';

export function ReportFindings({
  findings,
  periodLabel,
  cumulative,
}: {
  findings: Finding[];
  periodLabel: string;
  cumulative: boolean;
}) {
  return (
    <section
      className="analytics-findings"
      aria-labelledby="findings-title"
      id="report-findings"
      data-nav-label
    >
      <div className="analytics-findings-heading">
        <div>
          <p className="analytics-eyebrow">The story in the numbers</p>
          <h2 id="findings-title">
            {cumulative ? 'This period' : 'This month'} in three findings
          </h2>
        </div>
        <span>{periodLabel} · Portal-wide</span>
      </div>
      <div className="analytics-findings-grid">
        {findings.map((finding, index) => (
          <article key={finding.label}>
            <p className="analytics-finding-label">
              <span aria-hidden="true">0{index + 1}</span>
              {finding.label}
            </p>
            <h3>{finding.headline}</h3>
            <p>{finding.detail}</p>
            {finding.supportingLink && (
              <div className="analytics-finding-contributor">
                <span>
                  Largest qualifying member change in the same direction
                </span>
                <Link to={finding.supportingLink.href}>
                  {finding.supportingLink.label}
                </Link>
                <small>Period totals; catalog attribution can differ.</small>
              </div>
            )}
            <Link to={finding.href}>
              {finding.action}
              <ArrowUpRight size={16} aria-hidden="true" />
            </Link>
          </article>
        ))}
      </div>
      <div className="analytics-findings-notes">
        <details>
          <summary>How these findings are selected</summary>
          <p>
            We highlight the largest absolute daily-rate change among searches,
            resource views and download clicks. Both months must have at least
            100 records, a total difference of at least 50, and a daily-rate
            change of at least 5%. Month lengths are normalized. These are
            descriptive thresholds, not statistical significance tests. Resource
            headlines require at least 10 views; discovery headlines require 100
            searches and 10 searches without results. A missing baseline is
            never treated as zero.
          </p>
        </details>
        <a href="#report-provenance">Check evidence and coverage</a>
      </div>
    </section>
  );
}

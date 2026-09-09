import { Link } from 'react-router';

import {
  analyticsReports,
  analyticsReportHref,
  type AnalyticsReport,
} from '../../config/analyticsReports';

export function AnalyticsHeader({
  activeReport,
}: {
  activeReport: AnalyticsReport;
}) {
  return (
    <header className="analytics-header">
      <a className="analytics-skip-link" href="#analytics-main">
        Skip to report
      </a>
      <div className="analytics-shell analytics-header-brand">
        <Link to="/analytics" className="analytics-brand">
          <span>BTAA</span> Analytics
        </Link>
        <Link to="/" className="analytics-portal-link">
          Back to Geoportal <span aria-hidden="true">↗</span>
        </Link>
      </div>
      <nav
        className="analytics-shell analytics-report-nav"
        aria-label="Analytics reports"
      >
        {analyticsReports.map((report) => (
          <Link
            key={report.id}
            to={analyticsReportHref(report.id)}
            aria-current={report.id === activeReport ? 'page' : undefined}
          >
            {report.label}
          </Link>
        ))}
      </nav>
    </header>
  );
}

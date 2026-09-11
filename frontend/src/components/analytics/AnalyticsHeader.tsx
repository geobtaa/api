import { Link, useSearchParams } from 'react-router';

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
  const [params] = useSearchParams();
  const reportHref = (id: AnalyticsReport) => {
    const href = analyticsReportHref(id, params.get('month'));
    return params.get('runtime') === '1'
      ? `${href}${href.includes('?') ? '&' : '?'}runtime=1`
      : href;
  };
  return (
    <header className="analytics-header">
      <a className="analytics-skip-link" href="#analytics-main">
        Skip to report
      </a>
      <div className="analytics-shell analytics-header-brand">
        <Link to="/analytics" className="analytics-brand">
          <img
            src="/btaa-logo.png"
            alt="Big Ten Academic Alliance"
            className="analytics-brand-logo"
          />
          <span className="analytics-brand-lockup">
            <span>API Analytics</span>
          </span>
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
            to={reportHref(report.id)}
            aria-current={report.id === activeReport ? 'page' : undefined}
          >
            {report.label}
          </Link>
        ))}
      </nav>
    </header>
  );
}

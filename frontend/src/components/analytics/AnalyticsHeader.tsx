import { CircleCheck, LogOut, X } from 'lucide-react';
import { Form, Link, useSearchParams } from 'react-router';

import {
  visibleAnalyticsReports,
  analyticsReportHref,
  type AnalyticsReport,
} from '../../config/analyticsReports';

export function AnalyticsHeader({
  activeReport,
}: {
  activeReport?: AnalyticsReport;
}) {
  const [params, setParams] = useSearchParams();
  const reportHref = (id: AnalyticsReport) => {
    const href = analyticsReportHref(id, params.get('month'));
    return params.get('runtime') === '1'
      ? `${href}${href.includes('?') ? '&' : '?'}runtime=1`
      : href;
  };
  return (
    <header className="analytics-header">
      <a className="analytics-skip-link" href="#analytics-main">
        {activeReport ? 'Skip to report' : 'Skip to sign in'}
      </a>
      <div className="analytics-shell analytics-header-brand">
        <Link
          to={activeReport ? '/analytics' : '/'}
          className="analytics-brand"
        >
          <img
            src="/btaa-logo.png"
            alt="Big Ten Academic Alliance"
            className="analytics-brand-logo"
          />
          <span className="analytics-brand-lockup">
            <span>API Analytics</span>
          </span>
        </Link>
        <div className="analytics-header-actions">
          <Link to="/" className="analytics-portal-link">
            Back to Geoportal <span aria-hidden="true">↗</span>
          </Link>
          {activeReport && (
            <Form method="post" action="/analytics/login">
              <input type="hidden" name="intent" value="logout" />
              <button type="submit" className="analytics-sign-out">
                Sign out of analytics <LogOut size={16} aria-hidden="true" />
              </button>
            </Form>
          )}
        </div>
      </div>
      {activeReport && (
        <nav
          className="analytics-shell analytics-report-nav"
          aria-label="Analytics reports"
        >
          {visibleAnalyticsReports.map((report) => (
            <Link
              key={report.id}
              to={reportHref(report.id)}
              aria-current={report.id === activeReport ? 'page' : undefined}
            >
              {report.label}
            </Link>
          ))}
        </nav>
      )}
      {activeReport && params.get('welcome') === '1' && (
        <div className="analytics-access-notice" role="status">
          <div className="analytics-shell analytics-access-notice-content">
            <CircleCheck size={28} aria-hidden="true" />
            <div>
              <strong>You’re signed in for 24 hours</strong>
              <p>You now have access to all analytics reports and downloads.</p>
            </div>
            <button
              type="button"
              className="analytics-notice-dismiss"
              aria-label="Dismiss sign-in notification"
              onClick={() => {
                const next = new URLSearchParams(params);
                next.delete('welcome');
                setParams(next, { replace: true, preventScrollReset: true });
              }}
            >
              <X size={20} aria-hidden="true" />
            </button>
          </div>
        </div>
      )}
    </header>
  );
}

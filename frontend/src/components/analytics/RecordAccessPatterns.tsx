import { useAnalyticsData } from './AnalyticsData';
import {
  resourceAccessPatterns,
  type ResourceAccessPattern,
} from '../../utils/analyticsSummary';

const number = new Intl.NumberFormat('en-US');
const ratio = new Intl.NumberFormat('en-US', {
  style: 'percent',
  maximumFractionDigits: 1,
});

function RecordAccessList({
  title,
  rows,
}: {
  title: string;
  rows: ResourceAccessPattern[];
}) {
  return (
    <article className="analytics-panel analytics-summary-card">
      <h3>{title}</h3>
      {rows.length ? (
        <ol className="analytics-summary-access-patterns">
          {rows.map((row) => (
            <li key={row.id}>
              <a href={`/resources/${encodeURIComponent(row.id)}`}>
                {row.title || row.id}
              </a>
              <dl>
                <div>
                  <dt>Views</dt>
                  <dd>{number.format(row.views)}</dd>
                </div>
                <div>
                  <dt>Outlinks</dt>
                  <dd>{number.format(row.sources)}</dd>
                </div>
                <div>
                  <dt>Downloads</dt>
                  <dd>{number.format(row.downloads)}</dd>
                </div>
                <div>
                  <dt>Clicks / views</dt>
                  <dd>{ratio.format(row.clicksPer100Views / 100)}</dd>
                </div>
              </dl>
            </li>
          ))}
        </ol>
      ) : (
        <p className="analytics-summary-empty">
          No records meet the sample criteria.
        </p>
      )}
    </article>
  );
}

export function RecordAccessPatterns({ period }: { period: string }) {
  const analytics = useAnalyticsData();
  const patterns =
    period === 'all'
      ? resourceAccessPatterns(
          analytics['allTimeCurrent.json'].default.resources
        )
      : null;
  return (
    <section aria-labelledby="content-record-access">
      <div className="analytics-summary-section-heading">
        <h2 id="content-record-access">Views and access clicks</h2>
        <span className="analytics-summary-caption">Experimental</span>
      </div>
      <aside className="analytics-summary-disclaimer" role="note">
        <strong>Temporary disclaimer</strong>
        <p>
          Outlink counts and access percentages currently exclude Licensed
          Access clicks.
        </p>
      </aside>
      {patterns ? (
        <>
          <div className="analytics-summary-grid">
            <RecordAccessList
              title="More access clicks per view"
              rows={patterns.moreClicks}
            />
            <RecordAccessList
              title="Fewer access clicks per view"
              rows={patterns.fewerClicks}
            />
          </div>
          <p className="analytics-summary-caption analytics-summary-catalog-note">
            Sample of published leading records with at least 20 views.
            Percentages combine outlinks and downloads relative to views.
            Repeated clicks count separately, so percentages can exceed 100%.
            These are not visit success rates.
          </p>
        </>
      ) : (
        <div className="analytics-panel analytics-summary-card">
          <p className="analytics-summary-caption">
            Combined views and access-click counts are unavailable for this
            period. Select All time to see the saved sample.
          </p>
        </div>
      )}
    </section>
  );
}

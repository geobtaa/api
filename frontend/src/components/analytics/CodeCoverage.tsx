import { AnalyticsTable } from './AnalyticsTable';
import { providerSnapshots } from '../../data/analytics/providers2026';
const number = new Intl.NumberFormat('en-US');
export function CodeCoverage({ month }: { month: string }) {
  const snapshot = providerSnapshots[month];
  if (!snapshot) return null;
  return (
    <section
      className="analytics-panel analytics-comparison-panel"
      aria-label="Contribution code coverage"
    >
      <h3>All contribution codes: coverage check</h3>
      <p className="analytics-comparison-note">
        Recalculated against the published, unsuppressed catalog on{' '}
        {snapshot.catalogSnapshotDate}. These totals include other and missing
        codes. The university charts above retain their original export dates,
        so July figures can differ as catalog metadata changes.
      </p>
      <div
        className="analytics-comparison-scroll"
        role="region"
        aria-label="Contribution code coverage table"
        tabIndex={0}
      >
        <AnalyticsTable className="analytics-comparison-table">
          <caption className="sr-only">
            {month} contribution-code coverage using the September 10 catalog
          </caption>
          <thead>
            <tr>
              <th scope="col">Group</th>
              <th scope="col">Catalog records</th>
              <th scope="col">Views</th>
              <th scope="col">Download clicks</th>
              <th scope="col">Source clicks</th>
            </tr>
          </thead>
          <tbody>
            {snapshot.codeCoverage.map((row) => (
              <tr key={row.label}>
                <th scope="row">{row.label}</th>
                <td>{number.format(row.catalogRecords)}</td>
                <td>{number.format(row.resourceViews)}</td>
                <td>{number.format(row.downloadClicks)}</td>
                <td>{number.format(row.sourceClicks)}</td>
              </tr>
            ))}
          </tbody>
        </AnalyticsTable>
      </div>
      <details>
        <summary>Inspect all code prefixes</summary>
        <div
          className="analytics-comparison-scroll"
          role="region"
          aria-label="All code prefixes"
          tabIndex={0}
        >
          <AnalyticsTable className="analytics-comparison-table">
            <caption className="sr-only">
              Catalog counts and views by exact two-character prefix
            </caption>
            <thead>
              <tr>
                <th scope="col">Prefix</th>
                <th scope="col">Catalog records</th>
                <th scope="col">Views</th>
              </tr>
            </thead>
            <tbody>
              {snapshot.codePrefixes?.map((row, index) => (
                <tr key={index}>
                  <th scope="row">
                    {row.prefix === null
                      ? 'Missing (null)'
                      : row.prefix === ''
                        ? 'Missing (empty)'
                        : row.prefix}
                  </th>
                  <td>{number.format(row.catalogRecords)}</td>
                  <td>{number.format(row.resourceViews)}</td>
                </tr>
              ))}
            </tbody>
          </AnalyticsTable>
        </div>
      </details>
      <p className="analytics-comparison-note">
        These are the stored code prefixes, not classifications inferred from
        titles or providers. Provider mode separately lists BTAA-GIN and any
        other named providers; records with no Provider appear under Missing
        provider.
      </p>
    </section>
  );
}

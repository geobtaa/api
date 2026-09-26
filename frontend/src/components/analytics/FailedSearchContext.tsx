import { useState } from 'react';
import { Link } from 'react-router';
import {
  searchContexts,
  replaySearch,
  type OutcomePeriod,
} from '../../data/analytics/outcomes';
import { FACET_LABELS } from '../../utils/facetLabels';

const display = (value: unknown): string =>
  typeof value === 'string' ? value : JSON.stringify(value);
function label(key: string) {
  const facet = key.match(
    /^(include_filters|exclude_filters|f|fq)\[([^\]]+)\]/
  );
  if (facet)
    return `${facet[1] === 'exclude_filters' ? 'Exclude' : 'Filter'} ${FACET_LABELS[facet[2]] ?? facet[2]}`;
  return (
    (
      {
        geo: 'Map bounds',
        year_range: 'Year range',
        per_page: 'Results per page',
      } as Record<string, string>
    )[key] ?? key
  );
}
export function FailedSearchContext({
  period,
  term,
}: {
  period: OutcomePeriod;
  term: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const contexts = searchContexts(period, term);
  if (!contexts.length) return <span>Not available in this export</span>;
  return (
    <details
      className="analytics-query-context"
      onToggle={(event) => setExpanded(event.currentTarget.open)}
    >
      <summary>
        {contexts.length} recorded{' '}
        {contexts.length === 1 ? 'combination' : 'combinations'}
      </summary>
      {expanded && (
        <ul>
          {contexts.map((context, index) => (
            <li key={index}>
              <strong>
                {context.count} {context.count === 1 ? 'search' : 'searches'} ·{' '}
                {context.resultsCount === null
                  ? 'Result total unavailable'
                  : `${context.resultsCount} total results`}
              </strong>
              <dl>
                {Object.entries(context.constraints)
                  .filter(
                    ([key]) =>
                      !['q', 'page', 'view', 'sort', 'search_field'].includes(
                        key
                      )
                  )
                  .map(([key, value]) => (
                    <div key={key}>
                      <dt>{label(key)}</dt>
                      <dd>
                        {Array.isArray(value)
                          ? value.map(display).join(', ')
                          : display(value)}
                      </dd>
                    </div>
                  ))}
                <div>
                  <dt>Page / view / sort / field</dt>
                  <dd>
                    {context.page ?? 'Unknown'} / {context.view ?? 'Unknown'} /{' '}
                    {context.sort ?? 'Unknown'} /{' '}
                    {context.searchField ?? 'Unknown'}
                  </dd>
                </div>
              </dl>
              {(context.resultsCount ?? 0) > 0 && (
                <p>
                  Empty displayed page despite a positive total; not a query
                  with no matches.
                </p>
              )}
              <Link to={replaySearch(term, context)}>
                Repeat search with recorded parameters
              </Link>
            </li>
          ))}
        </ul>
      )}
      <p>
        Current results can differ from the historical catalog. Unknown or
        tracking parameters are omitted.
      </p>
    </details>
  );
}

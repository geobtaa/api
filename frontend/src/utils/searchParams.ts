import { AdvancedClause, SearchParams } from '../types/search';

/** Boolean facet fields must send "true"/"false" to the API, not "1"/"0". */
const BOOLEAN_FACET_FIELDS = ['gbl_georeferenced_b'];

/** Normalize facet value for URL/API (e.g. gbl_georeferenced_b: "1" -> "true", "0" -> "false"). */
export function normalizeFacetValueForUrl(
  field: string,
  value: string
): string {
  if (!BOOLEAN_FACET_FIELDS.includes(field)) return value;
  if (value === '1' || value === 'true') return 'true';
  if (value === '0' || value === 'false') return 'false';
  return value;
}

function parseAdvancedClauses(rawValue: string | null): AdvancedClause[] {
  if (!rawValue) return [];

  try {
    const parsed = JSON.parse(rawValue);

    if (!Array.isArray(parsed)) {
      console.warn('adv_q is not an array, ignoring value:', parsed);
      return [];
    }

    return parsed
      .map((item) => {
        if (
          item &&
          typeof item === 'object' &&
          typeof item.op === 'string' &&
          typeof item.f === 'string' &&
          typeof item.q === 'string'
        ) {
          const op = item.op.toUpperCase();
          if (op === 'AND' || op === 'OR' || op === 'NOT') {
            return { op, field: item.f, q: item.q } as AdvancedClause;
          }
        }
        console.warn('Invalid advanced clause skipped:', item);
        return null;
      })
      .filter((clause): clause is AdvancedClause => clause !== null);
  } catch (error) {
    console.warn('Failed to parse adv_q parameter:', error);
    return [];
  }
}

export function parseSearchParams(searchParams: URLSearchParams) {
  const queryParam = searchParams.get('q');
  const hasQueryParam = searchParams.has('q');
  const query = queryParam || '';
  const page = parseInt(searchParams.get('page') || '1', 10);

  // Get all facet parameters (now using fq instead of f); dedupe by (field, value) so duplicate URL params don't show as repeated constraints
  const rawFacets = Array.from(searchParams.entries())
    .filter(
      ([key]) =>
        (key.startsWith('fq[') || key.startsWith('include_filters[')) &&
        !key.startsWith('include_filters[geo]')
    )
    .map(([key, value]) => {
      const field = key.match(/(?:fq|include_filters)\[(.*?)\]/)?.[1] || '';
      return { field, value };
    });
  const seenFacets = new Set<string>();
  const facets = rawFacets.filter(({ field, value }) => {
    const key = `${field}\0${value}`;
    if (seenFacets.has(key)) return false;
    seenFacets.add(key);
    return true;
  });

  // Get excluded facet parameters; dedupe by (field, value)
  const rawExcludeFacets = Array.from(searchParams.entries())
    .filter(([key]) => key.startsWith('exclude_filters['))
    .map(([key, value]) => {
      const field = key.match(/exclude_filters\[(.*?)\]/)?.[1] || '';
      return { field, value };
    });
  const seenExclude = new Set<string>();
  const excludeFacets = rawExcludeFacets.filter(({ field, value }) => {
    const key = `${field}\0${value}`;
    if (seenExclude.has(key)) return false;
    seenExclude.add(key);
    return true;
  });

  const advancedQuery = parseAdvancedClauses(searchParams.get('adv_q'));

  return { query, page, facets, excludeFacets, advancedQuery, hasQueryParam };
}

export function buildSearchParams(params: SearchParams): URLSearchParams {
  const searchParams = new URLSearchParams();

  if (params.query) {
    searchParams.set('q', params.query);
  }

  if (params.page > 1) {
    searchParams.set('page', params.page.toString());
  }

  if (params.perPage !== 10) {
    searchParams.set('per_page', params.perPage.toString());
  }

  // Add facet parameters using include_filters[] format for new API while keeping fq for backward links
  params.facets.forEach(({ field, value }) => {
    searchParams.append(
      `include_filters[${field}][]`,
      normalizeFacetValueForUrl(field, value)
    );
  });

  // Add exclude filters if provided
  if (params.excludeFacets) {
    params.excludeFacets.forEach(({ field, value }) => {
      searchParams.append(
        `exclude_filters[${field}][]`,
        normalizeFacetValueForUrl(field, value)
      );
    });
  }

  if (params.advancedQuery && params.advancedQuery.length > 0) {
    const serialized = params.advancedQuery.map(({ op, field, q }) => ({
      op,
      f: field,
      q,
    }));
    searchParams.set('adv_q', JSON.stringify(serialized));
  }

  return searchParams;
}

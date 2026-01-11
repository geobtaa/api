import { AdvancedClause, SearchParams } from '../types/search';

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

  // Get all facet parameters (now using fq instead of f)
  const facets = Array.from(searchParams.entries())
    .filter(
      ([key]) => key.startsWith('fq[') || key.startsWith('include_filters[')
    )
    .map(([key, value]) => {
      const field = key.match(/(?:fq|include_filters)\[(.*?)\]/)?.[1] || '';
      return { field, value };
    });

  // Get excluded facet parameters
  const excludeFacets = Array.from(searchParams.entries())
    .filter(([key]) => key.startsWith('exclude_filters['))
    .map(([key, value]) => {
      const field = key.match(/exclude_filters\[(.*?)\]/)?.[1] || '';
      return { field, value };
    });

  const advancedQuery = parseAdvancedClauses(searchParams.get('adv_q'));

  console.log('🔗 parseSearchParams called with:', {
    rawParams: Object.fromEntries(searchParams.entries()),
    parsed: {
      query,
      page,
      facets: facets.length,
      excludeFacets: excludeFacets.length,
      advancedClauses: advancedQuery.length,
    },
  });

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
    searchParams.append(`include_filters[${field}][]`, value);
  });

  // Add exclude filters if provided
  if (params.excludeFacets) {
    params.excludeFacets.forEach(({ field, value }) => {
      searchParams.append(`exclude_filters[${field}][]`, value);
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

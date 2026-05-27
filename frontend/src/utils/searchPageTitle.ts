import { humanizeFieldName } from '../constants/fieldLabels';
import { getFacetLabel } from './facetLabels';

const SEARCH_RESULTS_TITLE = 'Search Results';

type AdvancedTitleClause = {
  op: string;
  f: string;
  q: string;
};

function cleanTitleValue(value: string | null): string {
  return (value || '').trim().replace(/\s+/g, ' ');
}

function getFieldLabel(field: string): string {
  const facetLabel = getFacetLabel(field);
  if (facetLabel !== field) return facetLabel;

  return humanizeFieldName(field);
}

function getBoundingBoxConstraint(
  searchParams: URLSearchParams
): string | null {
  const legacyBbox = cleanTitleValue(searchParams.get('bbox'));
  if (legacyBbox) {
    return `Bounding Box: ${legacyBbox}`;
  }

  if (searchParams.get('include_filters[geo][type]') !== 'bbox') {
    return null;
  }

  const north = cleanTitleValue(
    searchParams.get('include_filters[geo][top_left][lat]')
  );
  const west = cleanTitleValue(
    searchParams.get('include_filters[geo][top_left][lon]')
  );
  const south = cleanTitleValue(
    searchParams.get('include_filters[geo][bottom_right][lat]')
  );
  const east = cleanTitleValue(
    searchParams.get('include_filters[geo][bottom_right][lon]')
  );

  if (!north || !west || !south || !east) {
    return null;
  }

  return `Bounding Box: ${west} ${south} ${east} ${north}`;
}

function getYearRangeConstraint(searchParams: URLSearchParams): string | null {
  const start = cleanTitleValue(
    searchParams.get('include_filters[year_range][start]')
  );
  const end = cleanTitleValue(
    searchParams.get('include_filters[year_range][end]')
  );

  if (!start && !end) {
    return null;
  }

  return `Year Range: ${start || '?'} - ${end || '?'}`;
}

function getFacetConstraints(searchParams: URLSearchParams): string[] {
  const constraints: string[] = [];
  const seen = new Set<string>();

  searchParams.forEach((rawValue, key) => {
    const match = key.match(
      /^(include_filters|exclude_filters|fq|f)\[([^\]]+)\]/
    );
    if (!match) return;

    const [, kind, field] = match;
    if (!field || field === 'geo' || field === 'year_range') return;

    const value = cleanTitleValue(rawValue);
    if (!value) return;

    const labelPrefix = kind === 'exclude_filters' ? 'Exclude ' : '';
    const constraint = `${labelPrefix}${getFieldLabel(field)}: ${value}`;
    const dedupeKey = constraint;

    if (seen.has(dedupeKey)) return;
    seen.add(dedupeKey);
    constraints.push(constraint);
  });

  return constraints;
}

function parseAdvancedTitleClauses(
  rawValue: string | null
): AdvancedTitleClause[] {
  if (!rawValue) return [];

  try {
    const parsed = JSON.parse(rawValue);
    if (!Array.isArray(parsed)) return [];

    return parsed.filter(
      (item): item is AdvancedTitleClause =>
        item &&
        typeof item === 'object' &&
        typeof item.op === 'string' &&
        typeof item.f === 'string' &&
        typeof item.q === 'string' &&
        Boolean(cleanTitleValue(item.q))
    );
  } catch {
    return [];
  }
}

function getAdvancedConstraints(searchParams: URLSearchParams): string[] {
  return parseAdvancedTitleClauses(searchParams.get('adv_q')).map(
    (clause) =>
      `${clause.op.toUpperCase()} ${humanizeFieldName(clause.f)}: ${cleanTitleValue(
        clause.q
      )}`
  );
}

export function getSearchTitleConstraints(
  searchParams: URLSearchParams
): string[] {
  return [
    getYearRangeConstraint(searchParams),
    ...getFacetConstraints(searchParams),
    getBoundingBoxConstraint(searchParams),
    ...getAdvancedConstraints(searchParams),
  ].filter((constraint): constraint is string => Boolean(constraint));
}

export function buildSearchPageTitle(searchParams: URLSearchParams): string {
  const query = cleanTitleValue(searchParams.get('q'));
  const constraints = getSearchTitleConstraints(searchParams);

  if (query && constraints.length > 0) {
    return [query, ...constraints].join(' / ');
  }

  if (query) {
    return `Search: ${query}`;
  }

  if (constraints.length > 0) {
    return constraints.join(' / ');
  }

  return SEARCH_RESULTS_TITLE;
}

export function buildSearchPageTitleFromUrl(url: string | undefined): string {
  if (!url) {
    return SEARCH_RESULTS_TITLE;
  }

  try {
    return buildSearchPageTitle(new URL(url).searchParams);
  } catch {
    return SEARCH_RESULTS_TITLE;
  }
}

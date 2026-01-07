export interface FacetFilter {
  field: string;
  value: string;
}

export type AdvancedOperator = 'AND' | 'OR' | 'NOT';

export interface AdvancedClause {
  op: AdvancedOperator;
  field: string;
  q: string;
}

export interface SearchParams {
  query: string;
  page: number;
  perPage: number;
  facets: FacetFilter[];
  excludeFacets?: FacetFilter[];
  advancedQuery?: AdvancedClause[];
}

export interface SearchState extends SearchParams {
  isLoading: boolean;
  error: string | null;
}

import type { FacetValue } from '../types/api';

/**
 * Returns the best human-facing label for a facet value.
 *
 * - Prefer `attributes.label` when present and meaningful.
 * - Fall back to `attributes.value` (or `id`) when label is missing.
 * - Guard against the common UI bug where the "label" ends up being the hits/count.
 */
export function getFacetValueDisplayLabel(
  item: Pick<FacetValue, 'id' | 'attributes'>,
  facetId?: string
): string {
  const value = item.attributes?.value ?? item.id;
  const hits = item.attributes?.hits;
  const label = item.attributes?.label;

  // Special handling for boolean facets or specific IDs
  if (facetId === 'gbl_georeferenced_b' || facetId === 'georeferenced_agg') {
    if (String(value) === 'true' || String(value) === '1')
      return 'Georeferenced';
    if (String(value) === 'false' || String(value) === '0')
      return 'Not georeferenced';
  }

  if (typeof label === 'string') {
    const trimmed = label.trim();
    // If the label is literally the count, it's not a label.
    if (trimmed && trimmed !== String(hits)) {
      return trimmed;
    }
  }

  return String(value ?? '');
}

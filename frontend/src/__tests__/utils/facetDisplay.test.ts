import { describe, it, expect } from 'vitest';
import { getFacetValueDisplayLabel } from '../../utils/facetDisplay';

describe('getFacetValueDisplayLabel', () => {
  it('returns the label when present', () => {
    const item = {
      id: '1',
      attributes: { value: 'val', label: 'My Label', hits: 10 },
    };
    expect(getFacetValueDisplayLabel(item)).toBe('My Label');
  });

  it('returns value when label is missing', () => {
    const item = {
      id: '1',
      attributes: { value: 'val', hits: 10 },
    };
    expect(getFacetValueDisplayLabel(item)).toBe('val');
  });

  it('renames georeferenced values "1"/"true"', () => {
    const item1 = { id: '1', attributes: { value: '1', hits: 5 } };
    const itemTrue = { id: 'true', attributes: { value: 'true', hits: 5 } };

    expect(getFacetValueDisplayLabel(item1, 'gbl_georeferenced_b')).toBe(
      'Georeferenced'
    );
    expect(getFacetValueDisplayLabel(itemTrue, 'gbl_georeferenced_b')).toBe(
      'Georeferenced'
    );

    // Also check legacy ID
    expect(getFacetValueDisplayLabel(item1, 'georeferenced_agg')).toBe(
      'Georeferenced'
    );
  });

  it('renames georeferenced values "0"/"false"', () => {
    const item0 = { id: '0', attributes: { value: '0', hits: 5 } };
    const itemFalse = { id: 'false', attributes: { value: 'false', hits: 5 } };

    expect(getFacetValueDisplayLabel(item0, 'gbl_georeferenced_b')).toBe(
      'Not georeferenced'
    );
    expect(getFacetValueDisplayLabel(itemFalse, 'gbl_georeferenced_b')).toBe(
      'Not georeferenced'
    );
  });

  it('ignores other facet IDs', () => {
    const item = { id: '1', attributes: { value: '1', hits: 5 } };
    // Should return "1" because it's not the georeferenced facet
    expect(getFacetValueDisplayLabel(item, 'other_facet')).toBe('1');
  });
});

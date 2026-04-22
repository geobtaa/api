import { describe, it, expect, vi, beforeEach } from 'vitest';
import { parseSearchParams, buildSearchParams } from '../../utils/searchParams';
import { SearchParams } from '../../types/search';

describe('searchParams', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Mock console.log to avoid test output noise
    vi.spyOn(console, 'log').mockImplementation(() => {});
  });

  describe('parseSearchParams', () => {
    it('parses basic search parameters', () => {
      const searchParams = new URLSearchParams({
        q: 'test query',
        page: '2',
      });

      const result = parseSearchParams(searchParams);

      expect(result).toMatchObject({
        query: 'test query',
        page: 2,
        facets: [],
        excludeFacets: [],
        advancedQuery: [],
      });
      expect(result.hasQueryParam).toBe(true);
    });

    it('handles empty search parameters', () => {
      const searchParams = new URLSearchParams();

      const result = parseSearchParams(searchParams);

      expect(result).toMatchObject({
        query: '',
        page: 1,
        facets: [],
        excludeFacets: [],
        advancedQuery: [],
      });
      expect(result.hasQueryParam).toBe(false);
    });

    it('parses facet parameters with fq format', () => {
      const searchParams = new URLSearchParams({
        q: 'geospatial data',
        page: '1',
        'fq[dc_publisher_sm][]': 'MIT Libraries',
        'fq[gbl_resourceClass_sm][]': 'Dataset',
      });

      const result = parseSearchParams(searchParams);

      expect(result).toMatchObject({
        query: 'geospatial data',
        page: 1,
        facets: [
          { field: 'dc_publisher_sm', value: 'MIT Libraries' },
          { field: 'gbl_resourceClass_sm', value: 'Dataset' },
        ],
        excludeFacets: [],
        advancedQuery: [],
      });
    });

    it('handles multiple values for the same facet field', () => {
      const searchParams = new URLSearchParams();
      searchParams.set('q', 'maps');
      searchParams.set('page', '1');
      searchParams.append('fq[dc_publisher_sm][]', 'MIT Libraries');
      searchParams.append('fq[dc_publisher_sm][]', 'Harvard University');

      const result = parseSearchParams(searchParams);

      expect(result).toMatchObject({
        query: 'maps',
        page: 1,
        facets: [
          { field: 'dc_publisher_sm', value: 'MIT Libraries' },
          { field: 'dc_publisher_sm', value: 'Harvard University' },
        ],
        excludeFacets: [],
        advancedQuery: [],
      });
    });

    it('handles complex facet field names', () => {
      const searchParams = new URLSearchParams({
        q: 'geographic data',
        'fq[dct_temporal_sm][]': '2020',
        'fq[dc_subject_sm][]': 'Geographic Information Systems',
      });

      const result = parseSearchParams(searchParams);

      expect(result).toMatchObject({
        query: 'geographic data',
        page: 1,
        facets: [
          { field: 'dct_temporal_sm', value: '2020' },
          { field: 'dc_subject_sm', value: 'Geographic Information Systems' },
        ],
        excludeFacets: [],
        advancedQuery: [],
      });
    });

    it('ignores non-facet parameters', () => {
      const searchParams = new URLSearchParams({
        q: 'test',
        page: '1',
        sort: 'relevance',
        format: 'json',
        'fq[dc_publisher_sm][]': 'MIT Libraries',
      });

      const result = parseSearchParams(searchParams);

      expect(result).toMatchObject({
        query: 'test',
        page: 1,
        facets: [{ field: 'dc_publisher_sm', value: 'MIT Libraries' }],
        excludeFacets: [],
        advancedQuery: [],
      });
    });

    it('handles invalid page numbers gracefully', () => {
      const searchParams = new URLSearchParams({
        q: 'test',
        page: 'invalid',
      });

      const result = parseSearchParams(searchParams);

      expect(result).toMatchObject({
        query: 'test',
        page: NaN, // parseInt returns NaN for invalid input
        facets: [],
        excludeFacets: [],
        advancedQuery: [],
      });
    });

    it('handles negative page numbers', () => {
      const searchParams = new URLSearchParams({
        q: 'test',
        page: '-1',
      });

      const result = parseSearchParams(searchParams);

      expect(result).toMatchObject({
        query: 'test',
        page: -1,
        facets: [],
        excludeFacets: [],
        advancedQuery: [],
      });
    });

    it('handles zero page number', () => {
      const searchParams = new URLSearchParams({
        q: 'test',
        page: '0',
      });

      const result = parseSearchParams(searchParams);

      expect(result).toMatchObject({
        query: 'test',
        page: 0,
        facets: [],
        excludeFacets: [],
        advancedQuery: [],
      });
    });

    it('handles URL-encoded query parameters', () => {
      const searchParams = new URLSearchParams({
        q: 'geographic%20information%20systems',
        'fq[dc_publisher_sm][]': 'MIT%20Libraries',
      });

      const result = parseSearchParams(searchParams);

      expect(result).toMatchObject({
        query: 'geographic%20information%20systems', // URLSearchParams doesn't auto-decode
        page: 1,
        facets: [{ field: 'dc_publisher_sm', value: 'MIT%20Libraries' }],
        excludeFacets: [],
        advancedQuery: [],
      });
    });

    it('handles special characters in facet values', () => {
      const searchParams = new URLSearchParams({
        q: 'test',
        'fq[dc_publisher_sm][]': 'MIT Libraries & Archives',
        'fq[dc_subject_sm][]': 'GIS & Remote Sensing',
      });

      const result = parseSearchParams(searchParams);

      expect(result).toMatchObject({
        query: 'test',
        page: 1,
        facets: [
          { field: 'dc_publisher_sm', value: 'MIT Libraries & Archives' },
          { field: 'dc_subject_sm', value: 'GIS & Remote Sensing' },
        ],
        excludeFacets: [],
        advancedQuery: [],
      });
    });

    it('parses advanced query clauses', () => {
      const advanced = JSON.stringify([
        { op: 'AND', f: 'dct_title_s', q: 'Iowa' },
        { op: 'NOT', f: 'dct_title_s', q: 'Wisconsin' },
      ]);
      const searchParams = new URLSearchParams({
        adv_q: advanced,
      });

      const result = parseSearchParams(searchParams);

      expect(result.advancedQuery).toEqual([
        { op: 'AND', field: 'dct_title_s', q: 'Iowa' },
        { op: 'NOT', field: 'dct_title_s', q: 'Wisconsin' },
      ]);
      expect(result.hasQueryParam).toBe(false);
    });

    it('ignores malformed advanced clauses gracefully', () => {
      const searchParams = new URLSearchParams({
        adv_q: '{"op":"AND","bad":"data"}',
      });

      const result = parseSearchParams(searchParams);

      expect(result.advancedQuery).toEqual([]);
    });

    it('does not emit debug logging', () => {
      const consoleSpy = vi.spyOn(console, 'log');
      const searchParams = new URLSearchParams({
        q: 'test query',
        page: '2',
        'fq[dc_publisher_sm][]': 'MIT Libraries',
      });

      parseSearchParams(searchParams);

      expect(consoleSpy).not.toHaveBeenCalled();
    });

    it('handles malformed facet field names', () => {
      const searchParams = new URLSearchParams({
        q: 'test',
        'fq[malformed_field': 'value',
        'fq[valid_field][]': 'valid value',
      });

      const result = parseSearchParams(searchParams);

      expect(result).toMatchObject({
        query: 'test',
        page: 1,
        facets: [
          { field: '', value: 'value' }, // malformed field becomes empty string
          { field: 'valid_field', value: 'valid value' },
        ],
        excludeFacets: [],
        advancedQuery: [],
      });
    });
  });

  describe('buildSearchParams', () => {
    it('builds basic search parameters', () => {
      const params: SearchParams = {
        query: 'test query',
        page: 1,
        perPage: 10,
        facets: [],
      };

      const result = buildSearchParams(params);

      expect(result.get('q')).toBe('test query');
      expect(result.get('page')).toBeNull(); // page 1 is not included
      expect(result.get('per_page')).toBeNull(); // default perPage is not included
    });

    it('builds parameters with page > 1', () => {
      const params: SearchParams = {
        query: 'test query',
        page: 3,
        perPage: 10,
        facets: [],
      };

      const result = buildSearchParams(params);

      expect(result.get('q')).toBe('test query');
      expect(result.get('page')).toBe('3');
    });

    it('builds parameters with custom perPage', () => {
      const params: SearchParams = {
        query: 'test query',
        page: 1,
        perPage: 25,
        facets: [],
      };

      const result = buildSearchParams(params);

      expect(result.get('q')).toBe('test query');
      expect(result.get('per_page')).toBe('25');
    });

    it('builds parameters with facets', () => {
      const params: SearchParams = {
        query: 'geospatial data',
        page: 1,
        perPage: 10,
        facets: [
          { field: 'dc_publisher_sm', value: 'MIT Libraries' },
          { field: 'gbl_resourceClass_sm', value: 'Dataset' },
        ],
      };

      const result = buildSearchParams(params);

      expect(result.get('q')).toBe('geospatial data');
      expect(result.get('include_filters[dc_publisher_sm][]')).toBe(
        'MIT Libraries'
      );
      expect(result.get('include_filters[gbl_resourceClass_sm][]')).toBe(
        'Dataset'
      );
    });

    it('builds parameters with multiple facets for same field', () => {
      const params: SearchParams = {
        query: 'maps',
        page: 1,
        perPage: 10,
        facets: [
          { field: 'dc_publisher_sm', value: 'MIT Libraries' },
          { field: 'dc_publisher_sm', value: 'Harvard University' },
        ],
      };

      const result = buildSearchParams(params);

      expect(result.get('q')).toBe('maps');
      expect(result.getAll('include_filters[dc_publisher_sm][]')).toEqual([
        'MIT Libraries',
        'Harvard University',
      ]);
    });

    it('handles empty query', () => {
      const params: SearchParams = {
        query: '',
        page: 1,
        perPage: 10,
        facets: [],
      };

      const result = buildSearchParams(params);

      expect(result.get('q')).toBeNull(); // Empty string is not set (falsy check)
    });

    it('handles complex facet field names', () => {
      const params: SearchParams = {
        query: 'geographic data',
        page: 1,
        perPage: 10,
        facets: [
          { field: 'dct_temporal_sm', value: '2020' },
          { field: 'dc_subject_sm', value: 'Geographic Information Systems' },
        ],
      };

      const result = buildSearchParams(params);

      expect(result.get('q')).toBe('geographic data');
      expect(result.get('include_filters[dct_temporal_sm][]')).toBe('2020');
      expect(result.get('include_filters[dc_subject_sm][]')).toBe(
        'Geographic Information Systems'
      );
    });

    it('handles special characters in facet values', () => {
      const params: SearchParams = {
        query: 'test',
        page: 1,
        perPage: 10,
        facets: [
          { field: 'dc_publisher_sm', value: 'MIT Libraries & Archives' },
          { field: 'dc_subject_sm', value: 'GIS & Remote Sensing' },
        ],
      };

      const result = buildSearchParams(params);

      expect(result.get('q')).toBe('test');
      expect(result.get('include_filters[dc_publisher_sm][]')).toBe(
        'MIT Libraries & Archives'
      );
      expect(result.get('include_filters[dc_subject_sm][]')).toBe(
        'GIS & Remote Sensing'
      );
    });

    it('handles URL-encoded values', () => {
      const params: SearchParams = {
        query: 'geographic information systems',
        page: 1,
        perPage: 10,
        facets: [{ field: 'dc_publisher_sm', value: 'MIT Libraries' }],
      };

      const result = buildSearchParams(params);

      expect(result.get('q')).toBe('geographic information systems');
      expect(result.get('include_filters[dc_publisher_sm][]')).toBe(
        'MIT Libraries'
      );
    });

    it('serializes advanced query clauses', () => {
      const params: SearchParams = {
        query: 'maps',
        page: 1,
        perPage: 10,
        facets: [],
        advancedQuery: [
          { op: 'AND', field: 'dct_title_s', q: 'Iowa' },
          { op: 'OR', field: 'dct_description_sm', q: 'Water' },
        ],
      };

      const result = buildSearchParams(params);
      const advParam = result.get('adv_q');
      expect(advParam).not.toBeNull();
      expect(JSON.parse(advParam as string)).toEqual([
        { op: 'AND', f: 'dct_title_s', q: 'Iowa' },
        { op: 'OR', f: 'dct_description_sm', q: 'Water' },
      ]);
    });

    it('omits advanced query when no clauses are provided', () => {
      const params: SearchParams = {
        query: 'maps',
        page: 1,
        perPage: 10,
        facets: [],
        advancedQuery: [],
      };

      const result = buildSearchParams(params);
      expect(result.get('adv_q')).toBeNull();
    });

    it('handles very long query strings', () => {
      const longQuery =
        'This is a very long search query with many words that should be properly handled by the URL parameter building function';
      const params: SearchParams = {
        query: longQuery,
        page: 1,
        perPage: 10,
        facets: [],
      };

      const result = buildSearchParams(params);

      expect(result.get('q')).toBe(longQuery);
    });

    it('handles numeric facet values', () => {
      const params: SearchParams = {
        query: 'test',
        page: 1,
        perPage: 10,
        facets: [
          { field: 'dct_temporal_sm', value: '2023' },
          { field: 'gbl_resourceClass_sm', value: 'Dataset' },
        ],
      };

      const result = buildSearchParams(params);

      expect(result.get('include_filters[dct_temporal_sm][]')).toBe('2023');
      expect(result.get('include_filters[gbl_resourceClass_sm][]')).toBe(
        'Dataset'
      );
    });

    it('handles empty facet values', () => {
      const params: SearchParams = {
        query: 'test',
        page: 1,
        perPage: 10,
        facets: [
          { field: 'dc_publisher_sm', value: '' },
          { field: 'gbl_resourceClass_sm', value: 'Dataset' },
        ],
      };

      const result = buildSearchParams(params);

      expect(result.get('include_filters[dc_publisher_sm][]')).toBe('');
      expect(result.get('include_filters[gbl_resourceClass_sm][]')).toBe(
        'Dataset'
      );
    });
  });

  describe('Integration Tests', () => {
    it('parseSearchParams and buildSearchParams work together', () => {
      const originalParams: SearchParams = {
        query: 'geospatial data',
        page: 2,
        perPage: 25,
        facets: [
          { field: 'dc_publisher_sm', value: 'MIT Libraries' },
          { field: 'gbl_resourceClass_sm', value: 'Dataset' },
        ],
      };

      // Build URL parameters
      const searchParams = buildSearchParams(originalParams);

      // Parse them back
      const parsedParams = parseSearchParams(searchParams);

      expect(parsedParams.query).toBe(originalParams.query);
      expect(parsedParams.page).toBe(originalParams.page);
      expect(parsedParams.facets).toEqual(originalParams.facets);
    });

    it('handles round-trip conversion for complex parameters', () => {
      const originalParams: SearchParams = {
        query: 'geographic information systems & remote sensing',
        page: 3,
        perPage: 50,
        facets: [
          { field: 'dc_publisher_sm', value: 'MIT Libraries & Archives' },
          { field: 'dc_publisher_sm', value: 'Harvard University' },
          { field: 'dct_temporal_sm', value: '2020-2023' },
          { field: 'dc_subject_sm', value: 'GIS & Remote Sensing' },
        ],
      };

      const searchParams = buildSearchParams(originalParams);
      const parsedParams = parseSearchParams(searchParams);

      expect(parsedParams.query).toBe(originalParams.query);
      expect(parsedParams.page).toBe(originalParams.page);
      expect(parsedParams.facets).toEqual(originalParams.facets);
    });

    it('maintains consistency with real-world search scenarios', () => {
      const testCases = [
        {
          query: 'maps',
          page: 1,
          perPage: 10,
          facets: [{ field: 'dc_publisher_sm', value: 'MIT Libraries' }],
        },
        {
          query: 'geospatial data',
          page: 2,
          perPage: 25,
          facets: [
            { field: 'gbl_resourceClass_sm', value: 'Dataset' },
            { field: 'dct_temporal_sm', value: '2020' },
          ],
        },
        {
          query: 'remote sensing',
          page: 1,
          perPage: 10,
          facets: [
            { field: 'dc_subject_sm', value: 'Remote Sensing' },
            { field: 'dc_publisher_sm', value: 'Stanford University' },
          ],
        },
      ];

      testCases.forEach((params) => {
        const searchParams = buildSearchParams(params);
        const parsedParams = parseSearchParams(searchParams);

        expect(parsedParams.query).toBe(params.query);
        expect(parsedParams.page).toBe(params.page);
        expect(parsedParams.facets).toEqual(params.facets);
      });
    });

    it('handles edge cases in round-trip conversion', () => {
      const edgeCases = [
        {
          query: '',
          page: 0,
          perPage: 1,
          facets: [],
        },
        {
          query: 'test',
          page: 1,
          perPage: 10,
          facets: [
            { field: '', value: 'empty field' },
            { field: 'valid_field', value: '' },
          ],
        },
      ];

      edgeCases.forEach((params) => {
        const searchParams = buildSearchParams(params);
        const parsedParams = parseSearchParams(searchParams);

        expect(parsedParams.query).toBe(params.query);
        // Page 0 gets converted to 1 in the parsing logic (parseInt with fallback)
        if (params.page === 0) {
          expect(parsedParams.page).toBe(1);
        } else {
          expect(parsedParams.page).toBe(params.page);
        }
        expect(parsedParams.facets).toEqual(params.facets);
      });
    });
  });
});

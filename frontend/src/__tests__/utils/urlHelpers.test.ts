import { describe, it, expect, vi, beforeEach } from 'vitest';
import { parseFacetUrl, createFacetSearchUrl } from '../../utils/urlHelpers';

describe('urlHelpers', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('parseFacetUrl', () => {
    it('parses a valid facet URL with single parameter', () => {
      const url = '/catalog?f[dc_publisher_sm][]=MIT%20Libraries';
      const result = parseFacetUrl(url);

      expect(result).toEqual({
        field: 'dc_publisher_sm',
        value: 'MIT Libraries',
      });
    });

    it('parses a valid facet URL with multiple parameters', () => {
      const url =
        '/catalog?f[dc_publisher_sm][]=MIT%20Libraries&f[gbl_resourceClass_sm][]=Dataset';
      const result = parseFacetUrl(url);

      // Should return the first facet found
      expect(result).toEqual({
        field: 'dc_publisher_sm',
        value: 'MIT Libraries',
      });
    });

    it('handles URL-encoded values correctly', () => {
      const url = '/catalog?f[dct_temporal_sm][]=2020-2021';
      const result = parseFacetUrl(url);

      expect(result).toEqual({
        field: 'dct_temporal_sm',
        value: '2020-2021',
      });
    });

    it('handles complex field names', () => {
      const url = '/catalog?f[gbl_resourceClass_sm][]=Point%20Data';
      const result = parseFacetUrl(url);

      expect(result).toEqual({
        field: 'gbl_resourceClass_sm',
        value: 'Point Data',
      });
    });

    it('returns null for URLs without facet parameters', () => {
      const url = '/catalog?q=test&page=1';
      const result = parseFacetUrl(url);

      expect(result).toBeNull();
    });

    it('returns null for URLs that do not start with /catalog', () => {
      const url = '/search?f[dc_publisher_sm][]=MIT%20Libraries';
      const result = parseFacetUrl(url);

      expect(result).toBeNull();
    });

    it('returns null for malformed URLs', () => {
      const url = 'not-a-valid-url';
      const result = parseFacetUrl(url);

      expect(result).toBeNull();
    });

    it('handles empty search parameters', () => {
      const url = '/catalog?';
      const result = parseFacetUrl(url);

      expect(result).toBeNull();
    });

    it('handles URLs with non-facet parameters', () => {
      const url =
        '/catalog?q=test&format=json&f[dc_publisher_sm][]=MIT%20Libraries';
      const result = parseFacetUrl(url);

      expect(result).toEqual({
        field: 'dc_publisher_sm',
        value: 'MIT Libraries',
      });
    });

    it('logs error for invalid URLs', () => {
      const consoleSpy = vi
        .spyOn(console, 'error')
        .mockImplementation(() => {});
      const url = 'http://[invalid-url';

      const result = parseFacetUrl(url);

      expect(result).toBeNull();
      expect(consoleSpy).toHaveBeenCalledWith(
        'Error parsing facet URL:',
        expect.any(Error)
      );

      consoleSpy.mockRestore();
    });

    it('handles URLs with special characters in field names', () => {
      const url =
        '/catalog?f[dc_subject_sm][]=Geographic%20Information%20Systems';
      const result = parseFacetUrl(url);

      expect(result).toEqual({
        field: 'dc_subject_sm',
        value: 'Geographic Information Systems',
      });
    });

    it('handles URLs with special characters in values', () => {
      const url =
        '/catalog?f[dc_publisher_sm][]=MIT%20Libraries%20%26%20Archives';
      const result = parseFacetUrl(url);

      expect(result).toEqual({
        field: 'dc_publisher_sm',
        value: 'MIT Libraries & Archives',
      });
    });
  });

  describe('createFacetSearchUrl', () => {
    it('creates a valid facet search URL with basic parameters', () => {
      const result = createFacetSearchUrl('dc_publisher_sm', 'MIT Libraries');

      expect(result).toBe(
        'https://geo.btaa.org/?format=json&search_field=all_fields&f%5Bdc_publisher_sm%5D%5B%5D=MIT+Libraries'
      );
    });

    it('creates URL with resource class facet', () => {
      const result = createFacetSearchUrl('gbl_resourceClass_sm', 'Dataset');

      expect(result).toBe(
        'https://geo.btaa.org/?format=json&search_field=all_fields&f%5Bgbl_resourceClass_sm%5D%5B%5D=Dataset'
      );
    });

    it('creates URL with temporal facet', () => {
      const result = createFacetSearchUrl('dct_temporal_sm', '2020');

      expect(result).toBe(
        'https://geo.btaa.org/?format=json&search_field=all_fields&f%5Bdct_temporal_sm%5D%5B%5D=2020'
      );
    });

    it('handles special characters in field names', () => {
      const result = createFacetSearchUrl(
        'dc_subject_sm',
        'Geographic Information Systems'
      );

      expect(result).toBe(
        'https://geo.btaa.org/?format=json&search_field=all_fields&f%5Bdc_subject_sm%5D%5B%5D=Geographic+Information+Systems'
      );
    });

    it('handles special characters in values', () => {
      const result = createFacetSearchUrl(
        'dc_publisher_sm',
        'MIT Libraries & Archives'
      );

      expect(result).toBe(
        'https://geo.btaa.org/?format=json&search_field=all_fields&f%5Bdc_publisher_sm%5D%5B%5D=MIT+Libraries+%26+Archives'
      );
    });

    it('handles empty field name', () => {
      const result = createFacetSearchUrl('', 'test value');

      expect(result).toBe(
        'https://geo.btaa.org/?format=json&search_field=all_fields&f%5B%5D%5B%5D=test+value'
      );
    });

    it('handles empty value', () => {
      const result = createFacetSearchUrl('dc_publisher_sm', '');

      expect(result).toBe(
        'https://geo.btaa.org/?format=json&search_field=all_fields&f%5Bdc_publisher_sm%5D%5B%5D='
      );
    });

    it('handles numeric values', () => {
      const result = createFacetSearchUrl('dct_temporal_sm', '2023');

      expect(result).toBe(
        'https://geo.btaa.org/?format=json&search_field=all_fields&f%5Bdct_temporal_sm%5D%5B%5D=2023'
      );
    });

    it('handles complex field names with underscores', () => {
      const result = createFacetSearchUrl('gbl_resourceClass_sm', 'Point Data');

      expect(result).toBe(
        'https://geo.btaa.org/?format=json&search_field=all_fields&f%5Bgbl_resourceClass_sm%5D%5B%5D=Point+Data'
      );
    });

    it('handles values with spaces and special characters', () => {
      const result = createFacetSearchUrl(
        'dc_publisher_sm',
        'University of Minnesota (Twin Cities)'
      );

      expect(result).toBe(
        'https://geo.btaa.org/?format=json&search_field=all_fields&f%5Bdc_publisher_sm%5D%5B%5D=University+of+Minnesota+%28Twin+Cities%29'
      );
    });

    it('creates URL with proper encoding for international characters', () => {
      const result = createFacetSearchUrl(
        'dc_publisher_sm',
        'Université de Montréal'
      );

      expect(result).toBe(
        'https://geo.btaa.org/?format=json&search_field=all_fields&f%5Bdc_publisher_sm%5D%5B%5D=Universit%C3%A9+de+Montr%C3%A9al'
      );
    });

    it('handles very long field names', () => {
      const longField =
        'very_long_field_name_with_many_underscores_and_characters';
      const result = createFacetSearchUrl(longField, 'test value');

      expect(result).toContain('format=json');
      expect(result).toContain('search_field=all_fields');
      expect(result).toContain(encodeURIComponent(`f[${longField}][]`));
      expect(result).toContain('test+value');
    });

    it('handles very long values', () => {
      const longValue =
        'This is a very long value with many words and characters that should be properly encoded in the URL';
      const result = createFacetSearchUrl('dc_publisher_sm', longValue);

      expect(result).toContain('format=json');
      expect(result).toContain('search_field=all_fields');
      expect(result).toContain('f%5Bdc_publisher_sm%5D%5B%5D=');
      // URLSearchParams uses + for spaces, not %20
      expect(result).toContain(
        'This+is+a+very+long+value+with+many+words+and+characters+that+should+be+properly+encoded+in+the+URL'
      );
    });
  });

  describe('Integration Tests', () => {
    it('parseFacetUrl and createFacetSearchUrl work together', () => {
      const originalField = 'dc_publisher_sm';
      const originalValue = 'MIT Libraries';

      // Create URL
      const createdUrl = createFacetSearchUrl(originalField, originalValue);

      // Extract the facet parameter from the created URL
      const url = new URL(createdUrl);
      const facetParam = url.searchParams.get('f[dc_publisher_sm][]');

      expect(facetParam).toBe(originalValue);
    });

    it('handles round-trip conversion for complex values', () => {
      const field = 'gbl_resourceClass_sm';
      const value = 'Point Data & Raster Data';

      const createdUrl = createFacetSearchUrl(field, value);
      const url = new URL(createdUrl);
      const facetParam = url.searchParams.get(`f[${field}][]`);

      expect(facetParam).toBe(value);
    });

    it('maintains consistency with real-world facet data', () => {
      // Test with actual facet data that might be used in the application
      const testCases = [
        { field: 'dc_publisher_sm', value: 'MIT Libraries' },
        { field: 'gbl_resourceClass_sm', value: 'Dataset' },
        { field: 'dct_temporal_sm', value: '2020' },
        { field: 'dc_subject_sm', value: 'Geographic Information Systems' },
        { field: 'dc_publisher_sm', value: 'University of Minnesota' },
      ];

      testCases.forEach(({ field, value }) => {
        const createdUrl = createFacetSearchUrl(field, value);
        const url = new URL(createdUrl);
        const facetParam = url.searchParams.get(`f[${field}][]`);

        expect(facetParam).toBe(value);
      });
    });
  });
});

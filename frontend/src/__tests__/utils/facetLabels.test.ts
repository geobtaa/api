import { describe, it, expect } from 'vitest';
import {
  getFacetLabel,
  normalizeFacetId,
  getLegacyFacetName,
  FACET_LABELS,
} from '../../utils/facetLabels';

describe('facetLabels', () => {
  describe('getFacetLabel', () => {
    it('returns humanized label for relationship field dct_isPartOf_sm', () => {
      expect(getFacetLabel('dct_isPartOf_sm')).toBe('Is part of');
    });

    it('returns humanized label for relationship field pcdm_memberOf_sm', () => {
      expect(getFacetLabel('pcdm_memberOf_sm')).toBe('Collection records');
    });

    it('returns humanized label for b1g_localCollectionLabel_sm', () => {
      expect(getFacetLabel('b1g_localCollectionLabel_sm')).toBe(
        'Local collection'
      );
    });

    it('returns known labels for standard facets', () => {
      expect(getFacetLabel('dct_spatial_sm')).toBe('Place');
      expect(getFacetLabel('gbl_resourceClass_sm')).toBe('Resource Class');
      expect(getFacetLabel('schema_provider_s')).toBe('Provider');
      expect(getFacetLabel('dct_publisher_sm')).toBe('Publisher');
    });

    it('returns normalized field when no label is defined', () => {
      expect(getFacetLabel('unknown_field_s')).toBe('unknown_field_s');
    });

    it('normalizes legacy agg IDs and returns label', () => {
      expect(getFacetLabel('spatial_agg')).toBe('Place');
      expect(getFacetLabel('resource_class_agg')).toBe('Resource Class');
    });
  });

  describe('normalizeFacetId', () => {
    it('maps legacy agg IDs to field names', () => {
      expect(normalizeFacetId('spatial_agg')).toBe('dct_spatial_sm');
      expect(normalizeFacetId('resource_class_agg')).toBe(
        'gbl_resourceClass_sm'
      );
      expect(normalizeFacetId('publisher_agg')).toBe('dct_publisher_sm');
    });

    it('returns field name unchanged when not in map', () => {
      expect(normalizeFacetId('dct_isPartOf_sm')).toBe('dct_isPartOf_sm');
    });
  });

  describe('getLegacyFacetName', () => {
    it('maps field names to legacy agg IDs where defined', () => {
      expect(getLegacyFacetName('dct_spatial_sm')).toBe('spatial_agg');
      expect(getLegacyFacetName('dct_publisher_sm')).toBe('publisher_agg');
    });

    it('returns field name unchanged when no legacy mapping', () => {
      expect(getLegacyFacetName('dct_isPartOf_sm')).toBe('dct_isPartOf_sm');
    });
  });

  describe('FACET_LABELS', () => {
    it('includes relationship and collection labels for Active Filters', () => {
      expect(FACET_LABELS['dct_isPartOf_sm']).toBe('Is part of');
      expect(FACET_LABELS['pcdm_memberOf_sm']).toBe('Collection records');
      expect(FACET_LABELS['b1g_localCollectionLabel_sm']).toBe(
        'Local collection'
      );
    });
  });
});

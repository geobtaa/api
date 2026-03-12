import { describe, it, expect } from 'vitest';
import {
  buildSearchUrl,
  buildSearchUrlForHexes,
} from '../../utils/h3SearchUrl';

describe('h3SearchUrl', () => {
  describe('buildSearchUrl', () => {
    it('builds URL for single hex', () => {
      const url = buildSearchUrl('861f1ee47ffffff', 6);
      expect(url).toMatch(/^\/search\?/);
      expect(url).toContain('include_filters%5Bh3_res6%5D%5B%5D=861f1ee47ffffff');
    });

    it('includes search query when provided', () => {
      const url = buildSearchUrl('861f1ee47ffffff', 6, 'test query');
      expect(url).toContain('q=test+query');
    });

    it('preserves existing query params and removes H3 filters', () => {
      const url = buildSearchUrl('861f1ee47ffffff', 6, '', 'foo=bar&include_filters[h3_res5][]=old');
      expect(url).toContain('foo=bar');
      expect(url).toContain('861f1ee47ffffff');
      expect(url).not.toContain('old');
    });
  });

  describe('buildSearchUrlForHexes', () => {
    it('builds URL for single hex', () => {
      const url = buildSearchUrlForHexes(['861f1ee47ffffff'], 6);
      expect(url).toMatch(/^\/search\?/);
      expect(url).toContain('include_filters%5Bh3_res6%5D%5B%5D=861f1ee47ffffff');
    });

    it('builds URL for multiple hexes', () => {
      const url = buildSearchUrlForHexes(
        ['861f1ee47ffffff', '861f1ee4fffffff'],
        6
      );
      expect(url).toContain('861f1ee47ffffff');
      expect(url).toContain('861f1ee4fffffff');
    });

    it('caps at maxHexes when provided', () => {
      const hexes = Array.from({ length: 100 }, (_, i) => `hex${i}`);
      const url = buildSearchUrlForHexes(hexes, 6, undefined, undefined, 10);
      const matches = url.match(/hex\d+/g) ?? [];
      expect(matches).toHaveLength(10);
    });
  });
});

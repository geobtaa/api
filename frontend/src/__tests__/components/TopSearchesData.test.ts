import {
  queryCategory,
  hasReviewedQueryCategory,
} from '../../data/analytics/queryCategories';
import { describe, expect, it } from 'vitest';
import snapshot from '../../data/analytics/topSearches2026.json';
import september from '../../data/analytics/september2026.json';
import allTime from '../../data/analytics/allTimeThroughSeptember2026.json';

const months = { ...snapshot.months, '2026-09': september.topSearches };

describe('top 50 search snapshots', () => {
  it.each([
    ['2026-07', 6457, 2124, 559],
    ['2026-08', 7545, 3021, 652],
    ['2026-09', 5536, 1706, 478],
  ] as const)(
    'preserves complete %s rankings and coverage',
    (month, searches, withQuery, ranked) => {
      const data = months[month];
      expect(data.searches).toBe(searches);
      expect(data.withQuery).toBe(withQuery);
      expect(data.queries).toHaveLength(50);
      expect(new Set(data.queries.map((row) => row.term)).size).toBe(50);
      expect(data.queries.reduce((sum, row) => sum + row.count, 0)).toBe(
        ranked
      );
      expect(data.rankedSearches).toBe(ranked);
      expect(
        data.queries.every(
          (row, index, all) =>
            row.term.trim() &&
            row.count > 0 &&
            (!index || all[index - 1].count >= row.count)
        )
      ).toBe(true);
    }
  );
});

it('categorizes all saved queries without changing case-specific counts', () => {
  for (const month of [...Object.values(months), allTime]) {
    for (const query of month.queries) {
      expect(hasReviewedQueryCategory(query.term), query.term).toBe(true);
      expect(queryCategory(query.term) === 'Mixed or unclear').toBe(
        [
          '-sanborn',
          'indiana field survey iran hardin i 38l',
          'comparative',
        ].includes(query.term)
      );
    }
  }
  expect(queryCategory('Austin')).toBe(queryCategory('austin'));
  expect(queryCategory('turkey  maps')).toBe('Maps & imagery');
  expect(queryCategory('lakes rivers AND minneapolis')).toBe(
    'Environment & land use'
  );
  expect(queryCategory('an unreviewed query')).toBe('Mixed or unclear');
});

// Cover distinct September query forms, including topics, codes, and non-English places.
it.each([
  ['water quality', 'Environment & land use'],
  ['hennepin county parcels', 'Environment & land use'],
  ['indiana population', 'Society & history'],
  ['قم ایران', 'Places & regions'],
  ['Kitai', 'Places & regions'],
  ['n501', 'Maps & imagery'],
  ['DS1105-1009DA017', 'Maps & imagery'],
  ['08d-03', 'Catalogs & tools'],
  ['WMS', 'Catalogs & tools'],
  ['"indiana university"', 'People & institutions'],
  ['Main st childa pa', 'Addresses & coordinates'],
  ['comparative', 'Mixed or unclear'],
])('classifies %s as %s', (term, category) => {
  expect(queryCategory(term)).toBe(category);
});

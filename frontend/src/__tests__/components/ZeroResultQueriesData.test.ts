import snapshot from '../../data/analytics/zeroResultQueries2026.json';
import { searchSnapshots } from '../../data/analytics/searches2026';

describe('complete zero-result query rankings', () => {
  it.each(['2026-07', '2026-08'] as const)(
    'reconciles %s coverage and includes lower-frequency queries',
    (month) => {
      const data = snapshot.months[month];
      expect(data.zeroQueries).toHaveLength(100);
      expect(new Set(data.zeroQueries.map((row) => row.term)).size).toBe(100);
      expect(data.withQuery + data.withoutQuery).toBe(data.zeroResults);
      expect(data.zeroQueries.reduce((sum, row) => sum + row.count, 0)).toBe(
        data.rankedZeroResults
      );
      expect(data.rankedZeroResults).toBeLessThan(data.withQuery);
      expect(data.distinctQueries).toBeGreaterThan(100);
      expect(data.zeroQueries.some((row) => row.count === 2)).toBe(true);
      expect(
        data.zeroQueries.every((row) => row.count > 0 && row.term.trim())
      ).toBe(true);
      data.zeroQueries.slice(1).forEach((row, index) => {
        expect(row.count).toBeLessThanOrEqual(data.zeroQueries[index].count);
      });
      expect(searchSnapshots[month].zeroQueries).toEqual(data.zeroQueries);
      expect(searchSnapshots[month].zeroQueryCoverage.exportedAt).toBe(
        snapshot.exportedAt
      );
      expect(snapshot.minimumZeroResults).toBe(1);
    }
  );
});

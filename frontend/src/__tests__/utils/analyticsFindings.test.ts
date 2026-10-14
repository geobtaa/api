import { describe, expect, it } from 'vitest';
import {
  buildFindings,
  previousCalendarMonth,
  type FindingSummary,
} from '../../utils/analyticsFindings';
const summary: FindingSummary = {
  searches: 3000,
  resourceViews: 2000,
  downloadClicks: 300,
  zeroResultSearches: 200,
};

describe('defensible report findings', () => {
  it('normalizes month length and shows the source counts', () => {
    const findings = buildFindings({
      period: '2026-09',
      summary,
      previous: { ...summary, searches: 4650 },
      leader: { title: 'A map', views: 40 },
    });
    expect(findings).toHaveLength(3);
    expect(findings[0].headline).toBe('Searches: 33.3% fewer per day');
    expect(findings[0].detail).toContain('3,000 in September 2026 (30 days)');
    expect(findings[0].detail).toContain('4,650 in August 2026 (31 days)');
    expect(findings[1].href).toContain('month=2026-09#top-resources');
    expect(findings[2].headline).toBe('6.7% of searches displayed no results');
  });
  it('does not headline tiny baselines, zero baselines, or equal daily rates', () => {
    for (const before of [0, 1, 99, 3100]) {
      const result = buildFindings({
        period: '2026-09',
        summary,
        previous: { ...summary, searches: before },
      });
      expect(result[0].headline).toBe('3,000 searches recorded');
      expect(result[0].headline).not.toMatch(/Infinity|NaN/);
    }
  });
  it('does not invent a baseline for all time or small-volume discovery', () => {
    const result = buildFindings({
      period: 'all',
      summary: { ...summary, searches: 50, zeroResultSearches: 5 },
      leader: { title: 'Small count', views: 9 },
    });
    expect(result[0].detail).toContain(
      'A comparison with the previous month is not available'
    );
    expect(result[1].label).toBe('Resource activity');
    expect(result[2].href).toBe('#report-provenance');
    expect(previousCalendarMonth('2027-01')).toBe('2026-12');
    expect(previousCalendarMonth('all')).toBeNull();
  });
  it('links the largest same-direction member change and preserves the month', () => {
    const result = buildFindings({
      period: '2026-09',
      summary,
      previous: { ...summary, resourceViews: 4000 },
      members: [
        {
          code: '01',
          slug: 'example-university',
          shortName: 'Example',
          resourceViews: 200,
          downloadClicks: 20,
        },
        {
          code: '02',
          slug: 'growing-university',
          shortName: 'Growing',
          resourceViews: 1800,
          downloadClicks: 20,
        },
      ],
      previousMembers: [
        { code: '01', resourceViews: 1500, downloadClicks: 20 },
        { code: '02', resourceViews: 500, downloadClicks: 20 },
      ],
    });
    expect(result[0].supportingLink).toEqual({
      label: 'Example: 1,300 fewer resource views',
      href: '/analytics/members?month=2026-09&institution=example-university#members',
    });
  });
});

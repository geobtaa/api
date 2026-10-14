import { expect, it } from 'vitest';
import {
  allTimeMembers,
  allTimeMemberDaily,
  allTimeProviderSnapshot,
  memberDays,
} from '../../data/analytics/memberAllTime';
import baseline from '../../data/analytics/memberAllTimeCurrent.json';
const expectedDays =
  (Date.parse(baseline.endExclusive) - Date.parse(baseline.start)) / 86400000;
it('reconciles preserved university totals and every daily series', () => {
  expect(memberDays).toHaveLength(expectedDays);
  expect(memberDays[0]).toBe('2026-07-01');
  expect(memberDays.at(-1)).toBe(
    new Date(Date.parse(baseline.endExclusive) - 86400000)
      .toISOString()
      .slice(0, 10)
  );
  for (const member of allTimeMembers) {
    const saved = baseline.groups.find(
      (row) => row.grouping === 'code' && row.name === member.name
    )!;
    expect(saved, member.name).toBeDefined();
    expect(member.resourceViews).toBe(saved.views);
    expect(member.downloadClicks).toBe(saved.downloads);
    expect(member.catalogRecords).toBe(saved.inventory);
    expect(member.activeResources).toBe(saved.activeResources);
    expect(member.impressions).toBe(saved.impressions);
    expect(member.sourceClicks).toBe(saved.sourceClicks);
    expect(
      allTimeMemberDaily[member.code].views.reduce((a, b) => a + b, 0)
    ).toBe(member.resourceViews);
    expect(
      allTimeMemberDaily[member.code].downloads.reduce((a, b) => a + b, 0)
    ).toBe(member.downloadClicks);
  }
});
it('reconciles all provider daily values across all published months', () => {
  for (const group of allTimeProviderSnapshot.groups) {
    expect(group.daily).toHaveLength(expectedDays);
    expect(group.daily.reduce((n, day) => n + day.views, 0)).toBe(
      group.resourceViews
    );
    expect(group.daily.reduce((n, day) => n + day.downloads, 0)).toBe(
      group.downloadClicks
    );
  }
});

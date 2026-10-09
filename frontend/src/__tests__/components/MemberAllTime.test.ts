import { expect, it } from 'vitest';
import {
  allTimeMembers,
  allTimeMemberDaily,
  allTimeProviderSnapshot,
  memberDays,
} from '../../data/analytics/memberAllTime';
import baseline from '../../data/analytics/allTime2026.json';
it('reconciles preserved university totals and every daily series', () => {
  expect(memberDays).toHaveLength(62);
  expect(memberDays[0]).toBe('2026-07-01');
  expect(memberDays.at(-1)).toBe('2026-08-31');
  for (const member of allTimeMembers) {
    const saved = baseline.codes.find((row) => row.label === member.code)!;
    if (member.code !== '10')
      for (const key of [
        'catalogRecords',
        'activeResources',
        'resourceViews',
        'downloadClicks',
        'impressions',
        'sourceClicks',
      ] as const)
        expect(member[key]).toBe(saved[key]);
    expect(
      allTimeMemberDaily[member.code].views.reduce((a, b) => a + b, 0)
    ).toBe(member.resourceViews);
    expect(
      allTimeMemberDaily[member.code].downloads.reduce((a, b) => a + b, 0)
    ).toBe(member.downloadClicks);
  }
  expect(allTimeMembers.find((row) => row.code === '10')?.resourceViews).toBe(
    1180
  );
});
it('reconciles all provider daily values across both months', () => {
  for (const group of allTimeProviderSnapshot.groups) {
    expect(group.daily).toHaveLength(62);
    expect(group.daily.reduce((n, day) => n + day.views, 0)).toBe(
      group.resourceViews
    );
    expect(group.daily.reduce((n, day) => n + day.downloads, 0)).toBe(
      group.downloadClicks
    );
  }
});

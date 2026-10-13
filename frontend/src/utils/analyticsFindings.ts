import { analyticsReportHref } from '../config/analyticsReports';
import { monthDays, monthLabel } from '../config/analyticsPeriods';

export type FindingSummary = {
  searches: number;
  resourceViews: number;
  downloadClicks: number;
  zeroResultSearches: number;
};
export type Finding = {
  label: string;
  headline: string;
  detail: string;
  href: string;
  action: string;
  supportingLink?: { label: string; href: string };
};
const number = new Intl.NumberFormat('en-US');

export function previousCalendarMonth(period: string): string | null {
  if (!/^\d{4}-\d{2}$/.test(period)) return null;
  const date = new Date(`${period}-01T00:00:00Z`);
  date.setUTCMonth(date.getUTCMonth() - 1);
  return date.toISOString().slice(0, 7);
}

export function buildFindings({
  period,
  summary,
  previous,
  leader,
  members,
  previousMembers,
}: {
  period: string;
  summary: FindingSummary;
  previous?: FindingSummary;
  leader?: { title: string; views: number };
  members?: {
    code: string;
    slug: string;
    shortName: string;
    resourceViews: number;
    downloadClicks: number;
  }[];
  previousMembers?: {
    code: string;
    resourceViews: number;
    downloadClicks: number;
  }[];
}): Finding[] {
  const previousPeriod = previousCalendarMonth(period);
  const candidates =
    previous && previousPeriod
      ? (
          [
            ['searches', 'Searches'],
            ['resourceViews', 'Resource views'],
            ['downloadClicks', 'Download clicks'],
          ] as const
        )
          .flatMap(([key, label]) => {
            const before = previous[key];
            const current = summary[key];
            const percent =
              (current /
                monthDays(period) /
                (before / monthDays(previousPeriod)) -
                1) *
              100;
            // A descriptive signal, not a significance test. Never headline a tiny baseline.
            if (
              before < 100 ||
              current < 100 ||
              Math.abs(current - before) < 50 ||
              !Number.isFinite(percent) ||
              Math.abs(percent) < 5
            )
              return [];
            return [{ key, label, before, current, percent }];
          })
          .sort((a, b) => Math.abs(b.percent) - Math.abs(a.percent))
      : [];
  const change = candidates[0];
  const activity: Finding = change
    ? {
        label: 'A meaningful change',
        headline: `${change.label}: ${Math.abs(change.percent).toFixed(1)}% ${change.percent > 0 ? 'more' : 'fewer'} per day`,
        detail: `${number.format(change.current)} in ${monthLabel(period)} (${monthDays(period)} days), versus ${number.format(change.before)} in ${monthLabel(previousPeriod!)} (${monthDays(previousPeriod!)} days). This describes recorded activity, not its cause.`,
        href: `${analyticsReportHref('comparison', period)}#comparison`,
        action: 'Compare the months',
      }
    : {
        label:
          period === 'all'
            ? 'Across this reporting period'
            : 'Recorded activity',
        headline: `${number.format(summary.searches)} searches recorded`,
        detail: `${number.format(summary.resourceViews)} resource views and ${number.format(summary.downloadClicks)} download-link clicks. ${previous ? 'No daily-rate change met the headline thresholds.' : 'No comparable prior calendar month is available for this view.'}`,
        href: `${analyticsReportHref('comparison', period)}#comparison`,
        action: 'Explore the counts',
      };
  if (change && change.key !== 'searches' && members && previousMembers) {
    const metric = change.key;
    const contributors = members
      .flatMap((member) => {
        const before = previousMembers.find(
          (row) => row.code === member.code
        )?.[metric];
        const current = member[metric];
        if (
          before == null ||
          before < 100 ||
          Math.abs(current - before) < 50 ||
          Math.sign(current - before) !== Math.sign(change.percent)
        )
          return [];
        return [{ member, difference: current - before }];
      })
      .sort((a, b) => Math.abs(b.difference) - Math.abs(a.difference));
    const contributor = contributors[0];
    if (contributor)
      activity.supportingLink = {
        label: `${contributor.member.shortName}: ${number.format(Math.abs(contributor.difference))} ${contributor.difference > 0 ? 'more' : 'fewer'} ${change.label.toLowerCase()}`,
        href: `${analyticsReportHref('members', period)}&institution=${encodeURIComponent(contributor.member.slug)}#members`,
      };
  }
  const resource: Finding =
    leader && leader.views >= 10
      ? {
          label: 'A resource drawing attention',
          headline: leader.title,
          detail: `${number.format(leader.views)} resource views—the highest count in the saved resource ranking. Views count recorded actions, not unique people.`,
          href: `${analyticsReportHref('content', period)}#top-resources`,
          action: 'Explore the resource ranking',
        }
      : {
          label: 'Resource activity',
          headline: `${number.format(summary.resourceViews)} resource views`,
          detail:
            'No resource in the saved ranking meets the 10-view headline threshold.',
          href: `${analyticsReportHref('content', period)}#top-resources`,
          action: 'Explore resource activity',
        };
  const discovery: Finding =
    summary.searches >= 100 &&
    summary.zeroResultSearches >= 10 &&
    summary.zeroResultSearches <= summary.searches
      ? {
          label: 'A discovery opportunity',
          headline: `${((100 * summary.zeroResultSearches) / summary.searches).toFixed(1)}% of searches displayed no results`,
          detail: `${number.format(summary.zeroResultSearches)} of ${number.format(summary.searches)} recorded searches. Inspect saved filters and pagination before interpreting this as a gap in the collection.`,
          href: `${analyticsReportHref('discovery', period)}#zero-results`,
          action: 'Inspect searches without results',
        }
      : {
          label: 'Know the coverage',
          headline: 'Keep the evidence with the story',
          detail:
            'Review source coverage and definitions before sharing conclusions. Small counts do not support a discovery headline.',
          href: '#report-provenance',
          action: 'Review provenance and coverage',
        };
  return [activity, resource, discovery];
}

import { createContext, useContext, useMemo } from 'react';
import { restoreAnalyticsHelpers } from './analyticsHelpers';
export type AnalyticsData = {
  memberCollectionViews: Record<
    string,
    Record<string, { id: string; title: string; views: number }[]>
  >;
  memberLeadingContent: Record<
    string,
    Record<
      string,
      {
        viewed: import('../../data/analytics/memberJuly2026').MemberContentEntry[];
        downloaded: import('../../data/analytics/memberJuly2026').MemberContentEntry[];
      }
    >
  >;
  queryTranslations: Record<
    string,
    { language: string; english: string; note: string }
  >;
  'collectionViewsCurrent.json': {
    default: typeof import('../../data/analytics/collectionViewsCurrent.json');
  };
  outcomes: typeof import('../../data/analytics/outcomes');
  'allTimeCurrent.json': {
    default: typeof import('../../data/analytics/allTimeCurrent.json');
  };
  'monthlySnapshots.json': {
    default: typeof import('../../data/analytics/monthlySnapshots.json');
  };
  clients2026: typeof import('../../data/analytics/clients2026');
  providers2026: typeof import('../../data/analytics/providers2026');
  popularMomentum: typeof import('../../data/analytics/popularMomentum');
  september2026: typeof import('../../data/analytics/september2026');
  july2026: typeof import('../../data/analytics/july2026');
  august2026: typeof import('../../data/analytics/august2026');
  zeroQueryCategory: typeof import('../../data/analytics/zeroQueryCategory');
  'reliabilityEndpointsCurrent.json': {
    default: typeof import('../../data/analytics/reliabilityEndpointsCurrent.json');
  };
  memberAllTime: typeof import('../../data/analytics/memberAllTime');
  queryCategories: typeof import('../../data/analytics/queryCategories');
  'topSearches2026.json': {
    default: typeof import('../../data/analytics/topSearches2026.json');
  };
  searches2026: typeof import('../../data/analytics/searches2026');
  reportsAugust2026: typeof import('../../data/analytics/reportsAugust2026');
  popularHistory2026: typeof import('../../data/analytics/popularHistory2026');
  memberJuly2026: typeof import('../../data/analytics/memberJuly2026');
  'popularMomentumCurrent.json': {
    default: typeof import('../../data/analytics/popularMomentumCurrent.json');
  };
  'zeroQueryCategories.json': {
    default: typeof import('../../data/analytics/zeroQueryCategories.json');
  };
};
export const AnalyticsDataContext = createContext<AnalyticsData | null>(null);
export function useAnalyticsData(): AnalyticsData {
  const snapshot = useContext(AnalyticsDataContext);
  if (!snapshot) throw new Error('Authenticated analytics data is required');
  return useMemo(() => restoreAnalyticsHelpers(snapshot), [snapshot]);
}

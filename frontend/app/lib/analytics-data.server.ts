import queryTranslations from '../../src/data/analytics/queryTranslations.json';
// Server-only snapshot payload; the route authenticates before returning it.
// Functions are restored on the client from this authenticated data payload.
import collectionViewsCurrent from '../../src/data/analytics/collectionViewsCurrent.json';
import * as outcomes from '../../src/data/analytics/outcomes';
import allTimeCurrent from '../../src/data/analytics/allTimeCurrent.json';
import monthlySnapshots from '../../src/data/analytics/monthlySnapshots.json';
import * as clients2026 from '../../src/data/analytics/clients2026';
import * as providers2026 from '../../src/data/analytics/providers2026';
import * as popularMomentum from '../../src/data/analytics/popularMomentum';
import * as september2026 from '../../src/data/analytics/september2026';
import * as july2026 from '../../src/data/analytics/july2026';
import * as august2026 from '../../src/data/analytics/august2026';
import * as zeroQueryCategory from '../../src/data/analytics/zeroQueryCategory';
import reliabilityEndpointsCurrent from '../../src/data/analytics/reliabilityEndpointsCurrent.json';
import * as memberAllTime from '../../src/data/analytics/memberAllTime';
import * as queryCategories from '../../src/data/analytics/queryCategories';
import topSearches2026 from '../../src/data/analytics/topSearches2026.json';
import * as searches2026 from '../../src/data/analytics/searches2026';
import * as reportsAugust2026 from '../../src/data/analytics/reportsAugust2026';
import * as popularHistory2026 from '../../src/data/analytics/popularHistory2026';
import * as memberJuly2026 from '../../src/data/analytics/memberJuly2026';
import popularMomentumCurrent from '../../src/data/analytics/popularMomentumCurrent.json';
import zeroQueryCategories from '../../src/data/analytics/zeroQueryCategories.json';

export const analyticsSnapshot = JSON.parse(
  JSON.stringify({
    'collectionViewsCurrent.json': { default: collectionViewsCurrent },
    queryTranslations,
    outcomes: outcomes,
    'allTimeCurrent.json': { default: allTimeCurrent },
    'monthlySnapshots.json': { default: monthlySnapshots },
    clients2026: clients2026,
    providers2026: providers2026,
    popularMomentum: popularMomentum,
    september2026: september2026,
    july2026: july2026,
    august2026: august2026,
    zeroQueryCategory: zeroQueryCategory,
    'reliabilityEndpointsCurrent.json': {
      default: reliabilityEndpointsCurrent,
    },
    memberAllTime: memberAllTime,
    queryCategories: queryCategories,
    'topSearches2026.json': { default: topSearches2026 },
    searches2026: searches2026,
    reportsAugust2026: reportsAugust2026,
    popularHistory2026: popularHistory2026,
    memberJuly2026: memberJuly2026,
    'popularMomentumCurrent.json': { default: popularMomentumCurrent },
    'zeroQueryCategories.json': { default: zeroQueryCategories },
  })
);

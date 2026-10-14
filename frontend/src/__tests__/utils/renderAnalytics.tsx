import { render, type RenderOptions } from '@testing-library/react';
import type { ReactElement } from 'react';
import { AnalyticsDataContext } from '../../components/analytics/AnalyticsData';
import { analyticsSnapshot } from '../../../app/lib/analytics-data.server';

export function renderAnalytics(ui: ReactElement, options?: RenderOptions) {
  return render(
    <AnalyticsDataContext.Provider value={analyticsSnapshot}>
      {ui}
    </AnalyticsDataContext.Provider>,
    options
  );
}

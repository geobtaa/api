import { describe, expect, it } from 'vitest';
import {
  analyticsReports,
  analyticsReportHref,
  selectedAnalyticsReport,
} from '../../config/analyticsReports';
import { loader } from '../../../app/routes/analytics';
import type { LoaderFunctionArgs } from 'react-router';

function load(path: string, report?: string) {
  return loader({
    request: new Request(`http://localhost${path}`),
    params: { report },
  } as LoaderFunctionArgs);
}

describe('analytics report routes', () => {
  for (const report of analyticsReports) {
    const path =
      report.id === 'overview' ? '/analytics' : `/analytics/${report.id}`;
    it(`routes ${report.id} and preserves its month`, () => {
      expect(analyticsReportHref(report.id, '2026-09')).toBe(
        `${path}?month=2026-09`
      );
      expect(
        selectedAnalyticsReport(new URLSearchParams('month=2026-09'), path).id
      ).toBe(report.id);
      const legacy = load(
        `/analytics?report=${report.id}&month=2026-09&runtime=1`
      ) as Response;
      expect(legacy.status).toBe(301);
      expect(legacy.headers.get('Location')).toBe(
        `${path}?month=2026-09&runtime=1`
      );
      expect(
        load(
          `${path}?month=all`,
          report.id === 'overview' ? undefined : report.id
        )
      ).toHaveProperty('report.id', report.id);
    });
  }
  it('canonicalizes aliases, prioritizes paths, and rejects unknown paths', () => {
    expect(
      (
        load('/analytics/activity?month=all', 'activity') as Response
      ).headers.get('Location')
    ).toBe('/analytics?month=all');
    expect(
      (load('/analytics/overview', 'overview') as Response).headers.get(
        'Location'
      )
    ).toBe('/analytics');
    expect(
      (
        load(
          '/analytics/content?report=members&month=all',
          'content'
        ) as Response
      ).headers.get('Location')
    ).toBe('/analytics/content?month=all');
    try {
      load('/analytics/missing', 'missing');
      throw new Error('Expected 404');
    } catch (error) {
      expect(error).toBeInstanceOf(Response);
      expect((error as Response).status).toBe(404);
    }
  });
});

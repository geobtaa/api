import { describe, expect, it, vi } from 'vitest';
vi.mock('../../../app/lib/server-api', () => ({
  serverFetch: vi.fn(async () =>
    Response.json({ email: 'reader@example.org' })
  ),
}));
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
    context: {},
    url: new URL(`http://localhost${path}`),
    pattern: '/analytics/:report?',
  } as LoaderFunctionArgs);
}

describe('analytics report routes', () => {
  for (const report of analyticsReports) {
    const path =
      report.id === 'overview'
        ? '/analytics'
        : `/analytics/${report.id === 'discovery' ? 'searches' : report.id}`;
    it(`routes ${report.id} and preserves its month`, async () => {
      expect(analyticsReportHref(report.id, '2026-09')).toBe(
        `${path}?month=2026-09`
      );
      expect(
        selectedAnalyticsReport(new URLSearchParams('month=2026-09'), path).id
      ).toBe(report.id);
      const legacy = (await load(
        `/analytics?report=${report.id}&month=2026-09&runtime=1`
      )) as Response;
      expect(legacy.status).toBe(301);
      expect(legacy.headers.get('Location')).toBe(
        `${path}?month=2026-09&runtime=1`
      );
      expect(
        await load(
          `${path}?month=all`,
          report.id === 'overview'
            ? undefined
            : report.id === 'discovery'
              ? 'searches'
              : report.id
        )
      ).toHaveProperty('data.report.id', report.id);
    });
  }
  it('canonicalizes aliases, prioritizes paths, and rejects unknown paths', async () => {
    expect(
      (
        (await load('/analytics/discovery?month=all', 'discovery')) as Response
      ).headers.get('Location')
    ).toBe('/analytics/searches?month=all');
    expect(
      (
        (await load('/analytics/activity?month=all', 'activity')) as Response
      ).headers.get('Location')
    ).toBe('/analytics?month=all');
    expect(
      ((await load('/analytics/overview', 'overview')) as Response).headers.get(
        'Location'
      )
    ).toBe('/analytics');
    expect(
      (
        (await load(
          '/analytics/content?report=members&month=all',
          'content'
        )) as Response
      ).headers.get('Location')
    ).toBe('/analytics/content?month=all');
    try {
      await load('/analytics/missing', 'missing');
      throw new Error('Expected 404');
    } catch (error) {
      expect(error).toBeInstanceOf(Response);
      expect((error as Response).status).toBe(404);
    }
  });
});

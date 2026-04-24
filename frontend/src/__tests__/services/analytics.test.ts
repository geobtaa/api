import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../services/api', () => ({
  getApiBasePath: () => '/api/v1',
  getVisitToken: () => 'visit-123',
}));

import {
  sendAnalyticsBatch,
  serializeSearchParams,
} from '../../services/analytics';

describe('analytics service', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    Object.defineProperty(window, 'location', {
      value: {
        origin: 'https://geo.btaa.org',
        host: 'geo.btaa.org',
      },
      writable: true,
    });
    Object.defineProperty(window, 'sessionStorage', {
      value: {
        getItem: vi.fn().mockReturnValue('visit-123'),
        setItem: vi.fn(),
      },
      writable: true,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('serializes repeated search params into arrays', () => {
    const params = new URLSearchParams();
    params.append('q', 'maps');
    params.append('include_filters[dct_spatial_sm][]', 'Minnesota');
    params.append('include_filters[dct_spatial_sm][]', 'Wisconsin');

    expect(serializeSearchParams(params)).toEqual({
      'include_filters[dct_spatial_sm][]': ['Minnesota', 'Wisconsin'],
      q: 'maps',
    });
  });

  it('prefers sendBeacon for lightweight analytics delivery', () => {
    const sendBeacon = vi.fn().mockReturnValue(true);
    Object.defineProperty(navigator, 'sendBeacon', {
      value: sendBeacon,
      configurable: true,
    });

    const sent = sendAnalyticsBatch({
      events: [{ event_type: 'resource_view', resource_id: 'stanford-123' }],
    });

    expect(sent).toBe(true);
    expect(sendBeacon).toHaveBeenCalledWith(
      expect.stringContaining('/analytics/events'),
      expect.stringContaining('"event_type":"resource_view"')
    );
  });

  it('falls back to keepalive fetch when sendBeacon is unavailable', async () => {
    Object.defineProperty(navigator, 'sendBeacon', {
      value: undefined,
      configurable: true,
    });
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    global.fetch = fetchMock as unknown as typeof fetch;

    const sent = sendAnalyticsBatch({
      searches: [{ search_id: 'search-123', query: 'maps' }],
    });

    expect(sent).toBe(true);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/analytics/events'),
      expect.objectContaining({
        method: 'POST',
        keepalive: true,
        headers: expect.objectContaining({
          'Content-Type': 'text/plain;charset=UTF-8',
        }),
      })
    );
  });
});

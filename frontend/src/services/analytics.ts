import { getApiBasePath, getVisitToken } from './api';

export interface AnalyticsSearchRecord {
  search_id: string;
  visit_token?: string;
  client_name?: string;
  client_version?: string;
  client_channel?: string;
  client_instance?: string;
  source_host?: string;
  query?: string;
  search_url?: string;
  view?: string;
  page?: number;
  per_page?: number;
  sort?: string;
  search_field?: string;
  results_count?: number;
  total_pages?: number;
  zero_results?: boolean;
  occurred_at?: string;
  properties?: Record<string, unknown>;
}

export interface AnalyticsImpressionRecord {
  search_id: string;
  visit_token?: string;
  resource_id: string;
  rank: number;
  page?: number;
  view?: string;
  occurred_at?: string;
  properties?: Record<string, unknown>;
}

export interface AnalyticsEventRecord {
  event_id?: string;
  event_type: string;
  visit_token?: string;
  search_id?: string;
  resource_id?: string;
  client_name?: string;
  client_version?: string;
  client_channel?: string;
  client_instance?: string;
  source_host?: string;
  rank?: number;
  page?: number;
  view?: string;
  label?: string;
  destination_url?: string;
  source_component?: string;
  occurred_at?: string;
  properties?: Record<string, unknown>;
}

interface AnalyticsBatchPayload {
  searches?: AnalyticsSearchRecord[];
  impressions?: AnalyticsImpressionRecord[];
  events?: AnalyticsEventRecord[];
}

const ANALYTICS_CLIENT_NAME = 'geoportal-web';
const ANALYTICS_CLIENT_CHANNEL = 'browser';

function getAnalyticsUrl(): string | null {
  if (typeof window === 'undefined') return null;

  const basePath = getApiBasePath().replace(/\/$/, '');
  if (basePath.startsWith('http://') || basePath.startsWith('https://')) {
    return `${basePath}/analytics/events`;
  }

  return `${window.location.origin}${basePath}/analytics/events`;
}

export function generateAnalyticsId(prefix: string = 'evt'): string {
  if (
    typeof crypto !== 'undefined' &&
    typeof crypto.randomUUID === 'function'
  ) {
    return `${prefix}_${crypto.randomUUID()}`;
  }

  return `${prefix}_${Date.now()}_${Math.random().toString(16).slice(2)}`;
}

function getClientVersion(): string {
  return import.meta.env.VITE_APP_VERSION || 'dev';
}

function getSourceHost(): string | undefined {
  if (typeof window === 'undefined') return undefined;
  return window.location.host || undefined;
}

function withDefaults<T extends Record<string, unknown>>(row: T): T {
  return {
    ...row,
    visit_token: row.visit_token ?? getVisitToken(),
    client_name: row.client_name ?? ANALYTICS_CLIENT_NAME,
    client_version: row.client_version ?? getClientVersion(),
    client_channel: row.client_channel ?? ANALYTICS_CLIENT_CHANNEL,
    source_host: row.source_host ?? getSourceHost(),
    occurred_at:
      typeof row.occurred_at === 'string'
        ? row.occurred_at
        : new Date().toISOString(),
  };
}

export function serializeSearchParams(
  searchParams: URLSearchParams
): Record<string, string | string[]> {
  const serialized: Record<string, string | string[]> = {};

  Array.from(new Set(searchParams.keys()))
    .sort()
    .forEach((key) => {
      const values = searchParams.getAll(key);
      serialized[key] = values.length > 1 ? values : values[0] ?? '';
    });

  return serialized;
}

export function sendAnalyticsBatch(payload: AnalyticsBatchPayload): boolean {
  if (typeof window === 'undefined') return false;

  const searches = (payload.searches || []).map((row) => withDefaults(row));
  const impressions = (payload.impressions || []).map((row) =>
    withDefaults(row)
  );
  const events = (payload.events || []).map((row) =>
    withDefaults({
      ...row,
      event_id: row.event_id ?? generateAnalyticsId('event'),
    })
  );

  if (searches.length === 0 && impressions.length === 0 && events.length === 0) {
    return false;
  }

  const url = getAnalyticsUrl();
  if (!url) return false;

  const body = JSON.stringify({ searches, impressions, events });

  if (
    typeof navigator !== 'undefined' &&
    typeof navigator.sendBeacon === 'function'
  ) {
    try {
      return navigator.sendBeacon(url, body);
    } catch {
      // fall through to fetch keepalive
    }
  }

  void fetch(url, {
    method: 'POST',
    body,
    keepalive: true,
    credentials: 'omit',
    mode: 'cors',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'text/plain;charset=UTF-8',
    },
  }).catch(() => {});

  return true;
}

export function scheduleAnalyticsBatch(payload: AnalyticsBatchPayload): void {
  if (typeof window === 'undefined') return;

  const flush = () => {
    sendAnalyticsBatch(payload);
  };

  if ('requestIdleCallback' in window) {
    window.requestIdleCallback(flush, { timeout: 1000 });
    return;
  }

  window.setTimeout(flush, 0);
}

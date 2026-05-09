import type { GeoDocument } from '../types/api';
import { getApiBasePath } from '../services/api';

export type SearchResultAssetView = 'list' | 'gallery' | 'map';
export type StaticMapVariant = 'basemap' | 'geometry' | 'resource-class-icon';

const IMMUTABLE_THUMBNAIL_PATH_RE = /^\/api\/v1\/thumbnails\/[0-9a-f]{64}$/i;
const IMMUTABLE_STATIC_MAP_PATH_RE =
  /^\/api\/v1\/static-map-assets\/[0-9a-f]{64}$/i;

function toBrowserApiAssetUrl(pathname: string, search: string): string {
  const apiBasePath = getApiBasePath().replace(/\/$/, '');
  const assetPath = pathname.replace(/^\/api\/v1/, '');
  return `${apiBasePath}${assetPath}${search}`;
}

function extractMetaUiUrl(
  result: Pick<GeoDocument, 'meta'>,
  key: 'thumbnail_url' | 'static_map' | 'resource_class_icon_url'
): string | undefined {
  const metaUi = result.meta?.ui;
  let value = metaUi?.[key];

  if (!value && metaUi) {
    try {
      const parsed = JSON.parse(JSON.stringify(metaUi));
      value = parsed[key];
    } catch {
      // Ignore serialization edge cases and keep trying.
    }
  }

  if (!value && metaUi) {
    const descriptor = Object.getOwnPropertyDescriptor(metaUi, key);
    if (descriptor) {
      value = descriptor.value;
    }
  }

  if (!value && metaUi && key in metaUi) {
    value = (metaUi as Record<string, string | null | undefined>)[key];
  }

  if (typeof value !== 'string') {
    return undefined;
  }

  const normalized = value.trim();
  return normalized ? normalized : undefined;
}

export function extractThumbnailUrl(
  result: Pick<GeoDocument, 'meta'>
): string | undefined {
  return extractMetaUiUrl(result, 'thumbnail_url');
}

export function extractStaticMapUrl(
  result: Pick<GeoDocument, 'meta'>
): string | undefined {
  return extractMetaUiUrl(result, 'static_map');
}

export function extractResourceClassIconUrl(
  result: Pick<GeoDocument, 'meta'>
): string | undefined {
  return extractMetaUiUrl(result, 'resource_class_icon_url');
}

export function toSsrAssetUrl(url: string | undefined): string | undefined {
  if (!url || typeof url !== 'string') return undefined;

  const normalizePath = (pathname: string, search: string) => {
    if (IMMUTABLE_THUMBNAIL_PATH_RE.test(pathname)) {
      return toBrowserApiAssetUrl(pathname, search);
    }

    if (IMMUTABLE_STATIC_MAP_PATH_RE.test(pathname)) {
      return toBrowserApiAssetUrl(pathname, search);
    }

    if (pathname.startsWith('/api/v1/thumbnails/')) {
      return pathname.replace('/api/v1', '') + search;
    }

    if (pathname.startsWith('/api/v1/static-maps/')) {
      return pathname.replace('/api/v1', '') + search;
    }

    if (
      pathname.match(
        /^\/api\/v1\/resources\/[^/]+\/(thumbnail|static-map)(\/no-cache)?$/
      )
    ) {
      return pathname.replace('/api/v1', '') + search;
    }

    return url;
  };

  try {
    if (url.startsWith('http://') || url.startsWith('https://')) {
      const parsed = new URL(url);
      return normalizePath(parsed.pathname, parsed.search);
    }

    const base =
      typeof window !== 'undefined'
        ? window.location.origin
        : 'http://localhost';
    const parsed = new URL(url, base);
    return normalizePath(parsed.pathname, parsed.search);
  } catch {
    if (IMMUTABLE_THUMBNAIL_PATH_RE.test(url)) {
      return toBrowserApiAssetUrl(url, '');
    }
    if (IMMUTABLE_STATIC_MAP_PATH_RE.test(url)) {
      return toBrowserApiAssetUrl(url, '');
    }
    if (url.startsWith('/api/v1/')) {
      return url.replace('/api/v1', '');
    }
    return url;
  }
}

function isGenericResourceThumbnailUrl(url: string | undefined): boolean {
  if (!url) return false;

  try {
    const base =
      typeof window !== 'undefined'
        ? window.location.origin
        : 'http://localhost';
    const parsed = new URL(url, base);
    return Boolean(
      parsed.pathname.match(/^\/(api\/v1\/)?resources\/[^/]+\/thumbnail$/)
    );
  } catch {
    return false;
  }
}

function isBridgeThumbnailAssetUrl(url: string | undefined): boolean {
  if (!url) return false;

  try {
    const base =
      typeof window !== 'undefined'
        ? window.location.origin
        : 'http://localhost';
    const parsed = new URL(url, base);
    return parsed.pathname.includes('/store/asset/');
  } catch {
    return url.includes('/store/asset/');
  }
}

function getGeneratedThumbnailUrl(resourceId: string): string {
  return `/resources/${resourceId}/thumbnail`;
}

export function getThumbnailFallbackUrl(
  resourceId: string,
  view: SearchResultAssetView
): string {
  if (view === 'gallery') {
    return `/static-maps/${resourceId}/resource-class-icon`;
  }
  return getGeneratedThumbnailUrl(resourceId);
}

export function getResultPrimaryImageUrl(
  result: Pick<GeoDocument, 'id' | 'meta'>,
  view: SearchResultAssetView
): string | undefined {
  const extracted = extractThumbnailUrl(result);
  const normalized = toSsrAssetUrl(extracted);
  const galleryResourceClassIconUrl =
    view === 'gallery'
      ? toSsrAssetUrl(extractResourceClassIconUrl(result))
      : undefined;

  // Route generic thumbnail endpoints and bridge-backed assets through the
  // canonical resource thumbnail resolver. It decides whether to redirect to
  // hot immutable bytes or return the resource-class placeholder.
  if (
    normalized &&
    (isGenericResourceThumbnailUrl(normalized) ||
      isBridgeThumbnailAssetUrl(extracted))
  ) {
    return getGeneratedThumbnailUrl(result.id);
  }

  if (normalized) {
    return normalized;
  }

  if (galleryResourceClassIconUrl) {
    return galleryResourceClassIconUrl;
  }

  if (view === 'gallery') {
    return getThumbnailFallbackUrl(result.id, view);
  }

  return getGeneratedThumbnailUrl(result.id);
}

export function getStaticMapUrl(
  resourceId: string,
  variant: StaticMapVariant = 'geometry'
): string {
  if (variant === 'basemap') {
    return `/static-maps/${resourceId}`;
  }
  if (variant === 'resource-class-icon') {
    return `/static-maps/${resourceId}/resource-class-icon`;
  }
  return `/static-maps/${resourceId}/geometry`;
}

export function getResultStaticMapUrl(
  result: Pick<GeoDocument, 'id' | 'meta'>
): string {
  const extracted = extractStaticMapUrl(result);
  const normalized = toSsrAssetUrl(extracted);

  if (normalized) {
    return normalized;
  }

  return getStaticMapUrl(result.id, 'geometry');
}

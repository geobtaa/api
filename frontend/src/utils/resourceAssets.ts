import type { GeoDocument } from '../types/api';

export type SearchResultAssetView = 'list' | 'gallery' | 'map';
export type StaticMapVariant = 'basemap' | 'geometry' | 'resource-class-icon';

export function extractThumbnailUrl(
  result: Pick<GeoDocument, 'meta'>
): string | undefined {
  const metaUi = result.meta?.ui;

  let thumbnailUrl = metaUi?.thumbnail_url || metaUi?.['thumbnail_url'];

  if (!thumbnailUrl && metaUi) {
    try {
      const parsed = JSON.parse(JSON.stringify(metaUi));
      thumbnailUrl = parsed.thumbnail_url;
    } catch {
      // Ignore serialization edge cases and keep trying.
    }
  }

  if (!thumbnailUrl && metaUi) {
    const descriptor = Object.getOwnPropertyDescriptor(metaUi, 'thumbnail_url');
    if (descriptor) {
      thumbnailUrl = descriptor.value;
    }
  }

  if (!thumbnailUrl && metaUi && 'thumbnail_url' in metaUi) {
    thumbnailUrl = (metaUi as { thumbnail_url?: string | null }).thumbnail_url;
  }

  if (typeof thumbnailUrl !== 'string') {
    return undefined;
  }

  const normalized = thumbnailUrl.trim();
  return normalized ? normalized : undefined;
}

export function toSsrAssetUrl(url: string | undefined): string | undefined {
  if (!url || typeof url !== 'string') return undefined;

  const normalizePath = (pathname: string, search: string) => {
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
      typeof window !== 'undefined' ? window.location.origin : 'http://localhost';
    const parsed = new URL(url, base);
    return normalizePath(parsed.pathname, parsed.search);
  } catch {
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
      typeof window !== 'undefined' ? window.location.origin : 'http://localhost';
    const parsed = new URL(url, base);
    return Boolean(
      parsed.pathname.match(/^\/(api\/v1\/)?resources\/[^/]+\/thumbnail$/)
    );
  } catch {
    return false;
  }
}

export function getThumbnailFallbackUrl(
  resourceId: string,
  view: SearchResultAssetView
): string {
  if (view === 'gallery') {
    return `/static-maps/${resourceId}/resource-class-icon`;
  }
  return `/thumbnails/${resourceId}`;
}

export function getResultPrimaryImageUrl(
  result: Pick<GeoDocument, 'id' | 'meta'>,
  view: SearchResultAssetView
): string {
  const extracted = extractThumbnailUrl(result);
  const normalized = toSsrAssetUrl(extracted);

  // Search result layouts need the view-specific asset contract.
  // The generic /resources/:id/thumbnail endpoint can render the wrong fallback
  // variant for list/gallery/map cards, so we only trust it when we have a
  // concrete non-generic asset URL.
  if (normalized && !isGenericResourceThumbnailUrl(normalized)) {
    return normalized;
  }

  return getThumbnailFallbackUrl(result.id, view);
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

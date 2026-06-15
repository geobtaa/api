import type { GeoDocumentDetails } from '../types/api';

export interface AllmapsAttributes {
  allmaps_id?: string | null;
  allmaps_annotated?: boolean;
  allmaps_manifest_uri?: string | null;
  allmaps_annotation_url?: string | null;
}

interface AllmapsResource {
  meta?: {
    ui?: {
      allmaps?: AllmapsAttributes | null;
    };
  };
}

export function getAllmapsAttributes(
  resource: AllmapsResource | GeoDocumentDetails | null | undefined
): AllmapsAttributes | null {
  return resource?.meta?.ui?.allmaps ?? null;
}

export function getAllmapsAnnotationUrl(
  allmaps: AllmapsAttributes | null | undefined
): string | null {
  if (!allmaps) return null;

  if (allmaps.allmaps_annotation_url) {
    return allmaps.allmaps_annotation_url;
  }

  if (allmaps.allmaps_manifest_uri) {
    return `https://annotations.allmaps.org/?url=${encodeURIComponent(
      allmaps.allmaps_manifest_uri
    )}`;
  }

  if (allmaps.allmaps_id) {
    return `https://annotations.allmaps.org/manifests/${encodeURIComponent(
      allmaps.allmaps_id
    )}`;
  }

  return null;
}

export function hasAllmapsOverlay(
  resource: AllmapsResource | GeoDocumentDetails | null | undefined
): boolean {
  const allmaps = getAllmapsAttributes(resource);
  return Boolean(
    allmaps?.allmaps_annotated && getAllmapsAnnotationUrl(allmaps)
  );
}

export function getAllmapsViewerUrl(
  allmaps: AllmapsAttributes | null | undefined
): string | null {
  const annotationUrl = getAllmapsAnnotationUrl(allmaps);
  if (!annotationUrl) return null;

  const viewerUrl = new URL('https://viewer.allmaps.org/');
  viewerUrl.searchParams.set('url', annotationUrl);
  return viewerUrl.toString();
}

export function getAllmapsEditorUrl(
  allmaps: AllmapsAttributes | null | undefined
): string | null {
  if (!allmaps?.allmaps_manifest_uri) return null;

  return `https://editor.allmaps.org/#/collection?url=${encodeURIComponent(
    allmaps.allmaps_manifest_uri
  )}`;
}

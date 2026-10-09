import type { GeoDocumentDetails } from '../types/api';

export interface AllmapsAttributes {
  allmaps_id?: string | null;
  allmaps_annotated?: boolean;
  allmaps_manifest_uri?: string | null;
  allmaps_annotation_url?: string | null;
}

interface AllmapsResource {
  attributes?: {
    ogm?: { dct_references_s?: string | Record<string, string> };
  };
  meta?: {
    ui?: {
      allmaps?: AllmapsAttributes | null;
      viewer?: { protocol?: string; endpoint?: string };
    };
  };
}

function httpUrl(value: unknown): string | null {
  if (typeof value !== 'string' || !value.trim()) return null;
  try {
    const url = new URL(value);
    return ['http:', 'https:'].includes(url.protocol) ? value.trim() : null;
  } catch {
    return null;
  }
}

/** Find an editor input even when this resource has not been harvested by Allmaps. */
export function getAllmapsIiifUrl(
  resource: AllmapsResource | null | undefined
): string | null {
  const raw = resource?.attributes?.ogm?.dct_references_s;
  let references: Record<string, unknown> = {};
  try {
    const parsed = typeof raw === 'string' ? JSON.parse(raw) : raw;
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      references = parsed;
    }
  } catch {
    // A usable viewer endpoint may still be available with malformed metadata.
  }

  for (const protocol of ['presentation#manifest', 'image']) {
    for (const scheme of ['http', 'https']) {
      const url = httpUrl(references[`${scheme}://iiif.io/api/${protocol}`]);
      if (url) return url;
    }
  }

  const viewer = resource?.meta?.ui?.viewer;
  return ['iiif_manifest', 'iiif_image'].includes(viewer?.protocol ?? '')
    ? httpUrl(viewer?.endpoint)
    : null;
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
  if (!allmaps?.allmaps_annotated) return null;
  const annotationUrl = getAllmapsAnnotationUrl(allmaps);
  if (!annotationUrl) return null;

  const viewerUrl = new URL('https://viewer.allmaps.org/');
  viewerUrl.searchParams.set('url', annotationUrl);
  return viewerUrl.toString();
}

export function getAllmapsEditorUrl(
  allmaps: AllmapsAttributes | null | undefined,
  iiifUrl?: string | null
): string | null {
  const url = httpUrl(iiifUrl) || httpUrl(allmaps?.allmaps_manifest_uri);
  if (!url) return null;

  return `https://editor.allmaps.org/#/collection?url=${encodeURIComponent(
    url
  )}`;
}

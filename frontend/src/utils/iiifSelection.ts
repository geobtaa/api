/** Public event payload supplied by the temporary OGM Viewer event backport. */
export interface PreviewSelection {
  previewId: string;
  resourceId: string;
  resourceUrl: string;
  renderer: 'image' | 'map';
}
export interface ImageSelection extends PreviewSelection {
  image: {
    url: string;
    index: number;
    count: number;
    occurrence?: number;
  } | null;
}

/** Normalize info documents without confusing encoded identifiers or image requests. */
export function imageSourceKey(value?: string): string | undefined {
  if (!value) return undefined;
  try {
    const url = new URL(value);
    url.hash = '';
    url.pathname = url.pathname.replace(/\/info\.json$/, '').replace(/\/$/, '');
    return url.href;
  } catch {
    return undefined;
  }
}

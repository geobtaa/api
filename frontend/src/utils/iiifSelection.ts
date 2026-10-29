/** The fork owns the viewer event contract; application code imports its generated types. */
export type {
  PreviewSelection,
  ImageSelection,
  ImageNavigation,
} from 'ogm-viewer/lib';

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

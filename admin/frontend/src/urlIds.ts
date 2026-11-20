// Keep the URL-key contract synchronized with backend/app/url_ids.py.
const reserved = new Set([
  'new',
  'import',
  'imports',
  'csv',
  'selections',
  'facets',
  'source-candidates',
  'bridge',
  'detail',
  'association',
  'associations',
  'relationships',
  'metadata',
  'preview-metadata',
  'editor-contract',
  'contract',
  'ui',
]);
export function encodeId(id: string): string {
  if (/^[A-Za-z0-9_-]+$/.test(id) && !reserved.has(id)) return id;
  const bytes = new TextEncoder().encode(id);
  return (
    '~' +
    btoa(String.fromCharCode(...bytes))
      .replaceAll('+', '-')
      .replaceAll('/', '_')
      .replace(/=+$/, '')
  );
}
export function decodeId(key: string): string {
  try {
    const id = key.startsWith('~')
      ? new TextDecoder('utf-8', { fatal: true }).decode(
          Uint8Array.from(
            atob(key.slice(1).replaceAll('-', '+').replaceAll('_', '/')),
            (c) => c.charCodeAt(0)
          )
        )
      : key;
    return encodeId(id) === key &&
      id.trim() &&
      [...id].length <= 512 &&
      ![...id].some((character) => character.codePointAt(0)! < 32)
      ? id
      : '';
  } catch {
    return '';
  }
}
export const resourcePath = (id: string) => `/resources/${encodeId(id)}`;
export const resourceApiPath = (id: string) =>
  `/api/v1/admin${resourcePath(id)}`;

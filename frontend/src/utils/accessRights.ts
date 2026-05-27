import type { GeoDocument } from '../types/api';

export function isRestrictedAccessValue(value: unknown): boolean {
  const values = Array.isArray(value) ? value : [value];

  return values.some(
    (item) =>
      typeof item === 'string' && item.trim().toLowerCase() === 'restricted'
  );
}

export function isRestrictedAccessResource(
  resource: Pick<GeoDocument, 'attributes' | 'meta'> | null | undefined
): boolean {
  const ogm = resource?.attributes?.ogm;

  return isRestrictedAccessValue(
    ogm?.dct_accessRights_s ?? ogm?.dct_accessrights_s
  );
}

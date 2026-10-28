import type { GeoBlacklightSchemaAardvark } from 'ogm-viewer/lib';
export function toAardvarkRecord(data: {
  id?: string;
  attributes: { ogm?: object };
}) {
  const ogm = (data.attributes.ogm ?? {}) as Record<string, unknown>;
  const references = ogm.dct_references_s;

  return {
    ...ogm,
    id: ogm.id ?? data.id ?? '',
    dct_title_s: ogm.dct_title_s ?? '',
    gbl_resourceClass_sm: ogm.gbl_resourceClass_sm ?? [],
    dct_accessRights_s:
      ogm.dct_accessRights_s === 'Restricted' ? 'Restricted' : 'Public',
    gbl_mdVersion_s: ogm.gbl_mdVersion_s ?? ogm.gbl_mdversion_s ?? 'Aardvark',
    dct_references_s:
      typeof references === 'string'
        ? references
        : JSON.stringify(references ?? {}),
  } as unknown as GeoBlacklightSchemaAardvark;
}

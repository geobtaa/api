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

/** Content references supported by pinned OGM Viewer 1.6; geometry alone is not a preview. */
export function hasOgmContentPreview(data: {
  attributes: { ogm?: object };
}): boolean {
  const ogm = (data.attributes.ogm ?? {}) as Record<string, unknown>;
  let references = ogm.dct_references_s;
  if (typeof references === 'string') {
    try {
      references = JSON.parse(references);
    } catch {
      return false;
    }
  }
  if (
    !references ||
    typeof references !== 'object' ||
    Array.isArray(references)
  )
    return false;
  const contentReferences = new Set([
    'http://iiif.io/api/image',
    'http://iiif.io/api/presentation#manifest',
    'https://openindexmaps.org',
    'https://github.com/protomaps/PMTiles',
    'https://github.com/mapbox/tilejson-spec',
    'http://geojson.org/geojson-spec.html',
    'https://github.com/cogeotiff/cog-spec',
    'https://wiki.osgeo.org/wiki/Tile_Map_Service_Specification',
    'https://wiki.openstreetmap.org/wiki/Slippy_map_tilenames',
    'urn:x-esri:serviceType:ArcGIS#FeatureLayer',
    'urn:x-esri:serviceType:ArcGIS#DynamicMapLayer',
    'urn:x-esri:serviceType:ArcGIS#ImageMapLayer',
    'urn:x-esri:serviceType:ArcGIS#TiledMapLayer',
  ]);
  return Object.entries(references).some(([key, value]) => {
    if (typeof value !== 'string' || !value.trim()) return false;
    const uri = key.replace(/\/+$/, '');
    if (contentReferences.has(uri)) return true;
    return (
      Boolean(ogm.gbl_wxsIdentifier_s) &&
      [
        'http://www.opengis.net/def/serviceType/ogc/wms',
        'http://www.opengis.net/def/serviceType/ogc/wmts',
      ].includes(uri)
    );
  });
}

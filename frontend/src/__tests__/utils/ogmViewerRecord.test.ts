import { describe, expect, it } from 'vitest';
import { hasOgmContentPreview } from '../../utils/ogmViewerRecord';

const record = (references: unknown, extra = {}) => ({
  attributes: { ogm: { dct_references_s: references, ...extra } },
});
describe('hasOgmContentPreview', () => {
  it('does not mistake geometry, catalog links or downloads for a layer', () => {
    for (const references of [
      undefined,
      {},
      'null',
      '{invalid',
      {
        'http://schema.org/url': 'https://example.org/catalog',
        'http://schema.org/downloadUrl': 'https://example.org/file.zip',
      },
    ]) {
      expect(
        hasOgmContentPreview(
          record(references, { locn_geometry: 'ENVELOPE(-90,-89,45,44)' })
        )
      ).toBe(false);
    }
  });
  it('accepts serialized and object references for images and map layers', () => {
    for (const key of [
      'http://iiif.io/api/presentation#manifest',
      'http://iiif.io/api/image',
      'http://geojson.org/geojson-spec.html',
      'https://github.com/protomaps/PMTiles',
      'urn:x-esri:serviceType:ArcGIS#FeatureLayer',
    ]) {
      expect(
        hasOgmContentPreview(record({ [key]: 'https://example.org/resource' }))
      ).toBe(true);
      expect(
        hasOgmContentPreview(
          record(
            JSON.stringify({ [key + '/']: 'https://example.org/resource' })
          )
        )
      ).toBe(true);
      expect(hasOgmContentPreview(record({ [key]: '' }))).toBe(false);
    }
  });
  it('requires a layer identifier for WMS and WMTS', () => {
    for (const key of [
      'http://www.opengis.net/def/serviceType/ogc/wms',
      'http://www.opengis.net/def/serviceType/ogc/wmts',
    ]) {
      expect(
        hasOgmContentPreview(record({ [key]: 'https://example.org/service' }))
      ).toBe(false);
      expect(
        hasOgmContentPreview(
          record(
            { [key]: 'https://example.org/service' },
            { gbl_wxsIdentifier_s: 'layer' }
          )
        )
      ).toBe(true);
    }
  });
});

it('uses ready hosted IIIF without mutating harvested references', async () => {
  const { toAardvarkRecord } = await import('../../utils/ogmViewerRecord');
  const original = {
    'http://iiif.io/api/image': 'https://provider/image',
    'http://schema.org/downloadUrl': 'https://provider/original',
  };
  const data = {
    ...record(original),
    meta: {
      ui: {
        preview: {
          version: '1',
          status: 'ready',
          layers: [
            {
              id: 'iiif',
              name: 'Hosted',
              format: 'iiif-manifest',
              url: 'https://ours/manifest.json',
            },
          ],
        },
      },
    },
  };
  const refs = JSON.parse(toAardvarkRecord(data).dct_references_s as string);
  expect(refs['http://iiif.io/api/presentation#manifest']).toBe(
    'https://ours/manifest.json'
  );
  expect(refs['http://iiif.io/api/image']).toBeUndefined();
  expect(refs['http://schema.org/downloadUrl']).toBe(
    original['http://schema.org/downloadUrl']
  );
  expect(data.attributes.ogm.dct_references_s).toEqual(original);
  data.meta.ui.preview.status = 'needs-review';
  expect(JSON.parse(toAardvarkRecord(data).dct_references_s as string)).toEqual(
    original
  );
});

import { describe, it, expect } from 'vitest';
import { OgmRecord } from 'ogm-viewer/lib';
import {
  attachPreparedPreview,
  readyPreparedLayers,
} from '../../utils/preparedPreview';
import { hasOgmContentPreview } from '../../utils/ogmViewerRecord';
import { getHoverGeometryForResult } from '../../utils/geometryUtils';

const data = {
  attributes: {
    ogm: {
      id: 'download-only',
      dct_title_s: 'Roads',
      gbl_resourceClass_sm: ['Datasets'],
      dct_accessRights_s: 'Public',
      gbl_mdVersion_s: 'Aardvark',
      dct_references_s: JSON.stringify({
        'http://schema.org/downloadUrl': 'https://example.org/roads.zip',
      }),
    },
  },
  meta: {
    ui: {
      preview: {
        version: '1',
        status: 'ready',
        layers: [
          {
            id: 'roads',
            name: 'Roads',
            format: 'pmtiles',
            url: '/api/v1/resources/download-only/preview-assets/example.pmtiles',
          },
        ],
      },
    },
  },
};
describe('prepared previews', () => {
  it('uses explicit detail framing without changing published coverage bounds', () => {
    const full: [number, number, number, number] = [-175, -15, 145, 75];
    const detail: [number, number, number, number] = [-125, 24, -66, 50];
    const framed = {
      meta: {
        ui: {
          preview: {
            ...data.meta.ui.preview,
            layers: [
              {
                ...data.meta.ui.preview.layers[0],
                bounds: full,
                recipe: {
                  kind: 'vector' as const,
                  bands: [],
                  thumbnail_bounds: detail,
                },
              },
            ],
          },
        },
      },
    };
    const record = new OgmRecord(
      data.attributes.ogm as ConstructorParameters<typeof OgmRecord>[0]
    );
    const original = JSON.stringify(framed);
    const attached = attachPreparedPreview(record, framed) as OgmRecord & {
      preparedPreviews: { bounds: number[] }[];
    };
    expect(attached.preparedPreviews[0].bounds).toEqual(detail);
    expect(JSON.stringify(framed)).toBe(original);
    expect(framed.meta.ui.preview.layers[0].bounds).toEqual(full);
  });
  it('enables download-only records without changing their source references', () => {
    expect(hasOgmContentPreview(data)).toBe(true);
    const record = new OgmRecord(
      data.attributes.ogm as ConstructorParameters<typeof OgmRecord>[0]
    );
    const original = JSON.stringify(record.json);
    attachPreparedPreview(record, data);
    expect(JSON.stringify(record.json)).toBe(original);
    expect(
      (record as unknown as { preparedPreviews: unknown[] }).preparedPreviews
    ).toHaveLength(1);
  });
  it('does not advertise processing or unknown versions as previews', () => {
    expect(
      readyPreparedLayers({
        meta: {
          ui: { preview: { ...data.meta.ui.preview, status: 'processing' } },
        },
      })
    ).toEqual([]);
    expect(
      readyPreparedLayers({
        meta: { ui: { preview: { ...data.meta.ui.preview, version: '2' } } },
      })
    ).toEqual([]);
  });
  it('does not fall back to obsolete geometry when coverage is explicitly unavailable', () => {
    expect(
      getHoverGeometryForResult({
        meta: {
          ui: {
            coverage: { geometry: null },
            viewer: { geometry: 'POLYGON((0 0,1 0,1 1,0 1,0 0))' },
          },
        },
      })
    ).toBeNull();
  });
});

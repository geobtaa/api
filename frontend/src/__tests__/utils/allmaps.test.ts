import { describe, expect, it } from 'vitest';
import {
  getAllmapsEditorUrl,
  getAllmapsIiifUrl,
  getAllmapsViewerUrl,
  hasAllmapsOverlay,
} from '../../utils/allmaps';

describe('Allmaps eligibility', () => {
  const manifest = 'https://example.com/manifest?collection=maps&id=1';
  const image = 'https://example.com/image/info.json';

  it('prefers a manifest over an image service and preserves query parameters', () => {
    const url = getAllmapsIiifUrl({
      attributes: {
        ogm: {
          dct_references_s: {
            'http://iiif.io/api/image': image,
            'http://iiif.io/api/presentation#manifest': manifest,
          },
        },
      },
    });
    const editor = getAllmapsEditorUrl(null, url);
    expect(url).toBe(manifest);
    expect(
      new URLSearchParams(new URL(editor!).hash.split('?')[1]).get('url')
    ).toBe(manifest);
  });

  it.each(['iiif_manifest', 'iiif_image'])(
    'uses a %s viewer when references are malformed',
    (protocol) => {
      expect(
        getAllmapsIiifUrl({
          attributes: { ogm: { dct_references_s: '{broken' } },
          meta: { ui: { viewer: { protocol, endpoint: image } } },
        })
      ).toBe(image);
    }
  );

  it.each([
    '{}',
    'null',
    '[]',
    '{broken',
    JSON.stringify({
      'http://iiif.io/api/presentation#manifest': 'javascript:alert(1)',
      'http://iiif.io/api/image': 'not a URL',
    }),
  ])('ignores missing or unusable references: %s', (references) => {
    expect(
      getAllmapsIiifUrl({
        attributes: { ogm: { dct_references_s: references } },
        meta: { ui: { viewer: { protocol: 'wms', endpoint: image } } },
      })
    ).toBeNull();
  });

  it('does not offer an overlay or viewer for an unannotated manifest', () => {
    const allmaps = {
      allmaps_manifest_uri: manifest,
      allmaps_annotated: false,
    };
    expect(getAllmapsEditorUrl(allmaps)).toContain(
      encodeURIComponent(manifest)
    );
    expect(getAllmapsViewerUrl(allmaps)).toBeNull();
    expect(hasAllmapsOverlay({ meta: { ui: { allmaps } } })).toBe(false);
  });
});

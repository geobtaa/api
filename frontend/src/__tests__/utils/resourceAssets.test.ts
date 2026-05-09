import { describe, expect, it } from 'vitest';
import { getResultPrimaryImageUrl } from '../../utils/resourceAssets';
import type { GeoDocument } from '../../types/api';

function resultWithUi(ui: Record<string, string | undefined>) {
  return {
    id: 'resource-1',
    meta: { ui },
  } as Pick<GeoDocument, 'id' | 'meta'>;
}

describe('getResultPrimaryImageUrl', () => {
  it('uses the canonical resolver for generic gallery thumbnails', () => {
    const result = resultWithUi({
      thumbnail_url: '/api/v1/resources/resource-1/thumbnail',
      resource_class_icon_url:
        '/api/v1/static-maps/resource-1/resource-class-icon',
    });

    expect(getResultPrimaryImageUrl(result, 'gallery')).toBe(
      '/resources/resource-1/thumbnail'
    );
  });

  it('uses the canonical resolver when no hot icon exists', () => {
    const result = resultWithUi({
      thumbnail_url: '/api/v1/resources/resource-1/thumbnail',
    });

    expect(getResultPrimaryImageUrl(result, 'gallery')).toBe(
      '/resources/resource-1/thumbnail'
    );
  });

  it('uses the resource-class static-map fallback when gallery has no thumbnail URL', () => {
    const result = resultWithUi({});

    expect(getResultPrimaryImageUrl(result, 'gallery')).toBe(
      '/static-maps/resource-1/resource-class-icon'
    );
  });

  it('routes bridge-backed gallery thumbnail assets through the canonical resolver', () => {
    const result = resultWithUi({
      thumbnail_url:
        'https://geobtaa-assets-prod.s3.us-east-2.amazonaws.com/store/asset/example/thumb.jpg',
      resource_class_icon_url:
        '/api/v1/static-maps/resource-1/resource-class-icon',
    });

    expect(getResultPrimaryImageUrl(result, 'gallery')).toBe(
      '/resources/resource-1/thumbnail'
    );
  });

  it('uses generic thumbnail generation for non-gallery contexts', () => {
    const result = resultWithUi({
      thumbnail_url: '/api/v1/resources/resource-1/thumbnail',
      resource_class_icon_url:
        '/api/v1/static-maps/resource-1/resource-class-icon',
    });

    expect(getResultPrimaryImageUrl(result, 'list')).toBe(
      '/resources/resource-1/thumbnail'
    );
    expect(getResultPrimaryImageUrl(result, 'map')).toBe(
      '/resources/resource-1/thumbnail'
    );
  });

  it('keeps immutable hot thumbnails in gallery view', () => {
    const imageHash = 'a'.repeat(64);
    const result = resultWithUi({
      thumbnail_url: `/api/v1/thumbnails/${imageHash}`,
      resource_class_icon_url:
        '/api/v1/static-maps/resource-1/resource-class-icon',
    });

    expect(getResultPrimaryImageUrl(result, 'gallery')).toContain(
      `/api/v1/thumbnails/${imageHash}`
    );
  });
});

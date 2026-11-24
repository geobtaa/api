import { describe, expect, it } from 'vitest';
import { viewerImageDownloads } from '../../utils/viewerImageDownloads';
import type { ImageSelection } from '../../utils/iiifSelection';
const selection: ImageSelection = {
  previewId: 'manifest',
  resourceId: 'record',
  resourceUrl: 'https://example.org/collection',
  renderer: 'image',
  sequence: [],
  pageIndex: 0,
  image: {
    url: 'https://example.org/image/info.json',
    index: 0,
    count: 2,
    occurrence: 0,
    service: {
      id: 'https://example.org/image',
      version: 2,
      width: 4000,
      height: 2000,
      profile: 'http://iiif.io/api/image/2/level2.json',
    },
  },
};
const run = (
  changes: Partial<
    NonNullable<NonNullable<ImageSelection['image']>['service']>
  > = {}
) =>
  viewerImageDownloads(
    {
      ...selection,
      image: {
        ...selection.image!,
        service: { ...selection.image!.service!, ...changes },
      },
    },
    'record'
  );

describe('viewer image downloads', () => {
  it('uses the opened image service instead of traversing its collection', () => {
    expect(run().find((d) => d.label === 'Small')?.url).toBe(
      'https://example.org/image/full/800,/0/default.jpg'
    );
    expect(run().at(-1)?.url).toBe(
      'https://example.org/image/full/full/0/default.jpg'
    );
  });
  it('uses version-specific full size and quality', () => {
    expect(run({ version: 1 }).at(-1)?.url).toContain(
      '/full/full/0/native.jpg'
    );
    expect(run({ version: 3 }).at(-1)?.url).toContain(
      '/full/max/0/default.jpg'
    );
  });
  it('respects size/area limits, aspect ratio, and never upscales', () => {
    const limited = run({ maxArea: 500000 });
    expect(limited.at(-1)?.url).toContain('/1000,/');
    expect(limited.some((d) => d.url.includes('/2000,/'))).toBe(false);
    expect(
      run({ width: 100, height: 200 }).find((d) => d.label === 'Thumb')?.url
    ).toContain('/75,/');
    expect(
      run({
        profile: ['http://iiif.io/api/image/2/level2.json', { maxWidth: 600 }],
      }).at(-1)?.url
    ).toContain('/600,/');
  });
  it('offers only advertised sizes plus full/max for level zero', () => {
    const sizes = [{ width: 500, height: 250 }];
    expect(
      run({ profile: 'level0', version: 3, sizes }).map((d) => d.url)
    ).toEqual([
      'https://example.org/image/full/500,250/0/default.jpg',
      'https://example.org/image/full/max/0/default.jpg',
    ]);
    expect(run({ profile: 'level0', sizes, maxWidth: 200 }).length).toBe(0);
  });
  it('preserves encoded identifiers and query parameters', () => {
    expect(
      run({ id: 'https://example.org/a%2Fb/info.json?token=one#frag' })[0].url
    ).toBe('https://example.org/a%2Fb/full/150,/0/default.jpg?token=one');
  });
  it('does not invent downloads for stale, missing, unsafe, or unknown services', () => {
    expect(viewerImageDownloads(selection, 'other')).toEqual([]);
    expect(
      viewerImageDownloads({ ...selection, image: null }, 'record')
    ).toEqual([]);
    for (const changes of [
      { version: 0 },
      { id: 'javascript:alert(1)' },
      { width: 0 },
      { id: 'https://user:password@example.org/image' },
    ])
      expect(run(changes)).toEqual([]);
  });
});

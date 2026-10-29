import { deflateSync } from 'node:zlib';

// Small, deterministic images. The viewer still performs real HTTP requests and decodes real pixels.
const crc = (bytes) => {
  let value = 0xffffffff;
  for (const byte of bytes) {
    value ^= byte;
    for (let bit = 0; bit < 8; bit++)
      value = (value >>> 1) ^ (value & 1 ? 0xedb88320 : 0);
  }
  return (value ^ 0xffffffff) >>> 0;
};
const chunk = (name, data) => {
  const body = Buffer.concat([Buffer.from(name), data]);
  const size = Buffer.alloc(4);
  size.writeUInt32BE(data.length);
  const checksum = Buffer.alloc(4);
  checksum.writeUInt32BE(crc(body));
  return Buffer.concat([size, body, checksum]);
};
const png = (color) => {
  const header = Buffer.alloc(13);
  header.writeUInt32BE(256);
  header.writeUInt32BE(256, 4);
  header[8] = 8;
  header[9] = 2;
  const pixels = Buffer.alloc(256 * (1 + 256 * 3));
  for (let y = 0; y < 256; y++)
    for (let x = 0; x < 256; x++) {
      const line = x % 32 < 2 || y % 32 < 2;
      pixels.set(line ? [255, 255, 255] : color, y * 769 + 1 + x * 3);
    }
  return Buffer.concat([
    Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
    chunk('IHDR', header),
    chunk('IDAT', deflateSync(pixels)),
    chunk('IEND', Buffer.alloc(0)),
  ]);
};
const images = {
  a: png([160, 70, 50]),
  b: png([40, 90, 180]),
  single: png([70, 130, 80]),
};
const extent = {
  xmin: -1,
  ymin: -1,
  xmax: 1,
  ymax: 1,
  spatialReference: { wkid: 4326 },
};
const features = [
  {
    type: 'Feature',
    id: 1,
    properties: { OBJECTID: 1, NAME: 'Fixture region', POPULATION: 1234 },
    geometry: {
      type: 'Polygon',
      coordinates: [
        [
          [-1, -1],
          [1, -1],
          [1, 1],
          [-1, 1],
          [-1, -1],
        ],
      ],
    },
  },
];
export function fixtureResponse(url) {
  const base = url.origin;
  const json = (body) => ({
    type: 'application/json',
    body: JSON.stringify(body),
  });
  if (url.pathname === '/fixtures/style.json')
    return json({
      version: 8,
      sources: {},
      layers: [
        {
          id: 'background',
          type: 'background',
          paint: { 'background-color': '#eef2f6' },
        },
      ],
    });
  if (url.pathname === '/fixtures/FeatureServer/0')
    return json({
      name: 'Fixture regions',
      type: 'Feature Layer',
      geometryType: 'esriGeometryPolygon',
      objectIdField: 'OBJECTID',
      maxRecordCount: 1000,
      extent,
      supportedQueryFormats: 'JSON, geoJSON',
      advancedQueryCapabilities: { supportsPagination: true },
      fields: [
        { name: 'OBJECTID', type: 'esriFieldTypeOID' },
        { name: 'NAME', type: 'esriFieldTypeString' },
      ],
    });
  if (url.pathname === '/fixtures/FeatureServer/0/query')
    return url.searchParams.get('returnCountOnly') === 'true'
      ? json({ count: 1, extent })
      : json({ type: 'FeatureCollection', features });
  const info = url.pathname.match(/^\/fixtures\/iiif\/([^/]+)\/info.json$/);
  if (info) {
    const id = info[1];
    if (id === 'bad')
      return { status: 503, body: 'Intentional unavailable image' };
    return json({
      '@context': 'http://iiif.io/api/image/2/context.json',
      '@id': `${base}/fixtures/iiif/${id}`,
      protocol: 'http://iiif.io/api/image',
      profile: ['http://iiif.io/api/image/2/level2.json'],
      width: 512,
      height: 512,
      tiles: [{ width: 256, scaleFactors: [1, 2] }],
    });
  }
  const tile = url.pathname.match(/^\/fixtures\/iiif\/([^/]+)\/.+\.(jpg|png)$/);
  if (tile && images[tile[1]])
    return { type: 'image/png', body: images[tile[1]] };
  const manifest = url.pathname.match(/^\/fixtures\/manifest\/([^/]+)$/);
  if (manifest) {
    const scenario = manifest[1];
    if (scenario === 'unavailable')
      return { status: 503, body: 'Intentional unavailable manifest' };
    const ids =
      scenario === 'first-fails'
        ? ['bad', 'b']
        : scenario === 'later-fails'
          ? ['a', 'bad']
          : scenario === 'duplicate'
            ? ['a', 'a', 'b']
            : ['a', 'b'];
    if (scenario === 'v2')
      return json({
        '@context': 'http://iiif.io/api/presentation/2/context.json',
        '@id': url.href,
        '@type': 'sc:Manifest',
        label: 'Two scans',
        sequences: [
          {
            '@type': 'sc:Sequence',
            canvases: ids.map((id, i) => ({
              '@id': `${url.href}/canvas/${i}`,
              '@type': 'sc:Canvas',
              width: 512,
              height: 512,
              images: [
                {
                  '@type': 'oa:Annotation',
                  resource: {
                    '@type': 'dctypes:Image',
                    service: { '@id': `${base}/fixtures/iiif/${id}` },
                  },
                },
              ],
            })),
          },
        ],
      });
    const body = (id) => ({
      type: 'Image',
      id: `${base}/fixtures/iiif/${id}/full/full/0/default.jpg`,
      width: 512,
      height: 512,
      service: [
        {
          id: `${base}/fixtures/iiif/${id}`,
          type: 'ImageService2',
          profile: 'level2',
        },
      ],
    });
    return json({
      '@context': 'http://iiif.io/api/presentation/3/context.json',
      id: url.href,
      type: 'Manifest',
      label: { en: ['Two scans'] },
      items: (scenario === 'multi-image' ? [ids] : ids.map((id) => [id])).map(
        (canvas, i) => ({
          id: `${url.href}/canvas/${i}`,
          type: 'Canvas',
          width: 512,
          height: 512,
          items: [
            {
              type: 'AnnotationPage',
              items: [
                {
                  type: 'Annotation',
                  motivation: 'painting',
                  body: canvas.map(body),
                },
              ],
            },
          ],
        })
      ),
    });
  }
  return undefined;
}

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  availabilityStyle,
  normalizeIndexMapProperties,
  updateInformation,
} from '../../geoblacklight/layer_index_map';

describe('OpenIndexMap v1 information', () => {
  beforeEach(() => {
    document.body.innerHTML = '<div class="viewer-information"></div>';
  });

  afterEach(() => {
    vi.restoreAllMocks();
    document.body.innerHTML = '';
  });

  it('normalizes v1 link, thumbnail, and identifier property names', () => {
    expect(
      normalizeIndexMapProperties({
        thumbUrl: 'https://example.com/thumb.jpg',
        download: 'https://example.com/map.tif',
        recId: 'map-27',
      })
    ).toMatchObject({
      thumbnailUrl: 'https://example.com/thumb.jpg',
      downloadUrl: 'https://example.com/map.tif',
      recordIdentifier: 'map-27',
    });
  });

  it('renders v1 thumbnails and links for a selected feature', async () => {
    await updateInformation({
      title: 'Jaguaribe',
      label: 'SB 24',
      websiteUrl: 'https://example.com/item',
      download: 'https://example.com/map.tif',
      digHold: 'https://example.com/digital-holdings',
      physHold: 'Held in the map library',
      iiifUrl: 'https://example.com/manifest.json',
      thumbUrl: 'https://example.com/thumb.jpg',
      recId: 'am002175',
    });

    const information = document.querySelector('.viewer-information');
    const image = information?.querySelector('img');
    const links = Array.from(information?.querySelectorAll('a') || []);

    expect(image).toHaveAttribute('src', 'https://example.com/thumb.jpg');
    expect(image).toHaveAttribute('alt', 'Thumbnail for Jaguaribe');
    expect(links.map((link) => link.getAttribute('href'))).toEqual(
      expect.arrayContaining([
        'https://example.com/item',
        'https://example.com/map.tif',
        'https://example.com/digital-holdings',
        'https://example.com/manifest.json',
      ])
    );
    expect(information).toHaveTextContent('Record identifier');
    expect(information).toHaveTextContent('am002175');
    expect(information).toHaveTextContent('Held in the map library');
  });

  it('renders digHold when it is the feature’s only item link', async () => {
    await updateInformation({
      label: '19,20',
      digHold: 'https://collections.example.edu/digital/item/25010',
      recId: 'am002722',
    });

    const information = document.querySelector('.viewer-information');
    const link = information?.querySelector('a');

    expect(information).toHaveTextContent('Digital holdings');
    expect(link).toHaveAttribute(
      'href',
      'https://collections.example.edu/digital/item/25010'
    );
  });

  it('continues to support legacy OpenIndexMap property names', () => {
    expect(
      normalizeIndexMapProperties({
        thumbnailUrl: 'https://example.com/legacy-thumb.jpg',
        downloadUrl: 'https://example.com/legacy-map.tif',
        recordIdentifier: 'legacy-1',
      })
    ).toMatchObject({
      thumbnailUrl: 'https://example.com/legacy-thumb.jpg',
      downloadUrl: 'https://example.com/legacy-map.tif',
      recordIdentifier: 'legacy-1',
    });
  });

  it('uses a IIIF manifest thumbnail when thumbUrl is absent', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          thumbnail: [{ id: 'https://example.com/iiif-thumb.jpg' }],
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } }
      )
    );

    await updateInformation({
      label: '27',
      iiifUrl: 'https://example.com/manifest.json',
    });

    expect(document.querySelector('.viewer-information img')).toHaveAttribute(
      'src',
      'https://example.com/iiif-thumb.jpg'
    );
  });

  it('escapes remote text and does not link unsafe URL schemes', async () => {
    await updateInformation({
      title: '<img src=x onerror=alert(1)>',
      websiteUrl: 'javascript:alert(1)',
    });

    const information = document.querySelector('.viewer-information');

    expect(information?.querySelector('img')).not.toBeInTheDocument();
    expect(information?.querySelector('a')).not.toBeInTheDocument();
    expect(information).toHaveTextContent('<img src=x onerror=alert(1)>');
  });

  it('applies availability and opacity without mutating configured styles', () => {
    const defaultStyle = { color: 'green' };
    const unavailableStyle = { color: 'yellow' };
    const options = {
      opacity: 0.5,
      LAYERS: {
        INDEX: {
          DEFAULT: defaultStyle,
          UNAVAILABLE: unavailableStyle,
        },
      },
    };

    expect(availabilityStyle(true, options)).toEqual({
      color: 'green',
      fillOpacity: 0.5,
      opacity: 0.5,
    });
    expect(availabilityStyle(false, options)).toEqual({
      color: 'yellow',
      fillOpacity: 0.5,
      opacity: 0.5,
    });
    expect(defaultStyle).toEqual({ color: 'green' });
    expect(unavailableStyle).toEqual({ color: 'yellow' });
  });
});

import { render, waitFor } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { ResourceViewer } from '../../../components/resource/ResourceViewer';

const cogDataWithGeometry = {
  attributes: { dct_references_s: {} },
  meta: {
    ui: {
      viewer: {
        protocol: 'cog',
        endpoint: 'https://example.com/cog.tif',
        geometry: {
          type: 'Polygon',
          coordinates: [
            [
              [-97.73743, 30.28753],
              [-97.73743, 30.28409],
              [-97.73346, 30.28409],
              [-97.73346, 30.28753],
              [-97.73743, 30.28753],
            ],
          ],
        },
      },
    },
  },
} as Parameters<typeof ResourceViewer>[0]['data'];

describe('ResourceViewer', () => {
  describe('OpenLayers (COG/PMTiles) viewer', () => {
    it('renders OpenLayers viewer container with geometry for COG protocol', async () => {
      render(<ResourceViewer data={cogDataWithGeometry} pageValue="SHOW" />);

      // Viewer mounts after useEffect; look for the openlayers-viewer controller target
      const viewer = await waitFor(() =>
        document.querySelector('[data-controller="openlayers-viewer"]')
      );
      expect(viewer).toBeInTheDocument();
      expect(viewer).toHaveAttribute(
        'data-openlayers-viewer-protocol-value',
        'Cog'
      );
      expect(viewer).toHaveAttribute(
        'data-openlayers-viewer-url-value',
        'https://example.com/cog.tif'
      );
      const mapGeom = viewer?.getAttribute('data-openlayers-viewer-map-geom-value');
      expect(mapGeom).toBeTruthy();
      const parsed = JSON.parse(mapGeom!);
      expect(parsed.type).toBe('Feature');
      expect(parsed.geometry.type).toBe('Polygon');
      expect(parsed.geometry.coordinates[0][0]).toEqual([-97.73743, 30.28753]);
    });
  });
});

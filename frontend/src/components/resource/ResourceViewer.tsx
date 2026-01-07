import { useEffect, useState } from 'react';
import { leafletViewerOptions } from '../../config/leafletConfig';
import { MetadataTable } from './MetadataTable';

interface ResourceViewerProps {
  data: {
    attributes: {
      dct_references_s?: string | Record<string, string>;
      [key: string]: unknown;
    };
    meta?: {
      ui?: {
        viewer?: {
          protocol?: string;
          endpoint?: string;
          geometry?: string;
        };
      };
    };
  };
  pageValue: string;
  totalResults?: number;
  searchUrl?: string;
  currentPage?: number;
}

export function ResourceViewer({ data, pageValue }: ResourceViewerProps) {
  // Extract viewer information from the new data structure
  const protocol = data.meta?.ui?.viewer?.protocol || '';
  const endpoint = data.meta?.ui?.viewer?.endpoint || '';
  const geometry = data.meta?.ui?.viewer?.geometry;
  const available = !!protocol && !!endpoint && !!geometry;

  // Helper function to titleize a string
  const titleize = (str: string) => str.charAt(0).toUpperCase() + str.slice(1);

  // Helper function to determine viewer type
  const getViewerType = (protocol: string) => {
    if (['iiif_manifest', 'iiif_image'].includes(protocol)) {
      return 'mirador';
    }
    if (['cog', 'pmtiles'].includes(protocol)) {
      return 'openlayers';
    }
    if (protocol === 'oembed') {
      return 'oembed-viewer';
    }
    return 'leaflet';
  };

  const viewerType = getViewerType(protocol);

  // SSR safety + deterministic markup: don't render GeoBlacklight viewer containers
  // until after mount (prevents hydration mismatches and guarantees DOM insertion
  // after controllers are registered).
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  function formatProtocol(protocol: string): string | null {
    if (protocol === 'arcgis_dynamic_map_layer') {
      return 'DynamicMapLayer';
    }
    if (protocol === 'geo_json') {
      return null;
    }
    if (protocol === 'tile_map_service') {
      return 'Tms';
    }
    if (protocol === 'arcgis_tiled_map_layer') {
      return 'TiledMapLayer';
    }
    if (protocol === 'arcgis_feature_layer') {
      return 'FeatureLayer';
    }
    if (protocol === 'arcgis_image_map_layer') {
      return 'ImageMapLayer';
    }
    if (protocol === 'open_index_map') {
      return 'IndexMap';
    }
    if (protocol === 'xyz_tiles') {
      return 'Xyz';
    }
    if (protocol === 'tile_json') {
      return 'Tilejson';
    }
    return titleize(protocol);
  }

  const isWmsItem = protocol === 'wms';

  switch (viewerType) {
    case 'mirador': {
      // IMPORTANT: Mirador must not be allowed to leak global styles/scripts into the
      // parent document (it has in practice). We sandbox it in an iframe, similar to
      // how the oEmbed viewer embeds third-party content, so it can't clobber our app UI.
      if (!mounted) {
        return (
          <div className="viewer h-[600px] text-gray-500">
            Loading viewer…
          </div>
        );
      }

      // For iiif_image, we synthesize a Presentation manifest via a local SSR route.
      // Because Mirador runs in a sandboxed iframe with an opaque origin, we MUST use
      // absolute URLs (no relative `/path`), and the manifest route must send CORS headers.
      const pageOrigin = window.location.origin;
      const manifestUrl =
        protocol === 'iiif_image'
          ? `${pageOrigin}/iiif/manifest?image_service=${encodeURIComponent(endpoint)}`
          : endpoint;

      const miradorVersion = '3.4.3';

      // NOTE: srcDoc runs in an isolated document. We inject Mirador from a pinned CDN
      // and mount it into a local container. `manifestUrl` is JSON-stringified so it
      // can't break out of the inline script.
      const srcDoc = `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <style>
      html, body { height: 100%; margin: 0; }
      #mirador-root { height: 100vh; width: 100vw; }
    </style>
    <script defer src="https://unpkg.com/mirador@${miradorVersion}/dist/mirador.min.js"></script>
  </head>
  <body>
    <div id="mirador-root"></div>
    <script>
      (function () {
        var manifestUrl = ${JSON.stringify(manifestUrl)};
        function boot() {
          var Mirador = window.Mirador;
          if (!Mirador || typeof Mirador.viewer !== "function") {
            console.error("Mirador global not available");
            return;
          }
          if (!manifestUrl) {
            console.error("Missing manifestUrl");
            return;
          }
          Mirador.viewer({
            id: "mirador-root",
            windows: [{ manifestId: manifestUrl, thumbnailNavigationPosition: "far-bottom" }],
            window: {
              hideSearchPanel: false,
              hideWindowTitle: true,
              hideAnnotationsPanel: true,
              allowClose: false,
              allowMaximize: false,
              allowFullscreen: true
            },
            workspace: { showZoomControls: true },
            workspaceControlPanel: { enabled: false }
          });
        }
        if (document.readyState === "loading") {
          document.addEventListener("DOMContentLoaded", function () {
            // Give the deferred script a beat to execute
            setTimeout(boot, 0);
          });
        } else {
          setTimeout(boot, 0);
        }
      })();
    </script>
  </body>
</html>`;

      return (
        <iframe
          title="Mirador viewer"
          className="viewer h-[600px] w-full border-0"
          // Allow scripts so Mirador can run. Keep it isolated from the parent page.
          sandbox="allow-scripts"
          // Required for Fullscreen API inside sandboxed iframes (Mirador's fullscreen button).
          allow="fullscreen"
          allowFullScreen
          srcDoc={srcDoc}
        />
      );
    }

    case 'openlayers':
      if (!mounted) {
        return (
          <div className="viewer h-[600px] text-gray-500">
            Loading map…
          </div>
        );
      }
      return (
        <div
          className="viewer h-[600px]"
          data-controller="openlayers-viewer"
          data-openlayers-viewer-protocol-value={titleize(protocol)}
          data-openlayers-viewer-url-value={endpoint}
          data-openlayers-viewer-map-geom-value={JSON.stringify(geometry)}
        />
      );
    case 'oembed-viewer':
      if (!mounted) {
        return (
          <div className="viewer h-[600px] text-gray-500">
            Loading viewer…
          </div>
        );
      }
      return (
        <div
          className="viewer h-[600px]"
          data-controller="oembed-viewer"
          data-oembed-viewer-url-value={endpoint}
        />
      );
    case 'leaflet':
    default:
      // Don't render anything if no geometry is available
      if (!available) {
        return null;
      }

      if (!mounted) {
        return (
          <div className="viewer h-[500px] text-gray-500">
            Loading map…
          </div>
        );
      }
      return (
        <div className="sticky top-[88px]">
          <div
            id="leaflet-viewer"
            className="viewer h-[500px]"
            data-controller="leaflet-viewer"
            data-leaflet-viewer-available-value={available}
            data-leaflet-viewer-map-geom-value={JSON.stringify(geometry)}
            data-leaflet-viewer-layer-id-value={
              data.attributes.ogm.gbl_wxsIdentifier_s || ''
            }
            data-leaflet-viewer-options-value={JSON.stringify(
              leafletViewerOptions
            )}
            data-leaflet-viewer-page-value={pageValue}
            data-leaflet-viewer-draw-initial-bounds-value={true}
            {...(endpoint ? { 'data-leaflet-viewer-url-value': endpoint } : {})}
            {...(protocol
              ? {
                  'data-leaflet-viewer-protocol-value':
                    formatProtocol(protocol),
                }
              : {})}
            {...(isWmsItem
              ? {
                  'data-action':
                    'leaflet-viewer:getFeatureInfo->application#handleWmsFeatureInfo',
                }
              : {})}
            {...(isWmsItem
              ? {
                  'data-wms-feature-info-url': `${import.meta.env.VITE_WMS_BASE_URL}`,
                }
              : {})}
          />
        </div>
      );
  }

  return (
    <div className="bg-white shadow-sm rounded-lg">
      <div className="p-6">
        <MetadataTable data={{ data: { attributes: data.attributes } }} />
      </div>
    </div>
  );
}

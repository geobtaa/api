import { useEffect, useRef, useState } from 'react';
import OlMap from 'ol/Map';
import View from 'ol/View';
import { FullScreen, defaults as defaultControls } from 'ol/control';
import VectorTileLayer from 'ol/layer/VectorTile.js';
import { leafletViewerOptions } from '../../config/leafletConfig';
import { MetadataTable } from './MetadataTable';
import { getWgs84ExtentFromViewerGeometry } from '../../utils/geometryUtils';
import { fromExtent as polygonFromExtent } from 'ol/geom/Polygon';
import { transformExtent, useGeographic } from 'ol/proj';
import TileLayer from 'ol/layer/Tile';
import WebGLTileLayer from 'ol/layer/WebGLTile.js';
import XYZ from 'ol/source/XYZ';
import GeoTIFF from 'ol/source/GeoTIFF.js';
import { PMTilesVectorSource } from 'ol-pmtiles';
import { Circle as CircleStyle, Fill, Stroke, Style } from 'ol/style.js';

interface ResourceViewerProps {
  data: {
    attributes: {
      dct_references_s?: string | Record<string, string>;
      ogm?: {
        id?: string;
        gbl_wxsIdentifier_s?: string;
        gbl_wxsidentifier_s?: string;
      };
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

type ViewerExtent = [number, number, number, number];

const OPENLAYERS_BASEMAP = {
  url: 'https://{a-d}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png',
  attributions:
    '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, &copy; <a href="http://carto.com/attributionss">Carto</a>',
  maxZoom: 18,
};

function isFiniteExtent(
  extent: number[] | null | undefined
): extent is ViewerExtent {
  return !!extent && extent.length === 4 && extent.every(Number.isFinite);
}

function getFitSize(
  map: OlMap,
  element: HTMLDivElement
): [number, number] | null {
  const mapSize = map.getSize();
  if (
    mapSize &&
    mapSize.length === 2 &&
    mapSize[0] > 0 &&
    mapSize[1] > 0 &&
    Number.isFinite(mapSize[0]) &&
    Number.isFinite(mapSize[1])
  ) {
    return [mapSize[0], mapSize[1]];
  }

  const rect = element.getBoundingClientRect();
  if (rect.width > 0 && rect.height > 0) {
    return [Math.round(rect.width), Math.round(rect.height)];
  }

  return null;
}

function fitViewToWgs84Extent(params: {
  map: OlMap;
  view: View;
  element: HTMLDivElement;
  wgs84Extent: ViewerExtent;
}) {
  const { map, view, element, wgs84Extent } = params;
  map.updateSize();

  const fitSize = getFitSize(map, element);
  if (!fitSize) return;

  view.setViewportSize?.(fitSize);

  const projectionCode = view.getProjection()?.getCode?.() || 'EPSG:3857';
  const extentInViewProjection =
    projectionCode === 'EPSG:4326'
      ? wgs84Extent
      : (transformExtent(
          wgs84Extent,
          'EPSG:4326',
          projectionCode
        ) as ViewerExtent);

  if (!extentInViewProjection.every(Number.isFinite)) {
    return;
  }

  const fitOptions = {
    size: fitSize,
    padding: [16, 16, 16, 16] as [number, number, number, number],
    maxZoom: 19,
    duration: 0,
  };

  if (typeof (view as any).fitInternal === 'function') {
    (view as any).fitInternal(
      polygonFromExtent(extentInViewProjection),
      fitOptions
    );
  } else {
    view.fit(extentInViewProjection, fitOptions);
  }

  const center = view.getCenterInternal?.() ?? view.getCenter?.();
  if (center && Number.isFinite(center[0]) && Number.isFinite(center[1])) {
    return;
  }

  const fallbackCenter: [number, number] = [
    (extentInViewProjection[0] + extentInViewProjection[2]) / 2,
    (extentInViewProjection[1] + extentInViewProjection[3]) / 2,
  ];
  view.setCenter(fallbackCenter);

  if (typeof (view as any).getResolutionForExtentInternal === 'function') {
    const paddedSize: [number, number] = [
      Math.max(fitSize[0] - 32, 1),
      Math.max(fitSize[1] - 32, 1),
    ];
    const resolution = (view as any).getResolutionForExtentInternal(
      extentInViewProjection,
      paddedSize
    );
    if (Number.isFinite(resolution) && resolution > 0) {
      view.setResolution(resolution);
    }
  }
}

function createPmTilesLayer(url: string) {
  useGeographic();

  return new VectorTileLayer({
    declutter: true,
    source: new PMTilesVectorSource({ url }),
    style: new Style({
      stroke: new Stroke({
        color: '#7070B3',
        width: 1,
      }),
      fill: new Fill({
        color: '#FFFFFF',
      }),
      image: new CircleStyle({
        radius: 7,
        fill: new Fill({
          color: '#7070B3',
        }),
        stroke: new Stroke({
          color: '#FFFFFF',
          width: 2,
        }),
      }),
    }),
  });
}

function createCogLayer(url: string) {
  return new WebGLTileLayer({
    source: new GeoTIFF({
      sources: [{ url }],
      convertToRGB: true,
    }),
  });
}

function escapeHtml(value: string) {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function formatInspectionValue(value: unknown) {
  if (value === null || value === undefined) return '';
  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (/^https?:\/\//i.test(trimmed)) {
      const safeUrl = escapeHtml(trimmed);
      return `<a href="${safeUrl}" target="_blank" rel="noopener noreferrer">${safeUrl}</a>`;
    }
    return escapeHtml(trimmed);
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }

  try {
    return escapeHtml(JSON.stringify(value));
  } catch {
    return escapeHtml(String(value));
  }
}

function enablePmTilesInspection(map: OlMap) {
  map.on('pointermove', (event: any) => {
    const pixel = map.getEventPixel(event.originalEvent);
    const hit = map.hasFeatureAtPixel(pixel);
    map.getViewport().style.cursor = hit ? 'crosshair' : '';
  });

  map.on('click', (event: any) => {
    const tableBody = document.querySelector('.attribute-table-body');
    if (!tableBody) return;

    const features = map.getFeaturesAtPixel(event.pixel);
    if (!features.length) {
      tableBody.innerHTML =
        '<tr><td colspan="2">Could not find that feature</td></tr>';
      return;
    }

    const properties = features[0].getProperties();
    let html = '<tbody class="attribute-table-body">';
    Object.entries(properties).forEach(([property, value]) => {
      html += `<tr><td>${escapeHtml(property)}</td><td>${formatInspectionValue(value)}</td></tr>`;
    });
    html += '</tbody>';
    tableBody.outerHTML = html;
  });
}

function OpenLayersPreviewMap({
  protocol,
  endpoint,
  geometryForViewer,
  preCalculatedExtent,
}: {
  protocol: string;
  endpoint: string;
  geometryForViewer: string;
  preCalculatedExtent: number[] | null;
}) {
  const elementRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const element = elementRef.current;
    if (!element) return;

    const wgs84Extent =
      (isFiniteExtent(preCalculatedExtent) && preCalculatedExtent) ||
      getWgs84ExtentFromViewerGeometry(geometryForViewer);

    if (!isFiniteExtent(wgs84Extent)) {
      return;
    }

    const isPmtilesProtocol = protocol.toLowerCase() === 'pmtiles';
    const basemap = new TileLayer({
      source: new XYZ(OPENLAYERS_BASEMAP),
    });
    const overlay = isPmtilesProtocol
      ? createPmTilesLayer(endpoint)
      : createCogLayer(endpoint);
    const view = new View({
      projection: 'EPSG:3857',
      center: [0, 0],
      zoom: 2,
    });
    const map = new OlMap({
      target: element,
      controls: defaultControls().extend([new FullScreen()]),
      layers: [basemap, overlay],
      view,
    });

    if (isPmtilesProtocol) {
      try {
        enablePmTilesInspection(map);
      } catch (error) {
        console.warn('PMTiles inspection setup failed:', error);
      }
    }

    const refit = () => {
      fitViewToWgs84Extent({
        map,
        view,
        element,
        wgs84Extent,
      });
      map.renderSync?.();
    };

    let disposed = false;
    const timeoutIds = [0, 100, 300].map((delay) =>
      window.setTimeout(() => {
        if (!disposed) refit();
      }, delay)
    );
    let secondFrame = 0;
    const firstFrame = window.requestAnimationFrame(() => {
      refit();
      secondFrame = window.requestAnimationFrame(() => {
        if (!disposed) refit();
      });
    });

    const resizeObserver =
      typeof ResizeObserver !== 'undefined'
        ? new ResizeObserver(() => {
            if (!disposed) refit();
          })
        : null;
    resizeObserver?.observe(element);

    const source = overlay.getSource?.();
    const onSourceChange = () => {
      const state = source?.getState?.();
      if (state === 'ready') {
        refit();
      }
    };

    if (source && typeof (source as any).on === 'function') {
      (source as any).on('change', onSourceChange);
    }

    refit();

    return () => {
      disposed = true;
      window.cancelAnimationFrame(firstFrame);
      window.cancelAnimationFrame(secondFrame);
      timeoutIds.forEach((id) => window.clearTimeout(id));
      resizeObserver?.disconnect();
      if (source && typeof (source as any).un === 'function') {
        (source as any).un('change', onSourceChange);
      }
      map.setTarget(undefined);
    };
  }, [endpoint, geometryForViewer, preCalculatedExtent, protocol]);

  return <div ref={elementRef} className="viewer h-[600px]" />;
}

export function ResourceViewer({ data, pageValue }: ResourceViewerProps) {
  // Extract viewer information from the new data structure
  const protocol = data.meta?.ui?.viewer?.protocol || '';
  const endpoint = data.meta?.ui?.viewer?.endpoint || '';
  const geometry = data.meta?.ui?.viewer?.geometry;
  const available =
    !!protocol && !!endpoint && (protocol === 'iiif_image' || !!geometry);
  const layerIdentifier =
    data.attributes.ogm?.gbl_wxsIdentifier_s ||
    data.attributes.ogm?.gbl_wxsidentifier_s ||
    '';
  const resourceIdentifier = data.attributes.ogm?.id || '';
  const viewerInstanceKey = [
    protocol,
    endpoint,
    layerIdentifier,
    resourceIdentifier,
    pageValue,
  ].join('|');

  // Helper function to titleize a string
  const titleize = (str: string) => str.charAt(0).toUpperCase() + str.slice(1);

  // Helper function to determine viewer type
  const getViewerType = (protocol: string) => {
    if (protocol === 'iiif_manifest') {
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
    if (protocol === 'iiif_image') {
      return 'Iiif';
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
          <div className="viewer h-[600px] text-gray-500">Loading viewer…</div>
        );
      }

      // Mirador runs in a sandboxed iframe, so use an absolute URL for the manifest.
      const pageOrigin = window.location.origin;
      const manifestUrl = new URL(endpoint, pageOrigin).toString();

      const miradorUrl = new URL('/mirador', pageOrigin);
      miradorUrl.searchParams.set('manifest', manifestUrl);

      return (
        <iframe
          key={viewerInstanceKey}
          title="Mirador viewer"
          className="viewer h-[600px] w-full border-0"
          // Keep Mirador isolated in its own document while allowing local module scripts and plugin downloads.
          sandbox="allow-same-origin allow-scripts allow-popups allow-popups-to-escape-sandbox allow-downloads"
          // Required for Fullscreen API inside sandboxed iframes.
          allow="fullscreen"
          allowFullScreen
          src={miradorUrl.toString()}
        />
      );
    }

    case 'openlayers':
      if (!mounted) {
        return (
          <div className="viewer h-[600px] text-gray-500">Loading map…</div>
        );
      }
      // The OpenLayers GeoJSON reader expects a Feature or FeatureCollection,
      // not a raw geometry. Wrap the geometry in a Feature if it's a raw geometry.
      // For PMTiles, geometry is used to set initial bounds, but may be optional.
      let geometryForViewer: string | undefined;
      if (geometry) {
        try {
          // Handle geometry as object (GeoJSON) - the type definition says string but backend returns object
          let geomObj: any;
          if (typeof geometry === 'string') {
            // Skip empty strings
            if (!geometry.trim()) {
              geomObj = null;
            } else {
              try {
                geomObj = JSON.parse(geometry);
              } catch (e) {
                // If parsing fails, geometry might be a WKT string or invalid - skip it
                console.warn('Failed to parse geometry as JSON:', e);
                geomObj = null;
              }
            }
          } else {
            geomObj = geometry;
          }

          if (geomObj && typeof geomObj === 'object' && geomObj !== null) {
            // Check if geometry is already a Feature or FeatureCollection
            if (
              geomObj.type === 'Feature' ||
              geomObj.type === 'FeatureCollection'
            ) {
              geometryForViewer = JSON.stringify(geomObj);
            } else if (geomObj.type && geomObj.coordinates) {
              // It's a raw geometry (Polygon, Point, etc.), wrap it in a Feature
              // Note: OpenLayers GeoJSON reader expects Feature or FeatureCollection
              const feature = {
                type: 'Feature',
                geometry: geomObj,
                properties: {},
              };
              geometryForViewer = JSON.stringify(feature);
            } else {
              console.warn('Geometry object missing type or coordinates:', {
                hasType: !!geomObj.type,
                hasCoordinates: !!geomObj.coordinates,
                keys: Object.keys(geomObj),
              });
            }
          }
        } catch (e) {
          console.error('Error processing geometry for OpenLayers viewer:', e);
          // Don't set geometryForViewer if there's an error
        }
      }

      // The OpenLayers controller requires geometry for non-COG protocols to calculate bounds
      // If we don't have valid geometry, we can't render the viewer properly
      // For PMTiles, the controller tries to get bounds from geometry, so we need it
      if (!geometryForViewer) {
        // If geometry is missing or invalid, show a message instead of breaking
        return (
          <div className="viewer h-[600px] flex items-center justify-center text-gray-500 bg-gray-50">
            <div className="text-center">
              <p className="mb-2">Map viewer unavailable</p>
              <p className="text-sm">
                Geometry data is required to display this map.
              </p>
            </div>
          </div>
        );
      }

      // Pre-calculate the correct extent from geometry (WGS84) to avoid wrong initial render.
      // For COG, the GeoBlacklight controller gets extent from the GeoTIFF which may be in a
      // projected CRS or wrong; we always prefer our geometry-based extent for reliable pan/zoom.
      const preCalculatedExtent =
        getWgs84ExtentFromViewerGeometry(geometryForViewer);
      return (
        <OpenLayersPreviewMap
          key={viewerInstanceKey}
          protocol={protocol}
          endpoint={endpoint}
          geometryForViewer={geometryForViewer}
          preCalculatedExtent={preCalculatedExtent}
        />
      );
    case 'oembed-viewer':
      if (!mounted) {
        return (
          <div className="viewer h-[600px] text-gray-500">Loading viewer…</div>
        );
      }
      return (
        <div
          key={viewerInstanceKey}
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
          <div className="viewer h-[500px] text-gray-500">Loading map…</div>
        );
      }
      return (
        <div key={viewerInstanceKey} className="sticky top-[88px]">
          <div
            id="leaflet-viewer"
            className="viewer h-[500px]"
            data-controller="leaflet-viewer"
            data-leaflet-viewer-available-value={available}
            data-leaflet-viewer-map-geom-value={JSON.stringify(geometry)}
            data-leaflet-viewer-layer-id-value={layerIdentifier}
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

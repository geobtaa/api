import { useEffect, useState } from 'react';
import { leafletViewerOptions } from '../../config/leafletConfig';
import { MetadataTable } from './MetadataTable';
import { transformExtent } from 'ol/proj';

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
          <div className="viewer h-[600px] text-gray-500">Loading viewer…</div>
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
              console.log('Wrapped geometry in Feature:', {
                originalType: geomObj.type,
                hasCoordinates: !!geomObj.coordinates,
                featureType: feature.type,
              });
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

      const openlayersProps: Record<string, string> = {
        'data-controller': 'openlayers-viewer',
        'data-openlayers-viewer-protocol-value': titleize(protocol),
        'data-openlayers-viewer-url-value': endpoint,
        'data-openlayers-viewer-map-geom-value': geometryForViewer,
      };

      // Pre-calculate the correct extent from geometry to avoid wrong initial render
      let preCalculatedExtent: number[] | null = null;
      if (geometryForViewer) {
        try {
          const geom = JSON.parse(geometryForViewer);
          if (geom.geometry && geom.geometry.coordinates) {
            const coords = geom.geometry.coordinates[0]; // First ring
            const lons = coords.map((c: number[]) => c[0]);
            const lats = coords.map((c: number[]) => c[1]);
            const minX = Math.min(...lons);
            const minY = Math.min(...lats);
            const maxX = Math.max(...lons);
            const maxY = Math.max(...lats);
            preCalculatedExtent = [minX, minY, maxX, maxY];
          }
        } catch (e) {
          // Ignore parsing errors, will use controller's extent as fallback
        }
      }

      // Debug: Log what we're passing to the controller
      console.log('OpenLayers viewer props:', {
        protocol: titleize(protocol),
        endpoint: endpoint?.substring(0, 50) + '...',
        geometryLength: geometryForViewer?.length,
        geometryPreview: geometryForViewer?.substring(0, 100) + '...',
        preCalculatedExtent,
      });

      return (
        <div
          className="viewer h-[600px]"
          {...openlayersProps}
          ref={(el) => {
            if (el) {
              // GeoBlacklight controllers register asynchronously, so we need to wait
              // Check multiple times with increasing delays
              const checkController = (attempt = 1) => {
                const maxAttempts = 10;
                const delay = attempt * 200; // 200ms, 400ms, 600ms, etc.

                setTimeout(() => {
                  // Try both window.Stimulus and window.application
                  const stimulus =
                    (window as any).Stimulus || (window as any).application;
                  const controller =
                    stimulus?.getControllerForElementAndIdentifier?.(
                      el,
                      'openlayers-viewer'
                    );

                  if (controller) {
                    console.log(
                      `OpenLayers controller connected (attempt ${attempt}):`,
                      {
                        protocol: controller.protocolValue,
                        url: controller.urlValue?.substring(0, 50),
                        mapGeomLength: controller.mapGeomValue?.length,
                        element: el,
                        hasMap: !!controller.map,
                        elementId: el.id,
                        elementClasses: el.className,
                        hasExtent: !!controller.extent,
                        extent: controller.extent,
                      }
                    );

                    // Fit to known geometry extent, retrying after render when size is stable.
                    // We try both raw lon/lat extent and a transformed extent because
                    // GeoBlacklight's PMTiles path uses OpenLayers `useGeographic()`,
                    // and projection handling can differ across environments/builds.
                    const fitToGeometryExtent = (reason: string) => {
                      const map = controller.map;
                      if (map) {
                        const view = map.getView?.();
                        if (view) {
                          // Use pre-calculated extent or controller's extent
                          const extent =
                            preCalculatedExtent || controller.extent;
                          if (extent && extent.length === 4) {
                            const [minX, minY, maxX, maxY] = extent;
                            const wgs84Extent: [number, number, number, number] = [
                              minX,
                              minY,
                              maxX,
                              maxY,
                            ];
                            const projectionCode =
                              view.getProjection?.()?.getCode?.() || 'EPSG:3857';
                            const transformedExtent =
                              projectionCode === 'EPSG:4326'
                                ? wgs84Extent
                                : transformExtent(wgs84Extent, 'EPSG:4326', projectionCode);

                            map.updateSize?.();
                            const size = map.getSize();
                            if (
                              size &&
                              size.length === 2 &&
                              size[0] > 0 &&
                              size[1] > 0
                            ) {
                              const fitOptions = {
                                size,
                                padding: [50, 50, 50, 50] as [number, number, number, number],
                                maxZoom: 14,
                                duration: 0,
                              };

                              let bestZoom = -Infinity;
                              let bestCenter: number[] | undefined;
                              let bestLabel = 'wgs84-raw';

                              const tryFit = (candidateExtent: number[], label: string) => {
                                if (!candidateExtent || candidateExtent.length !== 4) return;
                                if (candidateExtent.some((n) => !isFinite(n))) return;
                                view.fit(candidateExtent, fitOptions);
                                const z = view.getZoom?.() ?? -Infinity;
                                const c = view.getCenter?.();
                                if (z > bestZoom && c && c.length === 2) {
                                  bestZoom = z;
                                  bestCenter = [c[0], c[1]];
                                  bestLabel = label;
                                }
                              };

                              tryFit(wgs84Extent, 'wgs84-raw');
                              tryFit(transformedExtent, `to-${projectionCode}`);

                              if (bestCenter && isFinite(bestZoom)) {
                                view.setCenter?.(bestCenter);
                                view.setZoom?.(bestZoom);
                              }

                              console.log(`View fit to extent (${reason})`, {
                                projectionCode,
                                bestLabel,
                                bestZoom,
                              });
                            }
                          }
                        }
                      }
                    };

                    // Try immediately, then after map render settles.
                    if (controller.map) {
                      requestAnimationFrame(() => {
                        fitToGeometryExtent('raf');
                      });
                      controller.map.once?.('rendercomplete', () => {
                        fitToGeometryExtent('rendercomplete');
                      });
                    } else {
                      // Map not ready yet, wait a bit
                      setTimeout(() => {
                        fitToGeometryExtent('delayed-init');
                      }, 50);
                    }
                    setTimeout(() => fitToGeometryExtent('post-init-timeout'), 250);
                    // One final guarded refit: only if still at obvious world-view zoom.
                    setTimeout(() => {
                      const map = controller.map;
                      const view = map?.getView?.();
                      const zoom = view?.getZoom?.() ?? 0;
                      if (zoom <= 3.5) {
                        fitToGeometryExtent('world-view-guard');
                      }
                    }, 900);

                    // Check if the map was created and inspect its state
                    setTimeout(() => {
                      const mapElement = el.querySelector('.ol-viewport');
                      console.log('Map element found:', !!mapElement);
                      if (mapElement) {
                        const map = controller.map;
                        if (map) {
                          try {
                            const view = map.getView?.();
                            const layers =
                              map.getLayers?.()?.getArray?.() || [];
                            console.log('Map state:', {
                              layersCount: layers.length,
                              layerTypes: layers.map(
                                (l) => l?.constructor?.name || typeof l
                              ),
                              hasView: !!view,
                              viewType: view?.constructor?.name,
                            });

                            // Check layer order and visibility
                            layers.forEach((layer, index) => {
                              const layerInfo: any = {
                                index,
                                type: layer?.constructor?.name,
                                visible: layer?.getVisible?.(),
                                opacity: layer?.getOpacity?.(),
                                zIndex: layer?.getZIndex?.(),
                              };

                              const source = layer?.getSource?.();
                              if (source) {
                                layerInfo.sourceType =
                                  source?.constructor?.name;
                                layerInfo.sourceState = source?.getState?.();
                              }

                              console.log(`Layer ${index}:`, layerInfo);
                            });

                            if (view && typeof view.getExtent === 'function') {
                              const extent = view.getExtent();
                              console.log('View state:', {
                                center: view.getCenter?.(),
                                zoom: view.getZoom?.(),
                                extent: extent,
                                resolution: view.getResolution?.(),
                              });
                            }

                            // Ensure final map position is based on record geometry even if
                            // PMTiles layer/source registration happens after initial connect.
                            fitToGeometryExtent('post-map-state-check');

                            // Check if PMTiles layer is present
                            const pmtilesLayer = layers.find((l) => {
                              const className = l?.getClassName?.() || '';
                              const source = l?.getSource?.();
                              const sourceClass =
                                source?.constructor?.name || '';
                              return (
                                className.includes('PMTiles') ||
                                sourceClass.includes('PMTiles')
                              );
                            });
                            console.log('PMTiles layer found:', !!pmtilesLayer);
                            if (pmtilesLayer) {
                              const source = pmtilesLayer.getSource?.();
                              // PMTiles source might store URL differently - check various properties
                              const sourceInfo: any = {
                                state: source?.getState?.(),
                                sourceType: source?.constructor?.name,
                                url: source?.getUrl?.(),
                              };

                              // Check for URL in various possible properties
                              if (source) {
                                sourceInfo.urlProperty = source.url;
                                sourceInfo.urlGetter = source.getUrl?.();
                                sourceInfo.tileUrl = source.tileUrl;
                                sourceInfo.url_ = source.url_;
                                // Check if it's in the options
                                if (source.options) {
                                  sourceInfo.optionsUrl = source.options.url;
                                }
                                // Check all enumerable properties
                                const props = Object.keys(source).filter((k) =>
                                  k.toLowerCase().includes('url')
                                );
                                if (props.length > 0) {
                                  sourceInfo.urlProperties = props.reduce(
                                    (acc, key) => {
                                      acc[key] = (source as any)[key];
                                      return acc;
                                    },
                                    {} as Record<string, any>
                                  );
                                }
                              }

                              console.log('PMTiles source state:', sourceInfo);

                              // Check if PMTiles layer is visible and has features
                              console.log('PMTiles layer visibility:', {
                                visible: pmtilesLayer.getVisible?.(),
                                opacity: pmtilesLayer.getOpacity?.(),
                                zIndex: pmtilesLayer.getZIndex?.(),
                                minZoom: pmtilesLayer.getMinZoom?.(),
                                maxZoom: pmtilesLayer.getMaxZoom?.(),
                              });

                              // Check if source has loaded features
                              if (
                                source &&
                                typeof source.getFeatures === 'function'
                              ) {
                                try {
                                  const features = source.getFeatures();
                                  console.log(
                                    'PMTiles source features count:',
                                    features?.length || 0
                                  );
                                } catch (e) {
                                  // getFeatures might not be available for PMTiles
                                }
                              }

                              // Check the layer's style function - PMTiles might need styling to be visible
                              const style = pmtilesLayer.getStyle?.();
                              const styleFunction =
                                pmtilesLayer.getStyleFunction?.();
                              console.log('PMTiles layer style:', {
                                hasStyle: !!style,
                                hasStyleFunction: !!styleFunction,
                                styleType: style?.constructor?.name,
                              });

                              // Check if we can see rendered tiles in the DOM
                              const canvas = el.querySelector('canvas');
                              console.log('Map canvas found:', !!canvas);
                              if (canvas) {
                                console.log('Canvas dimensions:', {
                                  width: canvas.width,
                                  height: canvas.height,
                                  clientWidth: canvas.clientWidth,
                                  clientHeight: canvas.clientHeight,
                                });
                              }

                              // Try zooming out to see if tiles appear at lower zoom
                              console.log(
                                'Current zoom is 28 - this might be too high. Try zooming out manually to see if tiles appear.'
                              );

                              // Check if map container has proper dimensions
                              const containerRect = el.getBoundingClientRect();
                              console.log('Map container dimensions:', {
                                width: containerRect.width,
                                height: containerRect.height,
                                visible:
                                  containerRect.width > 0 &&
                                  containerRect.height > 0,
                              });

                              // Check controller's extent property
                              if (controller.extent) {
                                console.log(
                                  'Controller extent:',
                                  controller.extent
                                );
                              } else {
                                console.warn(
                                  'Controller extent is not set - this might be the issue!'
                                );
                              }

                              // Try to manually trigger a map update
                              if (map && typeof map.updateSize === 'function') {
                                console.log('Attempting to update map size...');
                                try {
                                  map.updateSize();
                                  console.log('Map size updated');
                                } catch (e) {
                                  console.warn('Failed to update map size:', e);
                                }
                              }

                              // Check if we can see tile loading
                              if (source && source.tileCache) {
                                const cacheSize =
                                  source.tileCache?.getCount?.() || 0;
                                console.log(
                                  'PMTiles tile cache size:',
                                  cacheSize
                                );
                              }

                              // Canvas exists and has proper dimensions - tiles should be rendering
                              console.log('Canvas ready for rendering');

                              // Suggestion: Try manually zooming out using map controls
                              console.log(
                                '💡 SUGGESTION: Try using the zoom controls (-) to zoom out and see if PMTiles appear at lower zoom levels'
                              );

                              // Double-check view is correct (backup fix if immediate fix didn't work)
                              if (view && typeof view.getZoom === 'function') {
                                const currentZoom = view.getZoom();
                                const currentCenter = view.getCenter?.();

                                // Check if we're in the wrong location (off the coast of Africa would be around 0,0 or negative coords)
                                // Web Mercator coordinates for Philadelphia should be around [-8.4M, 4.8M]
                                const isWrongLocation =
                                  currentCenter &&
                                  (Math.abs(currentCenter[0]) < 1000000 ||
                                    Math.abs(currentCenter[1]) < 1000000 ||
                                    currentZoom > 15);

                                if (
                                  isWrongLocation ||
                                  (currentZoom && currentZoom > 15)
                                ) {
                                  console.log(
                                    `Map still incorrect. Center: ${currentCenter}, Zoom: ${currentZoom}. Refitting...`
                                  );
                                  try {
                                    // Use pre-calculated extent or controller's extent
                                    const extent =
                                      preCalculatedExtent || controller.extent;
                                    if (extent && extent.length === 4) {
                                      const [minX, minY, maxX, maxY] = extent;
                                      const wgs84Extent = [
                                        minX,
                                        minY,
                                        maxX,
                                        maxY,
                                      ];
                                      const webMercatorExtent = transformExtent(
                                        wgs84Extent,
                                        'EPSG:4326',
                                        'EPSG:3857'
                                      );

                                      const size = map.getSize();
                                      if (size && size.length === 2) {
                                        view.fit(webMercatorExtent, {
                                          size: size,
                                          padding: [50, 50, 50, 50],
                                          maxZoom: 14,
                                          duration: 0, // Instant
                                        });
                                        console.log(
                                          'Map view refitted (backup fix)'
                                        );
                                      }
                                    }
                                  } catch (e) {
                                    console.warn(
                                      'Could not adjust zoom/center:',
                                      e
                                    );
                                  }
                                } else {
                                  console.log(
                                    `Zoom level ${currentZoom} and center ${currentCenter} are correct`
                                  );
                                }
                              }

                              // Check if view has proper extent
                              if (view) {
                                try {
                                  // Try different ways to get extent
                                  let extent: number[] | undefined;
                                  if (typeof view.getExtent === 'function') {
                                    extent = view.getExtent();
                                  } else if (
                                    typeof (view as any).calculateExtent ===
                                    'function'
                                  ) {
                                    extent = (view as any).calculateExtent(
                                      map.getSize()
                                    );
                                  }

                                  if (extent && extent.length === 4) {
                                    const [minX, minY, maxX, maxY] = extent;
                                    const width = maxX - minX;
                                    const height = maxY - minY;
                                    console.log('View extent:', {
                                      minX,
                                      minY,
                                      maxX,
                                      maxY,
                                      width,
                                      height,
                                    });

                                    // Expected extent for Philadelphia (from the geometry)
                                    // Should be around: -75.28 to -74.96 (lon), 39.87 to 40.14 (lat)
                                    if (
                                      width === 0 ||
                                      height === 0 ||
                                      !isFinite(width) ||
                                      !isFinite(height)
                                    ) {
                                      console.warn(
                                        'Invalid extent - map might not be zoomed to data'
                                      );
                                    } else if (
                                      Math.abs(minX) < 1 ||
                                      Math.abs(minY) < 1
                                    ) {
                                      console.warn(
                                        'Extent looks like it might be in wrong projection or zoomed to origin'
                                      );
                                    }
                                  } else {
                                    console.warn(
                                      'Could not get valid extent from view'
                                    );
                                  }

                                  // Also check center and zoom
                                  const center = view.getCenter?.();
                                  const zoom = view.getZoom?.();
                                  console.log('View center and zoom:', {
                                    center,
                                    zoom,
                                  });
                                } catch (e) {
                                  console.warn('Could not inspect view:', e);
                                }
                              }

                              // Check network requests for PMTiles
                              console.log(
                                'Check Network tab for requests to geobtaa-assets-prod.s3.us-east-2.amazonaws.com'
                              );
                            }
                          } catch (e) {
                            console.error('Error inspecting map state:', e);
                          }
                        }
                      } else {
                        console.warn(
                          'OpenLayers map not initialized. Checking for errors...'
                        );
                        // Check if there are any error messages in the console or DOM
                        const errorElements = el.querySelectorAll(
                          '[class*="error"], [class*="Error"]'
                        );
                        console.log(
                          'Error elements in viewer:',
                          errorElements.length
                        );
                      }
                    }, 1000);
                  } else if (attempt < maxAttempts) {
                    checkController(attempt + 1);
                  } else {
                    console.warn(
                      'OpenLayers controller never connected after',
                      maxAttempts,
                      'attempts'
                    );
                    console.warn('Stimulus available:', !!stimulus);
                    console.warn('Element:', el);
                    console.warn('Data attributes:', {
                      controller: el.getAttribute('data-controller'),
                      protocol: el.getAttribute(
                        'data-openlayers-viewer-protocol-value'
                      ),
                      url: el
                        .getAttribute('data-openlayers-viewer-url-value')
                        ?.substring(0, 50),
                    });
                  }
                }, delay);
              };

              checkController(1);
            }
          }}
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

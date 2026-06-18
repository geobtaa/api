export const EMPTY_IIIF_TILE_URL =
  'data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs=';
export const IIIF_MIN_ZOOM = -5;

function getInfoId(info) {
  const id = info.id ?? info['@id'];
  return typeof id === 'string' ? id : null;
}

export function getIiifImageApiVersion(info) {
  const context = info['@context'];
  const contextValues = Array.isArray(context) ? context : [context];

  if (
    contextValues.some(
      (value) => typeof value === 'string' && value.includes('/image/2')
    )
  ) {
    return 2;
  }

  return info['@id'] && !info.id ? 2 : 3;
}

export function getIiifTileSize(info) {
  const firstTile = Array.isArray(info.tiles) ? info.tiles[0] : undefined;
  return firstTile?.width && firstTile.width > 0 ? firstTile.width : 256;
}

export function getIiifTileFormat(info) {
  const preferredFormats = info.preferredFormats;
  if (Array.isArray(preferredFormats)) {
    const firstFormat = preferredFormats.find(
      (format) => typeof format === 'string'
    );
    if (firstFormat) return firstFormat.replace(/^\./, '');
  }

  return 'jpg';
}

export function normalizeIiifImageServiceId(imageServiceOrInfoUrl, info) {
  const canonical = getInfoId(info);
  const serviceId = canonical || imageServiceOrInfoUrl;
  return serviceId.replace(/\/info\.json$/, '').replace(/\/$/, '');
}

export function getIiifMaxNativeZoom(width, height, tileSize) {
  return Math.max(
    Math.ceil(Math.log(width / tileSize) / Math.LN2),
    Math.ceil(Math.log(height / tileSize) / Math.LN2),
    0
  );
}

export function getIiifImageBounds(leaflet, width, height, maxNativeZoom) {
  const southWest = leaflet.CRS.Simple.pointToLatLng(
    leaflet.point(0, height),
    maxNativeZoom
  );
  const northEast = leaflet.CRS.Simple.pointToLatLng(
    leaflet.point(width, 0),
    maxNativeZoom
  );
  return leaflet.latLngBounds(southWest, northEast);
}

export function getIiifTileUrl({
  coords,
  imageApiVersion,
  imageHeight,
  imageWidth,
  maxNativeZoom,
  serviceId,
  tileFormat,
  tileQuality,
  tileSize,
}) {
  const zoom = Math.max(0, Math.min(maxNativeZoom, coords.z));
  const scale = Math.pow(2, maxNativeZoom - zoom);
  const sourceTileSize = tileSize * scale;
  const minX = coords.x * sourceTileSize;
  const minY = coords.y * sourceTileSize;

  if (
    coords.x < 0 ||
    coords.y < 0 ||
    minX >= imageWidth ||
    minY >= imageHeight
  ) {
    return EMPTY_IIIF_TILE_URL;
  }

  const maxX = Math.min(minX + sourceTileSize, imageWidth);
  const maxY = Math.min(minY + sourceTileSize, imageHeight);
  const regionWidth = maxX - minX;
  const regionHeight = maxY - minY;

  if (regionWidth <= 0 || regionHeight <= 0) {
    return EMPTY_IIIF_TILE_URL;
  }

  const outputWidth = Math.ceil(regionWidth / scale);
  const outputHeight = Math.ceil(regionHeight / scale);
  const size =
    imageApiVersion === 2
      ? `${outputWidth},`
      : `${outputWidth},${outputHeight}`;
  const region = [minX, minY, regionWidth, regionHeight].join(',');
  const baseUrl = serviceId.replace(/\/$/, '');

  return `${baseUrl}/${region}/${size}/0/${tileQuality}.${tileFormat}`;
}

export function resizeIiifTileToNaturalSize(tile, tileSize) {
  const { naturalHeight, naturalWidth } = tile;

  if (!naturalHeight || !naturalWidth) return;
  if (naturalHeight === tileSize && naturalWidth === tileSize) return;

  tile.style.width = `${naturalWidth}px`;
  tile.style.height = `${naturalHeight}px`;
}

export async function fetchIiifImageInfo(imageServiceOrInfoUrl) {
  const base = imageServiceOrInfoUrl.replace(/\/$/, '');
  const infoUrl = base.endsWith('/info.json') ? base : `${base}/info.json`;
  const response = await fetch(infoUrl, {
    headers: {
      Accept: 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch IIIF info.json: ${response.status}`);
  }

  return response.json();
}

export function getIiifLeafletMapOptions(
  leaflet,
  imageBounds,
  maxNativeZoom,
  sleepSettings,
  mapSettings
) {
  return {
    ...sleepSettings,
    ...mapSettings,
    attributionControl: false,
    center: imageBounds.getCenter(),
    crs: leaflet.CRS.Simple,
    maxBounds: imageBounds.pad(0.5),
    maxBoundsViscosity: 0.5,
    maxZoom: maxNativeZoom,
    minZoom: IIIF_MIN_ZOOM,
    preferCanvas: false,
    zoom: 0,
  };
}

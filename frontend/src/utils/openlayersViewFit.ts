export type ViewCenter = [number, number] | null | undefined;

export function shouldUseWgs84ExtentForFit(
  protocol: string,
  projectionCode: string,
  userProjectionCode?: string | null
): boolean {
  if (projectionCode === 'EPSG:4326') return true;
  const isPmtilesProtocol = protocol.toLowerCase() === 'pmtiles';
  // GeoBlacklight PMTiles calls useGeographic() in some runtime paths; when active,
  // OL API methods accept lon/lat (WGS84) even if the view projection is 3857.
  return isPmtilesProtocol && userProjectionCode === 'EPSG:4326';
}

export function resolveUseWgs84ExtentForFit(params: {
  protocol: string;
  projectionCode: string;
  userProjectionCode?: string | null;
  currentCenter: ViewCenter;
}): boolean {
  const { protocol, projectionCode, userProjectionCode, currentCenter } =
    params;
  const isPmtilesProtocol = protocol.toLowerCase() === 'pmtiles';

  const base = shouldUseWgs84ExtentForFit(
    protocol,
    projectionCode,
    userProjectionCode
  );
  if (!isPmtilesProtocol || projectionCode !== 'EPSG:3857') return base;

  // PMTiles runtime behavior differs across environments. Infer expected input mode
  // from the active center signature when available.
  if (!currentCenter) return base;
  const [x, y] = currentCenter;
  const looksDegrees = Math.abs(x) <= 180 && Math.abs(y) <= 90;
  const looksProjected = Math.abs(x) > 1000000 && Math.abs(y) > 1000000;
  const looksMixed = Math.abs(x) > 1000000 && Math.abs(y) <= 90;

  // Empirically:
  // - mixed signature (x in meters, y in degrees) needs WGS84 fit
  // - degrees-only in a 3857 view usually means degrees were treated as meters,
  //   so we should use projected fit to correct it.
  if (looksMixed) return true;
  if (looksProjected || looksDegrees) return false;
  return base;
}

export function isSuspiciousViewState(params: {
  protocol: string;
  projectionCode: string;
  userProjectionCode?: string | null;
  center: ViewCenter;
  zoom: number | null | undefined;
}): boolean {
  const { protocol, projectionCode, userProjectionCode, center, zoom } = params;
  if (center && (!Number.isFinite(center[0]) || !Number.isFinite(center[1]))) {
    return true;
  }
  const centerShouldLookWgs84 = resolveUseWgs84ExtentForFit({
    protocol,
    projectionCode,
    userProjectionCode,
    currentCenter: center,
  });

  const suspiciousByCenter = centerShouldLookWgs84
    ? !!center && (Math.abs(center[0]) > 180 || Math.abs(center[1]) > 90)
    : projectionCode === 'EPSG:3857'
      ? !!center &&
        (Math.abs(center[0]) < 1000000 || Math.abs(center[1]) < 1000000)
      : projectionCode === 'EPSG:4326'
        ? !!center && (Math.abs(center[0]) > 180 || Math.abs(center[1]) > 90)
        : false;

  const numericZoom = zoom ?? 0;
  const suspiciousByZoom = numericZoom <= 3.5 || numericZoom > 15;

  return suspiciousByCenter || suspiciousByZoom;
}

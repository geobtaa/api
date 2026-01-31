/**
 * Parse dcat_bbox string (ENVELOPE or CSV) to Leaflet bounds [[south, west], [north, east]].
 * Returns null if the string cannot be parsed.
 */
export function parseBboxToLeafletBounds(
  bboxStr: string | undefined
): [[number, number], [number, number]] | null {
  if (!bboxStr || typeof bboxStr !== "string") return null;

  let coords: [number, number, number, number] | null = null; // [minX, minY, maxX, maxY] (lon, lat)

  const envelopeMatch = bboxStr.match(
    /ENVELOPE\s*\(\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*\)/i
  );
  if (envelopeMatch) {
    const minX = parseFloat(envelopeMatch[1]);
    const maxX = parseFloat(envelopeMatch[2]);
    const maxY = parseFloat(envelopeMatch[3]);
    const minY = parseFloat(envelopeMatch[4]);
    coords = [minX, minY, maxX, maxY];
  } else {
    const parts = bboxStr.split(",").map((s) => parseFloat(s.trim()));
    if (parts.length === 4 && parts.every((n) => !isNaN(n))) {
      coords = [parts[0], parts[1], parts[2], parts[3]];
    }
  }

  if (!coords) return null;

  // Leaflet: [[south, west], [north, east]]
  return [
    [coords[1], coords[0]],
    [coords[3], coords[2]],
  ];
}

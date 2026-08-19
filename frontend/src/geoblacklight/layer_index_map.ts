interface IndexMapProperties {
  [key: string]: unknown;
}

interface NormalizedIndexMapProperties {
  title?: string;
  label?: string;
  note?: string;
  websiteUrl?: string;
  downloadUrl?: string;
  thumbnailUrl?: string;
  iiifUrl?: string;
  digitalHoldings?: string;
  physicalHoldings?: string;
  recordIdentifier?: string;
}

interface IndexMapStyle {
  [key: string]: unknown;
  fillOpacity?: number;
  opacity?: number;
}

interface IndexMapLeafletOptions {
  opacity?: number;
  LAYERS: {
    INDEX: {
      DEFAULT: IndexMapStyle;
      UNAVAILABLE: IndexMapStyle;
    };
  };
}

let informationRequestId = 0;

function stringValue(value: unknown): string | undefined {
  if (typeof value !== 'string') return undefined;

  const trimmed = value.trim();
  return trimmed || undefined;
}

function firstString(...values: unknown[]): string | undefined {
  return values.map(stringValue).find(Boolean);
}

function escapeHtml(value: string): string {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function safeHttpUrl(value: string | undefined): string | undefined {
  if (!value) return undefined;

  try {
    const url = new URL(value);
    return url.protocol === 'http:' || url.protocol === 'https:'
      ? url.toString()
      : undefined;
  } catch {
    return undefined;
  }
}

function renderLinkOrText(value: string): string {
  const url = safeHttpUrl(value);
  const escapedValue = escapeHtml(value);

  if (!url) return escapedValue;

  return `<a class="break-all text-blue-700 underline hover:text-blue-900" href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapedValue}</a>`;
}

function renderDefinition(label: string, value: string | undefined): string {
  if (!value) return '';

  return `
    <div class="grid gap-1 border-t border-gray-200 px-4 py-3 sm:grid-cols-[10rem_1fr]">
      <dt class="font-semibold text-gray-700">${escapeHtml(label)}</dt>
      <dd class="min-w-0 text-gray-900">${renderLinkOrText(value)}</dd>
    </div>`;
}

function extractIiifThumbnail(manifest: unknown): string | undefined {
  if (!manifest || typeof manifest !== 'object') return undefined;

  const thumbnail = (manifest as Record<string, unknown>).thumbnail;
  const candidate = Array.isArray(thumbnail) ? thumbnail[0] : thumbnail;

  if (typeof candidate === 'string') return safeHttpUrl(candidate);
  if (!candidate || typeof candidate !== 'object') return undefined;

  const thumbnailObject = candidate as Record<string, unknown>;
  return safeHttpUrl(firstString(thumbnailObject.id, thumbnailObject['@id']));
}

export function normalizeIndexMapProperties(
  properties: IndexMapProperties
): NormalizedIndexMapProperties {
  return {
    title: stringValue(properties.title),
    label: stringValue(properties.label),
    note: stringValue(properties.note),
    websiteUrl: stringValue(properties.websiteUrl),
    // OpenIndexMaps v1 shortened these three legacy property names.
    downloadUrl: firstString(properties.download, properties.downloadUrl),
    thumbnailUrl: firstString(properties.thumbUrl, properties.thumbnailUrl),
    recordIdentifier: firstString(
      properties.recId,
      properties.recordIdentifier
    ),
    iiifUrl: stringValue(properties.iiifUrl),
    digitalHoldings: stringValue(properties.digHold),
    physicalHoldings: stringValue(properties.physHold),
  };
}

export function renderIndexMapInformation(
  properties: NormalizedIndexMapProperties
): string {
  const thumbnailUrl = safeHttpUrl(properties.thumbnailUrl);
  const thumbnailLink =
    safeHttpUrl(properties.websiteUrl) ||
    safeHttpUrl(properties.digitalHoldings) ||
    safeHttpUrl(properties.downloadUrl);
  const thumbnailAlt = `Thumbnail for ${properties.title || properties.label || 'selected map sheet'}`;
  const digitalHoldings =
    properties.digitalHoldings === properties.websiteUrl
      ? undefined
      : properties.digitalHoldings;

  const thumbnail = thumbnailUrl
    ? `<img class="max-h-72 max-w-full rounded border border-gray-200 object-contain" src="${escapeHtml(thumbnailUrl)}" alt="${escapeHtml(thumbnailAlt)}">`
    : '';
  const linkedThumbnail =
    thumbnail && thumbnailLink
      ? `<a class="inline-block" href="${escapeHtml(thumbnailLink)}" target="_blank" rel="noopener noreferrer">${thumbnail}</a>`
      : thumbnail;

  return `
    <section class="index-map-info mt-4 overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm" aria-label="Selected map sheet">
      <div class="px-4 py-3">
        ${properties.title ? `<h2 class="text-xl font-semibold text-gray-900">${escapeHtml(properties.title)}</h2>` : '<h2 class="text-lg font-semibold text-gray-900">Selected map sheet</h2>'}
        ${linkedThumbnail ? `<div class="mt-3">${linkedThumbnail}</div>` : ''}
      </div>
      <dl class="text-sm">
        ${renderDefinition('Website', properties.websiteUrl)}
        ${renderDefinition('Download', properties.downloadUrl)}
        ${renderDefinition('Digital holdings', digitalHoldings)}
        ${renderDefinition('Physical holdings', properties.physicalHoldings)}
        ${renderDefinition('IIIF manifest', properties.iiifUrl)}
        ${renderDefinition('Record identifier', properties.recordIdentifier)}
        ${renderDefinition('Label', properties.label)}
        ${renderDefinition('Note', properties.note)}
      </dl>
    </section>`;
}

async function fetchIiifThumbnail(
  iiifUrl: string | undefined
): Promise<string | undefined> {
  const manifestUrl = safeHttpUrl(iiifUrl);
  if (!manifestUrl) return undefined;

  try {
    const response = await fetch(manifestUrl);
    if (!response.ok) return undefined;

    return extractIiifThumbnail(await response.json());
  } catch {
    return undefined;
  }
}

export const availabilityStyle = (
  availability: unknown,
  leafletOptions: IndexMapLeafletOptions
): IndexMapStyle => {
  const baseStyle =
    availability || typeof availability === 'undefined'
      ? leafletOptions.LAYERS.INDEX.DEFAULT
      : leafletOptions.LAYERS.INDEX.UNAVAILABLE;
  const opacity = leafletOptions.opacity || 0.65;

  return { ...baseStyle, fillOpacity: opacity, opacity };
};

export async function updateInformation(
  rawProperties: IndexMapProperties
): Promise<void> {
  const informationElement = document.querySelector<HTMLElement>(
    '.viewer-information'
  );
  if (!informationElement) return;

  const requestId = ++informationRequestId;
  const properties = normalizeIndexMapProperties(rawProperties);
  informationElement.innerHTML = renderIndexMapInformation(properties);

  if (properties.thumbnailUrl || !properties.iiifUrl) return;

  const thumbnailUrl = await fetchIiifThumbnail(properties.iiifUrl);
  if (!thumbnailUrl || requestId !== informationRequestId) return;

  informationElement.innerHTML = renderIndexMapInformation({
    ...properties,
    thumbnailUrl,
  });
}

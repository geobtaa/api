import type { ImageSelection } from './iiifSelection';

/** Build image requests from the service OGM Viewer actually opened, never a manifest guess. */
export function viewerImageDownloads(
  selection: ImageSelection | null,
  resourceId?: string
) {
  const image = selection?.resourceId === resourceId ? selection?.image : null;
  const service = image?.service;
  if (!service || ![1, 2, 3].includes(service.version)) return [];
  let base: URL;
  try {
    base = new URL(service.id);
    if (
      !['http:', 'https:'].includes(base.protocol) ||
      base.username ||
      base.password
    )
      return [];
  } catch {
    return [];
  }
  const positive = (n: unknown): n is number =>
    typeof n === 'number' && Number.isFinite(n) && n > 0;
  if (!positive(service.width) || !positive(service.height)) return [];
  base.pathname = base.pathname.replace(/\/info\.json$/, '').replace(/\/$/, '');
  base.hash = '';
  const profiles = Array.isArray(service.profile)
    ? service.profile
    : [service.profile];
  const limits = Object.assign(
    {},
    service,
    ...profiles.filter((p) => p && typeof p === 'object')
  );
  const level0 = JSON.stringify(service.profile ?? '').includes('level0');
  const { width, height, version } = service;
  let scale = 1;
  if (positive(limits.maxWidth))
    scale = Math.min(scale, limits.maxWidth / width);
  if (positive(limits.maxHeight))
    scale = Math.min(scale, limits.maxHeight / height);
  if (positive(limits.maxArea))
    scale = Math.min(scale, Math.sqrt(limits.maxArea / (width * height)));
  const result: Array<{
    label: string;
    url: string;
    type: string;
    source: string;
    image_source: string;
    iiif_resource_url: string;
  }> = [];
  const add = (label: string, size: string) => {
    const url = new URL(base);
    url.pathname += `/full/${size}/0/${version === 1 ? 'native' : 'default'}.jpg`;
    if (!result.some((d) => d.url === url.href))
      result.push({
        label,
        url: url.href,
        type: 'image/jpeg',
        source: 'iiif',
        image_source: image!.url,
        iiif_resource_url: selection!.resourceUrl,
      });
  };
  if (level0) {
    for (const size of service.sizes ?? []) {
      if (
        positive(size.width) &&
        positive(size.height) &&
        size.width <= width * scale &&
        size.height <= height * scale
      ) {
        add(
          `Image (${size.width} × ${size.height})`,
          version === 3 ? `${size.width},${size.height}` : `${size.width},`
        );
      }
    }
  } else {
    for (const [label, bound] of [
      ['Thumb', 150],
      ['Small', 800],
      ['Medium', 1200],
      ['Large', 2000],
    ] as const) {
      add(
        label,
        `${Math.max(1, Math.floor(width * Math.min(scale, bound / Math.max(width, height))))},`
      );
    }
  }
  if (version === 3) add('Largest Available', 'max');
  else if (scale === 1) add('Full Resolution', 'full');
  else if (!level0)
    add('Largest Available', `${Math.max(1, Math.floor(width * scale))},`);
  return result;
}

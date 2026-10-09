import { useEffect, useState } from 'react';
import { parseAnnotation } from '@allmaps/annotation';
import type { AllmapsAttributes } from '../utils/allmaps';

/** Check on each resource visit without waiting for the catalog's harvest cycle. */
export function useAllmapsAvailability(
  resourceId: string | undefined,
  iiifUrl: string | null,
  stored: AllmapsAttributes | null | undefined
): AllmapsAttributes | null | undefined {
  const [discovered, setDiscovered] = useState<{
    resourceId: string;
    iiifUrl: string;
    attributes: AllmapsAttributes;
  } | null>(null);

  useEffect(() => {
    if (!resourceId || !iiifUrl) return;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 8000);
    const annotationUrl = `https://annotations.allmaps.org/?url=${encodeURIComponent(iiifUrl)}`;

    async function check() {
      try {
        const response = await fetch(annotationUrl, {
          signal: controller.signal,
          cache: 'no-store',
          credentials: 'omit',
        });
        if (!response.ok) return;
        const annotation = await response.json();
        if (
          controller.signal.aborted ||
          parseAnnotation(annotation).length === 0
        )
          return;
        setDiscovered({
          resourceId: resourceId!,
          iiifUrl: iiifUrl!,
          attributes: {
            allmaps_annotated: true,
            allmaps_manifest_uri: iiifUrl,
            allmaps_annotation_url: annotationUrl,
          },
        });
      } catch {
        // A timeout, unavailable service, or invalid annotation must not hide a known overlay.
      } finally {
        clearTimeout(timeout);
      }
    }
    void check();
    return () => {
      controller.abort();
      clearTimeout(timeout);
    };
  }, [resourceId, iiifUrl]);

  return discovered?.resourceId === resourceId &&
    discovered?.iiifUrl === iiifUrl
    ? { ...stored, ...discovered.attributes }
    : stored;
}

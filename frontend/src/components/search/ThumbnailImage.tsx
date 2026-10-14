import { useEffect, useState, type ComponentProps } from 'react';

function parseSource(src: string | undefined): URL | undefined {
  try {
    return src ? new URL(src, 'http://localhost') : undefined;
  } catch {
    return undefined;
  }
}

/** Read pending-response headers that an ordinary <img> cannot observe. */
export function ThumbnailImage({
  resourceId,
  src,
  onError,
  ...props
}: ComponentProps<'img'> & { resourceId: string }) {
  const [recover, setRecover] = useState(false);
  const source = parseSource(src);
  const resolver = /^\/(api\/v1\/)?resources\/[^/]+\/thumbnail$/.test(
    source?.pathname ?? ''
  );
  const [resolved, setResolved] = useState<{ source: string; url: string }>();
  const requestUrl =
    resolver || recover
      ? `/resources/${encodeURIComponent(resourceId)}/thumbnail${
          source?.searchParams.get('variant') === 'icon-gradient'
            ? '?variant=icon-gradient'
            : ''
        }`
      : undefined;

  useEffect(() => {
    setRecover(false);
  }, [src, resourceId]);

  useEffect(() => {
    if (!requestUrl) return;
    let controller: AbortController;
    let disposed = false;
    let timer: ReturnType<typeof setTimeout>;
    let objectUrl: string | undefined;
    let attempts = 0;

    const load = async () => {
      attempts += 1;
      controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 10000);
      try {
        const response = await fetch(requestUrl, {
          signal: controller.signal,
          cache: 'no-store',
        });
        if (
          !response.ok ||
          !response.headers
            .get('Content-Type')
            ?.toLowerCase()
            .startsWith('image/')
        ) {
          throw new Error('Thumbnail unavailable');
        }
        const blob = await response.blob();
        if (disposed) return;
        const previous = objectUrl;
        objectUrl = URL.createObjectURL(blob);
        setResolved({ source: requestUrl, url: objectUrl });
        if (previous) URL.revokeObjectURL(previous);
        if (response.headers.get('X-Thumbnail-Pending') !== 'true') return;
      } catch {
        if (disposed) return;
        if (attempts === 12) {
          // Let the normal image error handler show the card's final fallback.
          setResolved({ source: requestUrl, url: requestUrl });
        }
      } finally {
        clearTimeout(timeout);
      }
      // Bounded retries: never poll permanent placeholders or an unmounted card.
      if (attempts < 12) {
        timer = setTimeout(load, Math.min(2000 * 2 ** (attempts - 1), 10000));
      }
    };
    void load();
    return () => {
      disposed = true;
      controller.abort();
      clearTimeout(timer);
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [requestUrl]);

  const displayUrl = requestUrl
    ? resolved?.source === requestUrl
      ? resolved.url
      : undefined
    : src;
  if (!displayUrl) return null;
  return (
    <img
      {...props}
      src={displayUrl}
      onError={(event) => {
        if (!requestUrl) setRecover(true);
        else onError?.(event);
      }}
    />
  );
}

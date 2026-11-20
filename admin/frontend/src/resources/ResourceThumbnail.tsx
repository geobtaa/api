import { useState } from 'react';

// Public presentation images only; administrative metadata stays in GEOMG.
const imageApi = (
  import.meta.env.VITE_GEOSPATIAL_API_URL || 'https://geo.btaa.org/api/v1'
).replace(/\/$/, '');

export function ResourceThumbnail({ id }: { id: string }) {
  const [fallback, setFallback] = useState(0);
  return (
    <div
      className="flex size-20 shrink-0 items-center justify-center overflow-hidden rounded-md border border-border bg-surface-subtle sm:size-24"
      aria-hidden="true"
    >
      {fallback < 2 ? (
        <img
          src={
            fallback === 0
              ? `${imageApi}/resources/${encodeURIComponent(id)}/thumbnail`
              : `${imageApi}/thumbnails/placeholder`
          }
          alt=""
          width={96}
          height={96}
          loading="lazy"
          decoding="async"
          referrerPolicy="no-referrer"
          className="size-full object-contain"
          onError={() => setFallback((current) => Math.min(2, current + 1))}
        />
      ) : (
        <svg
          className="size-10 text-text-muted"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.25"
        >
          <path d="m3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3V6Zm6-3v15M15 6v15" />
        </svg>
      )}
    </div>
  );
}

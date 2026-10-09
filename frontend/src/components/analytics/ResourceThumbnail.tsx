import { useState } from 'react';
import { Link } from 'react-router';
import { getResourceIcon } from '../../utils/resourceIcons';

export function ResourceThumbnail({
  resource,
  eager = false,
  href,
  compact = false,
}: {
  resource: { id?: string | null; title: string; resourceClass?: string };
  eager?: boolean;
  href?: string;
  compact?: boolean;
}) {
  const [imageFailed, setImageFailed] = useState(false);
  const resourceHref =
    href ?? `/resources/${encodeURIComponent(resource.id ?? '')}`;

  return (
    <Link
      to={resourceHref}
      className={`analytics-cover${compact ? ' analytics-cover--compact' : ''}`}
      aria-label={`View ${resource.title}`}
    >
      {imageFailed || !resource.id ? (
        <span
          className="analytics-cover-placeholder"
          data-testid={`analytics-thumbnail-fallback-${resource.id}`}
        >
          {getResourceIcon(resource.resourceClass || 'Other', {
            className: 'h-10 w-10',
          })}
        </span>
      ) : (
        <img
          src={`${resourceHref}/thumbnail`}
          alt=""
          loading={eager ? 'eager' : 'lazy'}
          decoding="async"
          data-testid={`analytics-thumbnail-${resource.id}`}
          onError={() => setImageFailed(true)}
        />
      )}
    </Link>
  );
}

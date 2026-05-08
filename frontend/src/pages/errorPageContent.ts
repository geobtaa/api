import {
  AlertTriangle,
  Clock,
  LockKeyhole,
  SearchX,
  ServerCrash,
  ShieldAlert,
  WifiOff,
  type LucideIcon,
} from 'lucide-react';

const GEO_PORTAL_ERROR_STATUSES = [
  401, 403, 404, 429, 500, 502, 503, 504,
] as const;

export type GeoportalErrorStatus = (typeof GEO_PORTAL_ERROR_STATUSES)[number];

interface ErrorPageCopy {
  eyebrow: string;
  title: string;
  description: string;
  note: string;
  seoTitle: string;
  Icon: LucideIcon;
}

interface ErrorPageContent extends ErrorPageCopy {
  status: number;
}

const ERROR_COPY: Record<GeoportalErrorStatus, ErrorPageCopy> = {
  401: {
    eyebrow: 'Authorization required',
    title: 'Login required',
    description:
      'This page is behind an authorization check. Sign in with an account that has access, then try the request again.',
    note: 'If you arrived from a shared link, it may require institutional access or a fresh session.',
    seoTitle: '401 Login Required',
    Icon: LockKeyhole,
  },
  403: {
    eyebrow: 'Access restricted',
    title: 'Permission denied',
    description:
      'Your account or network does not have permission to view this Geoportal resource.',
    note: 'If you believe you should have access, contact the Geoportal team and include the page URL.',
    seoTitle: '403 Permission Denied',
    Icon: ShieldAlert,
  },
  404: {
    eyebrow: 'Missing page',
    title: 'Page not found',
    description:
      'The page you are looking for does not exist, was moved, or is no longer available in the Geoportal.',
    note: 'Search the catalog to find current maps, datasets, imagery, and other geospatial resources.',
    seoTitle: '404 Page Not Found',
    Icon: SearchX,
  },
  429: {
    eyebrow: 'Too many requests',
    title: 'Rate limited',
    description:
      'The Geoportal received too many requests in a short period of time.',
    note: 'Wait a minute, then try again. Large automated requests should use the public API with a measured pace.',
    seoTitle: '429 Rate Limited',
    Icon: Clock,
  },
  500: {
    eyebrow: 'Server error',
    title: 'Something went wrong',
    description:
      'The Geoportal hit an unexpected server error while processing this request.',
    note: 'Try refreshing the page. If the problem continues, the team may already be investigating.',
    seoTitle: '500 Server Error',
    Icon: ServerCrash,
  },
  502: {
    eyebrow: 'Service interrupted',
    title: 'Service unavailable',
    description:
      'The Geoportal could not reach one of the services needed to complete this request.',
    note: 'This is usually temporary. Try again shortly, or continue searching while the service recovers.',
    seoTitle: '502 Service Unavailable',
    Icon: WifiOff,
  },
  503: {
    eyebrow: 'Service interrupted',
    title: 'Service unavailable',
    description:
      'The Geoportal service is temporarily unavailable or under maintenance.',
    note: 'This is usually temporary. Try again shortly, or continue searching while the service recovers.',
    seoTitle: '503 Service Unavailable',
    Icon: WifiOff,
  },
  504: {
    eyebrow: 'Service interrupted',
    title: 'Service unavailable',
    description:
      'The Geoportal waited too long for an upstream service to respond.',
    note: 'This is usually temporary. Try again shortly, or continue searching while the service recovers.',
    seoTitle: '504 Service Unavailable',
    Icon: WifiOff,
  },
};

export function isGeoportalErrorStatus(
  status: number | null | undefined
): status is GeoportalErrorStatus {
  return GEO_PORTAL_ERROR_STATUSES.includes(status as GeoportalErrorStatus);
}

export function getErrorPageContent(
  status: number | null | undefined,
  statusText?: string
): ErrorPageContent {
  if (isGeoportalErrorStatus(status)) {
    return { status, ...ERROR_COPY[status] };
  }

  const fallbackStatus = status && status >= 400 ? status : 500;

  return {
    status: fallbackStatus,
    eyebrow: 'Unexpected error',
    title: statusText || 'Something went wrong',
    description:
      'The Geoportal could not complete this request. Try again or return to search.',
    note: 'If the problem continues, contact the Geoportal team and include the page URL.',
    seoTitle: `${fallbackStatus} ${statusText || 'Error'}`,
    Icon: AlertTriangle,
  };
}

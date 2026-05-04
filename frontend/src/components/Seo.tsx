import { useEffect } from 'react';
import { useLocation } from 'react-router';
import {
  buildPageTitle,
  DEFAULT_SEO_DESCRIPTION,
  DEFAULT_SEO_IMAGE,
  SITE_TITLE,
} from '../config/seo';

interface SeoProps {
  title: string;
  description?: string;
  image?: string;
  url?: string;
  type?: 'website' | 'article' | 'book';
}

export function Seo({
  title,
  description = DEFAULT_SEO_DESCRIPTION,
  image = DEFAULT_SEO_IMAGE,
  url,
  type = 'website',
}: SeoProps) {
  const location = useLocation();

  useEffect(() => {
    document.title = buildPageTitle(title);
  }, [description, image, location.pathname, location.search, title, type, url]);

  // React Router route `meta` exports own SSR/head rendering. This component is
  // kept as a lightweight client fallback for the legacy SPA entry and tests.
  return null;
}

export { SITE_TITLE };

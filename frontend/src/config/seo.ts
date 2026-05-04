import type { MetaDescriptor } from 'react-router';

export const SITE_TITLE = 'Big Ten Academic Alliance Geoportal';

export const DEFAULT_SEO_DESCRIPTION =
  'The Big Ten Academic Alliance Geoportal provides discoverability and facilitates access to geospatial resources.';

export const DEFAULT_SEO_IMAGE = '/thumbnail_placeholder.png';

export function buildPageTitle(title: string) {
  return title === SITE_TITLE ? SITE_TITLE : `${title} - ${SITE_TITLE}`;
}

function absoluteUrl(value: string, baseUrl?: string) {
  if (!value || value.startsWith('http://') || value.startsWith('https://')) {
    return value;
  }

  if (!baseUrl) {
    return value;
  }

  try {
    return new URL(value, baseUrl).href;
  } catch {
    return value;
  }
}

export function buildSeoMeta({
  title,
  description = DEFAULT_SEO_DESCRIPTION,
  image = DEFAULT_SEO_IMAGE,
  url,
  type = 'website',
}: {
  title: string;
  description?: string;
  image?: string;
  url?: string;
  type?: 'website' | 'article' | 'book';
}): MetaDescriptor[] {
  const fullTitle = buildPageTitle(title);
  const resolvedImage = image ? absoluteUrl(image, url) : undefined;

  const descriptors: MetaDescriptor[] = [
    { title: fullTitle },
    { name: 'description', content: description },
    { property: 'og:type', content: type },
    { property: 'og:title', content: fullTitle },
    { property: 'og:description', content: description },
    { property: 'og:site_name', content: SITE_TITLE },
    { name: 'twitter:card', content: 'summary_large_image' },
    { name: 'twitter:title', content: fullTitle },
    { name: 'twitter:description', content: description },
  ];

  if (url) {
    descriptors.push(
      { property: 'og:url', content: url },
      { name: 'twitter:url', content: url }
    );
  }

  if (resolvedImage) {
    descriptors.push(
      { property: 'og:image', content: resolvedImage },
      { name: 'twitter:image', content: resolvedImage }
    );
  }

  return descriptors;
}

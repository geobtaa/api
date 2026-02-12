import React from 'react';
import { Helmet } from 'react-helmet-async';

interface ResourceJsonLdProps {
  /** Schema.org JSON-LD object for the resource */
  jsonLd: Record<string, unknown>;
}

/**
 * Embeds Schema.org JSON-LD in the document head for citation tools
 * (Zotero, Google Dataset Search) and SEO.
 */
export function ResourceJsonLd({ jsonLd }: ResourceJsonLdProps) {
  const scriptContent = JSON.stringify(jsonLd);
  return (
    <Helmet>
      <script type="application/ld+json">{scriptContent}</script>
    </Helmet>
  );
}

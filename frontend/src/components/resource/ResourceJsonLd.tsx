import { useEffect } from 'react';

interface ResourceJsonLdProps {
  /** Schema.org JSON-LD object for the resource */
  jsonLd: Record<string, unknown>;
}

/**
 * Embeds Schema.org JSON-LD in the document head for citation tools
 * (Zotero, Google Dataset Search) and SEO.
 */
export function ResourceJsonLd({ jsonLd }: ResourceJsonLdProps) {
  useEffect(() => {
    const selector = 'script[data-btaa-json-ld="resource"]';
    document.querySelector(selector)?.remove();

    const script = document.createElement('script');
    script.type = 'application/ld+json';
    script.dataset.btaaJsonLd = 'resource';
    script.textContent = JSON.stringify(jsonLd);
    document.head.appendChild(script);

    return () => {
      script.remove();
    };
  }, [jsonLd]);

  return null;
}

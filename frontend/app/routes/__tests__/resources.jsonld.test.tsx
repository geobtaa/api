import { cleanup, render, waitFor } from '@testing-library/react';
import { createRoutesStub, Meta } from 'react-router';
import type { LoaderFunctionArgs } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { loader, meta } from '../resources.$id';

// Keep this focused on the real API fetch, resource loader, and metadata renderer.
vi.mock('../../../src/pages/ResourceView', () => ({
  ResourceView: () => null,
}));

const citation = {
  '@context': {
    '@version': 1.1,
    '@vocab': 'https://schema.org/',
    url: { '@id': 'https://schema.org/url', '@type': '@id' },
    contentUrl: { '@id': 'https://schema.org/contentUrl', '@type': '@id' },
    datePublished: {
      '@id': 'https://schema.org/datePublished',
      '@type': 'http://www.w3.org/2001/XMLSchema#date',
    },
  },
  '@id': 'https://example.org/resources/points',
  '@type': 'Dataset',
  name: 'Address points',
  url: ['https://example.org/resources/points', 'https://example.org/catalog'],
  description: ['First description', 'Text containing </script> stays data'],
  inLanguage: ['eng', 'fra'],
  author: [{ name: 'Jane Smith' }, { name: 'Example City' }],
  publisher: [{ name: 'Publisher A' }, { name: 'Publisher B' }],
  license: [
    { '@id': 'https://creativecommons.org/licenses/by/4.0/' },
    { '@type': 'CreativeWork', text: 'Additional terms' },
  ],
  datePublished: '2025-07-03',
  distribution: [
    { '@type': 'DataDownload', contentUrl: 'https://example.org/points.zip' },
  ],
};

const resource = {
  id: 'points',
  type: 'resource',
  attributes: {
    ogm: {
      dct_title_s: 'Address points',
      dct_description_sm: ['First description'],
    },
  },
  meta: {
    jsonld: citation,
    ui: {
      citation: 'Jane Smith. (2025). Address points.',
      citations: {
        apa: 'Jane Smith. (2025). Address points.',
        mla: 'Jane Smith. Address points. 2025.',
      },
    },
  },
};

function mockApi(citationStatus = 200) {
  const fetchMock = vi.fn(async (input: string, options: RequestInit) => {
    const url = new URL(input);
    if (url.pathname.endsWith('/citation/json-ld')) {
      expect(new Headers(options.headers).get('Accept')).toBe(
        'application/ld+json'
      );
      return new Response(JSON.stringify(citation), {
        status: citationStatus,
        headers: { 'Content-Type': 'application/ld+json' },
      });
    }
    expect(url.pathname).toBe('/api/v1/resources/points');
    return Response.json({ data: resource });
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('resource citation JSON-LD compatibility', () => {
  it('renders the new inline context and multivalued nodes unchanged in the page script', async () => {
    const fetchMock = mockApi();
    const Routes = createRoutesStub([
      {
        path: '/resources/:id',
        loader,
        meta,
        Component: Meta,
        HydrateFallback: () => null,
      },
    ]);
    render(<Routes initialEntries={['/resources/points']} />);

    await waitFor(() => {
      const scripts = document.querySelectorAll(
        'script[type="application/ld+json"]'
      );
      expect(scripts).toHaveLength(1);
      expect(JSON.parse(scripts[0].textContent!)).toEqual(citation);
    });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('keeps resource data and display citation strings available if JSON-LD fails', async () => {
    mockApi(503);
    const result = await loader({
      params: { id: 'points' },
      request: new Request('https://example.org/resources/points'),
    } as LoaderFunctionArgs);

    expect(result.jsonLd).toBeNull();
    expect(result.resource).toEqual(resource);
    expect(result.resource?.meta?.ui?.citations).toEqual(
      resource.meta.ui.citations
    );
  });
});

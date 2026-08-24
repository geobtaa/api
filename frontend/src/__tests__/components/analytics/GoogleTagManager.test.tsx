import { render, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { GoogleTagManager } from '../../../components/analytics/GoogleTagManager';

describe('GoogleTagManager', () => {
  let injectedScript: HTMLScriptElement | undefined;

  beforeEach(() => {
    injectedScript = undefined;
    const appendChild = document.head.appendChild.bind(document.head);
    vi.spyOn(document.head, 'appendChild').mockImplementation(((node: Node) => {
      if (node instanceof HTMLScriptElement) {
        injectedScript = node;
        return node;
      }
      return appendChild(node);
    }) as typeof document.head.appendChild);
    window.dataLayer = [];
    window.history.replaceState({}, '', '/resources/example');
    document.title = 'Example resource';
  });

  afterEach(() => {
    vi.restoreAllMocks();
    document.getElementById('google-tag-manager')?.remove();
    window.dataLayer = [];
    window.history.replaceState({}, '', '/');
  });

  it('loads the container and initializes the dataLayer on mount', async () => {
    render(
      <GoogleTagManager containerId="GTM-TEST123" locationKey="initial" />
    );

    await waitFor(() => {
      expect(injectedScript).toHaveAttribute(
        'src',
        'https://www.googletagmanager.com/gtm.js?id=GTM-TEST123'
      );
    });
    expect(window.dataLayer).toEqual([
      expect.objectContaining({ event: 'gtm.js' }),
    ]);
  });

  it('does not emit a virtual page view for the initial render', () => {
    render(
      <GoogleTagManager containerId="GTM-TEST123" locationKey="initial" />
    );

    expect(window.dataLayer).not.toContainEqual(
      expect.objectContaining({ event: 'virtual_page_view' })
    );
  });

  it('emits page details after a client-side navigation', () => {
    const { rerender } = render(
      <GoogleTagManager containerId="GTM-TEST123" locationKey="initial" />
    );

    window.history.pushState({}, '', '/search?q=cape+town#results');
    document.title = 'Search results';
    rerender(<GoogleTagManager containerId="GTM-TEST123" locationKey="next" />);

    expect(window.dataLayer).toContainEqual({
      event: 'virtual_page_view',
      page_location: 'http://localhost:3000/search?q=cape+town#results',
      page_path: '/search?q=cape+town#results',
      page_title: 'Search results',
      previous_page_location: 'http://localhost:3000/resources/example',
    });
  });
});

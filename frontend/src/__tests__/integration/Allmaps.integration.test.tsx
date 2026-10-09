import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { parseAnnotation } from '@allmaps/annotation';
import minneapolis from './fixtures/allmaps/minneapolis.json';
import illinois from './fixtures/allmaps/illinois.json';
import { AllmapsViewerFrame } from '../../components/resource/AllmapsViewerFrame';
import { AllmapsLinksCard } from '../../components/resource/AllmapsLinksCard';
import { AllmapsOverlayViewer } from '../../components/resource/AllmapsOverlayViewer';
import { getAllmapsIiifUrl, hasAllmapsOverlay } from '../../utils/allmaps';
import { scheduleAnalyticsBatch } from '../../services/analytics';

vi.mock('../../services/analytics', () => ({
  scheduleAnalyticsBatch: vi.fn(),
}));

const allmapsFor = (fixture: typeof minneapolis | typeof illinois) => ({
  allmaps_annotated: true,
  allmaps_manifest_uri: fixture.manifestUrl,
});

beforeEach(() => {
  vi.clearAllMocks();
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe('Allmaps annotation contracts (real parser, captured public data)', () => {
  it('preserves the one annotated plate within a 39-page atlas', () => {
    const maps = parseAnnotation(minneapolis.annotation);
    expect(minneapolis.canvasCount).toBe(39);
    expect(maps).toHaveLength(1);
    expect(maps[0].resource.id).toContain('p16022coll245:289');
    expect(
      minneapolis.annotation.items[0].target.source.partOf[0].label.none
    ).toEqual(['Plate 22']);
  });

  it('preserves all three map regions across two source images', () => {
    const maps = parseAnnotation(illinois.annotation);
    expect(maps.map((map) => map.id).sort()).toEqual(
      illinois.annotation.items.map((item) => item.id).sort()
    );
    expect(maps).toHaveLength(3);
    expect(new Set(maps.map((map) => map.resource.id)).size).toBe(2);
    expect(illinois.canvasCount).toBe(2);
  });
});

describe('IIIF metadata → Allmaps links', () => {
  it('offers the editor before harvesting, without promising an overlay', () => {
    const resource = {
      attributes: {
        ogm: {
          dct_references_s: JSON.stringify({
            'http://iiif.io/api/presentation#manifest': minneapolis.manifestUrl,
          }),
        },
      },
    };
    render(
      <AllmapsLinksCard
        allmaps={null}
        iiifUrl={getAllmapsIiifUrl(resource)}
        resourceId={minneapolis.resourceId}
      />
    );
    const editor = screen.getByRole('link', {
      name: 'Georeference this map with Allmaps',
    });
    expect(editor).toHaveAttribute(
      'href',
      `https://editor.allmaps.org/#/collection?url=${encodeURIComponent(minneapolis.manifestUrl)}`
    );
    expect(
      screen.queryByRole('link', { name: /View map/ })
    ).not.toBeInTheDocument();
    expect(hasAllmapsOverlay(resource)).toBe(false);
    // Exercise analytics without letting happy-dom navigate to the external site.
    editor.addEventListener('click', (event) => event.preventDefault());
    fireEvent.click(editor);
    expect(scheduleAnalyticsBatch).toHaveBeenCalledWith({
      events: [
        expect.objectContaining({
          event_type: 'allmaps_editor_click',
          resource_id: minneapolis.resourceId,
          destination_url: editor.getAttribute('href'),
        }),
      ],
    });
  });

  it.each([minneapolis, illinois])(
    'offers whole-manifest viewer and editor links for $resourceId',
    (fixture) => {
      const allmaps = allmapsFor(fixture);
      render(<AllmapsLinksCard allmaps={allmaps} />);
      const link = screen.getByRole('link', {
        name: /View map in the Allmaps viewer/,
      });
      const annotationUrl = new URL(
        link.getAttribute('href')!
      ).searchParams.get('url')!;
      expect(new URL(annotationUrl).searchParams.get('url')).toBe(
        fixture.manifestUrl
      );
      expect(
        screen.getByRole('link', { name: /Edit map control points/ })
      ).toBeInTheDocument();
      expect(hasAllmapsOverlay({ meta: { ui: { allmaps } } })).toBe(true);
    }
  );

  it('renders no card without IIIF or annotation data', () => {
    const { container } = render(<AllmapsLinksCard allmaps={null} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe('Embedded Allmaps viewer', () => {
  const settings = (
    window as unknown as {
      happyDOM: { settings: { disableIframePageLoading: boolean } };
    }
  ).happyDOM.settings;
  let previousDisableIframePageLoading: boolean;
  beforeEach(() => {
    previousDisableIframePageLoading = settings.disableIframePageLoading;
    settings.disableIframePageLoading = true;
  });
  afterEach(() => {
    settings.disableIframePageLoading = previousDisableIframePageLoading;
  });

  it.each([minneapolis, illinois])(
    'embeds the entire annotation page for $resourceId',
    (fixture) => {
      render(<AllmapsOverlayViewer allmaps={allmapsFor(fixture)} />);
      const frame = screen.getByTitle('Allmaps viewer');
      const viewer = new URL(frame.getAttribute('src')!);
      expect(viewer.origin).toBe('https://viewer.allmaps.org');
      expect(
        new URL(viewer.searchParams.get('url')!).searchParams.get('url')
      ).toBe(fixture.manifestUrl);
      expect(viewer.searchParams.has('map')).toBe(false);
      expect(frame).toHaveAttribute('allowfullscreen');
      expect(frame.getAttribute('sandbox')).toContain('allow-scripts');
      expect(frame.getAttribute('sandbox')).toContain('allow-same-origin');

      expect(screen.queryByRole('slider')).not.toBeInTheDocument();
    }
  );

  it('replaces the embedded document when the resource changes', () => {
    const { rerender } = render(
      <AllmapsOverlayViewer allmaps={allmapsFor(minneapolis)} />
    );
    const original = screen.getByTitle('Allmaps viewer');
    rerender(<AllmapsOverlayViewer allmaps={allmapsFor(illinois)} />);
    expect(screen.getByTitle('Allmaps viewer')).not.toBe(original);
  });

  it.each([
    null,
    { allmaps_annotated: false, allmaps_manifest_uri: illinois.manifestUrl },
  ])('does not embed resources without annotations', (allmaps) => {
    render(<AllmapsOverlayViewer allmaps={allmaps} />);
    expect(screen.queryByTitle('Allmaps viewer')).not.toBeInTheDocument();
    expect(
      screen.getByText('Map overlay is not available.')
    ).toBeInTheDocument();
  });
});

describe('Allmaps viewer toolbar', () => {
  const content = () => (
    <AllmapsViewerFrame
      tabs={
        <div role="tablist" aria-label="Viewers">
          <button role="tab">Map Overlay</button>
        </div>
      }
      viewerUrl="https://viewer.allmaps.org/"
    >
      <div data-testid="viewer-content" />
    </AllmapsViewerFrame>
  );

  it('places the external link beside the tabs, outside the tablist', () => {
    render(content());
    const tabs = screen.getByRole('tablist');
    const link = screen.getByRole('link', { name: 'Open in new tab' });
    expect(tabs.parentElement).toBe(link.parentElement?.parentElement);
    expect(tabs.contains(link)).toBe(false);
  });

  it('expands without remounting the viewer and restores scrolling on exit', () => {
    render(content());
    const viewer = screen.getByTestId('viewer-content');
    const overflow = document.body.style.overflow;
    fireEvent.click(screen.getByRole('button', { name: 'Fullscreen' }));
    expect(
      screen.getByRole('button', { name: 'Exit fullscreen' })
    ).toHaveAttribute('aria-pressed', 'true');
    expect(document.body.style.overflow).toBe('hidden');
    expect(screen.getByTestId('viewer-content')).toBe(viewer);
    fireEvent.click(screen.getByRole('button', { name: 'Exit fullscreen' }));
    expect(document.body.style.overflow).toBe(overflow);
  });

  it('supports Escape and cleans up after unmount', () => {
    const { unmount } = render(content());
    fireEvent.click(screen.getByRole('button', { name: 'Fullscreen' }));
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.getByRole('button', { name: 'Fullscreen' })).toHaveAttribute(
      'aria-pressed',
      'false'
    );
    fireEvent.click(screen.getByRole('button', { name: 'Fullscreen' }));
    unmount();
    expect(document.body.style.overflow).not.toBe('hidden');
  });
});

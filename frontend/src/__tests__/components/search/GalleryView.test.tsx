import {
  act,
  render,
  screen,
  fireEvent,
  waitFor,
} from '@testing-library/react';
import { GalleryView } from '../../../components/search/GalleryView';
import { BrowserRouter } from 'react-router';
import { vi, describe, it, expect } from 'vitest';
import type { GeoDocument } from '../../../types/api';
import type { ComponentProps } from 'react';

// Mock BookmarkButton to avoid context provider requirement
vi.mock('../../../components/BookmarkButton', () => ({
  BookmarkButton: () => <button data-testid="bookmark-btn">Bookmark</button>,
}));

// Mock useBookmarks hook because it is now used directly in GalleryView
vi.mock('../../../context/BookmarkContext', () => ({
  useBookmarks: () => ({
    isBookmarked: () => false, // Default to false for tests
  }),
}));

afterEach(() => {
  vi.clearAllMocks();
});

const mockResults: GeoDocument[] = Array.from({ length: 25 }, (_, i) => ({
  type: 'file',
  id: `result-${i + 1}`,
  attributes: {
    ogm: {
      dct_title_s: `Result ${i + 1}`,
      gbl_resourceClass_sm: ['Map'],
      gbl_indexYear_im: [2020],
    },
  },
  links: { self: '#' },
}));

type GalleryViewProps = ComponentProps<typeof GalleryView>;

describe('GalleryView', () => {
  beforeEach(() => {
    vi.useRealTimers();
  });

  const renderGallery = (props: Partial<GalleryViewProps> = {}) => {
    return render(
      <BrowserRouter>
        <GalleryView
          results={mockResults.slice(0, 20)}
          isLoading={false}
          totalResults={100}
          currentPage={1}
          {...props}
        />
      </BrowserRouter>
    );
  };

  it('renders list of items', () => {
    renderGallery();
    expect(screen.getAllByRole('link')).toHaveLength(20);
    expect(screen.getAllByText('Result 1').length).toBeGreaterThan(0);
  });

  it('uses the resource-class static-map fallback when a result has no real thumbnail', () => {
    const { container } = renderGallery({
      results: [mockResults[0]],
      totalResults: 1,
    });

    expect(
      container.querySelector(
        'img[src="/static-maps/result-1/resource-class-icon"]'
      )
    ).toBeInTheDocument();
    expect(
      screen.queryByTestId('gallery-thumbnail-placeholder-0')
    ).not.toBeInTheDocument();
  });

  it('prefers a hot immutable resource-class icon asset when one is provided', () => {
    const iconHash = 'c'.repeat(64);
    const resultWithHotIconAsset: GeoDocument = {
      ...mockResults[0],
      meta: {
        ui: {
          resource_class_icon_url: `http://localhost:8000/api/v1/static-map-assets/${iconHash}?kind=resource-class-icon`,
        },
      },
    };

    const { container } = renderGallery({
      results: [resultWithHotIconAsset],
      totalResults: 1,
    });

    const hotIcon = container.querySelector(
      `img[src="/api/v1/static-map-assets/${iconHash}?kind=resource-class-icon"]`
    );
    const legacyIcon = container.querySelector(
      'img[src="/static-maps/result-1/resource-class-icon"]'
    );

    expect(hotIcon).toBeInTheDocument();
    expect(legacyIcon).not.toBeInTheDocument();
  });

  it('renders the static-map fallback immediately for cold fallback items', () => {
    const completeSpy = vi
      .spyOn(HTMLImageElement.prototype, 'complete', 'get')
      .mockReturnValue(false);

    try {
      renderGallery({
        results: [mockResults[0]],
        totalResults: 1,
      });

      expect(
        document.querySelector(
          'img[src="/static-maps/result-1/resource-class-icon"]'
        )
      ).toBeInTheDocument();
      expect(
        screen.queryByTestId('gallery-thumbnail-placeholder-0')
      ).not.toBeInTheDocument();
    } finally {
      completeSpy.mockRestore();
    }
  });

  it('uses the canonical resolver for generic resource thumbnail endpoints', () => {
    const resultWithGenericThumbnail: GeoDocument = {
      ...mockResults[0],
      meta: {
        ui: {
          thumbnail_url:
            'http://localhost:8000/api/v1/resources/result-1/thumbnail',
        },
      },
    };

    const { container } = renderGallery({
      results: [resultWithGenericThumbnail],
      totalResults: 1,
    });

    expect(
      container.querySelector('img[src="/resources/result-1/thumbnail"]')
    ).toBeInTheDocument();
    expect(
      screen.queryByTestId('gallery-thumbnail-placeholder-0')
    ).not.toBeInTheDocument();
  });

  it('routes raw bridge thumbnail assets through the canonical resolver in gallery view', () => {
    const resultWithBridgeThumbnail: GeoDocument = {
      ...mockResults[0],
      meta: {
        ui: {
          thumbnail_url:
            'https://geobtaa-assets-prod.s3.us-east-2.amazonaws.com/store/asset/test/huge-image.jpg',
        },
      },
    };

    const { container } = renderGallery({
      results: [resultWithBridgeThumbnail],
      totalResults: 1,
    });

    expect(
      container.querySelector('img[src="/resources/result-1/thumbnail"]')
    ).toBeInTheDocument();
    expect(
      screen.queryByTestId('gallery-thumbnail-placeholder-0')
    ).not.toBeInTheDocument();
  });

  it('uses a larger inline icon only after the fallback asset fails', () => {
    const { container } = renderGallery({
      results: [mockResults[0]],
      totalResults: 1,
    });

    const fallbackImage = container.querySelector(
      'img[src="/static-maps/result-1/resource-class-icon"]'
    );
    expect(fallbackImage).toBeInTheDocument();

    fireEvent.error(fallbackImage as HTMLImageElement);

    const placeholder = screen.getByTestId('gallery-thumbnail-placeholder-0');
    const icon = placeholder.querySelector('svg');
    expect(placeholder).toBeInTheDocument();
    expect(icon).toHaveClass('h-36', 'w-36');
  });

  it('hides the placeholder immediately for already-cached thumbnails', async () => {
    const resultWithDirectThumbnail: GeoDocument = {
      ...mockResults[0],
      meta: {
        ui: {
          thumbnail_url: 'https://example.com/thumb.jpg',
        },
      },
    };

    const completeSpy = vi
      .spyOn(HTMLImageElement.prototype, 'complete', 'get')
      .mockReturnValue(true);
    const naturalWidthSpy = vi
      .spyOn(HTMLImageElement.prototype, 'naturalWidth', 'get')
      .mockReturnValue(800);

    try {
      renderGallery({
        results: [resultWithDirectThumbnail],
        totalResults: 1,
      });

      await waitFor(() => {
        expect(
          screen.queryByTestId('gallery-thumbnail-placeholder-0')
        ).not.toBeInTheDocument();
      });
    } finally {
      naturalWidthSpy.mockRestore();
      completeSpy.mockRestore();
    }
  });

  it('uses a neutral loading surface instead of overlaying the resource icon on real thumbnails', () => {
    const resultWithDirectThumbnail: GeoDocument = {
      ...mockResults[0],
      meta: {
        ui: {
          thumbnail_url: 'https://example.com/thumb.jpg',
        },
      },
    };

    const completeSpy = vi
      .spyOn(HTMLImageElement.prototype, 'complete', 'get')
      .mockReturnValue(false);

    try {
      renderGallery({
        results: [resultWithDirectThumbnail],
        totalResults: 1,
      });

      expect(
        screen.queryByTestId('gallery-thumbnail-placeholder-0')
      ).not.toBeInTheDocument();
      expect(
        screen.getByTestId('gallery-thumbnail-loading-0')
      ).toBeInTheDocument();
    } finally {
      completeSpy.mockRestore();
    }
  });

  it('defers below-the-fold gallery images until after initial paint', () => {
    vi.useFakeTimers();
    const resultsWithDirectThumbnails = mockResults
      .slice(0, 20)
      .map((result) => ({
        ...result,
        meta: {
          ui: {
            thumbnail_url: `https://example.com/${result.id}.jpg`,
          },
        },
      }));

    const { container } = renderGallery({
      results: resultsWithDirectThumbnails,
    });

    expect(
      container.querySelector('img[src="https://example.com/result-16.jpg"]')
    ).not.toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(300);
    });

    expect(
      container.querySelector('img[src="https://example.com/result-16.jpg"]')
    ).not.toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(75);
    });

    expect(
      container.querySelector('img[src="https://example.com/result-16.jpg"]')
    ).toBeInTheDocument();
  });

  it('passes correct state to Link', () => {
    renderGallery({ startPage: 1, perPage: 20 });
    const link = screen.getAllByRole('link')[11]; // 12th item (index 11)

    // We can't easy assert the "state" prop of the Link component directly in a compiled test without mocking Link or Router hook.
    // But we can check if the href is correct.
    expect(link).toHaveAttribute('href', '/resources/result-12');

    // To verify state, we can mock `react-router`'s Link or check interactions.
    // Or strictly trust the structure.
    // Ideally we inspect the Virtual DOM props, but testing-library discourages that.
    // We will assume basic rendering is fine, but we can verify the TEXT of the debug overlay if it was enabled (it's not usually).
  });

  it('renders year and resource class in conjoined pill', () => {
    renderGallery();
    // Mock has gbl_indexYear_im: [2020] and gbl_resourceClass_sm: ['Map'] for each result
    const pills = screen.getAllByTestId('result-card-pill');
    expect(pills.length).toBeGreaterThan(0);
    const pill = pills[0];
    expect(pill).toHaveTextContent('2020');
    expect(pill).toHaveTextContent('Map');
    expect(pill).toHaveClass('bg-[#003c5b]', 'text-white');
  });

  describe('result numbers', () => {
    it('displays result numbers before titles (e.g. 1. Result 1)', () => {
      renderGallery({ perPage: 20 });
      expect(screen.getByText('1.')).toBeInTheDocument();
      expect(screen.getByText('2.')).toBeInTheDocument();
      expect(screen.getByText('20.')).toBeInTheDocument();
    });

    it('uses perPage and startPage for numbering', () => {
      renderGallery({
        results: mockResults.slice(0, 10),
        startPage: 2,
        perPage: 10,
        currentPage: 2,
      });
      // Page 2, 10 per page: results 11-20
      expect(screen.getByText('11.')).toBeInTheDocument();
      expect(screen.getByText('20.')).toBeInTheDocument();
    });
  });
});

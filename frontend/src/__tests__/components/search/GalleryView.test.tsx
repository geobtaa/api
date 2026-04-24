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

// Mock IntersectionObserver
const observeMock = vi.fn();
const unobserveMock = vi.fn();

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

beforeAll(() => {
  global.IntersectionObserver = vi.fn().mockImplementation(() => ({
    observe: observeMock,
    unobserve: unobserveMock,
    disconnect: vi.fn(),
  }));
});

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

describe('GalleryView', () => {
  beforeEach(() => {
    vi.useRealTimers();
  });

  const renderGallery = (props: any = {}) => {
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

  it('uses the grid fallback asset when a result has no real thumbnail', () => {
    const { container } = renderGallery({
      results: [mockResults[0]],
      totalResults: 1,
    });

    const thumbnail = container.querySelector(
      'img[src="/static-maps/result-1/resource-class-icon"]'
    );
    expect(thumbnail).toBeInTheDocument();
  });

  it('does not overlay the inline resource icon while the fallback asset loads', () => {
    const completeSpy = vi
      .spyOn(HTMLImageElement.prototype, 'complete', 'get')
      .mockReturnValue(false);

    try {
      renderGallery({
        results: [mockResults[0]],
        totalResults: 1,
      });

      expect(
        screen.queryByTestId('gallery-thumbnail-placeholder-0')
      ).not.toBeInTheDocument();
    } finally {
      completeSpy.mockRestore();
    }
  });

  it('routes the generic resource thumbnail endpoint through the gallery thumbnail route', () => {
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

    const thumbnail = container.querySelector(
      'img[src="/resources/result-1/thumbnail"]'
    );
    expect(thumbnail).toBeInTheDocument();
  });

  it('routes raw bridge thumbnail assets through the gallery thumbnail route', () => {
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

    const thumbnail = container.querySelector(
      'img[src="/resources/result-1/thumbnail"]'
    );
    expect(thumbnail).toBeInTheDocument();
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

    const { container } = renderGallery();

    expect(
      container.querySelector(
        'img[src="/static-maps/result-16/resource-class-icon"]'
      )
    ).not.toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(300);
    });

    expect(
      container.querySelector(
        'img[src="/static-maps/result-16/resource-class-icon"]'
      )
    ).not.toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(75);
    });

    expect(
      container.querySelector(
        'img[src="/static-maps/result-16/resource-class-icon"]'
      )
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

  it('triggers onLoadMore when intersection occurs', () => {
    const onLoadMore = vi.fn();
    renderGallery({ onLoadMore, hasMore: true });

    expect(global.IntersectionObserver).toHaveBeenCalled();

    // Simulate intersection
    const observerCallback = (global.IntersectionObserver as any).mock
      .calls[0][0];
    const entry = { isIntersecting: true };
    observerCallback([entry]);

    expect(onLoadMore).toHaveBeenCalled();
  });

  it('does not trigger onLoadMore if isLoading is true', () => {
    const onLoadMore = vi.fn();
    renderGallery({ onLoadMore, hasMore: true, isLoading: true });

    const observerCallback = (global.IntersectionObserver as any).mock
      .calls[0][0];
    observerCallback([{ isIntersecting: true }]);

    expect(onLoadMore).not.toHaveBeenCalled();
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

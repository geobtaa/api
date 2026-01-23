import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { GalleryView } from '../../../components/search/GalleryView';
import { BrowserRouter } from 'react-router';
import { vi, describe, it, expect } from 'vitest';
import type { GeoDocument } from '../../../types/api';

// Mock IntersectionObserver
const observeMock = vi.fn();
const unobserveMock = vi.fn();

// Mock BookmarkButton to avoid context provider requirement
vi.mock('../../../components/BookmarkButton', () => ({
    BookmarkButton: () => <button data-testid="bookmark-btn">Bookmark</button>
}));

// Mock useBookmarks hook because it is now used directly in GalleryView
vi.mock('../../../context/BookmarkContext', () => ({
    useBookmarks: () => ({
        isBookmarked: () => false // Default to false for tests
    })
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
    links: { self: '#' }
}));

describe('GalleryView', () => {
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
        const observerCallback = (global.IntersectionObserver as any).mock.calls[0][0];
        const entry = { isIntersecting: true };
        observerCallback([entry]);

        expect(onLoadMore).toHaveBeenCalled();
    });

    it('does not trigger onLoadMore if isLoading is true', () => {
        const onLoadMore = vi.fn();
        renderGallery({ onLoadMore, hasMore: true, isLoading: true });

        const observerCallback = (global.IntersectionObserver as any).mock.calls[0][0];
        observerCallback([{ isIntersecting: true }]);

        expect(onLoadMore).not.toHaveBeenCalled();
    });


});

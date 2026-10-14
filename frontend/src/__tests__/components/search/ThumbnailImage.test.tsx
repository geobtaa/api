import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { BrowserRouter } from 'react-router';
import { GalleryView } from '../../../components/search/GalleryView';
import { ThumbnailImage } from '../../../components/search/ThumbnailImage';

const pending = () =>
  new Response('<svg/>', {
    headers: { 'Content-Type': 'image/svg+xml', 'X-Thumbnail-Pending': 'true' },
  });
const ready = () =>
  new Response('image', { headers: { 'Content-Type': 'image/png' } });
const flush = async () => {
  await act(async () => {
    await Promise.resolve();
  });
};

describe('ThumbnailImage', () => {
  const fetchMock = vi.fn();
  beforeEach(() => {
    vi.useFakeTimers();
    vi.stubGlobal('fetch', fetchMock);
    fetchMock.mockReset();
    vi.spyOn(URL, 'createObjectURL')
      .mockReturnValueOnce('blob:pending')
      .mockReturnValue('blob:ready');
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});
  });
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it('replaces a successfully loaded pending SVG without a page refresh', async () => {
    fetchMock.mockResolvedValueOnce(pending()).mockResolvedValueOnce(ready());
    const { unmount } = render(
      <ThumbnailImage
        resourceId="map"
        src="/resources/map/thumbnail"
        alt="map"
      />
    );
    await flush();
    expect(screen.getByAltText('map')).toHaveAttribute('src', 'blob:pending');
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });
    expect(screen.getByAltText('map')).toHaveAttribute('src', 'blob:ready');
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30000);
    });
    expect(fetchMock).toHaveBeenCalledTimes(2);
    unmount();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:ready');
  });

  it('updates a real gallery card in place when capture finishes', async () => {
    fetchMock.mockResolvedValueOnce(pending()).mockResolvedValueOnce(ready());
    const { container, unmount } = render(
      <BrowserRouter>
        <GalleryView
          results={[
            {
              id: 'psu-map',
              type: 'resource',
              attributes: {
                ogm: {
                  dct_title_s: 'PSU Sanborn map',
                  gbl_resourceClass_sm: ['Maps'],
                },
              },
              meta: { ui: { thumbnail_url: '/resources/psu-map/thumbnail' } },
              links: { self: '#' },
            },
          ]}
          isLoading={false}
          totalResults={1}
          currentPage={1}
        />
      </BrowserRouter>
    );
    await flush();
    expect(
      container.querySelector('img[src="blob:pending"]')
    ).toBeInTheDocument();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });
    expect(
      container.querySelector('img[src="blob:ready"]')
    ).toBeInTheDocument();
    expect(screen.getByText('PSU Sanborn map')).toBeInTheDocument();
    unmount();
  });

  it('retains the image when updated search data uses an equivalent resolver URL', async () => {
    fetchMock.mockResolvedValueOnce(ready());
    const { rerender } = render(
      <ThumbnailImage
        resourceId="map"
        src="/resources/map/thumbnail"
        alt="map"
      />
    );
    await flush();
    rerender(
      <ThumbnailImage
        resourceId="map"
        src="https://example.org/api/v1/resources/map/thumbnail"
        alt="map"
      />
    );
    await flush();
    expect(screen.getByAltText('map')).toHaveAttribute('src', 'blob:pending');
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('does not poll permanent placeholders', async () => {
    fetchMock.mockResolvedValue(
      new Response('<svg/>', { headers: { 'X-Placeholder': 'true' } })
    );
    render(
      <ThumbnailImage
        resourceId="map"
        src="/resources/map/thumbnail"
        alt="map"
      />
    );
    await flush();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60000);
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('keeps immutable images on the normal img path and recovers a failed URL', async () => {
    fetchMock.mockResolvedValueOnce(ready());
    render(
      <ThumbnailImage resourceId="map" src="/api/v1/thumbnails/old" alt="map" />
    );
    expect(fetchMock).not.toHaveBeenCalled();
    fireEvent.error(screen.getByAltText('map'));
    await flush();
    expect(fetchMock).toHaveBeenCalledWith(
      '/resources/map/thumbnail',
      expect.objectContaining({ cache: 'no-store' })
    );
    expect(screen.getByAltText('map')).toHaveAttribute('src', 'blob:pending');
  });

  it('cancels pending requests and timers when unmounted', async () => {
    fetchMock.mockResolvedValue(pending());
    const { unmount } = render(
      <ThumbnailImage
        resourceId="map"
        src="/resources/map/thumbnail"
        alt="map"
      />
    );
    await flush();
    const signal = fetchMock.mock.calls[0][1].signal;
    unmount();
    expect(signal.aborted).toBe(true);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60000);
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('bounds retries for a source that never becomes ready', async () => {
    fetchMock.mockImplementation(async () => pending());
    const { unmount } = render(
      <ThumbnailImage
        resourceId="map"
        src="/resources/map/thumbnail"
        alt="map"
      />
    );
    await flush();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(200000);
    });
    expect(fetchMock).toHaveBeenCalledTimes(12);
    unmount();
  });
});

vi.mock('../../../components/BookmarkButton', () => ({
  BookmarkButton: () => null,
}));
vi.mock('../../../context/BookmarkContext', () => ({
  useBookmarks: () => ({ isBookmarked: () => false }),
}));

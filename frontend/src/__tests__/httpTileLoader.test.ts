import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import L from 'leaflet';
import { attachHttpTileLoader } from '../config/httpTileLoader';

describe('HTTP-aware OSM tiles', () => {
  const request = vi.fn();
  beforeEach(() => {
    vi.stubGlobal('fetch', request);
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:tile');
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    request.mockReset();
  });
  function setup() {
    const layer = L.tileLayer('/tiles/{z}/{x}/{y}.png');
    vi.spyOn(layer, 'getTileUrl').mockReturnValue('/tiles/5/1/2.png');
    attachHttpTileLoader(layer);
    const done = vi.fn();
    const tile = layer.createTile(
      { x: 1, y: 2, z: 5 } as L.Coords,
      done
    ) as HTMLImageElement;
    return { layer, tile, done };
  }
  it('rejects 403 image bodies without decoding or retrying', async () => {
    const blob = vi.fn();
    request.mockResolvedValue({ ok: false, status: 403, blob });
    const { tile, done } = setup();
    await vi.waitFor(() => expect(done).toHaveBeenCalledOnce());
    expect(done).toHaveBeenCalledWith(
      expect.objectContaining({ message: 'Basemap tile HTTP 403' }),
      tile
    );
    expect(blob).not.toHaveBeenCalled();
    expect(tile.hasAttribute('src')).toBe(false);
    expect(tile.style.visibility).toBe('hidden');
    expect(request).toHaveBeenCalledTimes(1);
  });
  it('preserves browser caching and decodes one successful request', async () => {
    request.mockResolvedValue({ ok: true, blob: async () => new Blob() });
    const { tile, done } = setup();
    await vi.waitFor(() => expect(tile.src).toBe('blob:tile'));
    expect(request).toHaveBeenCalledWith(
      '/tiles/5/1/2.png',
      expect.objectContaining({
        cache: 'default',
        mode: 'cors',
        credentials: 'omit',
        referrerPolicy: 'strict-origin-when-cross-origin',
      })
    );
    tile.dispatchEvent(new Event('load'));
    expect(done).toHaveBeenCalledWith(undefined, tile);
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:tile');
  });
  it('reports network/CORS errors without retrying as an image', async () => {
    request.mockRejectedValue(new TypeError('Failed to fetch'));
    const { done, tile } = setup();
    await vi.waitFor(() => expect(done).toHaveBeenCalledOnce());
    expect(tile.hasAttribute('src')).toBe(false);
    expect(request).toHaveBeenCalledOnce();
  });
  it('reports decoding errors and releases the blob', async () => {
    request.mockResolvedValue({ ok: true, blob: async () => new Blob() });
    const { tile, done } = setup();
    await vi.waitFor(() => expect(tile.src).toBe('blob:tile'));
    tile.dispatchEvent(new Event('error'));
    expect(done).toHaveBeenCalledWith(expect.any(Error), tile);
    expect(URL.revokeObjectURL).toHaveBeenCalledOnce();
  });
  it.each(['tileunload', 'tileabort', 'remove'])(
    'cancels requests on %s without late warnings',
    async (event) => {
      let resolve!: (value: unknown) => void;
      request.mockImplementation(
        () =>
          new Promise((r) => {
            resolve = r;
          })
      );
      const { layer, tile, done } = setup();
      const signal = request.mock.calls[0][1].signal;
      layer.fire(event, { tile });
      expect(signal.aborted).toBe(true);
      resolve({ ok: true, blob: async () => new Blob() });
      await new Promise((r) => setTimeout(r, 0));
      expect(done).not.toHaveBeenCalled();
      expect(URL.createObjectURL).not.toHaveBeenCalled();
    }
  );
  it('releases a decoding image on removal', async () => {
    request.mockResolvedValue({ ok: true, blob: async () => new Blob() });
    const { layer, tile, done } = setup();
    await vi.waitFor(() => expect(tile.src).toBe('blob:tile'));
    layer.fire('remove');
    tile.dispatchEvent(new Event('load'));
    expect(done).not.toHaveBeenCalled();
    expect(URL.revokeObjectURL).toHaveBeenCalledOnce();
  });
});

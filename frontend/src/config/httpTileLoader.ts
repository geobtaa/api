import type L from 'leaflet';

/** Load each tile once, checking HTTP status before decoding its image body. */
export function attachHttpTileLoader(layer: L.TileLayer): void {
  const pending = new Map<HTMLElement, () => void>();

  layer.createTile = function (coords: L.Coords, done: L.DoneCallback) {
    const tile = document.createElement('img');
    tile.alt = '';
    const controller = new AbortController();
    let objectUrl: string | undefined;
    let finished = false;

    const cleanup = () => {
      tile.onload = null;
      tile.onerror = null;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
      objectUrl = undefined;
      pending.delete(tile);
    };
    const finish = (error?: Error) => {
      if (finished) return;
      finished = true;
      cleanup();
      if (error) tile.style.visibility = 'hidden';
      done(error, tile);
    };
    pending.set(tile, () => {
      finished = true;
      controller.abort();
      cleanup();
    });

    void fetch(this.getTileUrl(coords), {
      mode: 'cors',
      credentials: 'omit',
      cache: 'default',
      referrerPolicy: 'strict-origin-when-cross-origin',
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`Basemap tile HTTP ${response.status}`);
        }
        const blob = await response.blob();
        if (finished) return;
        objectUrl = URL.createObjectURL(blob);
        tile.onload = () => finish();
        tile.onerror = () =>
          finish(new Error('Basemap tile image could not be decoded'));
        tile.src = objectUrl;
      })
      .catch((error: unknown) => {
        if (!finished)
          finish(
            error instanceof Error
              ? error
              : new Error('Basemap tile request failed')
          );
      });
    return tile;
  };

  layer.on('tileunload tileabort', (event: L.TileEvent) => {
    pending.get(event.tile)?.();
  });
  layer.on('remove', () => {
    for (const cancel of pending.values()) cancel();
  });
}

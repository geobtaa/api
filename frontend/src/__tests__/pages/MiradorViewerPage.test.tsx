import { cleanup, render, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MiradorViewerPage } from '../../pages/MiradorViewerPage';
import { MiradorRotationControls } from '../../components/resource/MiradorRotationControls';

const viewer = vi.hoisted(() => vi.fn());
vi.mock('mirador', () => ({ default: { viewer } }));
vi.mock('mirador-dl-plugin', () => ({ default: [] }));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  window.history.replaceState({}, '', '/');
});

describe('Mirador presentation', () => {
  it.each([
    ['&embedded=1', false],
    ['', true],
  ])(
    'uses shared fullscreen only in embedded mode (%s)',
    async (query, fullscreen) => {
      window.history.replaceState(
        {},
        '',
        `/mirador?manifest=https%3A%2F%2Fexample.com%2Fmanifest${query}`
      );
      render(<MiradorViewerPage />);
      await waitFor(() => expect(viewer).toHaveBeenCalledOnce());
      expect(viewer).toHaveBeenCalledWith(
        expect.objectContaining({
          osdConfig: { drawer: 'canvas' },
          window: expect.objectContaining({
            allowFullscreen: fullscreen,
            allowTopMenuButton: false,
            allowClose: false,
            allowMaximize: false,
          }),
          windows: [
            {
              manifestId: 'https://example.com/manifest',
              thumbnailNavigationPosition: 'far-bottom',
            },
          ],
          workspace: { showZoomControls: true },
          workspaceControlPanel: { enabled: false },
          theme: expect.objectContaining({
            palette: expect.objectContaining({ primary: { main: '#2563eb' } }),
          }),
        }),
        [
          {
            target: 'ZoomControls',
            mode: 'wrap',
            component: MiradorRotationControls,
          },
        ]
      );
    }
  );
});

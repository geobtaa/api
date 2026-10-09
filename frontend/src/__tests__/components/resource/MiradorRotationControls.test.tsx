import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MiradorRotationControls } from '../../../components/resource/MiradorRotationControls';

afterEach(cleanup);

describe('Mirador rotation controls', () => {
  it.each([
    ['left', undefined, 270],
    ['right', undefined, 90],
    ['right', 270, 0],
    ['left', 90, 0],
  ] as const)(
    'rotates %s from %s to %s',
    async (direction, rotation, expected) => {
      const updateViewport = vi.fn();
      render(
        <MiradorRotationControls
          windowId="map-window"
          viewer={{ rotation }}
          updateViewport={updateViewport}
        >
          <button>Zoom in</button>
        </MiradorRotationControls>
      );
      expect(screen.getByRole('button', { name: 'Zoom in' })).toBeVisible();
      await userEvent.click(
        screen.getByRole('button', { name: `Rotate ${direction} 90°` })
      );
      // Update only rotation, leaving Mirador's current pan and zoom untouched.
      expect(updateViewport).toHaveBeenCalledWith('map-window', {
        rotation: expected,
      });
    }
  );
});

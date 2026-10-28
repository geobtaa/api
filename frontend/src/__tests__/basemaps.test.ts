import { afterEach, describe, expect, it } from 'vitest';
import Cookies from 'js-cookie';
import {
  BASEMAP_STYLES,
  getAvailableBasemapKeys,
  getSavedBasemapKey,
} from '../config/basemaps';
afterEach(() => Cookies.remove('preferred_basemap'));
describe('OpenFreeMap basemap selection', () => {
  it('offers only OpenFreeMap styles', () => {
    expect(getAvailableBasemapKeys()).toEqual([
      'liberty',
      'bright',
      'positron',
      'dark',
      'fiord',
    ]);
    for (const url of Object.values(BASEMAP_STYLES))
      expect(new URL(url).hostname).toBe('tiles.openfreemap.org');
  });
  it('defaults obsolete provider cookies to Liberty', () => {
    Cookies.set('preferred_basemap', 'esriWorldImagery');
    expect(getSavedBasemapKey()).toBe('liberty');
  });
  it('restores a supported style preference', () => {
    Cookies.set('preferred_basemap', 'dark');
    expect(getSavedBasemapKey()).toBe('dark');
  });
});

it('keeps the compact layers button and opens basemap choices on demand', async () => {
  const { fireEvent, screen, waitFor } = await import('@testing-library/react');
  const { vi } = await import('vitest');
  const { attachBasemapSwitcher } = await import('../config/basemaps');
  const native = {
    getStyle: () => ({ version: 8, sources: {}, layers: [] }),
    setStyle: vi.fn(),
    getCenter: () => ({ lng: -90, lat: 40 }),
    getZoom: () => 4,
    getBearing: () => 0,
    getPitch: () => 0,
    addControl: (control) => document.body.append(control.onAdd()),
    removeControl: (control) => control.onRemove(),
  };
  const map = { native, removed: false, whenReady: (callback) => callback() };
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({
      ok: true,
      json: async () => ({ version: 8, sources: {}, layers: [] }),
    }))
  );
  const cleanup = attachBasemapSwitcher(map as never, null);
  try {
    expect(screen.queryByRole('combobox')).toBeNull();
    const button = screen.getByRole('button', { name: 'Change basemap' });
    expect(button).toHaveAttribute('aria-expanded', 'false');
    const control = button.parentElement!;
    fireEvent.mouseEnter(control);
    const panel = screen.getByRole('radiogroup', { name: 'Basemap style' });
    expect(button).not.toBeVisible();
    expect(panel.style.position).not.toBe('absolute');
    expect(screen.getAllByRole('radio')).toHaveLength(5);
    expect(screen.getByLabelText('OpenFreeMap Positron')).toBeVisible();
    expect(screen.getByLabelText('OpenFreeMap Fiord')).toBeVisible();
    fireEvent.mouseLeave(control, { relatedTarget: panel });
    expect(panel).toBeVisible();
    fireEvent.mouseEnter(panel);
    expect(
      screen.getByRole('radiogroup', { name: 'Basemap style' })
    ).toBeVisible();
    fireEvent.click(screen.getByLabelText('OpenFreeMap Dark'));
    await waitFor(() => expect(native.setStyle).toHaveBeenCalledTimes(1));
    expect(button).toHaveAttribute('aria-expanded', 'false');
    expect(native.setStyle).toHaveBeenCalledWith(
      expect.objectContaining({ center: [-90, 40], zoom: 4 })
    );
    expect(getSavedBasemapKey()).toBe('dark');
    expect(button).toBeVisible();
    fireEvent.mouseEnter(control);
    fireEvent.mouseLeave(control, { relatedTarget: document.body });
    expect(panel).not.toBeVisible();
    fireEvent.click(button);
    expect(panel).toBeVisible();
    fireEvent.keyDown(control, { key: 'Escape' });
    expect(panel).not.toBeVisible();
  } finally {
    cleanup();
    vi.unstubAllGlobals();
  }
});

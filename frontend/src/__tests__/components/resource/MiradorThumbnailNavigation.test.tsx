import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MiradorThumbnailNavigation } from '../../../components/resource/MiradorThumbnailNavigation';
import { thumbnailColumnWidth } from '../../../utils/miradorThumbnailLayout';

vi.mock('mirador', () => ({
  ConnectedThumbnailCanvasGrouping: () => null,
}));
vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: () => 'Thumbnails' }),
}));

afterEach(cleanup);

const canvas = (width: number, height: number, index = 0) => ({
  index,
  getWidth: () => width,
  getHeight: () => height,
});

describe('Mirador thumbnail layout', () => {
  it('reserves an 80px target plus spacing for the ribbon without changing its dimensions', () => {
    const ribbon = canvas(1196, 39783);
    expect(thumbnailColumnWidth([ribbon], 112)).toBe(92);
    expect(ribbon.getWidth()).toBe(1196);
    expect(ribbon.getHeight()).toBe(39783);
  });

  it('preserves wider images and reserves space for each facing-page thumbnail', () => {
    const wide = canvas(1172, 699);
    const ribbon = canvas(1196, 39783);
    expect(thumbnailColumnWidth([wide], 112)).toBe(200);
    expect(thumbnailColumnWidth([wide, ribbon], 112)).toBe(280);
  });

  it.each([0, Number.NaN])('handles missing dimensions (%s)', (height) => {
    expect(thumbnailColumnWidth([canvas(100, height)], 112)).toBe(92);
  });

  const props = () => ({
    canvasGroupings: [[canvas(1196, 39783)]],
    canvasIndex: 0,
    position: 'far-bottom',
    thumbnailNavigation: { height: 130, width: 100 },
    windowId: 'window-1',
    hasNextCanvas: true,
    hasPreviousCanvas: false,
    setNextCanvas: vi.fn(),
    setPreviousCanvas: vi.fn(),
  });

  it('preserves arrow-key page navigation and respects the first-page boundary', () => {
    const navigation = props();
    render(<MiradorThumbnailNavigation {...navigation} />);
    const strip = screen.getByLabelText('Thumbnails');
    fireEvent.keyDown(strip, { key: 'ArrowRight' });
    fireEvent.keyDown(strip, { key: 'ArrowLeft' });
    expect(navigation.setNextCanvas).toHaveBeenCalledOnce();
    expect(navigation.setPreviousCanvas).not.toHaveBeenCalled();
  });

  it.each(['far-right', 'off'])('keeps upstream layout for %s', (position) => {
    render(
      <MiradorThumbnailNavigation {...props()} position={position}>
        <div>Original navigation</div>
      </MiradorThumbnailNavigation>
    );
    expect(screen.getByText('Original navigation')).toBeInTheDocument();
    expect(screen.queryByLabelText('Thumbnails')).not.toBeInTheDocument();
  });
});

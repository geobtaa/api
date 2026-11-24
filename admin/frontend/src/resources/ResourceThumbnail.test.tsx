import { fireEvent, render } from '@testing-library/react';
import { expect, it } from 'vitest';
import { ResourceThumbnail } from './ResourceThumbnail';

it('loads encoded Geospatial API thumbnails lazily and falls back without retry loops', () => {
  const { container } = render(<ResourceThumbnail id="ark:/123/example" />);
  const image = container.querySelector('img')!;
  expect(image.src).toBe(
    'https://geo.btaa.org/api/v1/resources/ark%3A%2F123%2Fexample/thumbnail'
  );
  expect(image).toHaveAttribute('loading', 'lazy');
  expect(image).toHaveAttribute('referrerpolicy', 'no-referrer');
  fireEvent.error(image);
  expect(image.src).toBe('https://geo.btaa.org/api/v1/thumbnails/placeholder');
  fireEvent.error(image);
  expect(container.querySelector('img')).toBeNull();
  expect(container.querySelector('svg')).not.toBeNull();
});

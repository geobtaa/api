import { render, screen } from '@testing-library/react';

import { StaticResultMap } from '../../../components/search/StaticResultMap';
import type { GeoDocument } from '../../../types/api';

describe('StaticResultMap', () => {
  it('falls back to the geometry static-map endpoint even when geometry is missing', () => {
    const result: GeoDocument = {
      id: 'no-geometry-result',
      type: 'document',
      attributes: {
        ogm: {
          id: 'no-geometry-result',
          dct_title_s: 'No Geometry Result',
        },
      },
      meta: {
        ui: {
          thumbnail_url: null,
          viewer: {
            geometry: null,
          },
        },
      },
    };

    const { container } = render(<StaticResultMap result={result} />);

    const image = container.querySelector(
      'img[src="/static-maps/no-geometry-result/geometry"]'
    );
    expect(image).toHaveAttribute('src', '/static-maps/no-geometry-result/geometry');
    expect(image).toHaveAttribute('alt', '');
    expect(image).not.toHaveStyle({ display: 'none' });
    expect(screen.queryByText('No map data')).not.toBeInTheDocument();
  });
});

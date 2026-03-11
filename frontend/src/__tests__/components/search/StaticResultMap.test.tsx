import { render, screen } from '@testing-library/react';

import { StaticResultMap } from '../../../components/search/StaticResultMap';
import type { GeoDocument } from '../../../types/api';

describe('StaticResultMap', () => {
  it('uses the backend static-map endpoint even when geometry is missing', () => {
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

    const image = container.querySelector('img[src="/resources/no-geometry-result/static-map"]');
    expect(image).toHaveAttribute('src', '/resources/no-geometry-result/static-map');
    expect(image).toHaveAttribute('alt', '');
    expect(screen.queryByText('No map data')).not.toBeInTheDocument();
  });
});

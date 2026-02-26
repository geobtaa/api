import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { ResourceBreadcrumbs } from '../../../components/resource/ResourceBreadcrumbs';
import type { GeoDocument } from '../../../types/api';

const renderWithRouter = (ui: React.ReactElement) =>
  render(<MemoryRouter>{ui}</MemoryRouter>);

const baseItem: GeoDocument = {
  id: 'test-id',
  type: 'document',
  attributes: {
    ogm: {
      id: 'test-id',
      dct_title_s: 'Test Resource',
    },
  },
};

describe('ResourceBreadcrumbs', () => {
  it('returns null when item has no breadcrumb attributes', () => {
    const { container } = renderWithRouter(
      <ResourceBreadcrumbs item={baseItem} />
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders a single breadcrumb when only Resource Class is present', () => {
    const item: GeoDocument = {
      ...baseItem,
      attributes: {
        ...baseItem.attributes,
        ogm: {
          ...baseItem.attributes.ogm,
          gbl_resourceClass_sm: ['Web services'],
        },
      },
    };
    renderWithRouter(<ResourceBreadcrumbs item={item} />);

    const link = screen.getByRole('link', { name: 'Filter by Web services' });
    expect(link).toHaveTextContent('Web services');
    expect(link).toHaveAttribute(
      'href',
      '/search?fq%5Bgbl_resourceClass_sm%5D%5B%5D=Web+services'
    );
  });

  it('renders multiple breadcrumbs in correct order with accumulated facets', () => {
    const item: GeoDocument = {
      ...baseItem,
      attributes: {
        ...baseItem.attributes,
        ogm: {
          ...baseItem.attributes.ogm,
          gbl_resourceClass_sm: ['Web services'],
          gbl_resourceType_sm: ['ArcGIS Feature Layer'],
          dct_spatial_sm: ['Illinois--Chicago'],
          dct_issued_s: '2011-04-17',
        },
      },
    };
    renderWithRouter(<ResourceBreadcrumbs item={item} />);

    expect(screen.getByRole('link', { name: 'Filter by Web services' })).toHaveAttribute(
      'href',
      expect.stringContaining('gbl_resourceClass_sm')
    );
    expect(
      screen.getByRole('link', { name: 'Filter by ArcGIS Feature Layer' })
    ).toHaveAttribute('href', expect.stringContaining('gbl_resourceType_sm'));
    expect(
      screen.getByRole('link', { name: 'Filter by Illinois--Chicago' })
    ).toHaveAttribute('href', expect.stringContaining('dct_spatial_sm'));
    expect(
      screen.getByRole('link', { name: 'Filter by 2011-04-17' })
    ).toHaveAttribute('href', expect.stringContaining('dct_issued_s'));
  });

  it('includes all prior facets in each breadcrumb link URL', () => {
    const item: GeoDocument = {
      ...baseItem,
      attributes: {
        ...baseItem.attributes,
        ogm: {
          ...baseItem.attributes.ogm,
          gbl_resourceClass_sm: ['Maps'],
          dct_spatial_sm: ['Minnesota'],
        },
      },
    };
    renderWithRouter(<ResourceBreadcrumbs item={item} />);

    const spatialLink = screen.getByRole('link', {
      name: 'Filter by Minnesota',
    });
    const href = spatialLink.getAttribute('href') ?? '';
    const params = new URLSearchParams(href.split('?')[1] ?? '');
    expect(params.getAll('fq[gbl_resourceClass_sm][]')).toContain('Maps');
    expect(params.getAll('fq[dct_spatial_sm][]')).toContain('Minnesota');
  });

  it('uses nav with aria-label Breadcrumb', () => {
    const item: GeoDocument = {
      ...baseItem,
      attributes: {
        ...baseItem.attributes,
        ogm: {
          ...baseItem.attributes.ogm,
          gbl_resourceClass_sm: ['Paper Maps'],
        },
      },
    };
    renderWithRouter(<ResourceBreadcrumbs item={item} />);

    const nav = screen.getByRole('navigation', { name: 'Breadcrumb' });
    expect(nav).toBeInTheDocument();
  });

  it('renders links with consistent aria-label for accessibility', () => {
    const item: GeoDocument = {
      ...baseItem,
      attributes: {
        ...baseItem.attributes,
        ogm: {
          ...baseItem.attributes.ogm,
          gbl_resourceClass_sm: ['Web services'],
        },
      },
    };
    renderWithRouter(<ResourceBreadcrumbs item={item} />);

    const link = screen.getByRole('link', { name: 'Filter by Web services' });
    expect(link).toHaveAttribute('aria-label', 'Filter by Web services');
  });
});

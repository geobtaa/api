import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { FullDetailsTable } from '../../../components/resource/FullDetailsTable';

const renderWithRouter = (ui: React.ReactElement) =>
  render(<MemoryRouter>{ui}</MemoryRouter>);

describe('FullDetailsTable', () => {
  const baseData = {
    attributes: {
      ogm: {
        id: 'eee6150b-ce2f-4837-9d17-ce72a0c1c26f',
        dct_title_s: 'Parent Resource',
      },
      b1g: {},
    },
  };

  it('renders "Has part..." label for dct:hasPart relationship', () => {
    const data = {
      ...baseData,
      meta: {
        ui: {
          relationships: {
            'dct:hasPart': [
              { resource_id: 'child-1', resource_title: 'Child 1' },
              { resource_id: 'child-2', resource_title: 'Child 2' },
            ],
          },
        },
      },
    };
    renderWithRouter(<FullDetailsTable data={data} />);
    expect(screen.getByText('Has part...')).toBeInTheDocument();
  });

  it('renders "Collection records..." label for pcdm:hasMember relationship', () => {
    const data = {
      ...baseData,
      meta: {
        ui: {
          relationships: {
            'pcdm:hasMember': [
              { resource_id: 'member-1', resource_title: 'Member 1' },
              { resource_id: 'member-2', resource_title: 'Member 2' },
            ],
          },
        },
      },
    };
    renderWithRouter(<FullDetailsTable data={data} />);
    expect(screen.getByText('Collection records...')).toBeInTheDocument();
  });

  it('Browse all link for dct:hasPart uses include_filters[dct_isPartOf_sm][]', () => {
    const parentId = 'eee6150b-ce2f-4837-9d17-ce72a0c1c26f';
    const data = {
      ...baseData,
      attributes: {
        ...baseData.attributes,
        ogm: { ...baseData.attributes.ogm, id: parentId },
      },
      meta: {
        ui: {
          relationships: {
            'dct:hasPart': Array.from({ length: 6 }, (_, i) => ({
              resource_id: `child-${i}`,
              resource_title: `Child ${i}`,
            })),
          },
        },
      },
    };
    renderWithRouter(<FullDetailsTable data={data} />);
    const browseLink = screen.getByRole('link', {
      name: /Browse all 6 records/,
    });
    expect(browseLink).toHaveAttribute(
      'href',
      expect.stringContaining('include_filters[dct_isPartOf_sm]')
    );
    expect(browseLink.getAttribute('href')).toContain(
      encodeURIComponent(parentId)
    );
  });

  it('Browse all link for pcdm:hasMember uses include_filters[pcdm_memberOf_sm][]', () => {
    const collectionId = 'dc8c18df-7d64-4ff4-a754-d18d0891187d';
    const data = {
      ...baseData,
      attributes: {
        ...baseData.attributes,
        ogm: { ...baseData.attributes.ogm, id: collectionId },
      },
      meta: {
        ui: {
          relationships: {
            'pcdm:hasMember': Array.from({ length: 6 }, (_, i) => ({
              resource_id: `member-${i}`,
              resource_title: `Member ${i}`,
            })),
          },
        },
      },
    };
    renderWithRouter(<FullDetailsTable data={data} />);
    const browseLink = screen.getByRole('link', {
      name: /Browse all 6 records/,
    });
    expect(browseLink).toHaveAttribute(
      'href',
      expect.stringContaining('include_filters[pcdm_memberOf_sm]')
    );
    expect(browseLink.getAttribute('href')).toContain(
      encodeURIComponent(collectionId)
    );
  });

  it('does not show Browse all link when 5 or fewer items', () => {
    const data = {
      ...baseData,
      meta: {
        ui: {
          relationships: {
            'dct:hasPart': [
              { resource_id: 'c1', resource_title: 'Child 1' },
              { resource_id: 'c2', resource_title: 'Child 2' },
            ],
          },
        },
      },
    };
    renderWithRouter(<FullDetailsTable data={data} />);
    expect(screen.getByText('Has part...')).toBeInTheDocument();
    expect(
      screen.queryByRole('link', { name: /Browse all/ })
    ).not.toBeInTheDocument();
  });

  it('renders Publisher as a clickable metadata facet link', () => {
    const data = {
      ...baseData,
      attributes: {
        ...baseData.attributes,
        ogm: {
          ...baseData.attributes.ogm,
          dct_publisher_sm: ['MIT Libraries'],
        },
      },
    };

    renderWithRouter(<FullDetailsTable data={data} />);

    const publisherLink = screen.getByRole('link', {
      name: 'Filter by MIT Libraries',
    });
    expect(publisherLink).toHaveAttribute(
      'href',
      '/search?include_filters[dct_publisher_sm][]=MIT%20Libraries'
    );
  });

  it('metadata facet labels use sequential heading level (h3 under h2)', () => {
    const data = {
      ...baseData,
      attributes: {
        ...baseData.attributes,
        ogm: {
          ...baseData.attributes.ogm,
          dct_publisher_sm: ['MIT Libraries'],
        },
      },
    };

    renderWithRouter(<FullDetailsTable data={data} />);
    const publisherLabel = screen.getByRole('heading', {
      name: 'Publisher',
      level: 3,
    });
    expect(publisherLabel).toBeInTheDocument();
  });

  it('metadata facets sidebar uses light background for sufficient contrast', () => {
    const data = {
      ...baseData,
      attributes: {
        ...baseData.attributes,
        ogm: {
          ...baseData.attributes.ogm,
          dct_publisher_sm: ['MIT Libraries'],
        },
      },
    };

    const { container } = renderWithRouter(<FullDetailsTable data={data} />);
    const sidebar = container.querySelector('.bg-gray-50');
    expect(sidebar).toBeInTheDocument();
  });
});

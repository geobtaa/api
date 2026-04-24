import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { SimilarItemsCarousel } from '../../../components/resource/SimilarItemsCarousel';

describe('SimilarItemsCarousel', () => {
  beforeEach(() => {
    vi.spyOn(console, 'log').mockImplementation(() => {});
    vi.spyOn(console, 'warn').mockImplementation(() => {});
  });

  it('renders nothing when similarItems is empty', () => {
    render(
      <MemoryRouter>
        <SimilarItemsCarousel similarItems={[]} />
      </MemoryRouter>
    );
    expect(screen.queryByText('Similar Items')).not.toBeInTheDocument();
  });

  it('renders nothing when similarItems is undefined', () => {
    render(
      <MemoryRouter>
        <SimilarItemsCarousel />
      </MemoryRouter>
    );
    expect(screen.queryByText('Similar Items')).not.toBeInTheDocument();
  });

  it('renders year and resource class in conjoined pill for flat API shape', () => {
    const items = [
      {
        id: 'similar-1',
        title: 'Map of France',
        gbl_indexYear_im: [1929],
        gbl_resourceClass_sm: ['Maps'],
      },
    ];
    render(
      <MemoryRouter>
        <SimilarItemsCarousel similarItems={items as never} />
      </MemoryRouter>
    );
    expect(screen.getByText('Similar Items')).toBeInTheDocument();
    const pill = screen.getByTestId('result-card-pill');
    expect(pill).toHaveTextContent('1929');
    expect(pill).toHaveTextContent('Maps');
    expect(pill).toHaveClass('bg-[#003c5b]', 'text-white');
  });

  it('renders year and resource class from full GeoDocument attributes.ogm', () => {
    const items = [
      {
        id: 'doc-1',
        attributes: {
          ogm: {
            dct_title_s: 'Historical Map',
            gbl_indexYear_im: [1943],
            gbl_resourceClass_sm: ['Datasets'],
          },
        },
      },
    ];
    render(
      <MemoryRouter>
        <SimilarItemsCarousel similarItems={items as never} />
      </MemoryRouter>
    );
    const pill = screen.getByTestId('result-card-pill');
    expect(pill).toHaveTextContent('1943');
    expect(pill).toHaveTextContent('Datasets');
  });

  it('shows only resource class when index year is missing (no em dash)', () => {
    const items = [
      {
        id: 'no-year',
        title: 'Undated Resource',
        gbl_resourceClass_sm: ['Maps'],
      },
    ];
    render(
      <MemoryRouter>
        <SimilarItemsCarousel similarItems={items as never} />
      </MemoryRouter>
    );
    const pill = screen.getByTestId('result-card-pill');
    expect(pill).toHaveTextContent('Maps');
    expect(pill).not.toHaveTextContent('—');
  });

  it('shows Item when resource class is missing', () => {
    const items = [
      {
        id: 'no-class',
        title: 'Uncategorized',
        gbl_indexYear_im: [2020],
      },
    ];
    render(
      <MemoryRouter>
        <SimilarItemsCarousel similarItems={items as never} />
      </MemoryRouter>
    );
    const pill = screen.getByTestId('result-card-pill');
    expect(pill).toHaveTextContent('2020');
    expect(pill).toHaveTextContent('Item');
  });

  it('renders links to resource detail pages', () => {
    const items = [
      {
        id: 'resource-abc',
        title: 'Test Resource',
        gbl_indexYear_im: [1985],
        gbl_resourceClass_sm: ['Imagery'],
      },
    ];
    render(
      <MemoryRouter>
        <SimilarItemsCarousel similarItems={items as never} />
      </MemoryRouter>
    );
    const link = screen.getByRole('link', { name: /Test Resource/i });
    expect(link).toHaveAttribute('href', '/resources/resource-abc');
  });

  it('pagination dot buttons meet minimum touch target size (44x44px)', () => {
    const items = Array.from({ length: 8 }, (_, i) => ({
      id: `item-${i}`,
      title: `Item ${i}`,
      gbl_indexYear_im: [2020],
      gbl_resourceClass_sm: ['Maps'],
    }));
    render(
      <MemoryRouter>
        <SimilarItemsCarousel similarItems={items as never} />
      </MemoryRouter>
    );
    const pageButtons = screen.getAllByRole('button', { name: /Go to page/ });
    expect(pageButtons.length).toBeGreaterThan(0);
    pageButtons.forEach((btn) => {
      expect(btn).toHaveClass('min-w-[44px]', 'min-h-[44px]');
    });
  });
});

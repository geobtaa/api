import { render, screen } from '@testing-library/react';
import { SanbornFeaturedCollection } from '../../../components/home/SanbornFeaturedCollection';

describe('SanbornFeaturedCollection', () => {
  it('renders all highlighted collections and CTA links', () => {
    render(<SanbornFeaturedCollection />);

    expect(
      screen.getByRole('heading', { name: /sanborn fire insurance maps/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('heading', {
        name: /big ten academic alliance libraries historical maps collection/i,
      })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: /urban base layers collection/i })
    ).toBeInTheDocument();
    const collectionRecordLinks = screen.getAllByRole('link', {
      name: /view collection record/i,
    });
    expect(collectionRecordLinks).toHaveLength(3);
    expect(collectionRecordLinks[0]).toHaveAttribute(
      'href',
      '/resources/b35f927e-9051-4d7f-9ca3-ad5b19024e0b'
    );
    expect(
      screen.getByRole('link', { name: /browse 15,000\+ maps/i })
    ).toHaveAttribute(
      'href',
      '/search?include_filters[pcdm_memberOf_sm][]=b35f927e-9051-4d7f-9ca3-ad5b19024e0b&view=gallery&per_page=20'
    );
    expect(
      screen.getByRole('link', { name: /browse historical maps/i })
    ).toHaveAttribute(
      'href',
      '/search?include_filters[pcdm_memberOf_sm][]=64bd8c4c-8e60-4956-b43d-bdc3f93db4883&view=gallery&per_page=20'
    );
    expect(
      screen.getByRole('link', { name: /browse urban base layers/i })
    ).toHaveAttribute(
      'href',
      '/search?include_filters[pcdm_memberOf_sm][]=b1g_urbanBaseLayers&view=gallery&per_page=20'
    );
  });
});

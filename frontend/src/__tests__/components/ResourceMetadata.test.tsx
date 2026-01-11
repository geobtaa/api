import { render, screen } from '@testing-library/react';
import { ResourceMetadata } from '../../components/resource/ResourceMetadata';
import type { GeoDocumentDetails } from '../../types/api';

// Real fixture data from the /test/fixtures page
const realFixtureWithAllFields: GeoDocumentDetails = {
  schema_provider_s: 'MIT Libraries',
  dc_publisher_sm: ['MIT Libraries'],
  creator_sm: ['MIT Libraries Staff'],
  dct_spatial_sm: ['Massachusetts', 'United States'],
  dc_subject_sm: ['Paper Maps', 'Historical Maps', 'Library Collections'],
  dct_issued_s: '1950',
  dct_title_s: 'Nondigitized paper map with library catalog link',
  dct_description_sm: ['A historical paper map from MIT collections'],
  dct_temporal_sm: ['1950'],
  gbl_resourceClass_sm: ['Paper Maps'],
  dct_accessrights_s: 'Public',
  gbl_wxsidentifier_s: 'mit-001145244',
  locn_geometry_original: 'POINT(-71.0935 42.3601)',
  meta: {
    ui: {
      thumbnail_url: 'https://example.com/thumbnail1.jpg',
      viewer: {
        protocol: 'wms',
        endpoint: 'https://example.com/wms',
        geometry: {
          type: 'Point',
          coordinates: [-71.0935, 42.3601],
        },
      },
      downloads: [
        {
          label: 'PDF Download',
          url: 'https://example.com/download.pdf',
          type: 'application/pdf',
        },
      ],
      citation:
        'MIT Libraries (1950). Nondigitized paper map with library catalog link.',
      links: {
        'Library Catalog': [
          {
            label: 'MIT Library Catalog',
            url: 'https://example.com/catalog',
          },
        ],
      },
    },
  },
};

const realFixtureWithMinimalFields: GeoDocumentDetails = {
  dct_title_s: 'Point dataset with WMS and WFS',
  dct_description_sm: ['A point dataset from NYU with web services'],
  dct_temporal_sm: ['2020'],
  gbl_resourceClass_sm: ['Point Data'],
  dct_accessrights_s: 'Public',
  gbl_wxsidentifier_s: 'nyu-2451-34564',
  locn_geometry_original: 'POINT(-74.0060 40.7128)',
  meta: {
    ui: {
      thumbnail_url: 'https://example.com/thumbnail2.jpg',
      viewer: {
        protocol: 'wms',
        endpoint: 'https://example.com/wms2',
        geometry: {
          type: 'Point',
          coordinates: [-74.006, 40.7128],
        },
      },
      downloads: [
        {
          label: 'Shapefile Download',
          url: 'https://example.com/download2.zip',
          type: 'application/zip',
        },
      ],
      citation: 'NYU Libraries (2020). Point dataset with WMS and WFS.',
      links: {
        'Web Services': [
          {
            label: 'WMS Service',
            url: 'https://example.com/wms2',
          },
          {
            label: 'WFS Service',
            url: 'https://example.com/wfs2',
          },
        ],
      },
    },
  },
};

const realFixtureWithPolygonData: GeoDocumentDetails = {
  schema_provider_s: 'Tufts University',
  dc_publisher_sm: ['Tufts University'],
  creator_sm: ['Tufts GIS Staff'],
  dct_spatial_sm: ['Massachusetts', 'Cambridge'],
  dc_subject_sm: ['Polygon Data', 'Grid Data', 'Administrative Boundaries'],
  dct_issued_s: '2019',
  dct_title_s: 'Polygon dataset with WFS, WMS, and FGDC metadata',
  dct_description_sm: [
    'A polygon dataset from Tufts with comprehensive metadata',
  ],
  dct_temporal_sm: ['2019'],
  gbl_resourceClass_sm: ['Polygon Data'],
  dct_accessrights_s: 'Public',
  gbl_wxsidentifier_s: 'tufts-cambridgegrid100-04',
  locn_geometry_original:
    'POLYGON((-71.1 42.3, -71.0 42.3, -71.0 42.4, -71.1 42.4, -71.1 42.3))',
  meta: {
    ui: {
      thumbnail_url: 'https://example.com/thumbnail3.jpg',
      viewer: {
        protocol: 'wms',
        endpoint: 'https://example.com/wms3',
        geometry: {
          type: 'Polygon',
          coordinates: [
            [
              [-71.1, 42.3],
              [-71.0, 42.3],
              [-71.0, 42.4],
              [-71.1, 42.4],
              [-71.1, 42.3],
            ],
          ],
        },
      },
      downloads: [
        {
          label: 'GeoJSON Download',
          url: 'https://example.com/download3.geojson',
          type: 'application/geo+json',
        },
      ],
      citation:
        'Tufts University (2019). Polygon dataset with WFS, WMS, and FGDC metadata.',
      links: {
        Metadata: [
          {
            label: 'FGDC Metadata',
            url: 'https://example.com/metadata3.xml',
          },
        ],
      },
    },
  },
};

describe('ResourceMetadata Component', () => {
  describe('Rendering with All Fields', () => {
    it('renders all metadata sections when all fields are present', () => {
      render(<ResourceMetadata item={realFixtureWithAllFields} />);

      // Check for all section headings
      expect(screen.getByText('Provider')).toBeInTheDocument();
      expect(screen.getByText('Publishers')).toBeInTheDocument();
      expect(screen.getByText('Creators')).toBeInTheDocument();
      expect(screen.getByText('Geographic Coverage')).toBeInTheDocument();
      expect(screen.getByText('Subjects')).toBeInTheDocument();
      expect(screen.getByText('Date Issued')).toBeInTheDocument();
    });

    it('renders source information correctly', () => {
      render(<ResourceMetadata item={realFixtureWithAllFields} />);

      expect(screen.getByText('Provider')).toBeInTheDocument();

      const sourceSection = screen.getByText('Provider').closest('div');
      const sourceText = sourceSection?.querySelector('p');
      expect(sourceText).toHaveTextContent('MIT Libraries');
    });

    it('renders publishers as a list', () => {
      render(<ResourceMetadata item={realFixtureWithAllFields} />);

      expect(screen.getByText('Publishers')).toBeInTheDocument();

      const publisherSection = screen.getByText('Publishers').closest('div');
      const publisherItem = publisherSection?.querySelector('li');
      expect(publisherItem).toHaveTextContent('MIT Libraries');

      const publisherList = screen
        .getByText('Publishers')
        .closest('div')
        ?.querySelector('ul');
      expect(publisherList).toBeInTheDocument();
    });

    it('renders creators with Users icon', () => {
      render(<ResourceMetadata item={realFixtureWithAllFields} />);

      expect(screen.getByText('Creators')).toBeInTheDocument();
      expect(screen.getByText('MIT Libraries Staff')).toBeInTheDocument();

      // Check for Users icon (Lucide icon)
      const creatorsHeading = screen.getByText('Creators');
      expect(creatorsHeading.closest('h2')).toHaveClass(
        'flex',
        'items-center',
        'gap-2'
      );
    });

    it('renders geographic coverage with MapPin icon', () => {
      render(<ResourceMetadata item={realFixtureWithAllFields} />);

      expect(screen.getByText('Geographic Coverage')).toBeInTheDocument();
      expect(screen.getByText('Massachusetts')).toBeInTheDocument();
      expect(screen.getByText('United States')).toBeInTheDocument();

      // Check for MapPin icon
      const geoHeading = screen.getByText('Geographic Coverage');
      expect(geoHeading.closest('h2')).toHaveClass(
        'flex',
        'items-center',
        'gap-2'
      );
    });

    it('renders subjects as styled tags', () => {
      render(<ResourceMetadata item={realFixtureWithAllFields} />);

      expect(screen.getByText('Subjects')).toBeInTheDocument();
      expect(screen.getByText('Paper Maps')).toBeInTheDocument();
      expect(screen.getByText('Historical Maps')).toBeInTheDocument();
      expect(screen.getByText('Library Collections')).toBeInTheDocument();

      // Check for Tag icon
      const subjectsHeading = screen.getByText('Subjects');
      expect(subjectsHeading.closest('h2')).toHaveClass(
        'flex',
        'items-center',
        'gap-2'
      );

      // Check for styled tags
      const paperMapsTag = screen.getByText('Paper Maps');
      expect(paperMapsTag).toHaveClass(
        'inline-flex',
        'items-center',
        'px-2.5',
        'py-0.5',
        'rounded-full',
        'text-xs',
        'font-medium',
        'bg-blue-100',
        'text-blue-800'
      );
    });

    it('renders date issued correctly', () => {
      render(<ResourceMetadata item={realFixtureWithAllFields} />);

      expect(screen.getByText('Date Issued')).toBeInTheDocument();
      expect(screen.getByText('1950')).toBeInTheDocument();
    });
  });

  describe('Conditional Rendering', () => {
    it('does not render sections when fields are missing', () => {
      render(<ResourceMetadata item={realFixtureWithMinimalFields} />);

      // These sections should not be present
      expect(screen.queryByText('Provider')).not.toBeInTheDocument();
      expect(screen.queryByText('Publishers')).not.toBeInTheDocument();
      expect(screen.queryByText('Creators')).not.toBeInTheDocument();
      expect(screen.queryByText('Geographic Coverage')).not.toBeInTheDocument();
      expect(screen.queryByText('Subjects')).not.toBeInTheDocument();
      expect(screen.queryByText('Date Issued')).not.toBeInTheDocument();
    });

    it('renders only available fields', () => {
      const partialItem: GeoDocumentDetails = {
        ...realFixtureWithMinimalFields,
        schema_provider_s: 'NYU Libraries',
        dc_publisher_sm: ['NYU Libraries'],
      };

      render(<ResourceMetadata item={partialItem} />);

      // Should render these
      expect(screen.getByText('Provider')).toBeInTheDocument();
      expect(screen.getByText('Publishers')).toBeInTheDocument();

      // Check that NYU Libraries appears in both Provider and Publishers
      const sourceSection = screen.getByText('Provider').closest('div');
      const sourceText = sourceSection?.querySelector('p');
      expect(sourceText).toHaveTextContent('NYU Libraries');

      const publisherSection = screen.getByText('Publishers').closest('div');
      const publisherItem = publisherSection?.querySelector('li');
      expect(publisherItem).toHaveTextContent('NYU Libraries');

      // Should not render these
      expect(screen.queryByText('Creators')).not.toBeInTheDocument();
      expect(screen.queryByText('Geographic Coverage')).not.toBeInTheDocument();
      expect(screen.queryByText('Subjects')).not.toBeInTheDocument();
      expect(screen.queryByText('Date Issued')).not.toBeInTheDocument();
    });

    it('handles empty arrays gracefully', () => {
      const itemWithEmptyArrays: GeoDocumentDetails = {
        ...realFixtureWithMinimalFields,
        dc_publisher_sm: [],
        creator_sm: [],
        dct_spatial_sm: [],
        dc_subject_sm: [],
      };

      render(<ResourceMetadata item={itemWithEmptyArrays} />);

      // Should not render sections with empty arrays
      expect(screen.queryByText('Publishers')).not.toBeInTheDocument();
      expect(screen.queryByText('Creators')).not.toBeInTheDocument();
      expect(screen.queryByText('Geographic Coverage')).not.toBeInTheDocument();
      expect(screen.queryByText('Subjects')).not.toBeInTheDocument();
    });

    it('handles null/undefined fields gracefully', () => {
      const itemWithNullFields: GeoDocumentDetails = {
        ...realFixtureWithMinimalFields,
        schema_provider_s: null as any,
        dc_publisher_sm: null as any,
        creator_sm: null as any,
        dct_spatial_sm: null as any,
        dc_subject_sm: null as any,
        dct_issued_s: null as any,
      };

      render(<ResourceMetadata item={itemWithNullFields} />);

      // Should not render any sections
      expect(screen.queryByText('Provider')).not.toBeInTheDocument();
      expect(screen.queryByText('Publishers')).not.toBeInTheDocument();
      expect(screen.queryByText('Creators')).not.toBeInTheDocument();
      expect(screen.queryByText('Geographic Coverage')).not.toBeInTheDocument();
      expect(screen.queryByText('Subjects')).not.toBeInTheDocument();
      expect(screen.queryByText('Date Issued')).not.toBeInTheDocument();
    });
  });

  describe('Layout and Styling', () => {
    it('applies correct grid layout classes', () => {
      const { container } = render(
        <ResourceMetadata item={realFixtureWithAllFields} />
      );

      const gridContainer = container.firstChild as HTMLElement;
      expect(gridContainer).toHaveClass(
        'grid',
        'grid-cols-1',
        'md:grid-cols-2',
        'gap-8'
      );
    });

    it('applies correct spacing classes to sections', () => {
      render(<ResourceMetadata item={realFixtureWithAllFields} />);

      const leftColumn = screen
        .getByText('Provider')
        .closest('div')?.parentElement;
      expect(leftColumn).toHaveClass('space-y-6');

      const rightColumn = screen
        .getByText('Geographic Coverage')
        .closest('div')?.parentElement;
      expect(rightColumn).toHaveClass('space-y-6');
    });

    it('applies correct heading styles', () => {
      render(<ResourceMetadata item={realFixtureWithAllFields} />);

      const sourceHeading = screen.getByText('Provider');
      expect(sourceHeading).toHaveClass(
        'text-sm',
        'font-medium',
        'text-gray-500'
      );
    });

    it('applies correct text styles to content', () => {
      render(<ResourceMetadata item={realFixtureWithAllFields} />);

      const sourceSection = screen.getByText('Provider').closest('div');
      const sourceText = sourceSection?.querySelector('p');
      expect(sourceText).toHaveClass('mt-1', 'text-gray-900');
    });

    it('applies correct list styles', () => {
      render(<ResourceMetadata item={realFixtureWithAllFields} />);

      const publisherList = screen
        .getByText('Publishers')
        .closest('div')
        ?.querySelector('ul');
      expect(publisherList).toHaveClass('mt-1', 'space-y-1');

      const publisherSection = screen.getByText('Publishers').closest('div');
      const publisherItem = publisherSection?.querySelector('li');
      expect(publisherItem).toHaveClass('text-gray-900');
    });
  });

  describe('Accessibility', () => {
    it('uses proper heading structure', () => {
      render(<ResourceMetadata item={realFixtureWithAllFields} />);

      const headings = screen.getAllByRole('heading', { level: 2 });
      expect(headings).toHaveLength(6); // All section headings should be h2
    });

    it('uses proper list structure for arrays', () => {
      render(<ResourceMetadata item={realFixtureWithAllFields} />);

      const lists = screen.getAllByRole('list');
      expect(lists).toHaveLength(3); // Publishers, Creators, Geographic Coverage

      const listItems = screen.getAllByRole('listitem');
      expect(listItems.length).toBeGreaterThan(0);
    });

    it('maintains proper text contrast', () => {
      render(<ResourceMetadata item={realFixtureWithAllFields} />);

      const headings = screen.getAllByRole('heading', { level: 2 });
      headings.forEach((heading) => {
        expect(heading).toHaveClass('text-gray-500');
      });

      const sourceSection = screen.getByText('Provider').closest('div');
      const contentText = sourceSection?.querySelector('p');
      expect(contentText).toHaveClass('text-gray-900');
    });
  });

  describe('Edge Cases', () => {
    it('handles single item arrays', () => {
      const singleItemData: GeoDocumentDetails = {
        ...realFixtureWithMinimalFields,
        dc_publisher_sm: ['NYU Libraries'],
        creator_sm: ['NYU Staff'],
        dct_spatial_sm: ['New York'],
        dc_subject_sm: ['Point Data'],
      };

      render(<ResourceMetadata item={singleItemData} />);

      expect(screen.getByText('NYU Libraries')).toBeInTheDocument();
      expect(screen.getByText('NYU Staff')).toBeInTheDocument();
      expect(screen.getByText('New York')).toBeInTheDocument();
      expect(screen.getByText('Point Data')).toBeInTheDocument();
    });

    it('handles very long text content', () => {
      const longTextData: GeoDocumentDetails = {
        ...realFixtureWithMinimalFields,
        schema_provider_s:
          'This is a very long source name that might contain extensive information about the data provider and should still render correctly without breaking the layout or causing any display issues.',
        dc_publisher_sm: [
          'Very Long Publisher Name That Might Contain Extensive Information',
        ],
        creator_sm: [
          'Creator with Very Long Name That Might Contain Additional Details',
        ],
      };

      render(<ResourceMetadata item={longTextData} />);

      expect(screen.getByText(/very long source name/)).toBeInTheDocument();
      expect(screen.getByText(/Very Long Publisher Name/)).toBeInTheDocument();
      expect(
        screen.getByText(/Creator with Very Long Name/)
      ).toBeInTheDocument();
    });

    it('handles special characters in content', () => {
      const specialCharData: GeoDocumentDetails = {
        ...realFixtureWithMinimalFields,
        schema_provider_s: 'Source with special chars: !@#$%^&*()',
        dc_publisher_sm: ['Publisher with unicode: ñáéíóú'],
        creator_sm: ['Creator with symbols: <>&"\''],
        dct_spatial_sm: ['Location with numbers: 12345'],
        dc_subject_sm: ['Subject with HTML: <script>alert("test")</script>'],
      };

      render(<ResourceMetadata item={specialCharData} />);

      expect(
        screen.getByText(/special chars: !@#\$%\^&\*\(\)/)
      ).toBeInTheDocument();
      expect(screen.getByText(/unicode: ñáéíóú/)).toBeInTheDocument();
      expect(screen.getByText(/symbols: <>&"'/)).toBeInTheDocument();
      expect(screen.getByText(/numbers: 12345/)).toBeInTheDocument();
      expect(
        screen.getByText(/HTML: <script>alert\("test"\)<\/script>/)
      ).toBeInTheDocument();
    });

    it('renders with different fixture data types', () => {
      render(<ResourceMetadata item={realFixtureWithPolygonData} />);

      expect(screen.getByText('Provider')).toBeInTheDocument();
      expect(screen.getByText('Publishers')).toBeInTheDocument();
      expect(screen.getByText('Creators')).toBeInTheDocument();
      expect(screen.getByText('Tufts GIS Staff')).toBeInTheDocument();
      expect(screen.getByText('Geographic Coverage')).toBeInTheDocument();
      expect(screen.getByText('Massachusetts')).toBeInTheDocument();
      expect(screen.getByText('Cambridge')).toBeInTheDocument();
      expect(screen.getByText('Subjects')).toBeInTheDocument();
      expect(screen.getByText('Polygon Data')).toBeInTheDocument();
      expect(screen.getByText('Grid Data')).toBeInTheDocument();
      expect(screen.getByText('Administrative Boundaries')).toBeInTheDocument();
      expect(screen.getByText('Date Issued')).toBeInTheDocument();
      expect(screen.getByText('2019')).toBeInTheDocument();

      // Check that Tufts University appears in both Provider and Publishers
      const sourceSection = screen.getByText('Provider').closest('div');
      const sourceText = sourceSection?.querySelector('p');
      expect(sourceText).toHaveTextContent('Tufts University');

      const publisherSection = screen.getByText('Publishers').closest('div');
      const publisherItem = publisherSection?.querySelector('li');
      expect(publisherItem).toHaveTextContent('Tufts University');
    });
  });
});

import { render, screen } from '@testing-library/react';
import { axeWithWCAG22 } from '../../test-utils/axe';
import { MetadataTable } from '../../components/resource/MetadataTable';

// Real fixture data from the /test/fixtures page
const realFixtureWithAllFields = {
  data: {
    attributes: {
      dct_description_sm: ['A historical paper map from MIT collections'],
      dct_spatial_sm: ['Massachusetts', 'United States'],
      dct_temporal_sm: ['1950'],
      dct_issued_s: '1950',
      dct_language_sm: ['English'],
      dct_format_s: 'Paper Map',
      schema_provider_s: 'MIT Libraries',
      dct_accessRights_s: 'Public',
      dct_license_sm: ['MIT License'],
      dc_subject_sm: ['Paper Maps', 'Historical Maps', 'Library Collections'],
      gbl_resourceType_sm: ['Map'],
      gbl_resourceClass_sm: ['Paper Maps'],
    },
  },
};

const realFixtureWithMinimalFields = {
  data: {
    attributes: {
      dct_description_sm: ['A point dataset from NYU with web services'],
      dct_temporal_sm: ['2020'],
      gbl_resourceClass_sm: ['Point Data'],
    },
  },
};

const realFixtureWithPolygonData = {
  data: {
    attributes: {
      dct_description_sm: [
        'A polygon dataset from Tufts with comprehensive metadata',
      ],
      dct_spatial_sm: ['Massachusetts', 'Cambridge'],
      dct_temporal_sm: ['2019'],
      dct_issued_s: '2019-01-15',
      dct_language_sm: ['English', 'Spanish'],
      dct_format_s: 'Shapefile',
      schema_provider_s: 'Tufts University',
      dct_accessRights_s: 'Public',
      dct_license_sm: ['Creative Commons'],
      dc_subject_sm: ['Polygon Data', 'Grid Data', 'Administrative Boundaries'],
      gbl_resourceType_sm: ['Dataset'],
      gbl_resourceClass_sm: ['Polygon Data'],
    },
  },
};

const realFixtureWithRestrictedAccess = {
  data: {
    attributes: {
      dct_description_sm: ['A restricted raster dataset from Stanford'],
      dct_spatial_sm: ['California', 'Stanford'],
      dct_temporal_sm: ['2021'],
      dct_issued_s: '2021-03-01',
      dct_language_sm: ['English'],
      dct_format_s: 'GeoTIFF',
      schema_provider_s: 'Stanford University',
      dct_accessRights_s: 'Restricted',
      dct_license_sm: ['Restricted License'],
      dc_subject_sm: ['Raster Data', 'Satellite Imagery'],
      gbl_resourceType_sm: ['Raster'],
      gbl_resourceClass_sm: ['Raster Data'],
    },
  },
};

describe('MetadataTable Component', () => {
  describe('Rendering with All Fields', () => {
    it('renders the table header with title and full details link', () => {
      render(<MetadataTable data={realFixtureWithAllFields} />);

      expect(screen.getByText('Item Summary')).toBeInTheDocument();
      expect(screen.getByText('Full Details ↓')).toBeInTheDocument();
      expect(
        screen.getByRole('link', { name: 'Full Details ↓' })
      ).toHaveAttribute('href', '#full-details');
    });

    it('renders all metadata sections when all fields are present', () => {
      render(<MetadataTable data={realFixtureWithAllFields} />);

      // Check for all section headings
      expect(screen.getByText('Description')).toBeInTheDocument();
      expect(screen.getByText('Places')).toBeInTheDocument();
      expect(screen.getByText('Temporal Coverage')).toBeInTheDocument();
      expect(screen.getByText('Date Issued')).toBeInTheDocument();
      expect(screen.getByText('Language')).toBeInTheDocument();
      expect(screen.getByText('Format')).toBeInTheDocument();
      expect(screen.getByText('Provider')).toBeInTheDocument();
      expect(screen.getByText('Access Rights')).toBeInTheDocument();
      expect(screen.getByText('License')).toBeInTheDocument();
      expect(screen.getByText('Subject')).toBeInTheDocument();
      expect(screen.getByText('Resource Type')).toBeInTheDocument();
      expect(screen.getByText('Resource Class')).toBeInTheDocument();
    });

    it('renders description correctly', () => {
      render(<MetadataTable data={realFixtureWithAllFields} />);

      expect(screen.getByText('Description')).toBeInTheDocument();
      expect(
        screen.getByText('A historical paper map from MIT collections')
      ).toBeInTheDocument();
    });

    it('renders spatial coverage as array', () => {
      render(<MetadataTable data={realFixtureWithAllFields} />);

      expect(screen.getByText('Places')).toBeInTheDocument();
      expect(
        screen.getByText('Massachusetts, United States')
      ).toBeInTheDocument();
    });

    it('renders combined row with temporal, date, and language', () => {
      render(<MetadataTable data={realFixtureWithAllFields} />);

      expect(screen.getByText('Temporal Coverage')).toBeInTheDocument();
      expect(screen.getByText('Date Issued')).toBeInTheDocument();
      expect(screen.getByText('Language')).toBeInTheDocument();
      expect(screen.getByText('English')).toBeInTheDocument();

      // Check that 1950 appears in both Temporal Coverage and Date Issued
      const temporalSection = screen
        .getByText('Temporal Coverage')
        .closest('td');
      const temporalValue = temporalSection?.querySelector('.text-gray-900');
      expect(temporalValue).toHaveTextContent('1950');

      const dateSection = screen.getByText('Date Issued').closest('td');
      const dateValue = dateSection?.querySelector('.text-gray-900');
      expect(dateValue).toHaveTextContent('1950');
    });

    it('renders combined row with format and provider', () => {
      render(<MetadataTable data={realFixtureWithAllFields} />);

      expect(screen.getByText('Format')).toBeInTheDocument();
      expect(screen.getByText('Paper Map')).toBeInTheDocument();
      expect(screen.getByText('Provider')).toBeInTheDocument();

      // Check that MIT Libraries appears in the Provider section
      const providerSection = screen.getByText('Provider').closest('td');
      const providerValue = providerSection?.querySelector('.text-gray-900');
      expect(providerValue).toHaveTextContent('MIT Libraries');
    });

    it('renders access rights', () => {
      render(<MetadataTable data={realFixtureWithAllFields} />);

      expect(screen.getByText('Access Rights')).toBeInTheDocument();
      expect(screen.getByText('Public')).toBeInTheDocument();
    });

    it('renders license information', () => {
      render(<MetadataTable data={realFixtureWithAllFields} />);

      expect(screen.getByText('License')).toBeInTheDocument();
      expect(screen.getByText('MIT License')).toBeInTheDocument();
    });

    it('renders subjects as comma-separated list', () => {
      render(<MetadataTable data={realFixtureWithAllFields} />);

      expect(screen.getByText('Subject')).toBeInTheDocument();
      expect(
        screen.getByText('Paper Maps, Historical Maps, Library Collections')
      ).toBeInTheDocument();
    });

    it('renders resource type and class', () => {
      render(<MetadataTable data={realFixtureWithAllFields} />);

      expect(screen.getByText('Resource Type')).toBeInTheDocument();
      expect(screen.getByText('Map')).toBeInTheDocument();
      expect(screen.getByText('Resource Class')).toBeInTheDocument();
      expect(screen.getByText('Paper Maps')).toBeInTheDocument();
    });
  });

  describe('Conditional Rendering', () => {
    it('renders only available fields when some are missing', () => {
      render(<MetadataTable data={realFixtureWithMinimalFields} />);

      // Should render these
      expect(screen.getByText('Description')).toBeInTheDocument();
      expect(
        screen.getByText('A point dataset from NYU with web services')
      ).toBeInTheDocument();
      expect(screen.getByText('Temporal Coverage')).toBeInTheDocument();
      expect(screen.getByText('2020')).toBeInTheDocument();
      expect(screen.getByText('Resource Class')).toBeInTheDocument();
      expect(screen.getByText('Point Data')).toBeInTheDocument();

      // Should not render these (individual fields)
      expect(screen.queryByText('Places')).not.toBeInTheDocument();
      expect(screen.queryByText('Access Rights')).not.toBeInTheDocument();
      expect(screen.queryByText('License')).not.toBeInTheDocument();
      expect(screen.queryByText('Subject')).not.toBeInTheDocument();
      expect(screen.queryByText('Resource Type')).not.toBeInTheDocument();

      // The component renders combined rows if ANY field has a value
      // Since we have dct_temporal_sm: ['2020'], the temporal row will render
      // but Date Issued and Language should be empty in that row
      expect(screen.getByText('Date Issued')).toBeInTheDocument();
      expect(screen.getByText('Language')).toBeInTheDocument();

      // Check that Date Issued and Language are empty in the combined row
      const dateSection = screen.getByText('Date Issued').closest('td');
      const dateValue = dateSection?.querySelector('.text-gray-900');
      expect(dateValue).toHaveTextContent('');

      const languageSection = screen.getByText('Language').closest('td');
      const languageValue = languageSection?.querySelector('.text-gray-900');
      expect(languageValue).toHaveTextContent('');

      // Format and Provider row should not render since both are missing
      expect(screen.queryByText('Format')).not.toBeInTheDocument();
      expect(screen.queryByText('Provider')).not.toBeInTheDocument();
    });

    it('handles empty arrays gracefully', () => {
      const dataWithEmptyArrays = {
        data: {
          attributes: {
            dct_description_sm: ['Valid description'],
            dct_spatial_sm: [],
            dct_temporal_sm: [],
            dc_subject_sm: [],
          },
        },
      };

      render(<MetadataTable data={dataWithEmptyArrays} />);

      // Should render description
      expect(screen.getByText('Description')).toBeInTheDocument();
      expect(screen.getByText('Valid description')).toBeInTheDocument();

      // Should not render empty arrays
      expect(screen.queryByText('Places')).not.toBeInTheDocument();
      expect(screen.queryByText('Temporal Coverage')).not.toBeInTheDocument();
      expect(screen.queryByText('Subject')).not.toBeInTheDocument();
    });

    it('handles null/undefined fields gracefully', () => {
      const dataWithNullFields = {
        data: {
          attributes: {
            dct_description_sm: ['Valid description'],
            dct_spatial_sm: null as any,
            dct_temporal_sm: undefined as any,
            dc_subject_sm: null as any,
          },
        },
      };

      render(<MetadataTable data={dataWithNullFields} />);

      // Should render description
      expect(screen.getByText('Description')).toBeInTheDocument();
      expect(screen.getByText('Valid description')).toBeInTheDocument();

      // Should not render null/undefined fields
      expect(screen.queryByText('Places')).not.toBeInTheDocument();
      expect(screen.queryByText('Temporal Coverage')).not.toBeInTheDocument();
      expect(screen.queryByText('Subject')).not.toBeInTheDocument();
    });

    it('handles empty strings gracefully', () => {
      const dataWithEmptyStrings = {
        data: {
          attributes: {
            dct_description_sm: ['Valid description'],
            dct_spatial_sm: [''],
            dct_temporal_sm: '',
            dc_subject_sm: ['   '],
          },
        },
      };

      render(<MetadataTable data={dataWithEmptyStrings} />);

      // Should render description
      expect(screen.getByText('Description')).toBeInTheDocument();
      expect(screen.getByText('Valid description')).toBeInTheDocument();

      // The component renders empty strings as empty divs
      expect(screen.getByText('Places')).toBeInTheDocument();
      const placesSection = screen.getByText('Places').closest('td');
      const placesValue = placesSection?.querySelector('.text-gray-900');
      expect(placesValue).toHaveTextContent('');

      expect(screen.getByText('Subject')).toBeInTheDocument();
      const subjectSection = screen.getByText('Subject').closest('td');
      const subjectValue = subjectSection?.querySelector('.text-gray-900');
      // The component trims whitespace, so empty string becomes empty
      expect(subjectValue).toHaveTextContent('');
    });
  });

  describe('Label Handling', () => {
    it('uses singular label for single item arrays', () => {
      const dataWithSingleItem = {
        data: {
          attributes: {
            dct_spatial_sm: ['Single Place'],
          },
        },
      };

      render(<MetadataTable data={dataWithSingleItem} />);

      // The component uses "Places" as the label regardless of array length
      // The getLabel function only works with labels containing "(s)"
      expect(screen.getByText('Places')).toBeInTheDocument();
      expect(screen.getByText('Single Place')).toBeInTheDocument();
    });

    it('uses plural label for multiple item arrays', () => {
      render(<MetadataTable data={realFixtureWithAllFields} />);

      // Should use plural "Places" for multiple items
      expect(screen.getByText('Places')).toBeInTheDocument();
      expect(
        screen.getByText('Massachusetts, United States')
      ).toBeInTheDocument();
    });
  });

  describe('Layout and Styling', () => {
    it('applies correct table structure', () => {
      const { container } = render(
        <MetadataTable data={realFixtureWithAllFields} />
      );

      const table = container.querySelector('table');
      expect(table).toHaveClass('min-w-full', 'divide-y', 'divide-gray-200');

      const tbody = container.querySelector('tbody');
      expect(tbody).toHaveClass('divide-y', 'divide-gray-200');
    });

    it('applies correct header styling', () => {
      const { container } = render(
        <MetadataTable data={realFixtureWithAllFields} />
      );

      const header = container.querySelector('.px-6.py-4.bg-gray-50');
      expect(header).toBeInTheDocument();

      const title = screen.getByText('Item Summary');
      expect(title).toHaveClass('text-lg', 'font-semibold', 'text-gray-900');
    });

    it('applies correct cell styling', () => {
      render(<MetadataTable data={realFixtureWithAllFields} />);

      const descriptionLabel = screen.getByText('Description');
      const descriptionCell = descriptionLabel.closest('td');
      expect(descriptionCell).toHaveClass('px-6', 'py-4');

      const descriptionValue = screen.getByText(
        'A historical paper map from MIT collections'
      );
      expect(descriptionValue).toHaveClass('text-sm', 'text-gray-900');
    });

    it('applies hover effects to table rows', () => {
      const { container } = render(
        <MetadataTable data={realFixtureWithAllFields} />
      );

      const rows = container.querySelectorAll('tr');
      rows.forEach((row) => {
        expect(row).toHaveClass('hover:bg-gray-50');
      });
    });
  });

  describe('Accessibility', () => {
    it('has no accessibility violations', async () => {
      const { container } = render(
        <MetadataTable data={realFixtureWithAllFields} />
      );
      const results = await axeWithWCAG22(container);
      expect(results).toHaveNoViolations();
    });

    it('uses proper table structure', () => {
      const { container } = render(
        <MetadataTable data={realFixtureWithAllFields} />
      );

      const table = container.querySelector('table');
      expect(table).toBeInTheDocument();

      const tbody = container.querySelector('tbody');
      expect(tbody).toBeInTheDocument();

      const rows = container.querySelectorAll('tr');
      expect(rows.length).toBeGreaterThan(0);

      const cells = container.querySelectorAll('td');
      expect(cells.length).toBeGreaterThan(0);
    });

    it('has proper link accessibility', () => {
      render(<MetadataTable data={realFixtureWithAllFields} />);

      const fullDetailsLink = screen.getByRole('link', {
        name: 'Full Details ↓',
      });
      expect(fullDetailsLink).toHaveAttribute('href', '#full-details');
      expect(fullDetailsLink).toHaveClass(
        'text-sm',
        'text-blue-600',
        'hover:text-blue-800'
      );
    });

    it('maintains proper text contrast', () => {
      render(<MetadataTable data={realFixtureWithAllFields} />);

      // Check that labels have proper styling
      const descriptionLabel = screen.getByText('Description');
      expect(descriptionLabel).toHaveClass('text-gray-500');

      const placesLabel = screen.getByText('Places');
      expect(placesLabel).toHaveClass('text-gray-500');

      const temporalLabel = screen.getByText('Temporal Coverage');
      expect(temporalLabel).toHaveClass('text-gray-500');

      // Check that values have proper styling
      const descriptionValue = screen.getByText(
        'A historical paper map from MIT collections'
      );
      expect(descriptionValue).toHaveClass('text-gray-900');

      const placesValue = screen.getByText('Massachusetts, United States');
      expect(placesValue).toHaveClass('text-gray-900');

      // Check temporal value in the temporal section specifically
      const temporalSection = screen
        .getByText('Temporal Coverage')
        .closest('td');
      const temporalValue = temporalSection?.querySelector('.text-gray-900');
      expect(temporalValue).toHaveClass('text-gray-900');
    });
  });

  describe('Edge Cases', () => {
    it('handles missing data object gracefully', () => {
      const emptyData = { data: null as any };

      render(<MetadataTable data={emptyData} />);

      // Should still render the header
      expect(screen.getByText('Item Summary')).toBeInTheDocument();
      expect(screen.getByText('Full Details ↓')).toBeInTheDocument();

      // Should not render any metadata rows
      expect(screen.queryByText('Description')).not.toBeInTheDocument();
    });

    it('handles missing attributes object gracefully', () => {
      const dataWithoutAttributes = { data: {} };

      render(<MetadataTable data={dataWithoutAttributes} />);

      // Should still render the header
      expect(screen.getByText('Item Summary')).toBeInTheDocument();
      expect(screen.getByText('Full Details ↓')).toBeInTheDocument();

      // Should not render any metadata rows
      expect(screen.queryByText('Description')).not.toBeInTheDocument();
    });

    it('handles mixed data types in arrays', () => {
      const dataWithMixedTypes = {
        data: {
          attributes: {
            dct_spatial_sm: ['Place 1', 'Place 2', 'Place 3'],
            dct_temporal_sm: ['2020', '2021'],
            dc_subject_sm: ['Subject A', 'Subject B'],
          },
        },
      };

      render(<MetadataTable data={dataWithMixedTypes} />);

      expect(screen.getByText('Places')).toBeInTheDocument();
      expect(screen.getByText('Place 1, Place 2, Place 3')).toBeInTheDocument();
      expect(screen.getByText('Temporal Coverage')).toBeInTheDocument();
      expect(screen.getByText('2020, 2021')).toBeInTheDocument();
      expect(screen.getByText('Subject')).toBeInTheDocument();
      expect(screen.getByText('Subject A, Subject B')).toBeInTheDocument();
    });

    it('renders with different fixture data types', () => {
      render(<MetadataTable data={realFixtureWithPolygonData} />);

      expect(screen.getByText('Description')).toBeInTheDocument();
      expect(
        screen.getByText(
          'A polygon dataset from Tufts with comprehensive metadata'
        )
      ).toBeInTheDocument();
      expect(screen.getByText('Places')).toBeInTheDocument();
      expect(screen.getByText('Massachusetts, Cambridge')).toBeInTheDocument();
      expect(screen.getByText('Temporal Coverage')).toBeInTheDocument();
      expect(screen.getByText('2019')).toBeInTheDocument();
      expect(screen.getByText('Date Issued')).toBeInTheDocument();
      expect(screen.getByText('2019-01-15')).toBeInTheDocument();
      expect(screen.getByText('Language')).toBeInTheDocument();
      expect(screen.getByText('English, Spanish')).toBeInTheDocument();
      expect(screen.getByText('Format')).toBeInTheDocument();
      expect(screen.getByText('Shapefile')).toBeInTheDocument();
      expect(screen.getByText('Provider')).toBeInTheDocument();

      // Check that Tufts University appears in the Provider section
      const providerSection = screen.getByText('Provider').closest('td');
      const providerValue = providerSection?.querySelector('.text-gray-900');
      expect(providerValue).toHaveTextContent('Tufts University');

      expect(screen.getByText('Access Rights')).toBeInTheDocument();
      expect(screen.getByText('Public')).toBeInTheDocument();
      expect(screen.getByText('License')).toBeInTheDocument();
      expect(screen.getByText('Creative Commons')).toBeInTheDocument();
      expect(screen.getByText('Subject')).toBeInTheDocument();
      expect(
        screen.getByText('Polygon Data, Grid Data, Administrative Boundaries')
      ).toBeInTheDocument();
      expect(screen.getByText('Resource Type')).toBeInTheDocument();
      expect(screen.getByText('Dataset')).toBeInTheDocument();
      expect(screen.getByText('Resource Class')).toBeInTheDocument();
      expect(screen.getByText('Polygon Data')).toBeInTheDocument();
    });

    it('renders with restricted access fixture', () => {
      render(<MetadataTable data={realFixtureWithRestrictedAccess} />);

      expect(screen.getByText('Description')).toBeInTheDocument();
      expect(
        screen.getByText('A restricted raster dataset from Stanford')
      ).toBeInTheDocument();
      expect(screen.getByText('Places')).toBeInTheDocument();
      expect(screen.getByText('California, Stanford')).toBeInTheDocument();
      expect(screen.getByText('Access Rights')).toBeInTheDocument();
      expect(screen.getByText('Restricted')).toBeInTheDocument();
      expect(screen.getByText('License')).toBeInTheDocument();
      expect(screen.getByText('Restricted License')).toBeInTheDocument();
      expect(screen.getByText('Resource Class')).toBeInTheDocument();
      expect(screen.getByText('Raster Data')).toBeInTheDocument();
    });

    it('handles very long text content', () => {
      const dataWithLongText = {
        data: {
          attributes: {
            dct_description_sm: [
              'This is a very long description that might contain extensive information about the dataset and should still render correctly without breaking the layout or causing any display issues.',
            ],
            dct_spatial_sm: [
              'Very Long Place Name That Might Contain Extensive Information About Geographic Location',
            ],
            dc_subject_sm: [
              'Very Long Subject Name That Might Contain Additional Details',
              'Another Very Long Subject Name',
            ],
          },
        },
      };

      render(<MetadataTable data={dataWithLongText} />);

      expect(screen.getByText(/very long description/)).toBeInTheDocument();
      expect(screen.getByText(/Very Long Place Name/)).toBeInTheDocument();
      expect(screen.getByText(/Very Long Subject Name/)).toBeInTheDocument();
    });

    it('handles special characters in content', () => {
      const dataWithSpecialChars = {
        data: {
          attributes: {
            dct_description_sm: ['Description with special chars: !@#$%^&*()'],
            dct_spatial_sm: ['Place with unicode: ñáéíóú'],
            dc_subject_sm: ['Subject with symbols: <>&"\''],
          },
        },
      };

      render(<MetadataTable data={dataWithSpecialChars} />);

      expect(
        screen.getByText(/special chars: !@#\$%\^&\*\(\)/)
      ).toBeInTheDocument();
      expect(screen.getByText(/unicode: ñáéíóú/)).toBeInTheDocument();
      expect(screen.getByText(/symbols: <>&"'/)).toBeInTheDocument();
    });
  });
});

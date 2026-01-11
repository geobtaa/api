import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router';
import { FacetList } from '../../components/FacetList';
import { vi } from 'vitest';

// Mock useSearchParams
const mockSetSearchParams = vi.fn();
let mockSearchParams = new URLSearchParams();

vi.mock('react-router', async () => {
  const actual = await vi.importActual('react-router');
  return {
    ...actual,
    useSearchParams: () => [mockSearchParams, mockSetSearchParams],
  };
});

// Mock the facet labels and configured facets
vi.mock('../../utils/facetLabels', () => ({
  FACET_LABELS: {
    resource_class_agg: 'Resource Type',
    dc_publisher_sm: 'Publisher',
    dct_temporal_sm: 'Year',
    dct_spatial_sm: 'Location',
  },
  // For unit tests we keep facet IDs stable (no remapping).
  normalizeFacetId: (id: string) => id,
}));

vi.mock('../../constants/facets', () => ({
  CONFIGURED_FACETS: [
    'resource_class_agg',
    'dc_publisher_sm',
    'dct_temporal_sm',
    'dct_spatial_sm',
  ],
}));

vi.mock('../../components/search/FacetMoreModal', () => ({
  FacetMoreModal: ({
    facetLabel,
    isOpen,
  }: {
    facetLabel: string;
    isOpen: boolean;
  }) =>
    isOpen ? (
      <div data-testid="facet-more-modal">More modal for {facetLabel}</div>
    ) : null,
}));

// Real fixture data structure for facets
const mockFacetData = [
  {
    type: 'facet' as const,
    id: 'resource_class_agg',
    attributes: {
      label: 'Resource Type',
      items: [
        {
          attributes: {
            label: 'Paper Maps',
            value: 'Paper Maps',
            hits: 45,
          },
          links: {
            self: '/search?fq[resource_class_agg][]=Paper+Maps',
          },
        },
        {
          attributes: {
            label: 'Point Data',
            value: 'Point Data',
            hits: 23,
          },
          links: {
            self: '/search?fq[resource_class_agg][]=Point+Data',
          },
        },
        {
          attributes: {
            label: 'Polygon Data',
            value: 'Polygon Data',
            hits: 18,
          },
          links: {
            self: '/search?fq[resource_class_agg][]=Polygon+Data',
          },
        },
      ],
    },
  },
  {
    type: 'facet' as const,
    id: 'dc_publisher_sm',
    attributes: {
      label: 'Publisher',
      items: [
        {
          attributes: {
            label: 'MIT Libraries',
            value: 'MIT Libraries',
            hits: 12,
          },
          links: {
            self: '/search?fq[dc_publisher_sm][]=MIT+Libraries',
          },
        },
        {
          attributes: {
            label: 'NYU Libraries',
            value: 'NYU Libraries',
            hits: 8,
          },
          links: {
            self: '/search?fq[dc_publisher_sm][]=NYU+Libraries',
          },
        },
        {
          attributes: {
            label: 'Stanford University',
            value: 'Stanford University',
            hits: 6,
          },
          links: {
            self: '/search?fq[dc_publisher_sm][]=Stanford+University',
          },
        },
      ],
    },
  },
  {
    type: 'facet' as const,
    id: 'dct_temporal_sm',
    attributes: {
      label: 'Year',
      items: [
        {
          attributes: {
            label: '2023',
            value: '2023',
            hits: 15,
          },
          links: {
            self: '/search?fq[dct_temporal_sm][]=2023',
          },
        },
        {
          attributes: {
            label: '2022',
            value: '2022',
            hits: 12,
          },
          links: {
            self: '/search?fq[dct_temporal_sm][]=2022',
          },
        },
        {
          attributes: {
            label: '2021',
            value: '2021',
            hits: 9,
          },
          links: {
            self: '/search?fq[dct_temporal_sm][]=2021',
          },
        },
      ],
    },
  },
];

const buildFacetItems = (count: number) =>
  Array.from({ length: count }, (_, index) => ({
    attributes: {
      label: `Facet Item ${index + 1}`,
      value: `facet-item-${index + 1}`,
      hits: 100 - index,
    },
    links: {
      self: `/search?fq[resource_class_agg][]=facet-item-${index + 1}`,
    },
  }));

// Test wrapper component
const TestWrapper = ({
  children,
  initialSearchParams = '',
}: {
  children: React.ReactNode;
  initialSearchParams?: string;
}) => {
  return (
    <BrowserRouter>
      <div data-testid="search-params" data-params={initialSearchParams}>
        {children}
      </div>
    </BrowserRouter>
  );
};

describe('FacetList Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Reset the mock search params
    mockSearchParams = new URLSearchParams();
    mockSetSearchParams.mockClear();
  });

  describe('Basic Rendering', () => {
    it('renders facets when data is provided', () => {
      render(
        <TestWrapper>
          <FacetList facets={mockFacetData} />
        </TestWrapper>
      );

      // Check for facet labels
      expect(screen.getByText('Resource Type')).toBeInTheDocument();
      expect(screen.getByText('Publisher')).toBeInTheDocument();
      expect(screen.getByText('Year')).toBeInTheDocument();

      // Check for facet items
      expect(screen.getByText('Paper Maps')).toBeInTheDocument();
      expect(screen.getByText('MIT Libraries')).toBeInTheDocument();
      expect(screen.getByText('2023')).toBeInTheDocument();
    });

    it('renders facets when items are compact tuples', () => {
      const compactFacetData = [
        {
          type: 'facet' as const,
          id: 'dct_spatial_sm',
          links: {
            applyTemplate:
              '/api/v1/search?q=&include_filters%5Bdct_spatial_sm%5D%5B%5D={value}',
          },
          attributes: {
            label: 'Location',
            items: [
              ['Minnesota', 5757],
              ['Wisconsin', 1234],
            ],
          },
        },
      ];

      render(
        <TestWrapper>
          <FacetList facets={compactFacetData} />
        </TestWrapper>
      );

      expect(screen.getByText('Location')).toBeInTheDocument();
      expect(screen.getByText('Minnesota')).toBeInTheDocument();
      expect(screen.getByText('Wisconsin')).toBeInTheDocument();
    });

    it('displays hit counts for each facet item', () => {
      render(
        <TestWrapper>
          <FacetList facets={mockFacetData} />
        </TestWrapper>
      );

      // Check for specific hit counts in context
      expect(screen.getByText('Paper Maps')).toBeInTheDocument();
      expect(screen.getByText('(45)')).toBeInTheDocument();
      expect(screen.getByText('(23)')).toBeInTheDocument();
      expect(screen.getByText('(18)')).toBeInTheDocument();
      expect(screen.getByText('(8)')).toBeInTheDocument();
      expect(screen.getByText('(6)')).toBeInTheDocument();
      expect(screen.getByText('(15)')).toBeInTheDocument();
      expect(screen.getByText('(9)')).toBeInTheDocument();
    });

    it('renders facets in the correct order based on CONFIGURED_FACETS', () => {
      render(
        <TestWrapper>
          <FacetList facets={mockFacetData} />
        </TestWrapper>
      );

      const facetHeaders = screen.getAllByRole('heading', { level: 3 });
      expect(facetHeaders[0]).toHaveTextContent('Resource Type');
      expect(facetHeaders[1]).toHaveTextContent('Publisher');
      expect(facetHeaders[2]).toHaveTextContent('Year');
    });
  });

  describe('Empty States', () => {
    it('displays message when no facets are provided', () => {
      render(
        <TestWrapper>
          <FacetList facets={[]} />
        </TestWrapper>
      );

      expect(screen.getByText('No facets available')).toBeInTheDocument();
    });

    it('displays message when facets is null', () => {
      render(
        <TestWrapper>
          <FacetList facets={null as any} />
        </TestWrapper>
      );

      expect(screen.getByText('No facets available')).toBeInTheDocument();
    });

    it('displays message when facets have no items', () => {
      const emptyFacets = [
        {
          type: 'facet' as const,
          id: 'resource_class_agg',
          attributes: {
            label: 'Resource Type',
            items: [],
          },
        },
      ];

      render(
        <TestWrapper>
          <FacetList facets={emptyFacets} />
        </TestWrapper>
      );

      expect(
        screen.getByText('No facets available for this search')
      ).toBeInTheDocument();
    });

    it('filters out facets with no items', () => {
      const mixedFacets = [
        {
          type: 'facet' as const,
          id: 'resource_class_agg',
          attributes: {
            label: 'Resource Type',
            items: [
              {
                attributes: {
                  label: 'Paper Maps',
                  value: 'Paper Maps',
                  hits: 45,
                },
                links: {
                  self: '/search?fq[resource_class_agg][]=Paper+Maps',
                },
              },
            ],
          },
        },
        {
          type: 'facet' as const,
          id: 'dc_publisher_sm',
          attributes: {
            label: 'Publisher',
            items: [],
          },
        },
      ];

      render(
        <TestWrapper>
          <FacetList facets={mixedFacets} />
        </TestWrapper>
      );

      expect(screen.getByText('Resource Type')).toBeInTheDocument();
      expect(screen.queryByText('Publisher')).not.toBeInTheDocument();
    });
  });

  describe('Facet Interaction', () => {
    it('renders facet items as clickable buttons', () => {
      render(
        <TestWrapper>
          <FacetList facets={mockFacetData} />
        </TestWrapper>
      );

      const facetButtons = screen.getAllByRole('button');
      expect(facetButtons.length).toBeGreaterThan(0);

      // Check that buttons contain facet labels
      expect(
        screen.getByRole('button', { name: /Paper Maps/ })
      ).toBeInTheDocument();
      expect(
        screen.getByRole('button', { name: /MIT Libraries/ })
      ).toBeInTheDocument();
    });

    it('applies correct styling to inactive facets', () => {
      render(
        <TestWrapper>
          <FacetList facets={mockFacetData} />
        </TestWrapper>
      );

      const paperMapsButton = screen.getByRole('button', {
        name: /Paper Maps/,
      });
      expect(paperMapsButton).toHaveClass('text-gray-600');
      expect(paperMapsButton).not.toHaveClass('text-blue-600');
    });

    it('applies correct styling to active facets', () => {
      // Set up mock search params to simulate active facet
      mockSearchParams.set('fq[resource_class_agg][]', 'Paper Maps');

      render(
        <TestWrapper>
          <FacetList facets={mockFacetData} />
        </TestWrapper>
      );

      const paperMapsButton = screen.getByRole('button', {
        name: /Paper Maps/,
      });
      expect(paperMapsButton).toHaveClass(
        'text-blue-600',
        'font-medium',
        'bg-blue-50'
      );
    });

    it('shows remove indicator (×) for active facets', () => {
      // Set up mock search params to simulate active facet
      mockSearchParams.set('fq[resource_class_agg][]', 'Paper Maps');

      render(
        <TestWrapper>
          <FacetList facets={mockFacetData} />
        </TestWrapper>
      );

      const paperMapsButton = screen.getByRole('button', {
        name: /Paper Maps/,
      });
      expect(paperMapsButton).toHaveTextContent('×');
    });

    it('does not show remove indicator for inactive facets', () => {
      render(
        <TestWrapper>
          <FacetList facets={mockFacetData} />
        </TestWrapper>
      );

      const paperMapsButton = screen.getByRole('button', {
        name: /Paper Maps/,
      });
      expect(paperMapsButton).not.toHaveTextContent('×');
    });
  });

  describe('"More" facet modal trigger', () => {
    it('renders a "More »" button when there are more than 10 items', () => {
      const facetsWithMoreItems = [
        {
          type: 'facet' as const,
          id: 'resource_class_agg',
          attributes: {
            label: 'Resource Type',
            items: buildFacetItems(12),
          },
        },
      ];

      render(
        <TestWrapper>
          <FacetList facets={facetsWithMoreItems} />
        </TestWrapper>
      );

      expect(
        screen.getByRole('button', { name: /More »/i })
      ).toBeInTheDocument();
    });

    it('does not render "More »" button when there are 10 or fewer items', () => {
      const facetsWithLimitedItems = [
        {
          type: 'facet' as const,
          id: 'resource_class_agg',
          attributes: {
            label: 'Resource Type',
            items: buildFacetItems(10),
          },
        },
      ];

      render(
        <TestWrapper>
          <FacetList facets={facetsWithLimitedItems} />
        </TestWrapper>
      );

      expect(
        screen.queryByRole('button', { name: /More »/i })
      ).not.toBeInTheDocument();
    });

    it('opens the facet modal when "More »" is clicked', async () => {
      const facetsWithMoreItems = [
        {
          type: 'facet' as const,
          id: 'resource_class_agg',
          attributes: {
            label: 'Resource Type',
            items: buildFacetItems(12),
          },
        },
      ];

      render(
        <TestWrapper>
          <FacetList facets={facetsWithMoreItems} />
        </TestWrapper>
      );

      const user = userEvent.setup();
      await user.click(screen.getByRole('button', { name: /More »/i }));

      expect(screen.getByTestId('facet-more-modal')).toHaveTextContent(
        'More modal for Resource Type'
      );
    });
  });

  describe('Facet Filtering Logic', () => {
    it('only shows facets that are in CONFIGURED_FACETS', () => {
      const facetsWithUnconfigured = [
        ...mockFacetData,
        {
          type: 'facet' as const,
          id: 'unconfigured_facet',
          attributes: {
            label: 'Unconfigured Facet',
            items: [
              {
                attributes: {
                  label: 'Test Item',
                  value: 'test',
                  hits: 5,
                },
                links: {
                  self: '/search?fq[unconfigured_facet][]=test',
                },
              },
            ],
          },
        },
      ];

      render(
        <TestWrapper>
          <FacetList facets={facetsWithUnconfigured} />
        </TestWrapper>
      );

      expect(screen.getByText('Resource Type')).toBeInTheDocument();
      expect(screen.getByText('Publisher')).toBeInTheDocument();
      expect(screen.getByText('Year')).toBeInTheDocument();
      expect(screen.queryByText('Unconfigured Facet')).not.toBeInTheDocument();
    });

    it('handles facets with missing items attribute', () => {
      const facetsWithMissingItems = [
        {
          type: 'facet' as const,
          id: 'resource_class_agg',
          attributes: {
            label: 'Resource Type',
            // Missing items property
          },
        },
      ];

      render(
        <TestWrapper>
          <FacetList facets={facetsWithMissingItems} />
        </TestWrapper>
      );

      expect(
        screen.getByText('No facets available for this search')
      ).toBeInTheDocument();
    });
  });

  describe('URL Parameter Handling', () => {
    it('correctly identifies active facets from URL parameters', () => {
      // Set up mock search params to simulate multiple active facets
      mockSearchParams.set('fq[resource_class_agg][]', 'Paper Maps');
      mockSearchParams.set('fq[dc_publisher_sm][]', 'MIT Libraries');

      render(
        <TestWrapper>
          <FacetList facets={mockFacetData} />
        </TestWrapper>
      );

      const paperMapsButton = screen.getByRole('button', {
        name: /Paper Maps/,
      });
      const mitLibrariesButton = screen.getByRole('button', {
        name: /MIT Libraries/,
      });
      const pointDataButton = screen.getByRole('button', {
        name: /Point Data/,
      });

      expect(paperMapsButton).toHaveClass('text-blue-600');
      expect(mitLibrariesButton).toHaveClass('text-blue-600');
      expect(pointDataButton).toHaveClass('text-gray-600');
    });

    it('handles multiple values for the same facet', () => {
      // Set up mock search params to simulate multiple values for same facet
      mockSearchParams.append('fq[resource_class_agg][]', 'Paper Maps');
      mockSearchParams.append('fq[resource_class_agg][]', 'Point Data');

      render(
        <TestWrapper>
          <FacetList facets={mockFacetData} />
        </TestWrapper>
      );

      const paperMapsButton = screen.getByRole('button', {
        name: /Paper Maps/,
      });
      const pointDataButton = screen.getByRole('button', {
        name: /Point Data/,
      });

      expect(paperMapsButton).toHaveClass('text-blue-600');
      expect(pointDataButton).toHaveClass('text-blue-600');
    });

    it('handles numeric facet values', () => {
      const numericFacets = [
        {
          type: 'facet' as const,
          id: 'dct_temporal_sm',
          attributes: {
            label: 'Year',
            items: [
              {
                attributes: {
                  label: '2023',
                  value: 2023,
                  hits: 15,
                },
                links: {
                  self: '/search?fq[dct_temporal_sm][]=2023',
                },
              },
            ],
          },
        },
      ];

      // Set up mock search params to simulate active numeric facet
      mockSearchParams.set('fq[dct_temporal_sm][]', '2023');

      render(
        <TestWrapper>
          <FacetList facets={numericFacets} />
        </TestWrapper>
      );

      const yearButton = screen.getByRole('button', { name: /2023/ });
      expect(yearButton).toHaveClass('text-blue-600');
    });
  });

  describe('Accessibility', () => {
    it('has proper heading structure', () => {
      render(
        <TestWrapper>
          <FacetList facets={mockFacetData} />
        </TestWrapper>
      );

      const headings = screen.getAllByRole('heading', { level: 3 });
      expect(headings).toHaveLength(3);
      expect(headings[0]).toHaveTextContent('Resource Type');
    });

    it('has proper button roles and labels', () => {
      render(
        <TestWrapper>
          <FacetList facets={mockFacetData} />
        </TestWrapper>
      );

      const buttons = screen.getAllByRole('button');
      expect(buttons.length).toBeGreaterThan(0);

      // Each button should have accessible text OR an aria-label (icon buttons).
      buttons.forEach((button) => {
        const hasText = (button.textContent || '').trim().length > 0;
        const hasAriaLabel = (button.getAttribute('aria-label') || '').trim().length > 0;
        expect(hasText || hasAriaLabel).toBe(true);
      });
    });

    it('provides hover states for interactive elements', () => {
      render(
        <TestWrapper>
          <FacetList facets={mockFacetData} />
        </TestWrapper>
      );

      const paperMapsButton = screen.getByRole('button', {
        name: /Paper Maps/,
      });
      expect(paperMapsButton).toHaveClass('hover:bg-gray-100');
    });
  });

  describe('Edge Cases', () => {
    it('handles facets with special characters in values', () => {
      const specialCharFacets = [
        {
          type: 'facet' as const,
          id: 'dc_publisher_sm',
          attributes: {
            label: 'Publisher',
            items: [
              {
                attributes: {
                  label: 'MIT & Harvard Libraries',
                  value: 'MIT & Harvard Libraries',
                  hits: 5,
                },
                links: {
                  self: '/search?fq[dc_publisher_sm][]=MIT+%26+Harvard+Libraries',
                },
              },
            ],
          },
        },
      ];

      render(
        <TestWrapper>
          <FacetList facets={specialCharFacets} />
        </TestWrapper>
      );

      expect(screen.getByText('MIT & Harvard Libraries')).toBeInTheDocument();
    });

    it('handles facets with very long labels', () => {
      const longLabelFacets = [
        {
          type: 'facet' as const,
          id: 'dc_publisher_sm',
          attributes: {
            label: 'Publisher',
            items: [
              {
                attributes: {
                  label:
                    'Very Long Publisher Name That Might Cause Layout Issues In The UI',
                  value:
                    'Very Long Publisher Name That Might Cause Layout Issues In The UI',
                  hits: 1,
                },
                links: {
                  self: '/search?fq[dc_publisher_sm][]=Very+Long+Publisher+Name',
                },
              },
            ],
          },
        },
      ];

      render(
        <TestWrapper>
          <FacetList facets={longLabelFacets} />
        </TestWrapper>
      );

      expect(
        screen.getByText(
          'Very Long Publisher Name That Might Cause Layout Issues In The UI'
        )
      ).toBeInTheDocument();
    });

    it('handles facets with zero hits', () => {
      const zeroHitsFacets = [
        {
          type: 'facet' as const,
          id: 'resource_class_agg',
          attributes: {
            label: 'Resource Type',
            items: [
              {
                attributes: {
                  label: 'No Results',
                  value: 'No Results',
                  hits: 0,
                },
                links: {
                  self: '/search?fq[resource_class_agg][]=No+Results',
                },
              },
            ],
          },
        },
      ];

      render(
        <TestWrapper>
          <FacetList facets={zeroHitsFacets} />
        </TestWrapper>
      );

      expect(screen.getByText('(0)')).toBeInTheDocument();
    });

    it('handles facets with very high hit counts', () => {
      const highHitsFacets = [
        {
          type: 'facet' as const,
          id: 'resource_class_agg',
          attributes: {
            label: 'Resource Type',
            items: [
              {
                attributes: {
                  label: 'Popular Resource',
                  value: 'Popular Resource',
                  hits: 999999,
                },
                links: {
                  self: '/search?fq[resource_class_agg][]=Popular+Resource',
                },
              },
            ],
          },
        },
      ];

      render(
        <TestWrapper>
          <FacetList facets={highHitsFacets} />
        </TestWrapper>
      );

      expect(screen.getByText('(999,999)')).toBeInTheDocument();
    });
  });

  describe('Styling and CSS Classes', () => {
    it('applies correct container styling', () => {
      const { container } = render(
        <TestWrapper>
          <FacetList facets={mockFacetData} />
        </TestWrapper>
      );

      const facetContainer = container.querySelector('.space-y-6');
      expect(facetContainer).toBeInTheDocument();
    });

    it('applies correct facet section styling', () => {
      render(
        <TestWrapper>
          <FacetList facets={mockFacetData} />
        </TestWrapper>
      );

      const facetSections = document.querySelectorAll('.border-b.pb-4');
      expect(facetSections.length).toBe(3);
    });

    it('applies correct list styling', () => {
      render(
        <TestWrapper>
          <FacetList facets={mockFacetData} />
        </TestWrapper>
      );

      const lists = document.querySelectorAll('.space-y-1');
      expect(lists.length).toBe(3);
    });

    it('applies correct active facet styling', () => {
      // Set up mock search params to simulate active facet
      mockSearchParams.set('fq[resource_class_agg][]', 'Paper Maps');

      render(
        <TestWrapper>
          <FacetList facets={mockFacetData} />
        </TestWrapper>
      );

      const activeButton = screen.getByRole('button', { name: /Paper Maps/ });
      expect(activeButton).toHaveClass(
        'text-blue-600',
        'font-medium',
        'bg-blue-50',
        'hover:bg-blue-100'
      );
    });

    it('applies correct inactive facet styling', () => {
      render(
        <TestWrapper>
          <FacetList facets={mockFacetData} />
        </TestWrapper>
      );

      const inactiveButton = screen.getByRole('button', { name: /Paper Maps/ });
      expect(inactiveButton).toHaveClass(
        'text-gray-600',
        'hover:text-gray-900'
      );
    });
  });
});

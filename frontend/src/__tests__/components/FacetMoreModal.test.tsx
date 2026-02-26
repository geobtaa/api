import { render, screen, fireEvent, within } from '@testing-library/react';
import { axeWithWCAG22 } from '../../test-utils/axe';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import { FacetMoreModal } from '../../components/search/FacetMoreModal';
import { MemoryRouter } from 'react-router';

const mockSetPage = vi.fn();
const mockSetSort = vi.fn();
const mockSetFacetQuery = vi.fn();
const mockResetFacetQuery = vi.fn();
const mockToggleFacetInclude = vi.fn();
const mockToggleFacetExclude = vi.fn();

vi.mock('../../hooks/useFacetModal', () => ({
  useFacetModal: vi.fn(),
}));

import { useFacetModal } from '../../hooks/useFacetModal';

describe('FacetMoreModal', () => {
  const defaultProps = {
    facetId: 'resource_class_agg',
    facetLabel: 'Resource Type',
    isOpen: true,
    onClose: vi.fn(),
    searchParams: new URLSearchParams(),
    onToggleInclude: vi.fn(),
    onToggleExclude: vi.fn(),
    onToggleFacetInclude: mockToggleFacetInclude,
    onToggleFacetExclude: mockToggleFacetExclude,
    isValueIncluded: vi.fn(() => false),
    isValueExcluded: vi.fn(() => false),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mockSetPage.mockReset();
    mockSetSort.mockReset();
    mockSetFacetQuery.mockReset();
    mockResetFacetQuery.mockReset();
    mockToggleFacetInclude.mockReset();
    mockToggleFacetExclude.mockReset();
    defaultProps.onToggleInclude.mockReset();
    defaultProps.onToggleExclude.mockReset();
    defaultProps.onClose.mockReset();
    const mockUseFacetModal = vi.mocked(useFacetModal);
    mockUseFacetModal.mockReturnValue({
      items: [
        {
          type: 'facet_value' as const,
          id: 'alpha',
          attributes: {
            label: 'Alpha',
            value: 'alpha',
            hits: 42,
          },
        },
        {
          type: 'facet_value' as const,
          id: 'beta',
          attributes: {
            value: 'beta',
            hits: 21,
          },
        },
      ],
      meta: {
        totalCount: 2,
        totalPages: 1,
        currentPage: 1,
        perPage: 10,
      },
      isLoading: false,
      hasLoaded: true,
      error: null,
      page: 1,
      perPage: 10,
      sort: 'count_desc' as const,
      qFacet: '',
      setPage: mockSetPage,
      setPerPage: vi.fn(),
      setSort: mockSetSort,
      setFacetQuery: mockSetFacetQuery,
      resetFacetQuery: mockResetFacetQuery,
      refetch: vi.fn(),
    });
  });

  const renderWithRouter = (ui: React.ReactElement) =>
    render(<MemoryRouter>{ui}</MemoryRouter>);

  it('has no accessibility violations when open', async () => {
    const { container } = renderWithRouter(<FacetMoreModal {...defaultProps} />);
    const results = await axeWithWCAG22(container);
    expect(results).toHaveNoViolations();
  });

  it('does not render when closed', () => {
    renderWithRouter(<FacetMoreModal {...defaultProps} isOpen={false} />);
    expect(screen.queryByText(/More options for/)).not.toBeInTheDocument();
  });

  it('renders facet values when open', () => {
    renderWithRouter(<FacetMoreModal {...defaultProps} />);
    expect(
      screen.getByRole('heading', { name: /More options for Resource Type/i })
    ).toBeInTheDocument();
    expect(screen.getByText('Alpha')).toBeInTheDocument();
    // Second value has no label; should fall back to rendering the value
    expect(screen.getByText('beta')).toBeInTheDocument();
  });

  it('does not treat the hits/count as the label', () => {
    vi.mocked(useFacetModal).mockReturnValueOnce({
      items: [
        {
          type: 'facet_value' as const,
          id: 'Subject Term',
          attributes: {
            // BUGGY SHAPE we want to guard against: label accidentally equals hits
            label: '12',
            value: 'Subject Term',
            hits: 12,
          },
        },
      ],
      meta: {
        totalCount: 1,
        totalPages: 1,
        currentPage: 1,
        perPage: 10,
      },
      page: 1,
      perPage: 10,
      sort: 'count_desc' as const,
      qFacet: '',
      isLoading: false,
      hasLoaded: true,
      error: null,
      setPage: mockSetPage,
      setPerPage: vi.fn(),
      setSort: mockSetSort,
      setFacetQuery: mockSetFacetQuery,
      resetFacetQuery: mockResetFacetQuery,
      refetch: vi.fn(),
    });

    renderWithRouter(<FacetMoreModal {...defaultProps} />);
    expect(screen.getByText('Subject Term')).toBeInTheDocument();
    expect(screen.queryByText(/^12$/)).not.toBeInTheDocument();
  });

  it('invokes include and exclude callbacks', async () => {
    const user = userEvent.setup();
    renderWithRouter(<FacetMoreModal {...defaultProps} />);

    const alphaRow = screen.getByText('Alpha').closest('li');
    expect(alphaRow).not.toBeNull();

    await user.click(
      within(alphaRow as HTMLElement).getByRole('button', { name: /Include/ })
    );
    expect(defaultProps.onToggleInclude).toHaveBeenCalledWith('alpha');

    await user.click(
      within(alphaRow as HTMLElement).getByRole('button', { name: /Exclude/ })
    );
    expect(defaultProps.onToggleExclude).toHaveBeenCalledWith('alpha');
  });

  it('changes sort order when selection changes', async () => {
    const user = userEvent.setup();
    renderWithRouter(<FacetMoreModal {...defaultProps} />);

    await user.selectOptions(
      screen.getByDisplayValue('Result Count (High → Low)'),
      'alpha_asc'
    );
    expect(mockSetSort).toHaveBeenCalledWith('alpha_asc');
  });

  it('submits facet search query', async () => {
    const user = userEvent.setup();
    renderWithRouter(<FacetMoreModal {...defaultProps} />);

    await user.type(
      screen.getByPlaceholderText('Search within facet values'),
      'roads'
    );
    await user.click(screen.getByRole('button', { name: /Filter/i }));

    expect(mockSetFacetQuery).toHaveBeenCalledWith('roads');
  });

  it('resets facet search query', async () => {
    const user = userEvent.setup();
    renderWithRouter(<FacetMoreModal {...defaultProps} />);

    await user.click(screen.getByRole('button', { name: /Reset/i }));
    expect(mockResetFacetQuery).toHaveBeenCalled();
  });

  it('navigates between pages', async () => {
    vi.mocked(useFacetModal).mockReturnValueOnce({
      items: [
        {
          type: 'facet_value' as const,
          id: 'alpha',
          attributes: {
            label: 'Alpha',
            value: 'alpha',
            hits: 42,
          },
        },
      ],
      meta: {
        totalCount: 30,
        totalPages: 3,
        currentPage: 1,
        perPage: 10,
      },
      page: 1,
      perPage: 10,
      sort: 'count_desc' as const,
      qFacet: '',
      isLoading: false,
      hasLoaded: true,
      error: null,
      setPage: mockSetPage,
      setPerPage: vi.fn(),
      setSort: mockSetSort,
      setFacetQuery: mockSetFacetQuery,
      resetFacetQuery: mockResetFacetQuery,
      refetch: vi.fn(),
    });

    const user = userEvent.setup();
    renderWithRouter(<FacetMoreModal {...defaultProps} />);

    await user.click(screen.getByRole('button', { name: /Next/i }));
    expect(mockSetPage).toHaveBeenCalledWith(2);
  });

  it('closes when Escape key is pressed', () => {
    renderWithRouter(<FacetMoreModal {...defaultProps} />);

    fireEvent.keyDown(document, { key: 'Escape' });
    expect(defaultProps.onClose).toHaveBeenCalled();
  });

  it('closes when clicking on the overlay background', () => {
    renderWithRouter(<FacetMoreModal {...defaultProps} />);

    fireEvent.mouseDown(screen.getByTestId('facet-modal-overlay'));
    expect(defaultProps.onClose).toHaveBeenCalled();
  });

  it('displays current search context chips', () => {
    const props = {
      ...defaultProps,
      searchParams: new URLSearchParams(
        'q=lakes&include_filters[resource_class_agg][]=Maps&exclude_filters[dct_spatial_sm][]=Illinois'
      ),
    };

    renderWithRouter(<FacetMoreModal {...props} />);

    expect(screen.getByText(/Current search context/i)).toBeInTheDocument();
    expect(screen.getByText(/Search:/)).toBeInTheDocument();
    expect(screen.getByText(/Maps/)).toBeInTheDocument();
    expect(screen.getByText(/Illinois/)).toBeInTheDocument();
  });

  it('displays geo bbox and year range as consolidated badges matching SearchConstraints', () => {
    const props = {
      ...defaultProps,
      searchParams: new URLSearchParams(
        'include_filters[geo][type]=bbox' +
          '&include_filters[geo][field]=dcat_bbox' +
          '&include_filters[geo][top_left][lat]=41.83&include_filters[geo][top_left][lon]=-80.51' +
          '&include_filters[geo][bottom_right][lat]=37.90&include_filters[geo][bottom_right][lon]=-71.15' +
          '&include_filters[gbl_resourceClass_sm][]=Maps' +
          '&include_filters[year_range][start]=1900&include_filters[year_range][end]=1949'
      ),
    };

    renderWithRouter(<FacetMoreModal {...props} />);

    // BBox: N E S W format (matches SearchConstraints)
    expect(
      screen.getByText(/BBox: 41\.83°N -71\.15°E 37\.90°S -80\.51°W/)
    ).toBeInTheDocument();
    // Resource Class
    expect(screen.getByText(/Resource Class:/)).toBeInTheDocument();
    expect(screen.getByText(/Maps/)).toBeInTheDocument();
    // Year range consolidated
    expect(screen.getByText(/Year Range: 1900 - 1949/)).toBeInTheDocument();
  });

  it('allows toggling include/exclude filters via context chips', async () => {
    const user = userEvent.setup();
    const props = {
      ...defaultProps,
      searchParams: new URLSearchParams(
        'include_filters[gbl_resourceClass_sm][]=Maps&exclude_filters[dct_spatial_sm][]=Illinois'
      ),
    };

    renderWithRouter(<FacetMoreModal {...props} />);

    await user.click(
      screen.getByRole('button', {
        name: /Remove included filter Maps/i,
      })
    );
    expect(mockToggleFacetInclude).toHaveBeenCalledWith(
      'gbl_resourceClass_sm',
      'Maps'
    );

    await user.click(
      screen.getByRole('button', {
        name: /Remove excluded filter Illinois/i,
      })
    );
    expect(mockToggleFacetExclude).toHaveBeenCalledWith(
      'dct_spatial_sm',
      'Illinois'
    );
  });
});

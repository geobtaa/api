import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import { axeWithWCAG22 } from '../../test-utils/axe';
import { LinksTable } from '../../components/resource/LinksTable';

vi.mock('../../services/analytics', () => ({
  scheduleAnalyticsBatch: vi.fn(),
}));

// Mock fetch for metadata display endpoint
const mockFetch = vi.fn();

describe('LinksTable', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  const mockLinks = {
    'Visit Source': [{ label: 'Original Website', url: 'https://example.com' }],
    'Web Services': [
      { label: 'WMS Service', url: 'https://example.com/wms' },
      { label: 'WFS Service', url: 'https://example.com/wfs' },
    ],
    'Open in ArcGIS': [
      {
        label: 'MapViewer',
        url: 'https://www.arcgis.com/home/webmap/viewer.html?urls=https%3A%2F%2Fexample.com%2Ffeature',
      },
      {
        label: 'REST Service Details',
        url: 'https://example.com/feature',
      },
    ],
    Metadata: [{ label: 'ISO 19115', url: 'https://example.com/metadata.xml' }],
  };

  const mockMetadataLinksWithFormat = {
    Metadata: [
      {
        label: 'ISO 19115 XML',
        url: 'https://example.com/iso.xml',
        format: 'iso' as const,
      },
      {
        label: 'FGDC XML',
        url: 'https://example.com/fgdc.xml',
        format: 'fgdc' as const,
      },
    ],
  };

  it('renders without crashing', () => {
    render(<LinksTable links={mockLinks} />);
    expect(screen.getByText('Links')).toBeInTheDocument();
  });

  it('renders all link categories', () => {
    render(<LinksTable links={mockLinks} />);
    expect(screen.getByText('Visit Source')).toBeInTheDocument();
    expect(screen.getByText('Web Services')).toBeInTheDocument();
    expect(screen.getByText('Open in ArcGIS')).toBeInTheDocument();
    expect(screen.getByText('Metadata')).toBeInTheDocument();
  });

  it('renders with optional resourceId prop', () => {
    render(<LinksTable links={mockLinks} resourceId="test-resource-123" />);
    expect(screen.getByText('Links')).toBeInTheDocument();
  });

  it('opens lightbox for Web Services category', () => {
    render(<LinksTable links={mockLinks} />);
    const webServicesButton = screen.getByRole('button', {
      name: 'Web Services',
    });
    fireEvent.click(webServicesButton);

    expect(screen.getByText('WMS Service')).toBeInTheDocument();
    expect(screen.getByText('WFS Service')).toBeInTheDocument();
  });

  it('closes lightbox when close button is clicked', () => {
    render(<LinksTable links={mockLinks} />);
    const webServicesButton = screen.getByRole('button', {
      name: 'Web Services',
    });
    fireEvent.click(webServicesButton);

    expect(screen.getByText('WMS Service')).toBeInTheDocument();

    const closeButton = screen.getByRole('button', { name: 'Close' });
    fireEvent.click(closeButton);

    expect(screen.queryByText('WMS Service')).not.toBeInTheDocument();
  });

  it('opens lightbox for Open in ArcGIS category', () => {
    render(<LinksTable links={mockLinks} />);
    const openInArcgisButton = screen.getByRole('button', {
      name: 'Open in ArcGIS',
    });
    fireEvent.click(openInArcgisButton);

    expect(screen.getByText('MapViewer')).toBeInTheDocument();
    expect(screen.getByText('REST Service Details')).toBeInTheDocument();
  });

  it('does not render when links are empty', () => {
    const { container } = render(<LinksTable links={{}} />);
    expect(container.firstChild).toBeNull();
  });

  it('does not render when links are null', () => {
    const { container } = render(<LinksTable links={null} />);
    expect(container.firstChild).toBeNull();
  });

  it('has no accessibility violations', async () => {
    const { container } = render(<LinksTable links={mockLinks} />);
    const results = await axeWithWCAG22(container);
    expect(results).toHaveNoViolations();
  });

  describe('Metadata lightbox with transformable formats', () => {
    it('opens Metadata lightbox and fetches transformed content when resourceId and format provided', async () => {
      const originalFetch = global.fetch;
      global.fetch = mockFetch;
      mockFetch.mockResolvedValueOnce({
        ok: true,
        text: () =>
          Promise.resolve('<html><body>Transformed Metadata</body></html>'),
      });

      render(
        <LinksTable
          links={mockMetadataLinksWithFormat}
          resourceId="test-resource-123"
        />
      );

      const metadataButton = screen.getByRole('button', { name: 'Metadata' });
      fireEvent.click(metadataButton);

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalled();
      });

      await waitFor(() => {
        expect(screen.getByTitle('ISO 19115 XML')).toBeInTheDocument();
      });

      global.fetch = originalFetch;
    });

    it('shows Download button when viewing transformed metadata', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        text: () => Promise.resolve('<html><body>Transformed</body></html>'),
      });

      render(
        <LinksTable
          links={mockMetadataLinksWithFormat}
          resourceId="test-resource-123"
        />
      );

      fireEvent.click(screen.getByRole('button', { name: 'Metadata' }));

      await waitFor(() => {
        expect(
          screen.getByRole('link', { name: /Download/i })
        ).toBeInTheDocument();
      });
    });

    it('shows format tabs when multiple transformable formats', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        text: () => Promise.resolve('<html><body>ISO Content</body></html>'),
      });

      render(
        <LinksTable
          links={mockMetadataLinksWithFormat}
          resourceId="test-resource-123"
        />
      );

      fireEvent.click(screen.getByRole('button', { name: 'Metadata' }));

      await waitFor(() => {
        expect(
          screen.getByRole('tab', { name: 'ISO 19115' })
        ).toBeInTheDocument();
        expect(screen.getByRole('tab', { name: 'FGDC' })).toBeInTheDocument();
      });
    });
  });
});

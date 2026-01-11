import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { LinksTable } from '../../components/resource/LinksTable';

describe('LinksTable', () => {
  const mockLinks = {
    'Visit Source': [{ label: 'Original Website', url: 'https://example.com' }],
    'Web Services': [
      { label: 'WMS Service', url: 'https://example.com/wms' },
      { label: 'WFS Service', url: 'https://example.com/wfs' },
    ],
    Metadata: [{ label: 'ISO 19115', url: 'https://example.com/metadata.xml' }],
  };

  it('renders without crashing', () => {
    render(<LinksTable links={mockLinks} />);
    expect(screen.getByText('Links')).toBeInTheDocument();
  });

  it('renders all link categories', () => {
    render(<LinksTable links={mockLinks} />);
    expect(screen.getByText('Visit Source')).toBeInTheDocument();
    expect(screen.getByText('Web Services')).toBeInTheDocument();
    expect(screen.getByText('Metadata')).toBeInTheDocument();
  });

  it('opens lightbox for Web Services category', () => {
    render(<LinksTable links={mockLinks} />);
    const webServicesButton = screen.getByRole('button', {
      name: 'Web Services',
    });
    fireEvent.click(webServicesButton);

    // Check if lightbox is opened - look for the lightbox content
    expect(screen.getByText('WMS Service')).toBeInTheDocument();
    expect(screen.getByText('WFS Service')).toBeInTheDocument();
  });

  it('closes lightbox when close button is clicked', () => {
    render(<LinksTable links={mockLinks} />);
    const webServicesButton = screen.getByRole('button', {
      name: 'Web Services',
    });
    fireEvent.click(webServicesButton);

    // Lightbox should be open
    expect(screen.getByText('WMS Service')).toBeInTheDocument();

    // Click close button (X) - it's the button with no accessible name
    const closeButton = screen.getByRole('button', { name: '' });
    fireEvent.click(closeButton);

    // Lightbox should be closed
    expect(screen.queryByText('WMS Service')).not.toBeInTheDocument();
  });

  it('does not render when links are empty', () => {
    const { container } = render(<LinksTable links={{}} />);
    expect(container.firstChild).toBeNull();
  });

  it('does not render when links are null', () => {
    const { container } = render(<LinksTable links={null} />);
    expect(container.firstChild).toBeNull();
  });
});

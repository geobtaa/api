import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MapGeosearchControl } from '../../../components/map/MapGeosearchControl';

const fetchNominatimSearchMock = vi.fn();
const latLngBoundsMock = vi.fn();
const controlCorner = document.createElement('div');
const zoomControl = document.createElement('div');

vi.mock('../../../services/api', () => ({
  fetchNominatimSearch: (...args: unknown[]) =>
    fetchNominatimSearchMock(...args),
}));

vi.mock('leaflet', () => ({
  default: {
    Control: {
      extend: (props: { onAdd: () => HTMLDivElement }) =>
        class {
          private container: HTMLDivElement | null = null;

          constructor(_options?: unknown) {}

          addTo() {
            this.container = props.onAdd();
            controlCorner.appendChild(this.container);
            return this;
          }

          getContainer() {
            return this.container;
          }

          remove() {
            this.container?.remove();
            this.container = null;
          }
        },
    },
    DomEvent: {
      disableClickPropagation: vi.fn(),
      disableScrollPropagation: vi.fn(),
    },
    latLngBounds: (...args: unknown[]) => latLngBoundsMock(...args),
  },
}));

describe('MapGeosearchControl', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    controlCorner.innerHTML = '';
    controlCorner.className = 'leaflet-top leaflet-left';
    zoomControl.className = 'leaflet-control-zoom';
    controlCorner.appendChild(zoomControl);
    document.body.appendChild(controlCorner);

    latLngBoundsMock.mockReturnValue({
      isValid: () => true,
    });
  });

  afterEach(() => {
    controlCorner.remove();
  });

  it('renders below zoom controls and fits the map to a selected place', async () => {
    const mapInstance = {
      fitBounds: vi.fn(),
      setView: vi.fn(),
    };

    fetchNominatimSearchMock.mockResolvedValue({
      data: [
        {
          id: 'nominatim-1',
          type: 'gazetteer_place',
          attributes: {
            id: 1,
            wok_id: 1,
            parent_id: 0,
            name: 'Chicago',
            placetype: 'locality',
            country: 'United States',
            repo: 'nominatim',
            latitude: 41.8781,
            longitude: -87.6298,
            min_latitude: 41.6443,
            min_longitude: -87.9401,
            max_latitude: 42.023,
            max_longitude: -87.5237,
            is_current: 1,
            is_deprecated: 0,
            is_ceased: 0,
            is_superseded: 0,
            is_superseding: 0,
            superseded_by: null,
            supersedes: null,
            lastmodified: 0,
            created_at: '2024-01-01T00:00:00Z',
            updated_at: '2024-01-01T00:00:00Z',
            display_name: 'Chicago, Illinois, United States',
          },
        },
      ],
    });

    render(<MapGeosearchControl mapInstance={mapInstance as any} />);

    const toggleButton = screen.getByRole('button', {
      name: 'Search places on map',
    });
    const controlContainer = toggleButton.closest('.leaflet-control');

    expect(controlCorner.children[0]).toBe(zoomControl);
    expect(controlCorner.children[1]).toBe(controlContainer);

    fireEvent.click(toggleButton);

    const input = screen.getByLabelText('Search for a place on the map');
    fireEvent.change(input, { target: { value: 'Chicago' } });

    await waitFor(() => {
      expect(fetchNominatimSearchMock).toHaveBeenCalledWith('Chicago', 8);
    });

    fireEvent.click(
      await screen.findByRole('button', {
        name: /Chicago, Illinois, United States/i,
      })
    );

    expect(latLngBoundsMock).toHaveBeenCalledWith(
      [41.6443, -87.9401],
      [42.023, -87.5237]
    );
    expect(mapInstance.fitBounds).toHaveBeenCalledWith(
      expect.objectContaining({ isValid: expect.any(Function) }),
      { padding: [24, 24], maxZoom: 12 }
    );
    expect(
      screen.queryByLabelText('Search for a place on the map')
    ).not.toBeInTheDocument();
  });
});

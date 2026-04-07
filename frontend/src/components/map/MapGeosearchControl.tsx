import {
  useContext,
  useEffect,
  useRef,
  useState,
  type KeyboardEvent,
} from 'react';
import { createPortal } from 'react-dom';
import L from 'leaflet';
import { LeafletContext } from '@react-leaflet/core';
import { Search, X } from 'lucide-react';
import { fetchNominatimSearch } from '../../services/api';
import type { GazetteerPlace } from '../../types/api';

const MAP_CONTROL_ICON_PROPS = {
  size: 17,
  strokeWidth: 1.85,
  absoluteStrokeWidth: true as const,
};

interface MapGeosearchControlProps {
  mapInstance?: L.Map | null;
  position?: L.ControlPosition;
  placeholder?: string;
  maxResults?: number;
  onPlaceSelect?: (place: GazetteerPlace, map: L.Map) => void;
}

function fitMapToPlace(map: L.Map, place: GazetteerPlace) {
  const attrs = place.attributes;
  const bounds = L.latLngBounds(
    [attrs.min_latitude, attrs.min_longitude],
    [attrs.max_latitude, attrs.max_longitude]
  );

  if (bounds.isValid()) {
    map.fitBounds(bounds, { padding: [24, 24], maxZoom: 12 });
    return;
  }

  map.setView([attrs.latitude, attrs.longitude], 12);
}

export function MapGeosearchControl({
  mapInstance,
  position = 'topleft',
  placeholder = 'Search places',
  maxResults = 8,
  onPlaceSelect,
}: MapGeosearchControlProps) {
  const context = useContext(LeafletContext);
  const map = context?.map ?? mapInstance ?? null;
  const [container, setContainer] = useState<HTMLDivElement | null>(null);
  const [query, setQuery] = useState('');
  const [suggestions, setSuggestions] = useState<GazetteerPlace[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const [isLoading, setIsLoading] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!map) return;

    const CustomControl = L.Control.extend({
      onAdd: () => {
        const div = document.createElement('div');
        div.className = 'leaflet-control leaflet-bar map-geosearch-control';
        L.DomEvent.disableClickPropagation(div);
        L.DomEvent.disableScrollPropagation(div);
        return div;
      },
    });

    const control = new CustomControl({ position });
    control.addTo(map);

    const controlContainer = control.getContainer();
    if (position === 'topleft' && controlContainer?.parentElement) {
      const cornerContainer = controlContainer.parentElement;
      const zoomControl = cornerContainer.querySelector(
        '.leaflet-control-zoom'
      );

      if (zoomControl?.nextSibling) {
        cornerContainer.insertBefore(controlContainer, zoomControl.nextSibling);
      } else if (zoomControl) {
        cornerContainer.appendChild(controlContainer);
      }
    }

    setContainer(controlContainer);

    return () => {
      control.remove();
      setContainer(null);
    };
  }, [map, position]);

  useEffect(() => {
    const trimmedQuery = query.trim();
    if (!trimmedQuery) {
      setSuggestions([]);
      setIsLoading(false);
      return;
    }

    let cancelled = false;
    const fetchSuggestionsDebounced = setTimeout(async () => {
      setIsLoading(true);
      try {
        const response = await fetchNominatimSearch(trimmedQuery, maxResults);
        if (cancelled) return;
        setSuggestions(response.data || []);
        setShowSuggestions(true);
      } catch (error) {
        if (!cancelled) {
          console.error('Error fetching geosearch suggestions:', error);
          setSuggestions([]);
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }, 350);

    return () => {
      cancelled = true;
      clearTimeout(fetchSuggestionsDebounced);
    };
  }, [maxResults, query]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setShowSuggestions(false);
        setIsExpanded(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    if (!isExpanded) return;
    inputRef.current?.focus();
    inputRef.current?.select();
  }, [isExpanded]);

  const handleSelectPlace = (place: GazetteerPlace) => {
    if (!map) return;
    fitMapToPlace(map, place);
    setQuery(place.attributes.display_name || place.attributes.name);
    setShowSuggestions(false);
    setSelectedIndex(-1);
    setIsExpanded(false);
    onPlaceSelect?.(place, map);
  };

  const handleClear = () => {
    setQuery('');
    setSuggestions([]);
    setShowSuggestions(false);
    setSelectedIndex(-1);
    inputRef.current?.focus();
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setSelectedIndex((prev) =>
        prev < suggestions.length - 1 ? prev + 1 : prev
      );
      setShowSuggestions(true);
      return;
    }

    if (event.key === 'ArrowUp') {
      event.preventDefault();
      setSelectedIndex((prev) => (prev > -1 ? prev - 1 : -1));
      return;
    }

    if (event.key === 'Enter') {
      if (selectedIndex >= 0 && suggestions[selectedIndex]) {
        event.preventDefault();
        handleSelectPlace(suggestions[selectedIndex]);
        return;
      }

      if (suggestions[0]) {
        event.preventDefault();
        handleSelectPlace(suggestions[0]);
      }
      return;
    }

    if (event.key === 'Escape') {
      event.preventDefault();
      setShowSuggestions(false);
      setSelectedIndex(-1);
      setIsExpanded(false);
    }
  };

  if (!container) return null;

  return createPortal(
    <div ref={rootRef} className="relative" data-map-geosearch-control>
      <button
        type="button"
        onClick={() => setIsExpanded((open) => !open)}
        aria-label={isExpanded ? 'Hide place search' : 'Search places on map'}
        title={isExpanded ? 'Hide place search' : 'Search places on map'}
        className="leaflet-control-custom-button focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 transition-colors"
      >
        <Search
          {...MAP_CONTROL_ICON_PROPS}
          className="text-gray-700"
          aria-hidden="true"
        />
      </button>

      {isExpanded && (
        <div className="absolute left-[calc(100%+0.5rem)] top-1/2 w-[220px] -translate-y-1/2 sm:w-[240px]">
          <div className="flex items-center gap-2 rounded-md border border-gray-300 bg-white px-2.5 py-2 shadow-sm">
            <Search
              {...MAP_CONTROL_ICON_PROPS}
              className="shrink-0 text-gray-400"
              aria-hidden="true"
            />
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
                setSelectedIndex(-1);
                if (!showSuggestions && event.target.value.trim()) {
                  setShowSuggestions(true);
                }
              }}
              onFocus={() => {
                if (query.trim() || suggestions.length > 0) {
                  setShowSuggestions(true);
                }
              }}
              onKeyDown={handleKeyDown}
              placeholder={placeholder}
              aria-label="Search for a place on the map"
              className="min-w-0 flex-1 border-0 bg-transparent p-0 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none"
            />
            {query && (
              <button
                type="button"
                onClick={handleClear}
                className="rounded p-0.5 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500"
                aria-label="Clear map place search"
              >
                <X {...MAP_CONTROL_ICON_PROPS} />
              </button>
            )}
          </div>

          {showSuggestions && (isLoading || query.trim()) && (
            <div className="absolute left-0 right-0 top-[calc(100%+0.25rem)] max-h-64 overflow-auto rounded-md border border-gray-200 bg-white shadow-lg">
              {isLoading ? (
                <div className="px-3 py-2 text-sm text-gray-500">
                  Searching...
                </div>
              ) : suggestions.length === 0 ? (
                <div className="px-3 py-2 text-sm text-gray-500">
                  No places found
                </div>
              ) : (
                suggestions.map((place, index) => (
                  <button
                    key={place.id}
                    type="button"
                    className={`block w-full px-3 py-2 text-left hover:bg-gray-50 focus:bg-gray-50 focus:outline-none ${
                      index === selectedIndex ? 'bg-gray-50' : ''
                    }`}
                    onClick={() => handleSelectPlace(place)}
                    onMouseEnter={() => setSelectedIndex(index)}
                  >
                    <div className="text-sm font-medium text-gray-900">
                      {place.attributes.name}
                    </div>
                    <div className="text-xs text-gray-500">
                      {place.attributes.display_name || place.attributes.name}
                    </div>
                  </button>
                ))
              )}
            </div>
          )}
        </div>
      )}
    </div>,
    container
  );
}

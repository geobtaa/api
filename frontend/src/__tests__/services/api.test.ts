import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { FacetFilter } from '../../types/search';

// Unmock the API service to test the actual implementation
vi.doUnmock('../../services/api');

// Mock environment variables by directly setting them
// const originalEnv = import.meta.env; // Reserved for potential future use

// Mock fetch globally
const mockFetch = vi.fn();
global.fetch = mockFetch;

// Mock performance API
const mockPerformance = {
  now: vi.fn(() => Date.now()),
};
global.performance = mockPerformance as any;

// Mock console methods to capture logs for testing
// const consoleSpy = {
//   log: vi.spyOn(console, 'log'),
//   error: vi.spyOn(console, 'error'),
// }; // Reserved for potential future use

// Import the actual API functions after unmocking
let ApiError: any;
let fetchSearchResults: any;
let fetchResourceDetails: any;
let fetchSuggestions: any;
let fetchBookmarkedResources: any;

describe('API Service', () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    mockFetch.mockClear();
    mockPerformance.now.mockClear();

    // Set up test environment variables
    (import.meta.env as any).VITE_API_BASE_URL = 'https://test-api.example.com';
    (import.meta.env as any).VITE_CSRF_TOKEN = 'test-csrf-token';
    (import.meta.env as any).VITE_ENFORCE_HTTPS = 'true';
    (import.meta.env as any).VITE_USE_JSONP = 'false';

    // Dynamically import the actual API functions
    const apiModule = await import('../../services/api');
    ApiError = apiModule.ApiError;
    fetchSearchResults = apiModule.fetchSearchResults;
    fetchResourceDetails = apiModule.fetchResourceDetails;
    fetchSuggestions = apiModule.fetchSuggestions;
    fetchBookmarkedResources = apiModule.fetchBookmarkedResources;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('ApiError Class', () => {
    it('creates ApiError with message and status', () => {
      const error = new ApiError('Test error', 404);

      expect(error.message).toBe('Test error');
      expect(error.status).toBe(404);
      expect(error.name).toBe('ApiError');
      expect(error).toBeInstanceOf(Error);
    });

    it('creates ApiError with message only', () => {
      const error = new ApiError('Test error');

      expect(error.message).toBe('Test error');
      expect(error.status).toBeUndefined();
      expect(error.name).toBe('ApiError');
    });
  });

  describe('fetchSearchResults', () => {
    it('fetches search results with basic query', async () => {
      const mockResponse = {
        jsonapi: { version: '1.0', profile: [] },
        links: { self: '', first: '', last: '' },
        meta: {
          totalCount: 4,
          totalPages: 1,
          currentPage: 1,
          perPage: 10,
          query: 'minnesota',
        },
        data: [
          {
            id: 'mit-001145244',
            type: 'document',
            attributes: {
              dct_title_s: 'Nondigitized paper map with library catalog link',
              dct_description_sm: [
                'A historical paper map from MIT collections',
              ],
              dct_temporal_sm: ['1950'],
              dc_publisher_sm: ['MIT Libraries'],
              gbl_resourceClass_sm: ['Paper Maps'],
            },
            meta: {
              ui: {
                thumbnail_url: 'https://example.com/thumbnail1.jpg',
                viewer: {
                  geometry: {
                    type: 'Point',
                    coordinates: [-71.0935, 42.3601],
                  },
                },
              },
            },
          },
        ],
        included: [],
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      const result = await fetchSearchResults('minnesota');

      expect(result).toEqual(mockResponse);
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('https://test-api.example.com/search'),
        expect.objectContaining({
          headers: expect.objectContaining({
            Accept: 'application/vnd.api+json, application/json',
            'Content-Type': 'application/json',
            'X-CSRF-Token': expect.any(String),
          }),
        })
      );
    });

    it('fetches search results with pagination', async () => {
      const mockResponse = {
        jsonapi: { version: '1.0', profile: [] },
        links: { self: '', first: '', last: '' },
        meta: {
          totalCount: 20,
          totalPages: 2,
          currentPage: 2,
          perPage: 10,
          query: 'geospatial',
        },
        data: [],
        included: [],
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      const result = await fetchSearchResults('geospatial', 2, 10);

      expect(result).toEqual(mockResponse);
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('page=2&per_page=10'),
        expect.any(Object)
      );
    });

    it('fetches search results with facets', async () => {
      const mockResponse = {
        jsonapi: { version: '1.0', profile: [] },
        links: { self: '', first: '', last: '' },
        meta: {
          totalCount: 1,
          totalPages: 1,
          currentPage: 1,
          perPage: 10,
          query: 'maps',
        },
        data: [],
        included: [],
      };

      const facets: FacetFilter[] = [
        { field: 'gbl_resourceClass_sm', value: 'Paper Maps' },
        { field: 'dc_publisher_sm', value: 'MIT Libraries' },
      ];

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      const result = await fetchSearchResults('maps', 1, 10, facets);

      expect(result).toEqual(mockResponse);
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining(
          'fq%5Bgbl_resourceClass_sm%5D%5B%5D=Paper+Maps'
        ),
        expect.any(Object)
      );
    });

    it('fetches search results with advanced clauses', async () => {
      const mockResponse = {
        jsonapi: { version: '1.0', profile: [] },
        links: { self: '', first: '', last: '' },
        meta: {
          totalCount: 2,
          totalPages: 1,
          currentPage: 1,
          perPage: 10,
          query: '',
        },
        data: [],
        included: [],
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      const advancedClauses = [
        { op: 'AND', field: 'dct_title_s', q: 'Iowa' },
        { op: 'NOT', field: 'dct_title_s', q: 'Wisconsin' },
      ];

      const result = await fetchSearchResults(
        '',
        1,
        10,
        [],
        undefined,
        undefined,
        [],
        advancedClauses
      );

      expect(result).toEqual(mockResponse);
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining(
          encodeURIComponent('adv_q') +
            '=' +
            encodeURIComponent(
              JSON.stringify([
                { op: 'AND', f: 'dct_title_s', q: 'Iowa' },
                { op: 'NOT', f: 'dct_title_s', q: 'Wisconsin' },
              ])
            )
        ),
        expect.any(Object)
      );
    });

    it('fetches search results with sort parameter', async () => {
      const mockResponse = {
        jsonapi: { version: '1.0', profile: [] },
        links: { self: '', first: '', last: '' },
        meta: {
          totalCount: 1,
          totalPages: 1,
          currentPage: 1,
          perPage: 10,
          query: 'data',
        },
        data: [],
        included: [],
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      const result = await fetchSearchResults(
        'data',
        1,
        10,
        [],
        undefined,
        'title'
      );

      expect(result).toEqual(mockResponse);
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('sort=title'),
        expect.any(Object)
      );
    });

    it('calls onApiCall callback when provided', async () => {
      const mockResponse = {
        jsonapi: { version: '1.0', profile: [] },
        links: { self: '', first: '', last: '' },
        meta: {
          totalCount: 1,
          totalPages: 1,
          currentPage: 1,
          perPage: 10,
          query: 'test',
        },
        data: [],
        included: [],
      };

      const onApiCall = vi.fn();

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      await fetchSearchResults('test', 1, 10, [], onApiCall);

      expect(onApiCall).toHaveBeenCalledWith(
        expect.stringContaining('https://test-api.example.com/search')
      );
    });

    it('handles API errors gracefully', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        text: () => Promise.resolve('Internal Server Error'),
      });

      await expect(fetchSearchResults('test')).rejects.toThrow(ApiError);
    });

    it('handles network errors', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'));

      await expect(fetchSearchResults('test')).rejects.toThrow('Network error');
    });

    it('uses default API URL when VITE_API_BASE_URL is not set', async () => {
      // Temporarily override the environment variable
      const originalEnv = import.meta.env.VITE_API_BASE_URL;
      delete (import.meta.env as any).VITE_API_BASE_URL;

      const mockResponse = {
        jsonapi: { version: '1.0', profile: [] },
        links: { self: '', first: '', last: '' },
        meta: {
          totalCount: 1,
          totalPages: 1,
          currentPage: 1,
          perPage: 10,
          query: 'test',
        },
        data: [],
        included: [],
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      await fetchSearchResults('test');

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('http://localhost:8000/api/v1/search'),
        expect.any(Object)
      );

      // Restore original environment variable
      (import.meta.env as any).VITE_API_BASE_URL = originalEnv;
    });
  });

  describe('fetchResourceDetails', () => {
    it('fetches resource details successfully', async () => {
      const mockResourceDetails = {
        id: 'mit-001145244',
        type: 'document',
        attributes: {
          dct_title_s: 'Nondigitized paper map with library catalog link',
          dct_description_sm: ['A historical paper map from MIT collections'],
          dct_temporal_sm: ['1950'],
          dc_publisher_sm: ['MIT Libraries'],
          gbl_resourceClass_sm: ['Paper Maps'],
        },
        meta: {
          ui: {
            thumbnail_url: 'https://example.com/thumbnail1.jpg',
            viewer: {
              geometry: {
                type: 'Point',
                coordinates: [-71.0935, 42.3601],
              },
            },
          },
        },
      };

      const mockResponse = {
        data: mockResourceDetails,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      const result = await fetchResourceDetails('mit-001145244');

      expect(result).toEqual(mockResourceDetails);
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining(
          'https://test-api.example.com/resources/mit-001145244'
        ),
        expect.any(Object)
      );
    });

    it('calls onApiCall callback when provided', async () => {
      const mockResourceDetails = {
        id: 'nyu-2451-34564',
        type: 'document',
        attributes: {
          dct_title_s: 'Point dataset with WMS and WFS',
          dct_description_sm: ['A point dataset with web mapping services'],
        },
        meta: {
          ui: {
            thumbnail_url: null,
            viewer: {
              geometry: {
                type: 'Point',
                coordinates: [-74.006, 40.7128],
              },
            },
          },
        },
      };

      const mockResponse = {
        data: mockResourceDetails,
      };

      const onApiCall = vi.fn();

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      await fetchResourceDetails('nyu-2451-34564', onApiCall);

      expect(onApiCall).toHaveBeenCalledWith(
        expect.stringContaining(
          'https://test-api.example.com/resources/nyu-2451-34564'
        )
      );
    });

    it('handles API errors gracefully', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
        text: () => Promise.resolve('Not Found'),
      });

      await expect(fetchResourceDetails('nonexistent-id')).rejects.toThrow(
        ApiError
      );
    });

    it('handles network errors', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'));

      await expect(fetchResourceDetails('test-id')).rejects.toThrow(ApiError);
    });

    it('uses default API URL when VITE_API_BASE_URL is not set', async () => {
      // Temporarily override the environment variable
      const originalEnv = import.meta.env.VITE_API_BASE_URL;
      delete (import.meta.env as any).VITE_API_BASE_URL;

      const mockResourceDetails = {
        id: 'test-id',
        type: 'document',
        attributes: { dct_title_s: 'Test Resource' },
        meta: { ui: { thumbnail_url: null, viewer: { geometry: null } } },
      };

      const mockResponse = {
        data: mockResourceDetails,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      await fetchResourceDetails('test-id');

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('http://localhost:8000/api/v1/resources/test-id'),
        expect.any(Object)
      );

      // Restore original environment variable
      (import.meta.env as any).VITE_API_BASE_URL = originalEnv;
    });
  });

  describe('fetchSuggestions', () => {
    it('fetches suggestions successfully', async () => {
      const mockSuggestions = {
        data: [
          {
            type: 'suggestion',
            id: '1',
            attributes: {
              text: 'Minnesota',
              title: 'Minnesota State',
              score: 0.95,
            },
          },
          {
            type: 'suggestion',
            id: '2',
            attributes: {
              text: 'Minneapolis',
              title: 'Minneapolis City',
              score: 0.87,
            },
          },
        ],
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockSuggestions),
      });

      const result = await fetchSuggestions('minn');

      expect(result).toHaveLength(2);
      expect(result[0].attributes.text).toBe('Minnesota');
      expect(result[0].attributes.title).toBe(''); // Title should be removed
      expect(result[1].attributes.text).toBe('Minneapolis');
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('https://test-api.example.com/api/v1/suggest'),
        expect.any(Object)
      );
    });

    it('returns empty array for empty query', async () => {
      const result = await fetchSuggestions('');

      expect(result).toEqual([]);
      expect(mockFetch).not.toHaveBeenCalled();
    });

    it('returns empty array for whitespace-only query', async () => {
      const result = await fetchSuggestions('   ');

      expect(result).toEqual([]);
      expect(mockFetch).not.toHaveBeenCalled();
    });

    it('handles API errors gracefully and returns empty array', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        text: () => Promise.resolve('Internal Server Error'),
      });

      const result = await fetchSuggestions('test');

      expect(result).toEqual([]);
    });

    it('handles network errors gracefully and returns empty array', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'));

      const result = await fetchSuggestions('test');

      expect(result).toEqual([]);
    });

    it('uses default API URL when VITE_API_BASE_URL is not set', async () => {
      // Temporarily override the environment variable
      const originalEnv = import.meta.env.VITE_API_BASE_URL;
      delete (import.meta.env as any).VITE_API_BASE_URL;

      const mockSuggestions = {
        data: [
          {
            type: 'suggestion',
            id: '1',
            attributes: {
              text: 'Test',
              title: 'Test Title',
              score: 0.9,
            },
          },
        ],
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockSuggestions),
      });

      await fetchSuggestions('test');

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('https://geo.btaa.org/api/v1/suggest'),
        expect.any(Object)
      );

      // Restore original environment variable
      (import.meta.env as any).VITE_API_BASE_URL = originalEnv;
    });
  });

  describe('fetchBookmarkedResources', () => {
    it('fetches bookmarked resources successfully', async () => {
      const mockResponse = {
        jsonapi: { version: '1.0', profile: [] },
        links: { self: '', first: '', last: '' },
        meta: {
          totalCount: 2,
          totalPages: 1,
          currentPage: 1,
          perPage: 10,
          query: '',
        },
        data: [
          {
            id: 'mit-001145244',
            type: 'document',
            attributes: {
              dct_title_s: 'Nondigitized paper map with library catalog link',
              dct_description_sm: [
                'A historical paper map from MIT collections',
              ],
            },
            meta: {
              ui: {
                thumbnail_url: 'https://example.com/thumbnail1.jpg',
                viewer: {
                  geometry: {
                    type: 'Point',
                    coordinates: [-71.0935, 42.3601],
                  },
                },
              },
            },
          },
          {
            id: 'nyu-2451-34564',
            type: 'document',
            attributes: {
              dct_title_s: 'Point dataset with WMS and WFS',
              dct_description_sm: ['A point dataset with web mapping services'],
            },
            meta: {
              ui: {
                thumbnail_url: null,
                viewer: {
                  geometry: {
                    type: 'Point',
                    coordinates: [-74.006, 40.7128],
                  },
                },
              },
            },
          },
        ],
        included: [],
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      const result = await fetchBookmarkedResources([
        'mit-001145244',
        'nyu-2451-34564',
      ]);

      expect(result).toEqual(mockResponse);
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('fq%5Bid_agg%5D%5B%5D=mit-001145244'),
        expect.any(Object)
      );
    });

    it('returns empty response for empty IDs array', async () => {
      const result = await fetchBookmarkedResources([]);

      expect(result).toEqual({
        jsonapi: { version: '1.0', profile: [] },
        links: { self: '', first: '', last: '' },
        meta: {
          totalCount: 0,
          totalPages: 0,
          currentPage: 1,
          perPage: 10,
          query: '',
        },
        data: [],
        included: [],
      });
      expect(mockFetch).not.toHaveBeenCalled();
    });

    it('calls onApiCall callback when provided', async () => {
      const mockResponse = {
        jsonapi: { version: '1.0', profile: [] },
        links: { self: '', first: '', last: '' },
        meta: {
          totalCount: 1,
          totalPages: 1,
          currentPage: 1,
          perPage: 10,
          query: '',
        },
        data: [],
        included: [],
      };

      const onApiCall = vi.fn();

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      await fetchBookmarkedResources(['test-id'], onApiCall);

      expect(onApiCall).toHaveBeenCalledWith(
        expect.stringContaining('https://test-api.example.com/search/')
      );
    });

    it('handles invalid response format', async () => {
      const mockResponse = {
        jsonapi: { version: '1.0', profile: [] },
        links: { self: '', first: '', last: '' },
        meta: {
          totalCount: 1,
          totalPages: 1,
          currentPage: 1,
          perPage: 10,
          query: '',
        },
        data: null, // Invalid format
        included: [],
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      await expect(fetchBookmarkedResources(['test-id'])).rejects.toThrow(
        ApiError
      );
    });

    it('handles API errors gracefully', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        text: () => Promise.resolve('Internal Server Error'),
      });

      await expect(fetchBookmarkedResources(['test-id'])).rejects.toThrow(
        ApiError
      );
    });

    it('handles network errors', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'));

      await expect(fetchBookmarkedResources(['test-id'])).rejects.toThrow(
        ApiError
      );
    });

    it('uses default API URL when VITE_API_BASE_URL is not set', async () => {
      // Temporarily override the environment variable
      const originalEnv = import.meta.env.VITE_API_BASE_URL;
      delete (import.meta.env as any).VITE_API_BASE_URL;

      const mockResponse = {
        jsonapi: { version: '1.0', profile: [] },
        links: { self: '', first: '', last: '' },
        meta: {
          totalCount: 1,
          totalPages: 1,
          currentPage: 1,
          perPage: 10,
          query: '',
        },
        data: [],
        included: [],
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      await fetchBookmarkedResources(['test-id']);

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('http://localhost:8000/api/v1/'),
        expect.any(Object)
      );

      // Restore original environment variable
      (import.meta.env as any).VITE_API_BASE_URL = originalEnv;
    });
  });

  describe('URL Security and HTTPS Enforcement', () => {
    it('enforces HTTPS when VITE_ENFORCE_HTTPS is true', async () => {
      const mockResponse = {
        jsonapi: { version: '1.0', profile: [] },
        links: { self: '', first: '', last: '' },
        meta: {
          totalCount: 1,
          totalPages: 1,
          currentPage: 1,
          perPage: 10,
          query: 'test',
        },
        data: [],
        included: [],
      };

      // Override environment to use HTTP URL
      const originalEnv = import.meta.env.VITE_API_BASE_URL;
      (import.meta.env as any).VITE_API_BASE_URL =
        'http://test-api.example.com';

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      await fetchSearchResults('test');

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('https://test-api.example.com/search'),
        expect.any(Object)
      );

      // Restore original environment variable
      (import.meta.env as any).VITE_API_BASE_URL = originalEnv;
    });
  });

  describe('Performance Monitoring', () => {
    it('completes search requests within reasonable time', async () => {
      const mockResponse = {
        jsonapi: { version: '1.0', profile: [] },
        links: { self: '', first: '', last: '' },
        meta: {
          totalCount: 1,
          totalPages: 1,
          currentPage: 1,
          perPage: 10,
          query: 'test',
        },
        data: [],
        included: [],
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      const startTime = Date.now();

      await fetchSearchResults('test');

      const endTime = Date.now();
      const duration = endTime - startTime;

      // Should complete within 100ms in test environment
      expect(duration).toBeLessThan(100);
    });
  });

  describe('Real Fixture Data Integration', () => {
    it('handles MIT Libraries fixture data in search results', async () => {
      const mockResponse = {
        jsonapi: { version: '1.0', profile: [] },
        links: { self: '', first: '', last: '' },
        meta: {
          totalCount: 1,
          totalPages: 1,
          currentPage: 1,
          perPage: 10,
          query: 'MIT',
        },
        data: [
          {
            id: 'mit-001145244',
            type: 'document',
            attributes: {
              dct_title_s: 'Nondigitized paper map with library catalog link',
              dct_description_sm: [
                'A historical paper map from MIT collections',
              ],
              dct_temporal_sm: ['1950'],
              dc_publisher_sm: ['MIT Libraries'],
              gbl_resourceClass_sm: ['Paper Maps'],
            },
            meta: {
              ui: {
                thumbnail_url: 'https://example.com/thumbnail1.jpg',
                viewer: {
                  geometry: {
                    type: 'Point',
                    coordinates: [-71.0935, 42.3601],
                  },
                },
              },
            },
          },
        ],
        included: [],
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      const result = await fetchSearchResults('MIT');

      expect(result.data[0].id).toBe('mit-001145244');
      expect(result.data[0].attributes.ogm.dct_title_s).toBe(
        'Nondigitized paper map with library catalog link'
      );
      expect(result.data[0].attributes.ogm.dc_publisher_sm).toEqual([
        'MIT Libraries',
      ]);
    });

    it('handles NYU Libraries fixture data in resource details', async () => {
      const mockResourceDetails = {
        id: 'nyu-2451-34564',
        type: 'document',
        attributes: {
          ogm: {
            id: 'nyu-2451-34564',
            dct_title_s: 'Point dataset with WMS and WFS',
            dct_description_sm: ['A point dataset with web mapping services'],
            dct_temporal_sm: ['2020'],
            dc_publisher_sm: ['NYU Libraries'],
            gbl_resourceClass_sm: ['Point Data'],
          },
        },
        meta: {
          ui: {
            thumbnail_url: null,
            viewer: {
              geometry: {
                type: 'Point',
                coordinates: [-74.006, 40.7128],
              },
            },
          },
        },
      };

      const mockResponse = {
        data: mockResourceDetails,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      const result = await fetchResourceDetails('nyu-2451-34564');

      expect(result.id).toBe('nyu-2451-34564');
      expect(result.attributes.ogm.dct_title_s).toBe(
        'Point dataset with WMS and WFS'
      );
      expect(result.attributes.ogm.dc_publisher_sm).toEqual(['NYU Libraries']);
    });

    it('handles Tufts University fixture data in bookmarked resources', async () => {
      const mockResponse = {
        jsonapi: { version: '1.0', profile: [] },
        links: { self: '', first: '', last: '' },
        meta: {
          totalCount: 1,
          totalPages: 1,
          currentPage: 1,
          perPage: 10,
          query: '',
        },
        data: [
          {
            id: 'tufts-cambridgegrid100-04',
            type: 'document',
            attributes: {
              ogm: {
                id: 'tufts-cambridgegrid100-04',
                dct_title_s: 'Polygon dataset with WFS, WMS, and FGDC metadata',
                dct_description_sm: ['A comprehensive polygon dataset'],
                dct_temporal_sm: ['2019', '2020'],
                dc_publisher_sm: ['Tufts University', 'Cambridge Grid'],
                gbl_resourceClass_sm: ['Polygon Data'],
              },
            },
            meta: {
              ui: {
                thumbnail_url: 'https://example.com/thumbnail3.jpg',
                viewer: {
                  geometry: {
                    type: 'Polygon',
                    coordinates: [
                      [
                        [-71.1, 42.3],
                        [-71, 42.3],
                        [-71, 42.4],
                        [-71.1, 42.4],
                        [-71.1, 42.3],
                      ],
                    ],
                  },
                },
              },
            },
          },
        ],
        included: [],
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      const result = await fetchBookmarkedResources([
        'tufts-cambridgegrid100-04',
      ]);

      expect(result.data[0].id).toBe('tufts-cambridgegrid100-04');
      expect(result.data[0].attributes.ogm.dct_title_s).toBe(
        'Polygon dataset with WFS, WMS, and FGDC metadata'
      );
      expect(result.data[0].attributes.ogm.dc_publisher_sm).toEqual([
        'Tufts University',
        'Cambridge Grid',
      ]);
    });

    it('handles Stanford University fixture data in suggestions', async () => {
      const mockSuggestions = {
        data: [
          {
            type: 'suggestion',
            id: '1',
            attributes: {
              text: 'Stanford University',
              title: 'Stanford University',
              score: 0.95,
            },
          },
          {
            type: 'suggestion',
            id: '2',
            attributes: {
              text: 'Stanford Libraries',
              title: 'Stanford Libraries',
              score: 0.87,
            },
          },
        ],
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockSuggestions),
      });

      const result = await fetchSuggestions('stanford');

      expect(result).toHaveLength(2);
      expect(result[0].attributes.text).toBe('Stanford University');
      expect(result[1].attributes.text).toBe('Stanford Libraries');
    });
  });
});

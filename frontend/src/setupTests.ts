import '@testing-library/jest-dom';
import { vi } from 'vitest';
import * as matchers from 'vitest-axe/matchers';
import { expect } from 'vitest';

expect.extend(matchers);

// Mock API functions
vi.mock('./services/api', () => ({
  getApiBasePath: vi.fn(() => '/api/v1'),
  fetchSearchResults: vi.fn().mockResolvedValue({
    jsonapi: { version: '1.1', profile: [] },
    links: {
      self: '/api/v1/search',
      first: '/api/v1/search',
      last: '/api/v1/search',
    },
    meta: {
      totalCount: 0,
      totalPages: 0,
      currentPage: 1,
      perPage: 10,
      query: '',
    },
    data: [],
    included: [],
  }),
  fetchFacetValues: vi.fn().mockResolvedValue({
    data: [],
    meta: {
      totalCount: 0,
      totalPages: 0,
      currentPage: 1,
      perPage: 10,
      facetName: 'dct_spatial_sm',
      sort: 'count_desc',
    },
  }),
  fetchResourceDetails: vi.fn().mockResolvedValue({
    id: 'test-id',
    type: 'resource',
    attributes: {
      ogm: {
        id: 'test-id',
        dct_title_s: 'Test Resource',
        dct_description_sm: ['Test description'],
        dct_temporal_sm: ['2023'],
        dc_publisher_sm: ['Test Publisher'],
        gbl_resourceClass_sm: ['Dataset'],
      },
    },
    meta: {
      ui: {
        thumbnail_url: null,
        viewer: {
          geometry: {
            type: 'Point',
            coordinates: [-93.265, 44.9778],
          },
        },
      },
    },
  }),
  fetchFeaturedResourcePreview: vi.fn().mockResolvedValue({
    id: 'test-id',
    type: 'resource',
    attributes: {
      ogm: {
        id: 'test-id',
        dct_title_s: 'Test Resource',
        dct_description_sm: ['Test description'],
        dct_temporal_sm: ['2023'],
        dc_publisher_sm: ['Test Publisher'],
        gbl_resourceClass_sm: ['Dataset'],
      },
    },
    meta: {
      ui: {
        thumbnail_url: null,
        viewer: {
          geometry: {
            type: 'Point',
            coordinates: [-93.265, 44.9778],
          },
        },
      },
    },
  }),
  fetchSuggestions: vi.fn().mockResolvedValue([
    {
      id: 'suggestion-1',
      type: 'suggestion',
      attributes: {
        text: 'minnesota',
        score: 1,
      },
    },
  ]),
  fetchHomeBlogPosts: vi.fn().mockResolvedValue({
    data: [],
  }),
  fetchBookmarkedResources: vi.fn().mockResolvedValue({
    jsonapi: { version: '1.1', profile: [] },
    links: {
      self: '/api/v1/bookmarks',
      first: '/api/v1/bookmarks',
      last: '/api/v1/bookmarks',
    },
    meta: {
      totalCount: 0,
      totalPages: 0,
      currentPage: 1,
      perPage: 10,
      query: '',
    },
    data: [],
    included: [],
  }),
}));

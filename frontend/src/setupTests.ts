import '@testing-library/jest-dom';
import { vi } from 'vitest';

// Mock API functions
vi.mock('./services/api', () => ({
  fetchSearchResults: vi.fn().mockResolvedValue({
    data: [],
    meta: {
      total: 0,
      page: 1,
      per_page: 10,
    },
    included: [],
  }),
  fetchResourceDetails: vi.fn().mockResolvedValue({
    id: 'test-id',
    type: 'document',
    attributes: {
      dct_title_s: 'Test Resource',
      dct_description_sm: ['Test description'],
      dct_temporal_sm: ['2023'],
      dc_publisher_sm: ['Test Publisher'],
      gbl_resourceClass_sm: ['Dataset'],
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
        title: 'Minnesota',
      },
    },
  ]),
  fetchBookmarkedResources: vi.fn().mockResolvedValue({
    data: [],
    meta: {
      total: 0,
      page: 1,
      per_page: 10,
    },
    included: [],
  }),
}));

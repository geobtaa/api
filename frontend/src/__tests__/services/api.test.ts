import { describe, it, expect, vi } from 'vitest';
import { fetchBookmarkedResources } from '../../services/api';

// Mock fetch
global.fetch = vi.fn();

// Unmock the API service to test the real implementation
vi.unmock('../../services/api');

describe('fetchBookmarkedResources', () => {
  it('constructs correct URL for bookmarked resources', async () => {
    const ids = ['123', '456'];
    const onApiCall = vi.fn();

    // Mock success response
    (global.fetch as any).mockResolvedValue({
      ok: true,
      json: async () => ({ data: [] })
    });

    await fetchBookmarkedResources(ids, onApiCall);

    expect(onApiCall).toHaveBeenCalled();
    const url = new URL(onApiCall.mock.calls[0][0]);

    // Verify we are using the correct filter parameter
    // Current implementation uses fq[id][], which is suspected to be wrong.
    // We expect it to be include_filters[id][] based on fetchSearchResults logic.

    // Log what we got for debugging
    console.log('Generated URL search params:', url.search);

    // The test serves to document current behavior first
    const fqIds = url.searchParams.getAll('fq[id][]');
    const includeIds = url.searchParams.getAll('include_filters[id][]');

    console.log('fq[id][] values:', fqIds);
    console.log('include_filters[id][] values:', includeIds);
  });
});

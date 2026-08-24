import { describe, expect, it } from 'vitest';
import { CONFIGURED_FACETS } from '../constants/facets';

describe('configured facets', () => {
  it('shows Local Collection immediately after Provider', () => {
    const providerIndex = CONFIGURED_FACETS.indexOf('schema_provider_s');
    const localCollectionIndex = CONFIGURED_FACETS.indexOf(
      'b1g_localCollectionLabel_sm'
    );

    expect(providerIndex).toBeGreaterThanOrEqual(0);
    expect(localCollectionIndex).toBe(providerIndex + 1);
  });
});

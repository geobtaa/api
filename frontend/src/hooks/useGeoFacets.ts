import { useEffect, useState } from 'react';
import { fetchSearchResults } from '../services/api';
import type { JsonApiResponse } from '../types/api';
import type { ChoroplethData, GeoFacet } from '../types/map';

// Fetches search facet aggregations (country/region/county) for a given query.
// Returns normalized choropleth data structure + loading/error states.
export function useGeoFacets(query: string, onApiCall?: (url: string) => void) {
  const [data, setData] = useState<ChoroplethData>({
    country: [],
    region: [],
    county: [],
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    const run = async () => {
      try {
        setLoading(true);
        setError(null);
        // Delegate to unified API service; record URL via onApiCall (Footer shows last request)
        const response: JsonApiResponse = await fetchSearchResults(
          query || '',
          1,
          10,
          [],
          onApiCall
        );
        if (!isMounted) return;
        if (response.included) {
          // Extract only the three geo facets we're interested in (field-named IDs)
          const geoFacets = response.included.filter(
            (item): item is GeoFacet =>
              item.type === 'facet' &&
              ['geo_country', 'geo_region', 'geo_county'].includes(item.id)
          );
          // Normalize into ChoroplethData shape used by map updaters
          const newData: ChoroplethData = {
            country: [],
            region: [],
            county: [],
          };
          geoFacets.forEach((facet) => {
            if (facet.id === 'geo_country')
              newData.country = facet.attributes.items;
            if (facet.id === 'geo_region')
              newData.region = facet.attributes.items;
            if (facet.id === 'geo_county')
              newData.county = facet.attributes.items;
          });
          setData(newData);
        } else {
          setError('No geographic data found in API response');
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Unknown error');
      } finally {
        if (isMounted) setLoading(false);
      }
    };
    run();
    return () => {
      isMounted = false;
    };
  }, [query, onApiCall]);

  return { data, loading, error };
}

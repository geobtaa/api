import { useEffect, useState } from 'react';
import { fetchSearchResults } from '../services/api';
import type { JsonApiResponse } from '../types/api';
import type { ChoroplethData, GeoFacet } from '../types/map';

// Fetches search facet aggregations (country/region/county) for a given query.
// Returns normalized choropleth data structure + loading/error states + globalCount.
export function useGeoFacets(query: string, onApiCall?: (url: string) => void) {
  const [data, setData] = useState<ChoroplethData>({
    country: [],
    region: [],
    county: [],
  });
  const [globalCount, setGlobalCount] = useState<number>(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    const run = async () => {
      try {
        setLoading(true);
        setError(null);
        const response: JsonApiResponse = await fetchSearchResults(
          query || '',
          1,
          10,
          [],
          onApiCall
        );
        if (!isMounted) return;
        const mapStats = (
          response.meta as { mapStats?: { globalCount?: number } } | undefined
        )?.mapStats;
        setGlobalCount(
          typeof mapStats?.globalCount === 'number' ? mapStats.globalCount : 0
        );
        if (response.included) {
          const geoFacets = response.included.filter(
            (item): item is GeoFacet =>
              item.type === 'facet' &&
              ['geo_country', 'geo_region', 'geo_county'].includes(item.id)
          );
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

  return { data, loading, error, globalCount };
}

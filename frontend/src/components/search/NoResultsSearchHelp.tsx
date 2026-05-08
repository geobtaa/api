import { useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { AlertCircle, ArrowRight, MapPin, Search } from 'lucide-react';
import { Link, useSearchParams } from 'react-router';
import { fetchNominatimSearch } from '../../services/api';
import type { GazetteerPlace } from '../../types/api';

type SearchSuggestion = { text: string };
type SearchSuggestionResponseItem = {
  attributes?: {
    text?: string;
  };
};

interface NoResultsSearchHelpProps {
  query: string;
  advancedSearchHref: string;
}

const KEYWORD_SUGGESTION_LIMIT = 5;
const NOMINATIM_SUGGESTION_LIMIT = 5;

const PLACE_TYPE_LABELS: Record<string, string> = {
  city: 'City',
  town: 'Town',
  village: 'Village',
  hamlet: 'Hamlet',
  municipality: 'Municipality',
  county: 'County',
  state: 'State',
  region: 'Region',
  province: 'Province',
  country: 'Country',
  administrative: 'Administrative Area',
};

function formatPlaceTypeLabel(placeType: string | null | undefined) {
  const normalized = (placeType || '').trim().replace(/_/g, ' ').toLowerCase();
  if (!normalized) return null;
  return (
    PLACE_TYPE_LABELS[normalized] ||
    normalized.replace(/\b\w/g, (char) => char.toUpperCase())
  );
}

function buildBaseSearchParams(currentParams: URLSearchParams) {
  const params = new URLSearchParams();
  const view = currentParams.get('view');
  const perPage = currentParams.get('per_page');

  if (view && view !== 'list') {
    params.set('view', view);
  }
  if (perPage) {
    params.set('per_page', perPage);
  }

  return params;
}

function buildKeywordSearchHref(currentParams: URLSearchParams, query: string) {
  const params = buildBaseSearchParams(currentParams);
  params.set('q', query);
  return `/search?${params.toString()}`;
}

function buildPlaceSearchHref(
  currentParams: URLSearchParams,
  place: GazetteerPlace
) {
  const attrs = place.attributes;
  const params = buildBaseSearchParams(currentParams);

  params.set('q', '');
  params.set('include_filters[geo][type]', 'bbox');
  params.set('include_filters[geo][field]', 'dcat_bbox');
  params.set('include_filters[geo][relation]', 'intersects');
  params.set(
    'include_filters[geo][top_left][lat]',
    attrs.max_latitude.toString()
  );
  params.set(
    'include_filters[geo][top_left][lon]',
    attrs.min_longitude.toString()
  );
  params.set(
    'include_filters[geo][bottom_right][lat]',
    attrs.min_latitude.toString()
  );
  params.set(
    'include_filters[geo][bottom_right][lon]',
    attrs.max_longitude.toString()
  );

  return `/search?${params.toString()}`;
}

function SuggestionGroup({
  title,
  attribution,
  children,
}: {
  title: string;
  attribution?: string;
  children: ReactNode;
}) {
  return (
    <div>
      <div className="flex items-center px-4 pb-1 pt-3 text-xs font-medium uppercase text-gray-500">
        <span>{title}</span>
        {attribution && (
          <span className="ml-2 normal-case text-gray-400">{attribution}</span>
        )}
      </div>
      <div>{children}</div>
    </div>
  );
}

function EmptySuggestionRow({ children }: { children: ReactNode }) {
  return <div className="px-4 py-2 text-sm text-gray-500">{children}</div>;
}

export function NoResultsSearchHelp({
  query,
  advancedSearchHref,
}: NoResultsSearchHelpProps) {
  const [searchParams] = useSearchParams();
  const [keywordSuggestions, setKeywordSuggestions] = useState<
    SearchSuggestion[]
  >([]);
  const [placeSuggestions, setPlaceSuggestions] = useState<GazetteerPlace[]>(
    []
  );
  const [isLoadingKeywords, setIsLoadingKeywords] = useState(() =>
    Boolean(query.trim())
  );
  const [isLoadingPlaces, setIsLoadingPlaces] = useState(() =>
    Boolean(query.trim())
  );

  const trimmedQuery = useMemo(
    () => query.trim().replace(/\s+/g, ' '),
    [query]
  );

  useEffect(() => {
    let isCurrent = true;

    if (!trimmedQuery) {
      setKeywordSuggestions([]);
      setIsLoadingKeywords(false);
      return () => {
        isCurrent = false;
      };
    }

    const fetchKeywordSuggestions = async () => {
      setKeywordSuggestions([]);
      setIsLoadingKeywords(true);
      try {
        const res = await fetch(
          `/suggest?q=${encodeURIComponent(trimmedQuery)}`,
          {
            headers: { Accept: 'application/json' },
          }
        );
        if (!res.ok) {
          throw new Error(`Suggestion request failed: ${res.status}`);
        }
        const json = await res.json();
        const data: SearchSuggestionResponseItem[] = Array.isArray(json?.data)
          ? json.data
          : [];
        if (!isCurrent) return;
        setKeywordSuggestions(
          data
            .map((item) => ({ text: item.attributes?.text ?? '' }))
            .filter((suggestion) => suggestion.text)
            .slice(0, KEYWORD_SUGGESTION_LIMIT)
        );
      } catch (error) {
        console.error('Error fetching keyword suggestions:', error);
        if (isCurrent) {
          setKeywordSuggestions([]);
        }
      } finally {
        if (isCurrent) {
          setIsLoadingKeywords(false);
        }
      }
    };

    fetchKeywordSuggestions();

    return () => {
      isCurrent = false;
    };
  }, [trimmedQuery]);

  useEffect(() => {
    let isCurrent = true;

    if (!trimmedQuery) {
      setPlaceSuggestions([]);
      setIsLoadingPlaces(false);
      return () => {
        isCurrent = false;
      };
    }

    const fetchPlaceSuggestions = async () => {
      setPlaceSuggestions([]);
      setIsLoadingPlaces(true);
      try {
        const response = await fetchNominatimSearch(
          trimmedQuery,
          NOMINATIM_SUGGESTION_LIMIT
        );
        if (!isCurrent) return;
        setPlaceSuggestions(
          (response.data || []).slice(0, NOMINATIM_SUGGESTION_LIMIT)
        );
      } catch (error) {
        console.error('Error fetching placename suggestions:', error);
        if (isCurrent) {
          setPlaceSuggestions([]);
        }
      } finally {
        if (isCurrent) {
          setIsLoadingPlaces(false);
        }
      }
    };

    fetchPlaceSuggestions();

    return () => {
      isCurrent = false;
    };
  }, [trimmedQuery]);

  const bannerMessage = trimmedQuery
    ? 'Try a suggested search, a geographic area, or Advanced Search.'
    : 'Try clearing filters or building a more precise query in Advanced Search.';

  return (
    <section className="flex w-full flex-col gap-4 pt-1">
      <div
        role="status"
        className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-amber-950"
      >
        <div className="flex gap-3">
          <AlertCircle
            className="mt-0.5 h-5 w-5 shrink-0 text-amber-600"
            aria-hidden="true"
          />
          <div>
            <h3 className="font-semibold">No search results found</h3>
            <p className="mt-1 text-sm text-amber-900">{bannerMessage}</p>
          </div>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(16rem,22rem)] xl:items-start">
        {trimmedQuery && (
          <div
            className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm"
            aria-label="Search suggestions"
          >
            <SuggestionGroup
              title="Geographic Areas"
              attribution="Via OpenStreetMap"
            >
              {isLoadingPlaces ? (
                <EmptySuggestionRow>Searching places...</EmptySuggestionRow>
              ) : placeSuggestions.length > 0 ? (
                placeSuggestions.map((place) => {
                  const attrs = place.attributes;
                  const placeName =
                    attrs.name || attrs.display_name || place.id;
                  const placeTypeLabel = formatPlaceTypeLabel(attrs.placetype);

                  return (
                    <Link
                      key={place.id}
                      to={buildPlaceSearchHref(searchParams, place)}
                      className="flex items-start gap-2 px-4 py-2 hover:bg-gray-50 focus:bg-gray-50 focus:outline-none"
                    >
                      <MapPin
                        className="mt-0.5 h-4 w-4 shrink-0 text-gray-400"
                        aria-hidden="true"
                      />
                      <span className="min-w-0">
                        <span className="block text-sm text-gray-900">
                          <span className="font-medium">{placeName}</span>{' '}
                          {placeTypeLabel && (
                            <span className="text-gray-500">
                              ({placeTypeLabel})
                            </span>
                          )}
                        </span>
                        <span className="block truncate text-xs text-gray-500">
                          {attrs.display_name || placeName}
                        </span>
                      </span>
                    </Link>
                  );
                })
              ) : (
                <EmptySuggestionRow>
                  No matching geographic areas found.
                </EmptySuggestionRow>
              )}
            </SuggestionGroup>

            <SuggestionGroup title="Suggestions">
              {isLoadingKeywords ? (
                <EmptySuggestionRow>
                  Searching suggestions...
                </EmptySuggestionRow>
              ) : keywordSuggestions.length > 0 ? (
                keywordSuggestions.map((suggestion) => (
                  <Link
                    key={suggestion.text}
                    to={buildKeywordSearchHref(searchParams, suggestion.text)}
                    className="flex items-center gap-2 px-4 py-2 text-sm text-gray-900 hover:bg-gray-50 focus:bg-gray-50 focus:outline-none"
                  >
                    <Search
                      className="h-4 w-4 shrink-0 text-gray-400"
                      aria-hidden="true"
                    />
                    <span>{suggestion.text}</span>
                  </Link>
                ))
              ) : (
                <EmptySuggestionRow>
                  No close keyword suggestions found.
                </EmptySuggestionRow>
              )}
            </SuggestionGroup>

            <div className="mt-1 flex items-stretch border-t border-gray-200">
              <Link
                to={buildKeywordSearchHref(searchParams, trimmedQuery)}
                className="flex min-w-0 flex-1 items-center justify-between gap-3 px-4 py-3 text-sm font-medium text-blue-700 hover:bg-blue-50 focus:bg-blue-50 focus:outline-none"
              >
                <span className="truncate">
                  See all results for {trimmedQuery}
                </span>
                <ArrowRight className="h-4 w-4 shrink-0" aria-hidden="true" />
              </Link>
              <Link
                to={advancedSearchHref}
                className="shrink-0 px-4 py-3 text-sm font-medium text-blue-700 hover:bg-blue-50 focus:bg-blue-50 focus:outline-none"
              >
                Advanced Search
              </Link>
            </div>
          </div>
        )}

        <aside className="flex flex-col gap-3 rounded-lg border border-gray-200 bg-white px-4 py-4 shadow-sm">
          <div>
            <h3 className="font-semibold text-gray-900">
              Build a more precise search
            </h3>
            <p className="mt-1 text-sm text-gray-600">
              Combine fields and terms with Advanced Search.
            </p>
          </div>
          <Link
            to={advancedSearchHref}
            className="inline-flex items-center justify-center self-start rounded-md bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand/90 focus:outline-none focus:ring-2 focus:ring-brand focus:ring-offset-2"
          >
            Advanced Search
          </Link>
        </aside>
      </div>
    </section>
  );
}

import { useEffect, useRef, useState } from 'react';
import { Seo } from '../components/Seo';
import { useParams, Link, useLocation, useNavigate } from 'react-router';
import { ArrowLeft, ArrowRight, ArrowLeftCircle, XCircle } from 'lucide-react';
import {
  fetchSearchResults,
  fetchResourceDetails,
  ApiError,
} from '../services/api';
import type { GeoDocument, GeoDocumentDetails } from '../types/api';
import { ErrorMessage } from '../components/ErrorMessage';
import { Header } from '../components/layout/Header';
import { Footer } from '../components/layout/Footer';
import { useApi } from '../context/ApiContext';
import { ResourceViewer } from '../components/resource/ResourceViewer';
import { ResourceBreadcrumbs } from '../components/resource/ResourceBreadcrumbs';
import { ResourceSubtitle } from '../components/resource/ResourceSubtitle';
import { CitationTable } from '../components/resource/CitationTable';
import { ResourceJsonLd } from '../components/resource/ResourceJsonLd';
import { FullDetailsTable } from '../components/resource/FullDetailsTable';
import { LocationMap } from '../components/resource/LocationMap';
import { DownloadsTable } from '../components/resource/DownloadsTable';
import { LinksTable } from '../components/resource/LinksTable';
import { SimilarItemsCarousel } from '../components/resource/SimilarItemsCarousel';
import { EnvironmentNavButtons } from '../components/resource/EnvironmentNavButtons';
import { formatCount } from '../utils/formatNumber';
import { DisplayNotes } from '../components/resource/DisplayNotes';
import { DataDictionariesSection } from '../components/resource/DataDictionariesSection';
import { LightboxModal } from '../components/ui/LightboxModal';
import { scheduleAnalyticsBatch } from '../services/analytics';

// Define types for search results
interface SearchResult {
  id: string;
  // Add other properties as needed
}

interface SearchState {
  searchResults: SearchResult[];
  currentIndex: number;
  totalResults: number;
  searchUrl: string;
  currentPage: number;
  absoluteIndex?: number;
  perPage?: number;
  searchId?: string;
  view?: 'list' | 'gallery' | 'map';
}

// Define the ResourceData type to match the actual API response
interface ResourceData extends GeoDocument {
  meta?: {
    ui?: {
      viewer?: {
        protocol?: string;
        endpoint?: string;
        geometry?: string;
      };
      downloads?: Array<{
        label: string;
        url: string;
        type: string;
        format?: string;
        generated?: boolean;
        generation_path?: string;
        download_type?: string;
      }>;
      citation?: string;
      thumbnail_url?: string;
      static_map?: string;
      links?: Record<string, Array<{ label: string; url: string }>>;
      relationships?: Record<string, unknown>;
      similar_items?: Array<{
        id: string;
        attributes: {
          dct_title_s: string;
          schema_provider_s?: string;
          gbl_resourceClass_sm?: string[];
          [key: string]: unknown;
        };
        meta?: {
          ui?: {
            thumbnail_url?: string;
            [key: string]: unknown;
          };
        };
      }>;
    };
  };
}

// New component for index map
function IndexMap() {
  return <div className="viewer-information"></div>;
}

// New component for the attribute table
function AttributeTable() {
  return (
    <div id="table-container" className="w-full">
      <table id="attribute-table" className="w-full table-auto border-collapse">
        <thead className="bg-gray-50">
          <tr>
            <th
              scope="col"
              className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              Attribute
            </th>
            <th
              scope="col"
              className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              Value
            </th>
          </tr>
        </thead>
        <tbody className="attribute-table-body bg-white divide-y divide-gray-200">
          <tr className="hover:bg-gray-50">
            <td className="border px-4 py-2" colSpan={2}>
              <em>Click on map to inspect values</em>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

export function ResourceView({
  prefetchedResource,
  jsonLd,
  currentUrl,
}: {
  prefetchedResource?: GeoDocumentDetails | null;
  jsonLd?: Record<string, unknown> | null;
  currentUrl?: string;
} = {}) {
  const { id } = useParams<{ id: string }>();
  const location = useLocation();
  const navigate = useNavigate();
  const searchState = (location.state as SearchState | null) ?? null;
  // SSR does not have access to `location.state`, so anything derived from it must not
  // affect the initial HTML. Otherwise we get hydration mismatches.
  const [isMounted, setIsMounted] = useState(false);
  useEffect(() => setIsMounted(true), []);
  const [data, setData] = useState<ResourceData | null>(() => {
    if (prefetchedResource && id && prefetchedResource.id === id) {
      return prefetchedResource as unknown as ResourceData;
    }
    return null;
  });
  const [isLoading, setIsLoading] = useState(() => {
    if (prefetchedResource && id && prefetchedResource.id === id) return false;
    return true;
  });
  const [error, setError] = useState<string | null>(null);
  const [isDataDictionaryModalOpen, setIsDataDictionaryModalOpen] =
    useState(false);
  const { setLastApiUrl } = useApi();
  const trackedResourceViewRef = useRef<string | null>(null);

  // Get configured perPage or default to 10
  const perPage = searchState?.perPage || 10;

  // Calculate pagination state
  const isLastInCurrentSet =
    !!searchState &&
    searchState.currentIndex === searchState.searchResults.length - 1;
  const isFirstInCurrentSet = searchState?.currentIndex === 0;

  // Update these calculations to use absoluteIndex when available
  const absoluteCurrentIndex =
    searchState?.absoluteIndex !== undefined
      ? searchState.absoluteIndex
      : searchState
        ? (searchState.currentPage - 1) * perPage + searchState.currentIndex
        : 0;

  // Fix the hasMoreResults and hasPreviousResults calculations
  const hasMoreResults = searchState
    ? absoluteCurrentIndex < searchState.totalResults - 1
    : false;

  const hasPreviousResults = absoluteCurrentIndex > 0;

  // Get prev/next IDs from current result set
  const prevId = !isFirstInCurrentSet
    ? searchState?.searchResults[searchState?.currentIndex - 1]?.id
    : null;
  const nextId = !isLastInCurrentSet
    ? searchState?.searchResults[searchState?.currentIndex + 1]?.id
    : null;

  // Function to fetch next page of results
  const fetchSearchPage = async (pageNumber: number) => {
    if (!searchState) return null;
    try {
      const urlParams = new URLSearchParams(
        searchState.searchUrl.split('?')[1] || ''
      );
      const results = await fetchSearchResults(
        urlParams.get('q') || '',
        pageNumber,
        perPage,
        [],
        setLastApiUrl,
        undefined,
        [],
        [],
        undefined,
        urlParams
      );

      return results.data;
    } catch (error) {
      console.error(`Error fetching search page ${pageNumber}:`, error);
      return null;
    }
  };

  const fetchNextPage = async () => {
    if (!searchState) return null;
    return fetchSearchPage(searchState.currentPage + 1);
  };

  // Function to fetch previous page of results
  const fetchPrevPage = async () => {
    if (!searchState) return null;
    return fetchSearchPage(searchState.currentPage - 1);
  };

  // Handle next result click
  const handleNextClick = async () => {
    if (!searchState) return;

    scheduleAnalyticsBatch({
      events: [
        {
          event_type: 'next_result',
          search_id: searchState.searchId,
          resource_id: id,
          rank: absoluteCurrentIndex + 1,
          page: searchState.currentPage,
          view: searchState.view,
          source_component: 'ResourceView',
          properties: {
            search_url: searchState.searchUrl,
          },
        },
      ],
    });

    if (isLastInCurrentSet && hasMoreResults) {
      // Need to fetch next page
      try {
        const nextResults = await fetchNextPage();
        if (nextResults && nextResults.length > 0) {
          // The new relative index in the next page should be 0 (first item)
          navigate(`/resources/${nextResults[0].id}`, {
            state: {
              ...searchState,
              searchResults: nextResults,
              currentIndex: 0, // Start at the beginning of the new page
              currentPage: searchState.currentPage + 1,
              // Update absolute index to be one more than current
              absoluteIndex: absoluteCurrentIndex + 1,
            },
          });
        }
      } catch (error) {
        console.error('Error navigating to next page:', error);
      }
    } else if (!isLastInCurrentSet && nextId) {
      // Just move to next item in current results
      navigate(`/resources/${nextId}`, {
        state: {
          ...searchState,
          currentIndex: searchState.currentIndex + 1,
          // Update absolute index to be one more than current
          absoluteIndex: absoluteCurrentIndex + 1,
        },
      });
    }
  };

  // Handle previous result click
  const handlePrevClick = async () => {
    if (!searchState) return;

    scheduleAnalyticsBatch({
      events: [
        {
          event_type: 'previous_result',
          search_id: searchState.searchId,
          resource_id: id,
          rank: absoluteCurrentIndex + 1,
          page: searchState.currentPage,
          view: searchState.view,
          source_component: 'ResourceView',
          properties: {
            search_url: searchState.searchUrl,
          },
        },
      ],
    });

    if (isFirstInCurrentSet && hasPreviousResults) {
      // Need to fetch previous page
      try {
        const prevResults = await fetchPrevPage();
        if (prevResults && prevResults.length > 0) {
          // The new relative index in the previous page should be the last item
          navigate(`/resources/${prevResults[prevResults.length - 1].id}`, {
            state: {
              ...searchState,
              searchResults: prevResults,
              currentIndex: prevResults.length - 1, // Point to the last item on the previous page
              currentPage: searchState.currentPage - 1,
              // Update absolute index to be one less than current
              absoluteIndex: absoluteCurrentIndex - 1,
            },
          });
        }
      } catch (error) {
        console.error('Error navigating to previous page:', error);
      }
    } else if (!isFirstInCurrentSet && prevId) {
      // Just move to previous item in current results
      navigate(`/resources/${prevId}`, {
        state: {
          ...searchState,
          currentIndex: searchState.currentIndex - 1,
          // Update absolute index to be one less than current
          absoluteIndex: absoluteCurrentIndex - 1,
        },
      });
    }
  };

  // Update display to use the absoluteCurrentIndex directly
  const displayIndex = absoluteCurrentIndex + 1;

  useEffect(() => {
    let isMounted = true;

    // If the route provided prefetched data for this id, use it and skip client fetch.
    if (prefetchedResource && id && prefetchedResource.id === id) {
      setError(null);
      setData(prefetchedResource as unknown as ResourceData);
      setIsLoading(false);
      return () => {
        isMounted = false;
      };
    }

    const loadItem = async () => {
      if (!id) return;

      setIsLoading(true);
      setError(null);
      try {
        // Use a local function to avoid dependency on setLastApiUrl
        const jsonData = await fetchResourceDetails(id, (url) => {
          if (isMounted) {
            setLastApiUrl(url);
          }
        });

        if (isMounted) {
          // Cast the response to ResourceData type
          setData(jsonData as unknown as ResourceData);
          setIsLoading(false);
        }
      } catch (err) {
        if (isMounted) {
          const message =
            err instanceof ApiError
              ? err.message
              : 'An unexpected error occurred while fetching item details';
          setError(message);
          setIsLoading(false);
        }
      }
    };

    loadItem();

    return () => {
      isMounted = false;
    };
  }, [id, prefetchedResource]); // eslint-disable-line react-hooks/exhaustive-deps -- setLastApiUrl is stable and intentionally excluded

  useEffect(() => {
    if (!data?.id) return;

    const trackingKey = [
      data.id,
      searchState?.searchId || 'direct',
      searchState?.currentPage || 0,
      absoluteCurrentIndex,
    ].join(':');

    if (trackedResourceViewRef.current === trackingKey) {
      return;
    }
    trackedResourceViewRef.current = trackingKey;

    scheduleAnalyticsBatch({
      events: [
        {
          event_type: 'resource_view',
          search_id: searchState?.searchId,
          resource_id: data.id,
          rank: searchState ? absoluteCurrentIndex + 1 : undefined,
          page: searchState?.currentPage,
          view: searchState?.view,
          source_component: 'ResourceView',
          properties: {
            search_url: searchState?.searchUrl,
            total_results: searchState?.totalResults,
            has_search_context: Boolean(searchState),
          },
        },
      ],
    });
  }, [absoluteCurrentIndex, data?.id, searchState]);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  if (error) {
    return <ErrorMessage message={error} />;
  }

  // Debug: Show loading state and data status
  if (!data) {
    return (
      <div className="min-h-screen flex flex-col">
        <Header />
        <main className="flex-1 bg-gray-50 pt-4 pb-8">
          <div className="w-full px-4 sm:px-6 lg:px-8">
            <div className="bg-yellow-100 border border-yellow-400 text-yellow-700 px-4 py-3 rounded">
              <strong>Debug:</strong> No data loaded yet. Loading:{' '}
              {isLoading.toString()}, Error: {error || 'none'}
            </div>
          </div>
        </main>
        <Footer />
      </div>
    );
  }

  // Temporarily comment out to debug data structure
  // const viewerProtocol = data?.data?.meta?.ui?.viewer?.protocol;
  // const viewerEndpoint = data?.data?.meta?.ui?.viewer?.endpoint;
  // const wxsIdentifier = data?.data?.attributes?.gbl_wxsidentifier_s;
  // const accessRights = data?.data?.attributes?.dct_accessrights_s;
  // const layerId = data?.data?.attributes?.id;
  // const geometry = data?.data?.meta?.ui?.viewer?.geometry;

  // Extract data from the new structure
  const viewerProtocol = data?.meta?.ui?.viewer?.protocol;
  const dataDictionaries = data?.attributes?.b1g?.data_dictionaries || [];

  // Open Graph / Twitter card image: prefer thumbnail; when none or placeholder, use static map when available
  const thumbnailUrl = data?.meta?.ui?.thumbnail_url;
  const isPlaceholderThumbnail =
    !thumbnailUrl ||
    (typeof thumbnailUrl === 'string' && thumbnailUrl.includes('placeholder'));
  const hasStaticMap = Boolean(data?.meta?.ui?.static_map && data?.id);
  const ogImage = !isPlaceholderThumbnail
    ? thumbnailUrl
    : hasStaticMap
      ? `/resources/${data.id}/static-map`
      : undefined;

  return (
    <div className="min-h-screen flex flex-col">
      {jsonLd && <ResourceJsonLd jsonLd={jsonLd} />}
      {data?.attributes && (
        <Seo
          title={data.attributes.ogm.dct_title_s}
          description={(() => {
            const desc = data.attributes.ogm.dct_description_sm;
            if (Array.isArray(desc)) {
              return desc[0] ?? '';
            }
            return typeof desc === 'string' ? desc : '';
          })()}
          image={ogImage}
          url={currentUrl}
          type="article"
        />
      )}
      <Header />

      <main className="flex-1 bg-gray-50 pt-4 pb-8">
        <div className="w-full px-4 sm:px-6 lg:px-8">
          {data?.attributes && (
            <>
              {/* Navigation bar - Stack elements on mobile */}
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 mb-2">
                <div className="lg:col-span-8 text-sm">
                  <ResourceBreadcrumbs item={data} />
                </div>

                <div className="lg:col-span-4 flex flex-wrap items-center gap-2 lg:gap-4 justify-between text-sm">
                  <Link
                    // IMPORTANT: Keep SSR + first client render stable (no location.state).
                    to={isMounted ? searchState?.searchUrl || '/' : '/'}
                    className="flex items-center justify-center text-gray-500 hover:text-blue-600 hover:bg-blue-50 rounded-full transition-colors px-2 py-1"
                    title="Back to Search Results"
                  >
                    <ArrowLeftCircle size={20} />
                    <span className="ml-1">Back</span>
                  </Link>

                  {isMounted && hasPreviousResults && (
                    <button
                      onClick={handlePrevClick}
                      className="flex items-center gap-1 text-gray-500 hover:text-blue-600"
                      title="Previous"
                    >
                      <ArrowLeft size={20} />
                      Prev
                    </button>
                  )}

                  {isMounted && searchState && (
                    <span className="text-gray-500 px-2">
                      {formatCount(displayIndex)} of{' '}
                      {formatCount(searchState.totalResults)}
                    </span>
                  )}

                  {isMounted && hasMoreResults && (
                    <button
                      onClick={handleNextClick}
                      className="flex items-center gap-1 text-gray-500 hover:text-blue-600"
                      title="Next"
                    >
                      Next
                      <ArrowRight size={20} />
                    </button>
                  )}

                  <Link
                    to="/"
                    className="flex items-center justify-center text-gray-500 hover:text-red-600 hover:bg-red-50 rounded-full transition-colors ml-2 px-2 py-1"
                    title="Clear Search"
                  >
                    <span className="mr-1">Clear</span>
                    <XCircle size={20} />
                  </Link>
                </div>
              </div>

              {/* Main content - Stack on mobile */}
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
                {/* Title section */}
                <div className="lg:col-span-8">
                  <h1 className="text-3xl font-bold text-gray-900">
                    {data.attributes.ogm.dct_title_s}
                  </h1>
                  <ResourceSubtitle item={data} />
                  {/* Display notes from OGM Aardvark (gbl_displayNote_sm) */}
                  {Array.isArray(data.attributes.ogm.gbl_displayNote_sm) &&
                    data.attributes.ogm.gbl_displayNote_sm.length > 0 && (
                      <DisplayNotes
                        notes={data.attributes.ogm.gbl_displayNote_sm}
                      />
                    )}
                </div>

                {/* Viewer section */}
                <div className="lg:col-span-8 space-y-6">
                  {viewerProtocol && (
                    <div className="bg-white rounded-lg shadow-md overflow-hidden">
                      <div className="">
                        <ResourceViewer data={data} pageValue="SHOW" />
                      </div>
                    </div>
                  )}

                  {/* Conditionally render the attribute table if the protocol is 'wms' or 'arcgis_feature_layer' */}
                  {(viewerProtocol === 'wms' ||
                    viewerProtocol === 'arcgis_feature_layer') && (
                    <AttributeTable />
                  )}
                  {viewerProtocol === 'open_index_map' && <IndexMap />}

                  {/* Add Full Details table */}
                  <FullDetailsTable
                    data={{ attributes: data.attributes, meta: data.meta }}
                  />
                </div>

                {/* Sidebar */}
                <div className="lg:col-span-4">
                  <div className="lg:sticky lg:top-[88px] space-y-6">
                    {/* Location Map - using geometry from viewer, original geometry, or locn_geometry */}
                    {(data?.meta?.ui?.viewer?.geometry ||
                      data?.attributes?.ogm?.locn_geometry_original ||
                      data?.attributes?.ogm?.locn_geometry) && (
                      <LocationMap
                        geometry={
                          (data?.meta?.ui?.viewer?.geometry ||
                            data?.attributes?.ogm?.locn_geometry_original ||
                            data?.attributes?.ogm?.locn_geometry) as
                            | string
                            | GeoJSON.Polygon
                            | GeoJSON.MultiPolygon
                            | { wkt: string }
                            | null
                        }
                      />
                    )}

                    {/* Downloads section */}
                    {data?.meta?.ui?.downloads &&
                      data.meta.ui.downloads.length > 0 && (
                        <DownloadsTable
                          downloads={data.meta.ui.downloads}
                          resourceId={data.id}
                          searchId={searchState?.searchId}
                        />
                      )}

                    {/* Data Dictionary link card (opens modal) */}
                    {dataDictionaries.length > 0 && (
                      <div className="bg-white rounded-lg shadow-md overflow-hidden">
                        <div className="px-6 py-4 bg-gray-50 border-b border-gray-200">
                          <h2 className="text-lg font-semibold text-gray-900">
                            Data Dictionary
                          </h2>
                        </div>
                        <div className="px-6 py-4">
                          <button
                            type="button"
                            onClick={() => setIsDataDictionaryModalOpen(true)}
                            className="text-sm font-medium text-blue-600 hover:text-blue-800 hover:underline"
                          >
                            Data Dictionaries ({dataDictionaries.length})
                          </button>
                        </div>
                      </div>
                    )}

                    {/* Links section */}
                    {data?.meta?.ui?.links &&
                      Object.keys(data.meta.ui.links).length > 0 && (
                        <LinksTable
                          links={data.meta.ui.links}
                          resourceId={data?.id}
                          searchId={searchState?.searchId}
                        />
                      )}

                    {/* Citation & Export */}
                    {data && (
                      <div className="mt-6">
                        <CitationTable
                          citation={data.meta?.ui?.citation ?? ''}
                          citations={data.meta?.ui?.citations}
                          permalink={isMounted ? window.location.href : ''}
                          resourceId={data.id}
                          searchId={searchState?.searchId}
                        />
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </>
          )}

          {/* Similar Items Carousel - Full width above footer */}
          {data?.meta?.ui?.similar_items &&
            Array.isArray(data.meta.ui.similar_items) &&
            data.meta.ui.similar_items.length > 0 && (
              <SimilarItemsCarousel
                similarItems={
                  data.meta.ui.similar_items as unknown as GeoDocument[]
                }
              />
            )}
        </div>
      </main>

      <Footer />

      {/* Environment navigation buttons - fixed position */}
      {id && <EnvironmentNavButtons resourceId={id} />}

      <LightboxModal
        isOpen={isDataDictionaryModalOpen}
        onClose={() => setIsDataDictionaryModalOpen(false)}
        id="resource-data-dictionaries-modal"
        labelledBy="resource-data-dictionaries-modal-title"
        title="Data Dictionaries"
        subtitle={data?.attributes?.ogm?.dct_title_s}
        contentClassName="max-w-7xl"
      >
        <div className="overflow-y-auto p-6">
          <DataDictionariesSection
            dictionaries={dataDictionaries}
            showContainer={false}
          />
        </div>
      </LightboxModal>
    </div>
  );
}

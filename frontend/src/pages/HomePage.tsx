import {
  useEffect,
  useMemo,
  useState,
  Suspense,
  lazy,
  type ReactNode,
} from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import { useTheme } from '../hooks/useTheme';
import { Header } from '../components/layout/Header';
import { Footer } from '../components/layout/Footer';
import { Seo } from '../components/Seo';
import { GinBlogSection } from '../components/home/GinBlogSection';
import { SanbornFeaturedCollection } from '../components/home/SanbornFeaturedCollection';
import { FacetMoreModal } from '../components/search/FacetMoreModal';

const HomePageHexMapBackground = lazy(() =>
  import('../components/home/HomePageHexMapBackground.client').then((m) => ({
    default: m.HomePageHexMapBackground,
  }))
);
import { ArrowRight, X } from 'lucide-react';
import { fetchHomeBlogPosts, fetchSearchResults } from '../services/api';
import { formatCount } from '../utils/formatNumber';
import { BTAA_PARTNER_INSTITUTIONS } from '../constants/partnerInstitutions';
import { getActiveThemeId } from '../config/institution';
import type { HomeBlogPost } from '../types/api';
import { normalizeFacetId } from '../utils/facetLabels';
import { normalizeFacetValueForUrl } from '../utils/searchParams';
import { primaryCtaClass, secondaryCtaClass } from '../styles/cta';

type FacetItem = { value: string; label: string; count: number };
type FacetLike = { attributes?: { items?: unknown } };

export function HomePage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { theme } = useTheme();
  const announcement = theme.homepage?.announcement;
  const showAnnouncement =
    !!announcement?.enabled &&
    !!announcement.text &&
    !!announcement.link_label &&
    !!announcement.link_url;
  const [resourceTypeList, setResourceTypeList] = useState<FacetItem[]>([]);
  const [placeList, setPlaceList] = useState<FacetItem[]>([]);
  const [creatorList, setCreatorList] = useState<FacetItem[]>([]);
  const [publisherList, setPublisherList] = useState<FacetItem[]>([]);
  const [resourceTypeFacetId, setResourceTypeFacetId] =
    useState('gbl_resourceType_sm');
  const [placeFacetId, setPlaceFacetId] = useState('dct_spatial_sm');
  const [creatorFacetId, setCreatorFacetId] = useState('dct_creator_sm');
  const [publisherFacetId, setPublisherFacetId] = useState('dct_publisher_sm');
  const [activeFacetModal, setActiveFacetModal] = useState<{
    id: string;
    label: string;
  } | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [blogLoading, setBlogLoading] = useState(true);
  const [blogError, setBlogError] = useState<string | null>(null);
  const [blogPosts, setBlogPosts] = useState<HomeBlogPost[]>([]);
  const [mounted, setMounted] = useState(false);
  const [showHeroDescription, setShowHeroDescription] = useState(true);
  useEffect(() => setMounted(true), []);
  const blogCfg = theme.homepage?.blog;
  const blogEnabled = blogCfg?.enabled === true;
  const blogPinnedSlugs = useMemo(
    () => blogCfg?.pinned_slugs ?? [],
    [blogCfg?.pinned_slugs]
  );
  const blogLimit = 3;

  function parseFacetItems(rawItems: unknown): FacetItem[] {
    const items: FacetItem[] = [];
    if (!Array.isArray(rawItems)) return items;
    if (rawItems.length > 0 && Array.isArray(rawItems[0])) {
      (rawItems as Array<[string | number, number]>).forEach(
        ([value, hits]) => {
          const v = String(value);
          items.push({ value: v, label: v, count: Number(hits) || 0 });
        }
      );
    } else {
      (rawItems as Array<{ attributes?: { value?: unknown; hits?: unknown; label?: unknown } }>).forEach((item) => {
        const value = item?.attributes?.value;
        const hits = item?.attributes?.hits;
        const label = item?.attributes?.label ?? value;
        if (value !== undefined) {
          items.push({
            value: String(value),
            label: String(label ?? value),
            count: Number(hits) || 0,
          });
        }
      });
    }
    return items;
  }

  function topItems(items: FacetItem[], limit: number): FacetItem[] {
    const cleanedItems = items.filter(
      (item) => item.value.trim().length > 0 && item.label.trim().length > 0
    );
    cleanedItems.sort((a, b) => b.count - a.count);
    return cleanedItems.slice(0, limit);
  }

  useEffect(() => {
    const fetchFacets = async () => {
      try {
        const results = await fetchSearchResults('', 1, 1);
        const resourceTypeFacet = results.included?.find(
          (item) =>
            item.type === 'facet' &&
            (item.id === 'gbl_resourceType_sm' ||
              item.id === 'resource_type_agg')
        );
        const placeFacet = results.included?.find(
          (item) =>
            item.type === 'facet' &&
            (item.id === 'dct_spatial_sm' || item.id === 'spatial_agg')
        );
        const creatorFacet = results.included?.find(
          (item) =>
            item.type === 'facet' &&
            (item.id === 'dct_creator_sm' || item.id === 'creator_agg')
        );
        const publisherFacet = results.included?.find(
          (item) =>
            item.type === 'facet' &&
            (item.id === 'dct_publisher_sm' || item.id === 'publisher_agg')
        );

        const resourceTypeItems = parseFacetItems(
          (resourceTypeFacet as FacetLike | undefined)?.attributes?.items
        );
        const placeItems = parseFacetItems(
          (placeFacet as FacetLike | undefined)?.attributes?.items
        );
        const creatorItems = parseFacetItems(
          (creatorFacet as FacetLike | undefined)?.attributes?.items
        );
        const publisherItems = parseFacetItems(
          (publisherFacet as FacetLike | undefined)?.attributes?.items
        );

        if (resourceTypeFacet?.id) setResourceTypeFacetId(resourceTypeFacet.id);
        if (placeFacet?.id) setPlaceFacetId(placeFacet.id);
        if (creatorFacet?.id) setCreatorFacetId(creatorFacet.id);
        if (publisherFacet?.id) setPublisherFacetId(publisherFacet.id);

        setResourceTypeList(topItems(resourceTypeItems, 5));
        setPlaceList(topItems(placeItems, 5));
        setCreatorList(topItems(creatorItems, 5));
        setPublisherList(topItems(publisherItems, 5));
      } catch (error) {
        console.error('Error fetching facets:', error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchFacets();
  }, []);

  useEffect(() => {
    const handleHeroDescriptionVisibility = (event: Event) => {
      const customEvent = event as CustomEvent<{ visible?: boolean }>;
      if (typeof customEvent.detail?.visible === 'boolean') {
        setShowHeroDescription(customEvent.detail.visible);
      }
    };
    window.addEventListener(
      'btaa-hero-description-visibility',
      handleHeroDescriptionVisibility as EventListener
    );
    return () => {
      window.removeEventListener(
        'btaa-hero-description-visibility',
        handleHeroDescriptionVisibility as EventListener
      );
    };
  }, []);

  useEffect(() => {
    if (!blogEnabled) {
      setBlogLoading(false);
      setBlogError(null);
      setBlogPosts([]);
      return;
    }

    const fetchBlogPosts = async () => {
      setBlogLoading(true);
      setBlogError(null);
      try {
        const response = await fetchHomeBlogPosts({
          limit: blogLimit,
          theme: getActiveThemeId(),
          pinnedSlugs: blogPinnedSlugs,
        });
        setBlogPosts(response.data || []);
      } catch (error) {
        console.error('Error fetching homepage blog posts:', error);
        setBlogPosts([]);
        setBlogError('Unable to load GIN stories right now.');
      } finally {
        setBlogLoading(false);
      }
    };

    fetchBlogPosts();
  }, [blogEnabled, blogLimit, blogPinnedSlugs]);

  const handleResourceTypeClick = (value: string) => {
    navigate(
      `/search?q=&include_filters[gbl_resourceType_sm][]=${encodeURIComponent(value)}`
    );
  };

  const handlePlaceClick = (value: string) => {
    navigate(
      `/search?q=&include_filters[dct_spatial_sm][]=${encodeURIComponent(value)}`
    );
  };

  const handleCreatorClick = (value: string) => {
    navigate(
      `/search?q=&include_filters[dct_creator_sm][]=${encodeURIComponent(value)}`
    );
  };

  const handlePublisherClick = (value: string) => {
    navigate(
      `/search?q=&include_filters[dct_publisher_sm][]=${encodeURIComponent(value)}`
    );
  };

  const handleBrowseAll = () => {
    navigate('/search?q=');
  };

  const handleFacetModalToggle = (
    field: string,
    value: string | number,
    type: 'include' | 'exclude'
  ) => {
    const normalizedField = normalizeFacetId(field);
    const normalizedValue = normalizeFacetValueForUrl(
      normalizedField,
      String(value)
    );
    const params = new URLSearchParams();
    params.set('q', '');
    params.append(
      `${type === 'include' ? 'include' : 'exclude'}_filters[${normalizedField}][]`,
      normalizedValue
    );
    navigate(`/search?${params.toString()}`);
  };

  const homepageSearchParams = useMemo(() => {
    const params = new URLSearchParams(searchParams);
    if (!params.has('q')) params.set('q', '');
    return params;
  }, [searchParams]);

  const renderFacetColumn = (
    title: string,
    facetId: string,
    items: FacetItem[],
    onClick: (value: string) => void,
    iconRenderer?: (value: string) => ReactNode
  ) => {
    return (
      <div>
        <h3 className="text-lg font-semibold text-gray-900 mb-3">{title}</h3>
        <div className="space-y-2">
          {items.map((item) => {
            const formattedCount = !isLoading ? formatCount(item.count) : '';
            const rowAriaLabel = !isLoading
              ? `${title} ${item.label}, ${formattedCount} resources`
              : `${title} ${item.label}`;

            return (
              <button
                key={`${title.toLowerCase()}-${item.value}`}
                onClick={() => onClick(item.value)}
                className="flex w-full items-center gap-2 border border-gray-200 border-l-[2px] border-l-[#003C5B] bg-white px-3 py-2 text-left transition-colors group hover:bg-slate-50"
                aria-label={rowAriaLabel}
              >
                <div className="flex w-full items-center gap-2">
                  {iconRenderer && (
                    <div className="shrink-0 text-gray-500">
                      {iconRenderer(item.value)}
                    </div>
                  )}
                  <span className="truncate text-gray-700">
                    {item.label}
                  </span>
                  <span className="ml-auto shrink-0 px-1.5 py-0.5 text-sm font-semibold tabular-nums text-gray-900">
                    {formattedCount}
                  </span>
                </div>
              </button>
            );
          })}
        </div>
        <button
          type="button"
          onClick={() => setActiveFacetModal({ id: facetId, label: title })}
          className={`${secondaryCtaClass} mt-3 px-3 py-1.5`}
        >
          View more
        </button>
      </div>
    );
  };

  return (
    <div className="min-h-screen flex flex-col">
      <Seo title="Big Ten Academic Alliance Geoportal" />
      {showAnnouncement && (
        <div className="bg-white text-gray-800 px-4 sm:px-6 lg:px-8 py-2 text-sm border-b border-gray-200">
          <p className="text-center">
            {announcement.text}{' '}
            <a
              href={announcement.link_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-brand-active underline underline-offset-2 hover:no-underline"
            >
              {announcement.link_label}
              <ArrowRight className="w-4 h-4" aria-hidden />
            </a>
          </p>
        </div>
      )}
      <Header />

      <main className="flex-1 bg-gray-50 flex flex-col">
        <h1 className="sr-only">{theme.institution.name}</h1>
        {/* Map hero sized to reveal the next section sooner */}
        <div className="flex-shrink-0 relative h-[calc(82vh-4rem)] min-h-[26rem] overflow-hidden">
          {mounted && (
            <Suspense fallback={null}>
              <HomePageHexMapBackground />
            </Suspense>
          )}
          {/* Description box - introduces the site; search is in header */}
          {showHeroDescription && (
            <div className="absolute inset-0 z-30 pointer-events-none flex items-start justify-center pt-20 pl-12 pr-4 sm:pt-4 sm:pl-6 sm:pr-6 lg:px-8">
              <div className="relative max-w-3xl w-full overflow-hidden bg-white/72 backdrop-blur-md p-6 lg:p-5 shadow-md pointer-events-auto">
                <div className="absolute inset-y-0 left-0 z-20 w-1.5 bg-[#003C5B]" />
                <div className="pointer-events-none absolute inset-y-0 left-1.5 right-0 z-0 bg-[linear-gradient(120deg,rgba(255,255,255,0.35)_0%,rgba(255,255,255,0.08)_60%,rgba(255,255,255,0)_100%)]" />
                <button
                  type="button"
                  onClick={() => setShowHeroDescription(false)}
                  className="absolute right-3 top-3 z-10 inline-flex h-7 w-7 items-center justify-center border border-gray-300 bg-white/90 text-gray-600 transition-colors hover:bg-white hover:text-gray-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-active"
                  aria-label="Hide map description"
                  title="Hide"
                >
                  <X className="h-4 w-4" />
                </button>
                <p className="relative z-10 text-xs font-semibold uppercase tracking-[0.14em] text-brand-primary">
                  BTAA Geoportal
                </p>
                <p className="relative z-10 mt-1 text-xl lg:text-2xl font-semibold text-gray-800">
                  {theme.institution.hero_text ||
                    'Search geospatial resources from Big Ten Academic Alliance institutions'}
                </p>
                <p className="relative z-10 text-sm text-gray-600 mt-2">
                  {theme.institution.hero_description ||
                    'Browse and download GIS data, maps, and other geospatial resources.'}
                </p>
              </div>
            </div>
          )}
        </div>
        <SanbornFeaturedCollection />
        {/* Browse All Resources section */}
        <div className="flex-shrink-0 w-full border-y border-gray-200 bg-white px-4 sm:px-6 lg:px-8 py-10">
          <div>
            <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
              <div className="max-w-2xl">
                <h2 className="text-2xl sm:text-3xl font-semibold text-gray-900">
                  Browse All Resources
                </h2>
              </div>
              <button
                onClick={handleBrowseAll}
                className={primaryCtaClass}
              >
                View all resources
                <ArrowRight className="h-4 w-4" />
              </button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
              {renderFacetColumn(
                'Resource Type',
                resourceTypeFacetId,
                resourceTypeList,
                handleResourceTypeClick
              )}
              {renderFacetColumn(
                'Place',
                placeFacetId,
                placeList,
                handlePlaceClick
              )}
              {renderFacetColumn(
                'Creator',
                creatorFacetId,
                creatorList,
                handleCreatorClick
              )}
              {renderFacetColumn(
                'Publisher',
                publisherFacetId,
                publisherList,
                handlePublisherClick
              )}
            </div>
          </div>
        </div>
        <section className="w-full border-t border-gray-200 bg-white px-4 sm:px-6 lg:px-8 py-10">
          <div className="w-full">
            <p className="text-xs font-semibold tracking-[0.16em] text-brand-primary uppercase text-center mb-2">
              Big Ten Academic Alliance Geoportal
            </p>
            <h2 className="text-2xl sm:text-3xl font-semibold text-gray-900 text-center mb-4">
              Partner Institutions
            </h2>

            <ul className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-9 gap-2">
              {BTAA_PARTNER_INSTITUTIONS.map((institution) => (
                <li
                  key={institution.name}
                  title={institution.name}
                  aria-label={`${institution.name} logo`}
                  className="group min-h-[64px] text-center"
                >
                  <div
                    className="flex h-full min-h-[64px] w-[88%] items-center justify-center border border-white/20 bg-[#003C5B] p-2 transition-colors group-hover:bg-[#002f49]"
                    style={{ clipPath: 'polygon(4% 0%, 100% 0%, 96% 100%, 0% 100%)' }}
                  >
                    <img
                      src={
                        institution.iconSrc ||
                        `/icons/${institution.iconSlug}.svg`
                      }
                      alt={`Logo for ${institution.name}`}
                      title={institution.name}
                      loading="lazy"
                      className={`w-auto object-contain ${
                        institution.iconSrc ? 'h-10' : 'h-8'
                      } ${
                        institution.monochrome === false
                          ? 'opacity-95'
                          : 'brightness-0 invert opacity-90'
                      }`}
                    />
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </section>
        {blogEnabled && (
          <div className="w-full">
            <GinBlogSection
              posts={blogPosts}
              loading={blogLoading}
              error={blogError}
              title={blogCfg?.title || 'BTAA-GIN News & Stories'}
              subtitle={blogCfg?.subtitle}
              ctaLabel={blogCfg?.cta_label || 'View all stories'}
              ctaUrl={blogCfg?.cta_url || 'https://gin.btaa.org/blog/'}
            />
          </div>
        )}
      </main>

      {activeFacetModal && (
        <FacetMoreModal
          facetId={activeFacetModal.id}
          facetLabel={activeFacetModal.label}
          isOpen
          onClose={() => setActiveFacetModal(null)}
          searchParams={homepageSearchParams}
          onToggleInclude={(value) =>
            handleFacetModalToggle(activeFacetModal.id, value, 'include')
          }
          onToggleExclude={(value) =>
            handleFacetModalToggle(activeFacetModal.id, value, 'exclude')
          }
          onToggleFacetInclude={(field, value) =>
            handleFacetModalToggle(field, value, 'include')
          }
          onToggleFacetExclude={(field, value) =>
            handleFacetModalToggle(field, value, 'exclude')
          }
          isValueIncluded={() => false}
          isValueExcluded={() => false}
        />
      )}

      <Footer />
    </div>
  );
}

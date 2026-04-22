import {
  useEffect,
  useMemo,
  useRef,
  useState,
  Suspense,
  lazy,
  type ReactNode,
} from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router';
import { useTheme } from '../hooks/useTheme';
import { Header } from '../components/layout/Header';
import { Footer } from '../components/layout/Footer';
import { Seo } from '../components/Seo';
import { GinBlogSection } from '../components/home/GinBlogSection';
import { HomepageFeaturedCollection } from '../components/home/HomepageFeaturedCollection';
import { FacetMoreModal } from '../components/search/FacetMoreModal';
import { LightboxModal } from '../components/ui/LightboxModal';

const HomePageHexMapBackground = lazy(() =>
  import('../components/home/HomePageHexMapBackground.client').then((m) => ({
    default: m.HomePageHexMapBackground,
  }))
);
import { ArrowRight, X } from 'lucide-react';
import { fetchFacetValues, fetchHomeBlogPosts } from '../services/api';
import { formatCount } from '../utils/formatNumber';
import {
  BTAA_PARTNER_INSTITUTIONS,
  getPartnerInstitutionSearchHref,
} from '../constants/partnerInstitutions';
import { getActiveThemeId } from '../config/institution';
import type { HomeBlogPost } from '../types/api';
import { normalizeFacetId } from '../utils/facetLabels';
import { normalizeFacetValueForUrl } from '../utils/searchParams';
import { primaryCtaClass, secondaryCtaClass } from '../styles/cta';

type FacetItem = { value: string; label: string; count: number };
const BTAA_VIDEO_MODAL_ID = 'btaa-video-modal';
const BTAA_VIDEO_MODAL_TITLE_ID = 'btaa-video-modal-title';
const BTAA_VIDEO_EMBED_URL =
  'https://www.youtube.com/embed/p060LdJodXQ?autoplay=1&rel=0';

function useSectionActivation<T extends HTMLElement>(rootMargin = '320px') {
  const ref = useRef<T | null>(null);
  const [active, setActive] = useState(false);

  useEffect(() => {
    if (active || typeof window === 'undefined') return;

    if (typeof window.IntersectionObserver !== 'function') {
      setActive(true);
      return;
    }

    const node = ref.current;
    if (!node) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setActive(true);
          observer.disconnect();
        }
      },
      { rootMargin, threshold: 0.01 }
    );

    observer.observe(node);
    return () => observer.disconnect();
  }, [active, rootMargin]);

  return { active, ref };
}

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
  const [themeList, setThemeList] = useState<FacetItem[]>([]);
  const [publisherList, setPublisherList] = useState<FacetItem[]>([]);
  const [resourceTypeFacetId, setResourceTypeFacetId] =
    useState('gbl_resourceType_sm');
  const [placeFacetId, setPlaceFacetId] = useState('dct_spatial_sm');
  const [themeFacetId, setThemeFacetId] = useState('dcat_theme_sm');
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
  const [isBtaaVideoOpen, setIsBtaaVideoOpen] = useState(false);
  useEffect(() => setMounted(true), []);
  const blogCfg = theme.homepage?.blog;
  const blogEnabled = blogCfg?.enabled === true;
  const blogLimit = 3;
  const browseSection = useSectionActivation<HTMLDivElement>('480px');
  const partnerSection = useSectionActivation<HTMLElement>('640px');
  const blogSection = useSectionActivation<HTMLDivElement>('480px');

  function facetValuesToItems(
    data: Array<{ attributes?: { value?: unknown; label?: unknown; hits?: number } }>
  ): FacetItem[] {
    const items: FacetItem[] = [];
    if (!Array.isArray(data)) return items;
    data.forEach((item) => {
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
    if (!browseSection.active) return;

    const fetchFacets = async () => {
      const searchParams = new URLSearchParams();
      searchParams.set('q', '');
      const facetIds = [
        'gbl_resourceType_sm',
        'dct_spatial_sm',
        'dcat_theme_sm',
        'dct_publisher_sm',
      ] as const;
      try {
        const [resourceTypeRes, placeRes, themeRes, publisherRes] =
          await Promise.all(
            facetIds.map((facetName) =>
              fetchFacetValues({
                facetName,
                searchParams,
                page: 1,
                perPage: 5,
                sort: 'count_desc',
              })
            )
          );

        const resourceTypeItems = facetValuesToItems(resourceTypeRes.data ?? []);
        const placeItems = facetValuesToItems(placeRes.data ?? []);
        const themeItems = facetValuesToItems(themeRes.data ?? []);
        const publisherItems = facetValuesToItems(publisherRes.data ?? []);

        setResourceTypeFacetId('gbl_resourceType_sm');
        setPlaceFacetId('dct_spatial_sm');
        setThemeFacetId('dcat_theme_sm');
        setPublisherFacetId('dct_publisher_sm');

        setResourceTypeList(topItems(resourceTypeItems, 5));
        setPlaceList(topItems(placeItems, 5));
        setThemeList(topItems(themeItems, 5));
        setPublisherList(topItems(publisherItems, 5));
      } catch (error) {
        console.error('Error fetching facets:', error);
      } finally {
        setIsLoading(false);
      }
    };

    void fetchFacets();
  }, [browseSection.active]);

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
    if (!blogSection.active) return;

    const fetchBlogPosts = async () => {
      setBlogLoading(true);
      setBlogError(null);
      try {
        const response = await fetchHomeBlogPosts({
          limit: blogLimit,
          theme: getActiveThemeId(),
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

    void fetchBlogPosts();
  }, [blogEnabled, blogLimit, blogSection.active]);

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

  const handleThemeClick = (value: string) => {
    navigate(
      `/search?q=&include_filters[dcat_theme_sm][]=${encodeURIComponent(value)}`
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
          {isLoading && items.length === 0
            ? Array.from({ length: 5 }, (_, index) => (
                <div
                  key={`${title.toLowerCase()}-skeleton-${index}`}
                  className="h-[46px] animate-pulse border border-gray-200 bg-slate-100"
                />
              ))
            : items.map((item) => {
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
        <HomepageFeaturedCollection />
        {/* Browse All Resources section */}
        <div
          ref={browseSection.ref}
          className="flex-shrink-0 w-full border-y border-gray-200 bg-white px-4 sm:px-6 lg:px-8 py-10"
        >
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
                'Theme',
                themeFacetId,
                themeList,
                handleThemeClick
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
        <section
          ref={partnerSection.ref}
          className="w-full border-t border-gray-200 bg-white px-4 sm:px-6 lg:px-8 py-10"
        >
          <div className="w-full">
            <p className="text-xs font-semibold tracking-[0.16em] text-brand-primary uppercase text-center mb-2">
              Big Ten Academic Alliance Geoportal
            </p>
            <h2 className="text-2xl sm:text-3xl font-semibold text-gray-900 text-center mb-4">
              Partner Institutions
            </h2>

            <ul className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-9 gap-2">
              {BTAA_PARTNER_INSTITUTIONS.map((institution) => {
                const searchHref = getPartnerInstitutionSearchHref(institution);
                const tileContent = (
                  <div
                    className="relative flex h-full min-h-[84px] w-full items-center justify-center overflow-hidden bg-[#003C5B] p-3"
                  >
                    {institution.campusMap &&
                      (partnerSection.active ? (
                        <img
                          src={`/institutions/${institution.slug}/static-map`}
                          alt=""
                          aria-hidden="true"
                          loading="lazy"
                          decoding="async"
                          fetchpriority="low"
                          className="pointer-events-none absolute inset-0 h-full w-full object-cover opacity-100 transition-transform duration-300 group-hover:scale-105"
                        />
                      ) : (
                        <div
                          aria-hidden="true"
                          className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_30%_35%,rgba(255,255,255,0.18),transparent_45%),linear-gradient(135deg,rgba(255,255,255,0.12),rgba(255,255,255,0.03))]"
                        />
                      ))}
                    <div className="relative z-10 flex items-center justify-center rounded-md bg-[#003C5B]/70 px-3 py-2 shadow-sm backdrop-blur-[1px] transition-colors group-hover:bg-[#003C5B]/78">
                      <img
                        src={
                          institution.iconSrc ||
                          `/icons/${institution.iconSlug}.svg`
                        }
                        alt={`Logo for ${institution.name}`}
                        title={institution.name}
                        loading="lazy"
                        className={`w-auto object-contain drop-shadow-[0_1px_2px_rgba(0,0,0,0.55)] ${institution.logoClassName || ''} ${
                          institution.iconSrc ? 'h-10' : 'h-8'
                        } ${
                          institution.monochrome === false
                            ? 'opacity-95'
                            : 'brightness-0 invert opacity-90'
                        }`}
                      />
                    </div>
                  </div>
                );

                return (
                  <li
                    key={institution.name}
                    title={institution.name}
                    className="group text-center"
                  >
                    {institution.slug === 'big-ten-academic-alliance' ? (
                      <button
                        type="button"
                        onClick={() => setIsBtaaVideoOpen(true)}
                        aria-label="Open Big Ten Academic Alliance video"
                        className="block h-full w-full focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-active focus-visible:ring-offset-2"
                      >
                        {tileContent}
                      </button>
                    ) : searchHref ? (
                      <Link
                        to={searchHref}
                        aria-label={`Search resources near ${institution.name}`}
                        className="block h-full focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-active focus-visible:ring-offset-2"
                      >
                        {tileContent}
                      </Link>
                    ) : (
                      tileContent
                    )}
                  </li>
                );
              })}
            </ul>
          </div>
        </section>
        {blogEnabled && (
          <div ref={blogSection.ref} className="w-full">
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

      <LightboxModal
        isOpen={isBtaaVideoOpen}
        onClose={() => setIsBtaaVideoOpen(false)}
        id={BTAA_VIDEO_MODAL_ID}
        labelledBy={BTAA_VIDEO_MODAL_TITLE_ID}
        title="Big Ten Academic Alliance video"
        subtitle="Watch the BTAA overview video."
        contentClassName="max-w-4xl"
        data-testid="btaa-video-modal-overlay"
      >
        <div className="aspect-video w-full bg-black">
          <iframe
            src={BTAA_VIDEO_EMBED_URL}
            title="Big Ten Academic Alliance overview video"
            className="h-full w-full"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
            referrerPolicy="strict-origin-when-cross-origin"
            allowFullScreen
          />
        </div>
      </LightboxModal>

      <Footer />
    </div>
  );
}

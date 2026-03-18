import { ArrowRight, ExternalLink } from 'lucide-react';
import { primaryCtaClass, secondaryCtaClass } from '../../styles/cta';

const SANBORN_COLLECTION_ID = 'b35f927e-9051-4d7f-9ca3-ad5b19024e0b';
const SANBORN_COLLECTION_URL = `/resources/${SANBORN_COLLECTION_ID}`;
const SANBORN_FEATURED_ITEM_URL =
  '/resources/1b831ef0-eed7-0137-6fec-02d0d7bfd6e4-3';
const SANBORN_FEATURED_ITEM_TITLE =
  'Centralia, Illinois Sanborn map sheet (1924)';
const SANBORN_SEARCH_URL = `/search?include_filters[pcdm_memberOf_sm][]=${encodeURIComponent(
  SANBORN_COLLECTION_ID
)}&view=gallery&per_page=20`;
const BTAA_HISTORICAL_MAPS_COLLECTION_ID =
  '64bd8c4c-8e60-4956-b43d-bdc3f93db488';
const BTAA_HISTORICAL_MAPS_COLLECTION_URL = `/resources/${BTAA_HISTORICAL_MAPS_COLLECTION_ID}`;
const BTAA_HISTORICAL_FEATURED_ITEM_URL =
  '/resources/a10a0f50-994e-0134-2096-0050569601ca-c';
const BTAA_HISTORICAL_FEATURED_ITEM_TITLE =
  "Chicago World's Fair pictorial map (1933)";
const BTAA_HISTORICAL_MAPS_SEARCH_URL = `/search?include_filters[pcdm_memberOf_sm][]=${encodeURIComponent(
  BTAA_HISTORICAL_MAPS_COLLECTION_ID
)}&view=gallery&per_page=20`;
const URBAN_BASE_LAYERS_COLLECTION_ID = 'b1g_urbanBaseLayers';
const URBAN_BASE_LAYERS_COLLECTION_URL =
  'https://geo.btaa.org/catalog/b1g_urbanBaseLayers';
const URBAN_BASE_LAYERS_FEATURED_ITEM_URL = '/resources/b1g_cUc3IBtJNisJ';
const URBAN_BASE_LAYERS_FEATURED_ITEM_TITLE =
  'Building footprints [Pennsylvania--Philadelphia] {2025}';
const URBAN_BASE_LAYERS_SEARCH_URL = `/search?include_filters[pcdm_memberOf_sm][]=${encodeURIComponent(
  URBAN_BASE_LAYERS_COLLECTION_ID
)}&view=gallery&per_page=20`;
const VIEW_ALL_COLLECTIONS_URL =
  '/search?q=&include_filters[gbl_resourceClass_sm][]=Collections';

type FeaturedCollection = {
  title: string;
  description: string;
  collectionUrl: string;
  browseUrl: string;
  browseLabel: string;
  featuredItemTitle: string;
  reverse?: boolean;
  imageTheme: 'sanborn' | 'historical' | 'urban';
};

const FEATURED_COLLECTIONS: FeaturedCollection[] = [
  {
    title: 'Sanborn Fire Insurance Maps',
    description:
      'Browse a large, detailed set of Sanborn maps from across the United States. Start with the collection record or jump straight into more than 15,000 indexed map sheets in gallery view.',
    collectionUrl: SANBORN_COLLECTION_URL,
    browseUrl: SANBORN_SEARCH_URL,
    browseLabel: 'Browse 15,000+ maps',
    featuredItemTitle: SANBORN_FEATURED_ITEM_TITLE,
    imageTheme: 'sanborn',
  },
  {
    title: 'Big Ten Academic Alliance Libraries Historical Maps Collection',
    description:
      'Explore historical maps curated from Big Ten Academic Alliance libraries. Use the collection record for context, then browse the full set in gallery mode.',
    collectionUrl: BTAA_HISTORICAL_MAPS_COLLECTION_URL,
    browseUrl: BTAA_HISTORICAL_MAPS_SEARCH_URL,
    browseLabel: 'Browse historical maps',
    featuredItemTitle: BTAA_HISTORICAL_FEATURED_ITEM_TITLE,
    imageTheme: 'historical',
    reverse: true,
  },
  {
    title: 'Urban Base Layers Collection',
    description:
      'Access foundational urban basemaps and reference layers for city-focused research and planning work across the BTAA Geoportal.',
    collectionUrl: URBAN_BASE_LAYERS_COLLECTION_URL,
    browseUrl: URBAN_BASE_LAYERS_SEARCH_URL,
    browseLabel: 'Browse urban base layers',
    featuredItemTitle: URBAN_BASE_LAYERS_FEATURED_ITEM_TITLE,
    imageTheme: 'urban',
  },
];

const TILTED_POLYGON_CLIP_PATH = 'polygon(3% 0%, 100% 0%, 97% 100%, 0% 100%)';

function TiltedPreviewCard({
  href,
  ariaLabel,
  imageSrc,
  imageAlt,
  featuredItemTitle,
}: {
  href: string;
  ariaLabel: string;
  imageSrc: string;
  imageAlt: string;
  featuredItemTitle: string;
}) {
  return (
    <div className="relative min-h-[220px] bg-slate-50">
      <a
        href={href}
        className="group relative block h-full w-full focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-active"
        aria-label={ariaLabel}
      >
        <div
          className="relative h-full w-full overflow-hidden"
          style={{ clipPath: TILTED_POLYGON_CLIP_PATH }}
        >
          <img
            src={imageSrc}
            alt={imageAlt}
            className="h-full w-full object-cover"
            loading="lazy"
          />
          <div className="pointer-events-none absolute inset-0 border border-white/20" />
          <div className="pointer-events-none absolute -left-[8%] top-[-12%] h-[150%] w-[1px] rotate-[14deg] bg-white/25" />
          <div className="pointer-events-none absolute -right-[6%] top-[-10%] h-[150%] w-[1px] rotate-[14deg] bg-white/20" />
          <div className="pointer-events-none absolute inset-x-0 bottom-0 h-20 bg-gradient-to-t from-black/75 to-transparent" />
          <div className="absolute inset-x-0 bottom-0 bg-[#003C5B]/90 px-4 py-3 shadow-md backdrop-blur-[1px]">
            <p className="text-sm font-semibold text-white">{featuredItemTitle}</p>
          </div>
        </div>
      </a>
    </div>
  );
}

function CollectionPreview({
  imageTheme,
  featuredItemTitle,
}: {
  imageTheme: FeaturedCollection['imageTheme'];
  featuredItemTitle: string;
}) {
  const isSanborn = imageTheme === 'sanborn';
  const isHistorical = imageTheme === 'historical';

  if (isSanborn) {
    return (
      <TiltedPreviewCard
        href={SANBORN_FEATURED_ITEM_URL}
        ariaLabel="View Sanborn featured item"
        imageSrc="/sanborn-featured-centralia.png"
        imageAlt="Sanborn map sheet for Centralia, Illinois"
        featuredItemTitle={featuredItemTitle}
      />
    );
  }

  if (isHistorical) {
    return (
      <TiltedPreviewCard
        href={BTAA_HISTORICAL_FEATURED_ITEM_URL}
        ariaLabel="View historical maps featured item"
        imageSrc="/historical-maps-featured.png"
        imageAlt="Illustrated historical city map from the BTAA historical maps collection"
        featuredItemTitle={featuredItemTitle}
      />
    );
  }

  if (imageTheme === 'urban') {
    return (
      <TiltedPreviewCard
        href={URBAN_BASE_LAYERS_FEATURED_ITEM_URL}
        ariaLabel="View urban base layers featured item"
        imageSrc="/urban-base-layers-featured.png"
        imageAlt="Building footprints map for Philadelphia, Pennsylvania"
        featuredItemTitle={featuredItemTitle}
      />
    );
  }

  return (
    <div className="relative overflow-hidden rounded-xl border border-slate-700/80 bg-[#040b15] p-6 min-h-[220px]">
      <div
        className="absolute inset-0 opacity-40 bg-[radial-gradient(circle_at_20%_20%,#1a5a73_0%,transparent_36%),radial-gradient(circle_at_80%_75%,#264f7b_0%,transparent_30%)]"
      />
      <div
        className="absolute inset-0 bg-[linear-gradient(90deg,rgba(58,79,110,0.22)_1px,transparent_1px),linear-gradient(rgba(58,79,110,0.2)_1px,transparent_1px)] bg-[size:36px_36px]"
      />
      <div
        className="absolute left-[14%] top-[20%] h-[34%] w-[26%] rounded-lg border border-slate-600/80 bg-slate-900/70"
      />
      <div
        className="absolute left-[44%] top-[35%] h-[38%] w-[32%] rounded-lg border border-slate-700/80 bg-slate-900/65"
      />
      <div
        className="absolute right-[10%] top-[16%] h-[28%] w-[14%] rounded-lg border border-slate-700/80 bg-slate-900/70"
      />
      <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/85 to-transparent px-4 py-3">
        <p className="text-sm font-medium text-white">{featuredItemTitle}</p>
      </div>
    </div>
  );
}

export function HomepageFeaturedCollection() {
  return (
    <section className="w-full bg-white px-4 py-10 sm:px-6 lg:px-8">
      <div className="w-full">
        <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
          <h2 className="text-2xl font-semibold text-gray-900 sm:text-3xl">
            Featured Collections
          </h2>
          <a
            href={VIEW_ALL_COLLECTIONS_URL}
            className={primaryCtaClass}
          >
            View all collections
            <ArrowRight className="h-4 w-4" />
          </a>
        </div>
        {FEATURED_COLLECTIONS.map((collection) => (
          <div
            key={collection.title}
            className="mb-6 grid gap-6 border border-slate-200 bg-slate-50 p-5 lg:grid-cols-5 lg:p-8"
          >
            <div
              className={`lg:col-span-3 ${
                collection.reverse ? 'lg:order-2' : ''
              }`}
            >
              <CollectionPreview
                imageTheme={collection.imageTheme}
                featuredItemTitle={collection.featuredItemTitle}
              />
            </div>
            <div
              className={`lg:col-span-2 flex flex-col justify-center ${
                collection.reverse ? 'lg:order-1' : ''
              }`}
            >
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                Featured Collection
              </p>
              <h2 className="mt-2 text-2xl font-semibold text-gray-900 sm:text-3xl">
                {collection.title}
              </h2>
              <p className="mt-3 max-w-xl text-sm text-gray-600 sm:text-base">
                {collection.description}
              </p>
              <div className="mt-5 flex flex-wrap gap-3">
                <a
                  href={collection.collectionUrl}
                  className={secondaryCtaClass}
                >
                  View collection record
                  <ExternalLink className="h-4 w-4" />
                </a>
                <a
                  href={collection.browseUrl}
                  className={primaryCtaClass}
                >
                  {collection.browseLabel}
                  <ArrowRight className="h-4 w-4" />
                </a>
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

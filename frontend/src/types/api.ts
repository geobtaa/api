export interface DataDictionaryEntry {
  id: number;
  resource_data_dictionary_id: number;
  friendlier_id: string;
  field_name: string;
  field_type?: string | null;
  values?: string | null;
  definition?: string | null;
  definition_source?: string | null;
  parent_field_name?: string | null;
  position: number;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface DataDictionary {
  id: number;
  friendlier_id: string;
  name?: string | null;
  description?: string | null;
  staff_notes?: string | null;
  tags: string;
  position: number;
  created_at?: string | null;
  updated_at?: string | null;
  entries: DataDictionaryEntry[];
}

export interface GeoDocument {
  id: string;
  type: string;
  attributes: {
    ogm: {
      id: string;
      dct_title_s: string;
      dct_creator_sm?: string[];
      dct_description_sm?: string[];
      dct_publisher_sm?: string[];
      dct_spatial_sm?: string[];
      gbl_resourceClass_sm?: string[];
      gbl_resourceType_sm?: string[];
      dct_language_sm?: string[];
      dcat_keyword_sm?: string[];
      schema_provider_s?: string;
      dct_accessRights_s?: string;
      dct_format_s?: string;
      dct_temporal_sm?: string[];
      dct_issued_s?: string;
      gbl_indexYear_im?: number[];
      gbl_indexyear_im?: number[];
      dct_references_s?: string | Record<string, string>;
      locn_geometry?: string;
      locn_geometry_original?: string;
      dcat_bbox?: string;
      dcat_centroid?: string;
      dcat_centroid_original?: string;
      dct_identifier_sm?: string[];
      gbl_mdVersion_s?: string;
      gbl_mdversion_s?: string;
      dct_alternative_sm?: string[];
      gbl_displayNote_sm?: string[];
      dcat_theme_sm?: string[];
      gbl_dateRange_drsim?: string[];
      pcdm_memberOf_sm?: string[];
      dct_isPartOf_sm?: string[];
      dct_rights_sm?: string[];
      gbl_wxsIdentifier_s?: string;
      dct_subjects_sm?: string[];
      dct_subject_sm?: string[];
      dc_publisher_sm?: string[];
      [key: string]: unknown;
    };
    b1g?: {
      b1g_code_s?: string;
      b1g_dct_accrualMethod_s?: string;
      b1g_dct_provenanceStatement_sm?: string[];
      date_created_dtsi?: string;
      geomg_id_s?: string;
      publication_state?: string;
      import_id?: string;
      data_dictionaries?: DataDictionary[];
      [key: string]: unknown;
    };
  };
  meta?: {
    ui?: {
      thumbnail_url?: string | null;
      resource_class_icon_url?: string | null;
      citation?: string;
      /** Citation formats: apa, mla, chicago */
      citations?: Record<string, string>;
      downloads?: Array<{
        label: string;
        url: string;
        type: string;
        format?: string;
        generated?: boolean;
        generation_path?: string;
        download_type?: string;
      }>;
      relationships?: Record<string, unknown>;
      relationship_counts?: Record<string, number>;
      relationship_browse_links?: Record<string, string>;
      summaries?: unknown[];
      ai_summaries?: unknown[];
      suggest?: {
        input: string[];
      };
      viewer?: {
        protocol?: string;
        endpoint?: string;
        geometry?: string | GeoJSON.Polygon | GeoJSON.MultiPolygon;
      };
      allmaps?: {
        allmaps_id?: string | null;
        allmaps_annotated?: boolean;
        allmaps_manifest_uri?: string | null;
        allmaps_annotation_url?: string;
      };
      /** URL for static map image when resource has geometry (used e.g. for og:image fallback) */
      static_map?: string | null;
    };
  };
}

export interface GeoDocumentDetails extends GeoDocument {
  // Additional fields specific to detailed view
  [key: string]: unknown;
}

export interface ParsedFacet {
  field: string;
  value: string;
}

type FacetItemTuple = [value: string | number, hits: number];

interface FacetItem {
  attributes: {
    label?: string;
    value: string | number;
    hits: number;
  };
  links?: {
    self: string;
  };
}

interface Facet {
  type: 'facet' | 'timeline';
  id: string;
  links?: {
    applyTemplate?: string;
  };
  attributes: {
    label: string;
    // Backend may return either legacy verbose items or compact tuples.
    items: FacetItem[] | FacetItemTuple[];
  };
}

export type FacetValuesSort =
  | 'count_desc'
  | 'count_asc'
  | 'alpha_asc'
  | 'alpha_desc';

export interface FacetValue {
  type: 'facet_value' | 'facet-item';
  id: string;
  attributes: {
    label?: string;
    value: string | number;
    hits: number;
  };
  links?: {
    self: string;
  };
}

export interface FacetValuesMeta {
  totalCount: number;
  totalPages: number;
  currentPage: number;
  perPage: number;
  facet?: {
    id: string;
    label: string;
  };
}

export interface FacetValuesResponse {
  jsonapi?: {
    version: string;
    profile: string[];
  };
  data: FacetValue[];
  links?: {
    self: string;
    next?: string;
    prev?: string;
    first?: string;
    last?: string;
  };
  meta: FacetValuesMeta;
}

export interface SortOption {
  type: 'sort';
  id: string;
  attributes: {
    label: string;
  };
  links: {
    self: string;
  };
}

export interface JsonApiResponse {
  jsonapi: {
    version: string;
    profile: string[];
  };
  links: {
    self: string;
    next?: string;
    first: string;
    last: string;
  };
  meta: {
    totalCount: number;
    totalPages: number;
    currentPage: number;
    perPage: number;
    query: string;
    sort?: string;
    query_time?: unknown;
    spellingSuggestions?: Array<{
      text: string;
      highlighted: string;
      score: number;
    }>;
  };
  data: Array<GeoDocument>;
  included?: Array<Facet | SortOption>;
}

export interface HomeBlogPost {
  slug: string;
  url: string;
  title: string;
  excerpt: string;
  published_at: string;
  category: 'post' | 'update';
  authors: string[];
  tags: string[];
  image_url: string | null;
  image_alt: string | null;
}

export interface HomeBlogPostsResponse {
  data: HomeBlogPost[];
  meta: {
    pinned_slugs: string[];
    total_count: number;
    fetched_at: string;
  };
}

interface SpellingSuggestion {
  text: string;
  highlighted: string;
  score: number;
}

interface SearchResponseMeta {
  pages: {
    current_page: number;
    next_page: number | null;
    prev_page: number | null;
    total_pages: number;
    limit_value: number;
    offset_value: number;
    total_count: number;
    first_page?: boolean;
    last_page?: boolean;
  };
  spellingSuggestions: SpellingSuggestion[];
}

export interface SearchResponse {
  response: {
    numFound: number;
    start: number;
    maxScore: number;
    docs: GeoDocument[];
  };
  facets: {
    [key: string]: FacetGroup;
  };
  sortOptions: SortOption[];
  meta: SearchResponseMeta;
}

export interface FacetGroup {
  label: string;
  items: Array<{
    label: string;
    value: string | number;
    hits: number;
    url: string;
  }>;
}

export interface GazetteerHierarchyItem {
  id: number;
  wok_id: number;
  ancestor_id: number;
  ancestor_placetype: string;
  lastmodified: number;
  created_at: string;
  updated_at: string;
  name: string | null;
}

export interface GazetteerPlaceAttributes {
  id: number;
  wok_id: number;
  parent_id: number;
  name: string;
  placetype: string;
  country: string;
  repo: string;
  latitude: number;
  longitude: number;
  min_latitude: number;
  min_longitude: number;
  max_latitude: number;
  max_longitude: number;
  is_current: number;
  is_deprecated: number;
  is_ceased: number;
  is_superseded: number;
  is_superseding: number;
  superseded_by: number | null;
  supersedes: number | null;
  lastmodified: number;
  created_at: string;
  updated_at: string;
  display_name?: string;
  hierarchy?: GazetteerHierarchyItem[];
  geojson?: GeoJSON.Feature;
}

export interface GazetteerPlace {
  id: string;
  type: string;
  attributes: GazetteerPlaceAttributes;
}

export interface GazetteerResponse {
  jsonapi: {
    version: string;
    profile: string[];
  };
  links: {
    self: string;
    next?: string;
    prev?: string;
    first?: string;
    last?: string;
  };
  meta: {
    totalCount: number;
    totalPages: number;
    currentPage: number;
    perPage: number;
    query: string;
    offset: number;
    gazetteer: string;
  };
  data: GazetteerPlace[];
}

// Nominatim API types
export interface NominatimResult {
  place_id: number;
  licence: string;
  osm_type: string;
  osm_id: number;
  lat: string;
  lon: string;
  class: string;
  type: string;
  place_rank: number;
  importance: number;
  addresstype?: string;
  name: string;
  display_name: string;
  boundingbox: [string, string, string, string]; // [min_lat, max_lat, min_lon, max_lon]
}

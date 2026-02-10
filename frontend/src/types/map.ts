export type ZoomLevel = 'country' | 'region' | 'county' | 'hex';

export interface GeoFacetItem {
  attributes: {
    label: string;
    value: string;
    hits: number;
  };
  links: {
    self: string;
  };
}

export interface GeoFacet {
  type: 'facet';
  id: string;
  attributes: {
    label: string;
    items: GeoFacetItem[];
  };
}

export interface ChoroplethData {
  country: GeoFacetItem[];
  region: GeoFacetItem[];
  county: GeoFacetItem[];
}

// GeoJSON feature types for map components
export interface GeoJsonFeature {
  type: 'Feature';
  properties: {
    name?: string;
    NAME?: string;
    ADMIN?: string;
    state?: string;
    county?: string;
    STATE?: string;
    STATEFP?: string;
    [key: string]: unknown;
  };
  geometry: {
    type: string;
    coordinates: unknown;
  };
}

export interface GeoJsonData {
  type: 'FeatureCollection';
  features: GeoJsonFeature[];
}

export interface MapFeatureClickPayload {
  properties: {
    name: string;
    hits: number;
  };
}

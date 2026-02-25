// Labels keyed by field-named facet IDs (new API)
export const FACET_LABELS: Record<string, string> = {
  dct_spatial_sm: 'Place',
  time_period: 'Time Period',
  gbl_resourceClass_sm: 'Resource Class',
  gbl_resourceType_sm: 'Resource Type',
  schema_provider_s: 'Provider',
  dct_creator_sm: 'Creator',
  dct_publisher_sm: 'Publisher',
  dct_accessRights_s: 'Access',
  gbl_indexyear_im: 'Year',
  dct_language_sm: 'Language',
  dct_subject_sm: 'Subject',
  dct_subjects_sm: 'Subject',
  dcat_theme_sm: 'Theme',
  gbl_georeferenced_b: 'Georeferenced',
  // Relationship / collection filters (Active Filters display)
  dct_isPartOf_sm: 'Is part of',
  pcdm_memberOf_sm: 'Collection records',
  b1g_localCollectionLabel_sm: 'Local collection',
};

// Backward-compat mapping for legacy *_agg IDs to new field IDs
export const FACET_ID_MAP: Record<string, string> = {
  spatial_agg: 'dct_spatial_sm',
  resource_class_agg: 'gbl_resourceClass_sm',
  resource_type_agg: 'gbl_resourceType_sm',
  provider_agg: 'schema_provider_s',
  creator_agg: 'dct_creator_sm',
  publisher_agg: 'dct_publisher_sm',
  access_rights_agg: 'dct_accessRights_s',
  access_agg: 'dct_accessRights_s',
  index_year_agg: 'gbl_indexyear_im',
  language_agg: 'dct_language_sm',
  subject_agg: 'dct_subject_sm',
  institution_agg: 'schema_provider_s',
  format_agg: 'dct_format_s',
  georeferenced_agg: 'gbl_georeferenced_b',
};

export function normalizeFacetId(id: string): string {
  return FACET_ID_MAP[id] || id;
}

export function getFacetLabel(field: string): string {
  const normalized = normalizeFacetId(field);
  return FACET_LABELS[normalized] || normalized;
}

// Reverse mapping: convert field names to legacy facet names for API endpoints
// Note: Both provider_agg and institution_agg map to schema_provider_s in the forward direction,
// but for reverse mapping we use provider_agg as the primary legacy name
const REVERSE_FACET_ID_MAP: Record<string, string> = {
  dct_spatial_sm: 'spatial_agg',
  gbl_resourceClass_sm: 'resource_class_agg',
  gbl_resourceType_sm: 'resource_type_agg',
  schema_provider_s: 'provider_agg',
  dct_creator_sm: 'creator_agg',
  dct_publisher_sm: 'publisher_agg',
  dct_accessRights_s: 'access_rights_agg',
  gbl_indexyear_im: 'index_year_agg',
  dct_language_sm: 'language_agg',
  dct_subject_sm: 'subject_agg',
  dct_format_s: 'format_agg',
  gbl_georeferenced_b: 'georeferenced_agg',
};

export function getLegacyFacetName(fieldName: string): string {
  return REVERSE_FACET_ID_MAP[fieldName] || fieldName;
}

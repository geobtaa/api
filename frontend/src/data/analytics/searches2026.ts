import zeroResultQueries from './zeroResultQueries2026.json';

// July/August facet aggregates exported September 9; query rankings September 10, 2026.
// Facet counts deduplicate search IDs across include/exclude and legacy f/fq keys.
export const searchSnapshots = {
  '2026-07': {
    zeroQueries: zeroResultQueries.months['2026-07'].zeroQueries,
    zeroQueryCoverage: {
      exportedAt: zeroResultQueries.exportedAt,
      rankingLimit: zeroResultQueries.rankingLimit,
      minimumZeroResults: zeroResultQueries.minimumZeroResults,
      distinctQueries: zeroResultQueries.months['2026-07'].distinctQueries,
      rankedZeroResults: zeroResultQueries.months['2026-07'].rankedZeroResults,
    },
    facets: [
      {
        field: 'geo',
        count: 1766,
      },
      {
        field: 'gbl_resourceClass_sm',
        count: 1521,
      },
      {
        field: 'dct_spatial_sm',
        count: 895,
      },
      {
        field: 'year_range',
        count: 582,
      },
      {
        field: 'gbl_resourceType_sm',
        count: 387,
      },
      {
        field: 'pcdm_memberOf_sm',
        count: 261,
      },
      {
        field: 'dct_isPartOf_sm',
        count: 167,
      },
      {
        field: 'b1g_localCollectionLabel_sm',
        count: 97,
      },
      {
        field: 'dct_publisher_sm',
        count: 78,
      },
      {
        field: 'b1g_code_s',
        count: 70,
      },
      {
        field: 'schema_provider_s',
        count: 67,
      },
      {
        field: 'dct_subject_sm',
        count: 37,
      },
      {
        field: 'dcat_theme_sm',
        count: 32,
      },
      {
        field: 'dct_issued_s',
        count: 32,
      },
      {
        field: 'gbl_georeferenced_b',
        count: 14,
      },
      {
        field: 'dct_accessRights_s',
        count: 13,
      },
      {
        field: 'b1g_language_sm',
        count: 10,
      },
      {
        field: 'b1g_georeferenced_allmaps_b',
        count: 6,
      },
      {
        field: 'h3_res2',
        count: 5,
      },
      {
        field: 'dct:isSourceOf_agg',
        count: 4,
      },
      {
        field: 'dct:sourceOf_agg',
        count: 3,
      },
      {
        field: 'h3_res7',
        count: 3,
      },
      {
        field: 'time_period',
        count: 3,
      },
      {
        field: 'dct_provenance_s',
        count: 1,
      },
      {
        field: 'h3_res4',
        count: 1,
      },
    ],
    searches: 6457,
  },
  '2026-08': {
    zeroQueries: zeroResultQueries.months['2026-08'].zeroQueries,
    zeroQueryCoverage: {
      exportedAt: zeroResultQueries.exportedAt,
      rankingLimit: zeroResultQueries.rankingLimit,
      minimumZeroResults: zeroResultQueries.minimumZeroResults,
      distinctQueries: zeroResultQueries.months['2026-08'].distinctQueries,
      rankedZeroResults: zeroResultQueries.months['2026-08'].rankedZeroResults,
    },
    facets: [
      {
        field: 'geo',
        count: 1727,
      },
      {
        field: 'gbl_resourceClass_sm',
        count: 1515,
      },
      {
        field: 'dct_spatial_sm',
        count: 954,
      },
      {
        field: 'pcdm_memberOf_sm',
        count: 643,
      },
      {
        field: 'year_range',
        count: 546,
      },
      {
        field: 'gbl_resourceType_sm',
        count: 451,
      },
      {
        field: 'dct_publisher_sm',
        count: 150,
      },
      {
        field: 'b1g_code_s',
        count: 145,
      },
      {
        field: 'b1g_localCollectionLabel_sm',
        count: 130,
      },
      {
        field: 'schema_provider_s',
        count: 118,
      },
      {
        field: 'dct_isPartOf_sm',
        count: 108,
      },
      {
        field: 'dct_issued_s',
        count: 103,
      },
      {
        field: 'dcat_theme_sm',
        count: 41,
      },
      {
        field: 'dct_subject_sm',
        count: 34,
      },
      {
        field: 'b1g_language_sm',
        count: 21,
      },
      {
        field: 'dct_accessRights_s',
        count: 18,
      },
      {
        field: 'gbl_georeferenced_b',
        count: 16,
      },
      {
        field: 'dct_creator_sm',
        count: 15,
      },
      {
        field: 'b1g_georeferenced_allmaps_b',
        count: 9,
      },
      {
        field: 'h3_res5',
        count: 2,
      },
      {
        field: 'time_period',
        count: 1,
      },
    ],
    searches: 7545,
  },
} as const;

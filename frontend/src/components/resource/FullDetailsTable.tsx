import React, { useState, useEffect } from 'react';
import { Link } from 'react-router';
import {
  humanizeFieldName,
  isFieldHidden,
  shouldDisplayField,
  getFacetField,
} from '../../constants/fieldLabels';
import { formatCount } from '../../utils/formatNumber';

// Define a type for the attributes
interface Attributes {
  [key: string]: unknown;
}

interface FullDetailsTableProps {
  data: {
    attributes: {
      ogm: Attributes;
      b1g?: Attributes;
    };
    meta?: {
      ui?: {
        relationships?: Record<string, unknown>;
      };
    };
  };
}

const relationshipLabels: { [key: string]: string } = {
  memberOf: 'Belongs to collection...',
  'pcdm:memberOf': 'Belongs to collection...',
  hasMember: 'Collection records...',
  isPartOf: 'Is part of...',
  'dct:isPartOf': 'Is part of...',
  hasPart: 'Has part...',
  relation: 'Related records...',
  'dct:relation': 'Related records...',
  replaces: 'Replaces...',
  isReplacedBy: 'Is replaced by...',
  isSourceOf: 'Source records...',
  source: 'Derived records...',
  isVersionOf: 'Is version of...',
  hasVersion: 'Has version...',
  browse_all_no_count: 'Browse all records...',
  browse_all: 'Browse all %{count} records...',
};

export function FullDetailsTable({ data }: FullDetailsTableProps) {
  // Merge ogm and b1g attributes for display
  const attributes = {
    ...(data?.attributes?.ogm || {}),
    ...(data?.attributes?.b1g || {}),
  };
  const uiRelationships = data?.meta?.ui?.relationships || {};
  const [isPlaceExpanded, setIsPlaceExpanded] = useState(false);

  // Reset expanded state when data changes
  useEffect(() => {
    setIsPlaceExpanded(false);
  }, [data]);

  // Define the fields for the Document Metadata table - BTAA schema only
  const documentMetadataFields = [
    // Core fields (Required by BTAA)
    'gbl_mdVersion_s',
    'dct_title_s',
    'dct_description_sm',
    'dct_language_sm',
    'dct_accessRights_s',
    'dct_license_sm',
    'b1g_code_s',
    'b1g_dct_accrualMethod_s',
    'b1g_dateAccessioned_s',
    'b1g_publication_state_s',
    'b1g_language_sm',

    // Additional BTAA fields
    'gbl_mdModified_dt',
    'dct_alternative_sm',
    'dct_subject_sm',
    'dct_creator_sm',
    'dct_publisher_sm',
    'dct_source_sm',
    'dct_isPartOf_sm',
    'pcdm_memberOf_sm',
    'dct_replaces_sm',
    'dct_isReplacedBy_sm',
    'dct_isVersionOf_sm',
    'dct_relation_sm',
    'dct_issued_s',
    'dct_temporal_sm',
    'solr_year_i',
    'layer_id_s',
    'suppressed_b',
    'dct_references_s',

    // BTAA custom fields
    'b1g_status_s',
    'b1g_dct_accrualPeriodicity_s',
    'b1g_dateRetired_s',
    'b1g_child_record_b',
    'b1g_dct_mediator_sm',
    'b1g_access_s',
    'b1g_image_ss',
    'b1g_geonames_sm',
    'b1g_creatorID_sm',
    'b1g_dct_conformsTo_sm',
    'b1g_dcat_spatialResolutionInMeters_sm',
    'b1g_geodcat_spatialResolutionAsText_sm',
    'b1g_dct_provenanceStatement_sm',
    'b1g_adminTags_sm',
  ];

  // Define the fields for the Metadata Facets table - BTAA schema only
  const metadataFacetsFields = [
    'gbl_resourceClass_sm',
    'gbl_resourceType_sm',
    'dcat_theme_sm',
    'dct_spatial_sm',
    'schema_provider_s',
    'b1g_localCollectionLabel_sm',
  ];

  // Define the relationship fields for the Metadata Facets table - BTAA schema only
  const relationshipFields = [
    'dct_relation_sm',
    'pcdm_memberOf_sm',
    'dct_isPartOf_sm',
    'dct_source_sm',
    'dct_isVersionOf_sm',
    'dct_replaces_sm',
    'dct_isReplacedBy_sm',
    'dct_references_s',
    'dct_license_sm',
    'dct_rightsHolder_sm',
    'b1g_dct_mediator_sm',
    'b1g_creatorID_sm',
    'b1g_dct_conformsTo_sm',
  ];

  // Custom field labels for better display - BTAA schema only
  const customFieldLabels: { [key: string]: string } = {
    // Core fields (Required by BTAA)
    id: 'ID',
    gbl_mdVersion_s: 'Metadata Version',
    schema_provider_s: 'Provider',
    dct_title_s: 'Title',
    dct_description_sm: 'Description',
    dct_language_sm: 'Language',
    dct_accessRights_s: 'Access Rights',
    dct_license_sm: 'License',
    b1g_code_s: 'BTAA Code',
    b1g_dct_accrualMethod_s: 'Accrual Method',
    b1g_dateAccessioned_s: 'Date Accessioned',
    b1g_publication_state_s: 'Publication State',
    b1g_language_sm: 'BTAA Language',

    // Additional BTAA fields
    gbl_mdModified_dt: 'Metadata Modified',
    dct_alternative_sm: 'Alternative Title',
    dct_subject_sm: 'Subject',
    dct_creator_sm: 'Creator',
    dct_publisher_sm: 'Publisher',
    gbl_resourceClass_sm: 'Resource Class',
    gbl_resourceType_sm: 'Resource Type',
    dct_source_sm: 'Source',
    dct_isPartOf_sm: 'Is Part Of',
    pcdm_memberOf_sm: 'Belongs to collection...',
    dct_replaces_sm: 'Replaces',
    dct_isReplacedBy_sm: 'Is Replaced By',
    dct_isVersionOf_sm: 'Is Version Of',
    dct_relation_sm: 'Related records...',
    dct_issued_s: 'Date Issued',
    dct_temporal_sm: 'Temporal Coverage',
    dct_spatial_sm: 'Spatial Coverage',
    dcat_bbox: 'Bounding Box',
    dcat_centroid: 'Centroid',
    locn_geometry: 'Geometry',
    layer_geom_type_s: 'Layer Geometry Type',
    solr_year_i: 'Year',
    layer_id_s: 'Layer ID',
    suppressed_b: 'Suppressed',
    dct_references_s: 'References',

    // BTAA custom fields
    b1g_status_s: 'Status',
    b1g_dct_accrualPeriodicity_s: 'Accrual Periodicity',
    b1g_dateRetired_s: 'Date Retired',
    b1g_child_record_b: 'Child Record',
    b1g_dct_mediator_sm: 'Mediator',
    b1g_access_s: 'Access',
    b1g_image_ss: 'Image',
    b1g_geonames_sm: 'Geonames',
    b1g_creatorID_sm: 'Creator ID',
    b1g_dct_conformsTo_sm: 'Conforms To',
    b1g_dcat_spatialResolutionInMeters_sm: 'Spatial Resolution (Meters)',
    b1g_geodcat_spatialResolutionAsText_sm: 'Spatial Resolution (Text)',
    b1g_dct_provenanceStatement_sm: 'Provenance Statement',
    b1g_adminTags_sm: 'Admin Tags',
  };

  // Group fields by their prefix/category
  const groupFields = () => {
    const entries = Object.entries(attributes).filter(
      ([key, value]) =>
        value !== null &&
        value !== undefined &&
        value !== '' &&
        !key.startsWith('ui_') &&
        !isFieldHidden(key) &&
        shouldDisplayField(key)
    );

    // Separate fields into:
    // Document Metadata, Metadata Facets, and Relationship Facets
    const documentMetadata = entries.filter(([key]) =>
      documentMetadataFields.includes(key)
    );
    const metadataFacets = entries
      .filter(([key]) => metadataFacetsFields.includes(key))
      .sort(([a], [b]) => {
        const indexA = metadataFacetsFields.indexOf(a);
        const indexB = metadataFacetsFields.indexOf(b);
        return indexA - indexB;
      });
    const relationshipFacets = entries.filter(([key]) =>
      relationshipFields.includes(key)
    );
    return { documentMetadata, metadataFacets, relationshipFacets };
  };

  const renderPlaceValues = (
    value: string | string[] | null | undefined,
    shouldLink: boolean = false
  ) => {
    // Return empty string for null or undefined values
    if (value === null || value === undefined) {
      return '';
    }

    const placeArray = Array.isArray(value) ? value : [value.toString()];
    const facetField = getFacetField('dct_spatial_sm');
    const maxInitial = 15;
    const hasMore = placeArray.length > maxInitial;
    const displayPlaces = isPlaceExpanded
      ? placeArray
      : placeArray.slice(0, maxInitial);

    return (
      <>
        {displayPlaces.map((place, i) => (
          <React.Fragment key={place}>
            {i > 0 && ', '}
            {facetField && shouldLink ? (
              <Link
                to={`/search?fq[${facetField}][]=${encodeURIComponent(place)}`}
                className="text-blue-600 hover:text-blue-800"
              >
                {place}
              </Link>
            ) : (
              <span>{place}</span>
            )}
          </React.Fragment>
        ))}
        {hasMore && (
          <>
            {!isPlaceExpanded && (
              <>
                {' '}
                <button
                  onClick={() => setIsPlaceExpanded(true)}
                  className="text-blue-600 hover:text-blue-800 underline text-sm ml-1"
                  aria-label={`Show ${placeArray.length - maxInitial} more places`}
                >
                  Show {placeArray.length - maxInitial} more
                </button>
              </>
            )}
            {isPlaceExpanded && (
              <>
                {' '}
                <button
                  onClick={() => setIsPlaceExpanded(false)}
                  className="text-blue-600 hover:text-blue-800 underline text-sm ml-1"
                  aria-label="Show fewer places"
                >
                  Show less
                </button>
              </>
            )}
          </>
        )}
      </>
    );
  };

  const renderValue = (
    key: string,
    value: string | string[] | null | undefined,
    shouldLink: boolean = false
  ) => {
    // Return empty string for null or undefined values
    if (value === null || value === undefined) {
      return '';
    }

    // Special handling for Place values (dct_spatial_sm) with collapse/expand
    if (key === 'dct_spatial_sm' && Array.isArray(value) && value.length > 15) {
      return renderPlaceValues(value, shouldLink);
    }

    // Special formatting for specific fields
    if (key === 'dct_language_sm') {
      const languageMap: { [key: string]: string } = {
        eng: 'English',
        English: 'English',
        spa: 'Spanish',
        Spanish: 'Spanish',
        fra: 'French',
        French: 'French',
        deu: 'German',
        German: 'German',
        ita: 'Italian',
        Italian: 'Italian',
        por: 'Portuguese',
        Portuguese: 'Portuguese',
        rus: 'Russian',
        Russian: 'Russian',
        jpn: 'Japanese',
        Japanese: 'Japanese',
        kor: 'Korean',
        Korean: 'Korean',
        zho: 'Chinese',
        Chinese: 'Chinese',
        ara: 'Arabic',
        Arabic: 'Arabic',
      };
      if (Array.isArray(value)) {
        return value.map((v) => languageMap[v] || v).join(', ');
      }
      return languageMap[value.toString()] || value.toString();
    }

    // Format boolean fields
    if (
      (key === 'suppressed_b' || key === 'b1g_child_record_b') &&
      value !== null &&
      value !== undefined
    ) {
      return value.toString() === 'true' ? 'Yes' : 'No';
    }

    // Format date fields to be more readable
    if (
      (key === 'b1g_dateAccessioned_s' ||
        key === 'b1g_dateRetired_s' ||
        key === 'gbl_mdModified_dt' ||
        key === 'dct_issued_s') &&
      value
    ) {
      try {
        // IMPORTANT: make this deterministic across SSR/client.
        // Manually parse YYYY-MM-DD to avoid `new Date(string)` ambiguity and timezone offsets.
        // We strictly interpret the date string as UTC YYYY-MM-DD.
        const valStr = value.toString();
        // Match YYYY-MM-DD pattern (stripping time if present)
        const match = valStr.match(/^(\d{4})-(\d{2})-(\d{2})/);

        if (match) {
          const [_, yearStr, monthStr, dayStr] = match;
          const date = new Date(
            Date.UTC(
              parseInt(yearStr, 10),
              parseInt(monthStr, 10) - 1, // Month is 0-indexed
              parseInt(dayStr, 10)
            )
          );

          if (!isNaN(date.getTime())) {
            return date.toLocaleDateString('en-US', {
              timeZone: 'UTC',
              year: 'numeric',
              month: 'long',
              day: 'numeric',
            });
          }
        }

        // Fallback for non-matching strings (e.g. just Year "2024")
        const date = new Date(valStr);
        if (!isNaN(date.getTime())) {
          // For fallback, also force UTC to be safe, assuming input is UTC-ish
          return date.toLocaleDateString('en-US', {
            timeZone: 'UTC',
            year: 'numeric',
            month: 'long',
            day: 'numeric',
          });
        }
      } catch {
        // Fall back to original value if date parsing fails
      }
    }

    const facetField = getFacetField(key);

    if (facetField && shouldLink) {
      if (Array.isArray(value)) {
        return value.map((v, i) => (
          <React.Fragment key={v}>
            {i > 0 && ', '}
            <Link
              to={`/search?fq[${facetField}][]=${encodeURIComponent(v)}`}
              className="text-blue-600 hover:text-blue-800"
            >
              {v}
            </Link>
          </React.Fragment>
        ));
      }
      return (
        <Link
          to={`/search?fq[${facetField}][]=${encodeURIComponent(value)}`}
          className="text-blue-600 hover:text-blue-800"
        >
          {value.toString()}
        </Link>
      );
    }

    return Array.isArray(value) ? value.join(', ') : value.toString();
  };

  const renderRelationships = (relationships: Record<string, unknown>) => {
    // Check if relationships exists and has properties
    if (!relationships || Object.keys(relationships).length === 0) {
      return null;
    }

    return Object.entries(relationships)
      .map(([relationshipType, items]) => {
        if (!Array.isArray(items) || items.length === 0) return null;

        // Get the total count of items
        const totalCount = items.length;

        // Only display the first 5 items
        const displayItems = items.slice(0, 5);

        // Determine if we need to show the "Browse all" link
        const showBrowseAll = totalCount > 5;

        // Map relationship type to its corresponding facet field if it exists
        // This would depend on how your search system handles relationship facets
        // For example: memberOf -> member_of_agg, source -> source_agg, etc.
        const relationshipFacetField = `${relationshipType}_agg`;

        // Get the ID of the current item to use as a filter
        // Ensure it's a string value for encodeURIComponent
        const currentItemId = String(attributes.id || '');

        return (
          <div key={relationshipType} className="mb-4">
            <h5 className="text-sm font-medium text-gray-500">
              {relationshipLabels[relationshipType] ||
                humanizeFieldName(relationshipType)}
            </h5>
            <ul className="list-none">
              {/* Display the first 5 items */}
              {displayItems.map(
                (doc: {
                  resource_id?: string;
                  item_id?: string;
                  resource_title?: string;
                  item_title?: string;
                  link?: string;
                }) => {
                  const id = doc.resource_id || doc.item_id;
                  const title = doc.resource_title || doc.item_title;
                  return (
                    <li key={id} className="text-sm text-gray-900">
                      <Link
                        to={`/resources/${id}`}
                        className="text-blue-600 hover:text-blue-800"
                      >
                        {title}
                      </Link>
                    </li>
                  );
                }
              )}

              {/* Show "Browse all" link if there are more than 5 items */}
              {showBrowseAll && (
                <li className="text-sm text-gray-900 mt-2 pt-2 border-t border-gray-200">
                  <Link
                    to={`/search?fq[${relationshipFacetField}][]=${encodeURIComponent(currentItemId)}`}
                    className="text-blue-600 hover:text-blue-800 flex items-center"
                  >
                    {relationshipLabels.browse_all
                      ? relationshipLabels.browse_all.replace(
                          '%{count}',
                          formatCount(totalCount)
                        )
                      : `Browse all ${formatCount(totalCount)} records...`}
                  </Link>
                </li>
              )}
            </ul>
          </div>
        );
      })
      .filter(Boolean);
  };

  const { documentMetadata, metadataFacets } = groupFields();

  return (
    <div
      id="full-details"
      className="bg-white rounded-lg shadow-md overflow-hidden"
    >
      <h2 className="text-lg font-semibold text-gray-900 px-6 py-4">
        Full Details
      </h2>
      <div className="flex flex-col sm:flex-row">
        <div className="w-full sm:w-2/3">
          <table className="min-w-full divide-y divide-gray-200">
            <tbody className="divide-y divide-gray-200">
              {documentMetadata.map(([key, value]) => (
                <tr key={key} className="hover:bg-gray-50">
                  <td className="px-6 py-4 w-1/3">
                    <div className="text-sm font-medium text-gray-500">
                      {customFieldLabels[key] || humanizeFieldName(key)}
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="text-sm text-gray-900">
                      {renderValue(
                        key,
                        value as string | string[] | null | undefined,
                        false
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="w-full sm:w-1/3">
          <div className="sr-only px-6 py-4 bg-gray-100 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">
              Metadata Facets
            </h2>
          </div>
          <div className="px-6 py-4 bg-gray-100">
            {metadataFacets.map(([key, value]) => (
              <div key={key} className="mb-4">
                <h5 className="text-sm font-medium text-gray-500">
                  {humanizeFieldName(key)}
                </h5>
                <ul className="list-none">
                  <li className="text-sm text-gray-900">
                    {key === 'dct_spatial_sm' &&
                    Array.isArray(value) &&
                    value.length > 15
                      ? renderPlaceValues(
                          value as string | string[] | null | undefined,
                          true
                        )
                      : renderValue(
                          key,
                          value as string | string[] | null | undefined,
                          true
                        )}
                  </li>
                </ul>
              </div>
            ))}

            {renderRelationships(uiRelationships)}
          </div>
        </div>
      </div>
    </div>
  );
}

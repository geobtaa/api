import React from 'react';
import { Link } from 'react-router';
import { ChevronRight } from 'lucide-react';
import type { GeoDocument } from '../../types/api';

interface ResourceBreadcrumbsProps {
  item: GeoDocument;
}

export function ResourceBreadcrumbs({ item }: ResourceBreadcrumbsProps) {
  // Helper to build search URL with accumulated facets
  const buildSearchUrl = (facets: Array<{ field: string; value: string }>) => {
    const params = new URLSearchParams();
    facets.forEach(({ field, value }) => {
      params.append(`fq[${field}][]`, value);
    });
    return `/search?${params.toString()}`;
  };

  // Build breadcrumb items with accumulated facets
  const breadcrumbs = [];
  let accumulatedFacets: Array<{ field: string; value: string }> = [];

  // Resource Class (e.g., "Maps")
  if (item.attributes.ogm.gbl_resourceClass_sm?.[0]) {
    accumulatedFacets = [
      {
        field: 'gbl_resourceClass_sm',
        value: item.attributes.ogm.gbl_resourceClass_sm[0],
      },
    ];
    breadcrumbs.push({
      label: item.attributes.ogm.gbl_resourceClass_sm[0],
      facets: [...accumulatedFacets],
    });
  }

  // Resource Type (e.g., "Aerial Photography")
  if (item.attributes.ogm.gbl_resourceType_sm?.[0]) {
    accumulatedFacets = [
      ...accumulatedFacets,
      {
        field: 'gbl_resourceType_sm',
        value: item.attributes.ogm.gbl_resourceType_sm[0],
      },
    ];
    breadcrumbs.push({
      label: item.attributes.ogm.gbl_resourceType_sm[0],
      facets: [...accumulatedFacets],
    });
  }

  // Geographic Coverage (e.g., "Minnesota")
  if (item.attributes.ogm.dct_spatial_sm?.[0]) {
    accumulatedFacets = [
      ...accumulatedFacets,
      {
        field: 'dct_spatial_sm',
        value: item.attributes.ogm.dct_spatial_sm[0],
      },
    ];
    breadcrumbs.push({
      label: item.attributes.ogm.dct_spatial_sm[0],
      facets: [...accumulatedFacets],
    });
  }

  // Date Issued (e.g., "1857")
  if (item.attributes.ogm.dct_issued_s) {
    accumulatedFacets = [
      ...accumulatedFacets,
      {
        field: 'dct_issued_s',
        value: item.attributes.ogm.dct_issued_s,
      },
    ];
    breadcrumbs.push({
      label: item.attributes.ogm.dct_issued_s,
      facets: [...accumulatedFacets],
    });
  }

  if (breadcrumbs.length === 0) return null;

  return (
    <nav className="flex" aria-label="Breadcrumb">
      <ol className="flex items-center space-x-2">
        {breadcrumbs.map((crumb, index) => (
          <li key={crumb.label} className="flex items-center">
            {index > 0 && (
              <ChevronRight className="h-4 w-4 text-gray-400 mx-2" />
            )}
            <Link
              to={buildSearchUrl(crumb.facets)}
              className="text-sm font-medium text-gray-500 hover:text-blue-600"
              aria-label={`Filter by ${crumb.label}`}
            >
              {crumb.label}
            </Link>
          </li>
        ))}
      </ol>
    </nav>
  );
}

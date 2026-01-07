import React from 'react';
// Remove unused import
// import { humanizeFieldName } from '../../constants/fieldLabels';

// Define types for the metadata structure
interface MetadataAttributes {
  dct_description_sm?: string | string[];
  dct_spatial_sm?: string | string[];
  dct_temporal_sm?: string | string[];
  dct_issued_s?: string;
  dct_language_sm?: string | string[];
  dct_format_s?: string;
  schema_provider_s?: string;
  dct_accessRights_s?: string;
  dct_license_sm?: string | string[];
  dc_subject_sm?: string | string[];
  gbl_resourceType_sm?: string | string[];
  gbl_resourceClass_sm?: string | string[];
  [key: string]: string | string[] | undefined;
}

interface MetadataTableProps {
  data: {
    data: {
      attributes: MetadataAttributes;
    };
  };
}

export function MetadataTable({ data }: MetadataTableProps) {
  const attributes = data?.data?.attributes || {};

  // Helper function to check if a value is empty
  const hasValue = (value: string | string[] | undefined): boolean => {
    if (Array.isArray(value)) {
      return value.length > 0;
    }
    if (typeof value === 'string') {
      return value.trim() !== '';
    }
    return value !== null && value !== undefined;
  };

  // Format value for display
  const formatValue = (value: string | string[] | undefined): string => {
    if (Array.isArray(value)) {
      return value.join(', ');
    }
    return value?.toString() || '';
  };

  // Helper function to determine if a value is singular or plural
  const getLabel = (key: string, label: string): string => {
    const value = attributes[key];
    if (Array.isArray(value) && value.length === 1) {
      return label.replace('(s)', '');
    }
    return label;
  };

  // Metadata field definitions with labels
  const metadataFields = [
    // Core Descriptive Fields
    { key: 'dct_description_sm', label: 'Description', colSpan: 3 },
    {
      key: 'dct_spatial_sm',
      label: getLabel('dct_spatial_sm', 'Places'),
      colSpan: 3,
    },

    // Temporal and Format Information
    {
      type: 'combined',
      cells: [
        { key: 'dct_temporal_sm', label: 'Temporal Coverage' },
        { key: 'dct_issued_s', label: 'Date Issued' },
        { key: 'dct_language_sm', label: 'Language' },
      ],
    },
    {
      type: 'combined',
      cells: [
        { key: 'dct_format_s', label: 'Format' },
        { key: 'schema_provider_s', label: 'Provider' },
      ],
    },

    // Access
    { key: 'dct_accessRights_s', label: 'Access Rights', colSpan: 3 },
    { key: 'dct_license_sm', label: 'License', colSpan: 3 },

    // Classification
    { key: 'dc_subject_sm', label: 'Subject', colSpan: 3 },
    { key: 'gbl_resourceType_sm', label: 'Resource Type', colSpan: 3 },
    { key: 'gbl_resourceClass_sm', label: 'Resource Class', colSpan: 3 },
  ];

  return (
    <div>
      <div className="px-6 py-4 bg-gray-50 border-b border-gray-200">
        <div className="flex justify-between items-center">
          <h2 className="text-lg font-semibold text-gray-900">Item Summary</h2>
          <a
            href="#full-details"
            className="text-sm text-blue-600 hover:text-blue-800 flex items-center gap-1"
          >
            Full Details ↓
          </a>
        </div>
      </div>
      <table className="min-w-full divide-y divide-gray-200">
        <tbody className="divide-y divide-gray-200">
          {metadataFields.map((field, index) => {
            if (field.type === 'combined') {
              // Handle the special combined row
              const hasAnyValue = field.cells.some((cell) =>
                hasValue(attributes[cell.key])
              );
              if (!hasAnyValue) return null;

              return (
                <tr key={`combined-${index}`} className="hover:bg-gray-50">
                  {field.cells.map((cell) => (
                    <td key={cell.key} className="px-6 py-4">
                      <div className="text-sm font-medium text-gray-500 mb-1">
                        {cell.label}
                      </div>
                      <div className="text-sm text-gray-900">
                        {formatValue(attributes[cell.key])}
                      </div>
                    </td>
                  ))}
                </tr>
              );
            }

            // Handle regular rows
            const value = attributes[field.key];
            if (!hasValue(value)) return null;

            return (
              <tr key={field.key} className="hover:bg-gray-50">
                <td colSpan={field.colSpan} className="px-6 py-4">
                  <div className="text-sm font-medium text-gray-500 mb-1">
                    {field.label}
                  </div>
                  <div className="text-sm text-gray-900">
                    {formatValue(value)}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

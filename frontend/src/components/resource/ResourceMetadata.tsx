import React from 'react';
import { Users, MapPin, Tag } from 'lucide-react';
import type { GeoDocumentDetails } from '../../types/api';

interface ResourceMetadataProps {
  item: GeoDocumentDetails;
}

export function ResourceMetadata({ item }: ResourceMetadataProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
      <div className="space-y-6">
        {item.schema_provider_s && (
          <div>
            <h2 className="text-sm font-medium text-gray-500">Provider</h2>
            <p className="mt-1 text-gray-900">{item.schema_provider_s}</p>
          </div>
        )}

        {item.dc_publisher_sm && item.dc_publisher_sm.length > 0 && (
          <div>
            <h2 className="text-sm font-medium text-gray-500">Publishers</h2>
            <ul className="mt-1 space-y-1">
              {item.dc_publisher_sm.map((publisher, index) => (
                <li key={index} className="text-gray-900">
                  {publisher}
                </li>
              ))}
            </ul>
          </div>
        )}

        {item.creator_sm && item.creator_sm.length > 0 && (
          <div>
            <h2 className="flex items-center gap-2 text-sm font-medium text-gray-500">
              <Users size={16} />
              Creators
            </h2>
            <ul className="mt-1 space-y-1">
              {item.creator_sm.map((creator, index) => (
                <li key={index} className="text-gray-900">
                  {creator}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <div className="space-y-6">
        {item.dct_spatial_sm && item.dct_spatial_sm.length > 0 && (
          <div>
            <h2 className="flex items-center gap-2 text-sm font-medium text-gray-500">
              <MapPin size={16} />
              Geographic Coverage
            </h2>
            <ul className="mt-1 space-y-1">
              {item.dct_spatial_sm.map((location, index) => (
                <li key={index} className="text-gray-900">
                  {location}
                </li>
              ))}
            </ul>
          </div>
        )}

        {item.dc_subject_sm && item.dc_subject_sm.length > 0 && (
          <div>
            <h2 className="flex items-center gap-2 text-sm font-medium text-gray-500">
              <Tag size={16} />
              Subjects
            </h2>
            <div className="mt-1 flex flex-wrap gap-2">
              {item.dc_subject_sm.map((subject, index) => (
                <span
                  key={index}
                  className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800"
                >
                  {subject}
                </span>
              ))}
            </div>
          </div>
        )}

        {item.dct_issued_s && (
          <div>
            <h2 className="text-sm font-medium text-gray-500">Date Issued</h2>
            <p className="mt-1 text-gray-900">{item.dct_issued_s}</p>
          </div>
        )}
      </div>
    </div>
  );
}

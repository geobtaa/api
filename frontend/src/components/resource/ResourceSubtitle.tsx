import React from 'react';
import type { GeoDocument } from '../../types/api';

interface ResourceSubtitleProps {
  item: GeoDocument;
}

export function ResourceSubtitle({ item }: ResourceSubtitleProps) {
  // Get publisher or creator
  const mainCredit = item.attributes.ogm.dct_publisher_sm?.length
    ? item.attributes.ogm.dct_publisher_sm.join(', ')
    : item.attributes.ogm.dct_creator_sm?.length
      ? item.attributes.ogm.dct_creator_sm.join(', ')
      : null;

  // Get year
  const year = item.attributes.ogm.dct_temporal_sm?.length
    ? item.attributes.ogm.dct_temporal_sm.join(', ')
    : null;

  if (!mainCredit && !year) return null;

  return (
    <h2 className="text-lg text-gray-600 italic">
      {mainCredit}
      {mainCredit && year && <span className="mx-2">&middot;</span>}
      {year}
    </h2>
  );
}

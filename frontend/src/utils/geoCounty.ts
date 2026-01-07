// Utilities for county-level matching based on Who's on First (WOF) facet values
// Facet value format: "<county_wof_id>|<region_wof_id>|<STATE_ABBR>|<County Name>"

export const stateFipsToAbbr: Record<string, string> = {
  '01': 'AL',
  '02': 'AK',
  '04': 'AZ',
  '05': 'AR',
  '06': 'CA',
  '08': 'CO',
  '09': 'CT',
  '10': 'DE',
  '11': 'DC',
  '12': 'FL',
  '13': 'GA',
  '15': 'HI',
  '16': 'ID',
  '17': 'IL',
  '18': 'IN',
  '19': 'IA',
  '20': 'KS',
  '21': 'KY',
  '22': 'LA',
  '23': 'ME',
  '24': 'MD',
  '25': 'MA',
  '26': 'MI',
  '27': 'MN',
  '28': 'MS',
  '29': 'MO',
  '30': 'MT',
  '31': 'NE',
  '32': 'NV',
  '33': 'NH',
  '34': 'NJ',
  '35': 'NM',
  '36': 'NY',
  '37': 'NC',
  '38': 'ND',
  '39': 'OH',
  '40': 'OK',
  '41': 'OR',
  '42': 'PA',
  '44': 'RI',
  '45': 'SC',
  '46': 'SD',
  '47': 'TN',
  '48': 'TX',
  '49': 'UT',
  '50': 'VT',
  '51': 'VA',
  '53': 'WA',
  '54': 'WV',
  '55': 'WI',
  '56': 'WY',
};

// Reverse lookup for mapping USPS abbreviation to zero-padded state FIPS code
export const stateAbbrToFips: Record<string, string> = Object.entries(
  stateFipsToAbbr
).reduce(
  (acc, [fips, abbr]) => {
    acc[abbr] = fips;
    return acc;
  },
  {} as Record<string, string>
);

// Normalize a name by lowercasing and stripping punctuation for robust matching
export function normalizeName(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z\s]/g, '')
    .trim();
}

// Parse the WOF facet value into structured parts
export function parseCountyFacetValue(value: string) {
  const parts = value.split('|');
  return {
    countyWofId: parts[0] || '',
    regionWofId: parts[1] || '',
    stateAbbr: parts[2] || '',
    countyName: parts.slice(3).join('|') || '',
  };
}

// Return facet hits for the GeoJSON county feature using state FIPS + normalized county match
import type { GeoJsonFeature } from '../types/map';

export function getCountyHitsFromFeature(
  feature: GeoJsonFeature,
  countyItems: Array<{ attributes: { value: string; hits: number } }>
): number {
  const featureCountyNameRaw =
    feature?.properties?.NAME ||
    feature?.properties?.name ||
    feature?.properties?.county ||
    'Unknown County';
  const featureStateFips: string = (
    feature?.properties?.STATE ||
    feature?.properties?.STATEFP ||
    ''
  )
    .toString()
    .padStart(2, '0');
  const featureStateAbbr = stateFipsToAbbr[featureStateFips] || '';
  const featureCountyName = normalizeName(featureCountyNameRaw);

  const item = countyItems.find((dataItem) => {
    const { stateAbbr, countyName } = parseCountyFacetValue(
      dataItem.attributes.value
    );
    if (!stateAbbr || !countyName) return false;
    const normCounty = normalizeName(countyName);
    return featureStateAbbr === stateAbbr && normCounty === featureCountyName;
  });

  return item ? item.attributes.hits : 0;
}

// Determine which state has the most county hits overall
export function getTopStateAbbrByCountyHits(
  countyItems: Array<{ attributes: { value: string; hits: number } }>
): string | null {
  const hitsByState: Record<string, number> = {};
  for (const item of countyItems) {
    const parsed = parseCountyFacetValue(item.attributes.value);
    if (!parsed.stateAbbr) continue;
    hitsByState[parsed.stateAbbr] =
      (hitsByState[parsed.stateAbbr] || 0) + (item.attributes.hits || 0);
  }
  const top = Object.entries(hitsByState).sort((a, b) => b[1] - a[1])[0];
  return top ? top[0] : null;
}

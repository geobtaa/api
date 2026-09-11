import reviewed from './zeroQueryCategories.json';
import { queryCategory } from './queryCategories';

export function zeroQueryCategory(term: string): string {
  const category = (reviewed as Record<string, string>)[term];
  if (category) return category;
  if (/^[+-]?\d{1,3}\.\d+\s*,\s*[+-]?\d{1,3}\.\d+$/.test(term.trim()))
    return 'Coordinates and Plus Codes';
  if (/\b(township|range|section)\b|\bT\d+N\b/i.test(term))
    return 'Township/range/section and land descriptions';
  if (
    /\b(street|avenue|road|lane|drive|blvd|addr|address)\b|^\d+\s+.*\b(st|ave|rd|ln|dr|way|ct)\b/i.test(
      term
    )
  )
    return 'Address and street search';
  if (/^\d{4}$/.test(term.trim())) return 'Date-only search';
  const inferred = queryCategory(term);
  if (inferred === 'Places & regions')
    return 'Named places and postal geography';
  if (inferred === 'Maps & imagery')
    return 'Subject or map series plus place/date';
  if (
    [
      'Environment & land use',
      'Society & history',
      'Transport & infrastructure',
    ].includes(inferred)
  )
    return 'Subject-only search';
  if (inferred === 'People & institutions' || inferred === 'Catalogs & tools')
    return 'Known map, title, citation, or creator';
  if (inferred === 'Addresses & coordinates')
    return 'Address and street search';
  return 'Unclassified or ambiguous';
}

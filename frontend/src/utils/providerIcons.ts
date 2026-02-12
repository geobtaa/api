/**
 * Maps provider institution names (schema_provider_s) to icon slugs in /icons/.
 * Icon filenames are lowercase with underscores (e.g. university_of_minnesota.svg).
 */

const VALID_ICON_SLUGS = new Set([
  'american_geographical_society_library_uwm_libraries',
  'baruch_cuny',
  'columbia_university',
  'cornell_university',
  'esri_globe',
  'george_mason_university',
  'harvard_university',
  'indiana_university',
  'lewis_&_clark_college',
  'massgis',
  'michigan_state_university',
  'mit',
  'northwestern_university',
  'nyu',
  'pennsylvania_state_university',
  'princeton_university',
  'purdue_university',
  'rutgers_university',
  'stanford_university',
  'the_ohio_state_university',
  'tufts_university',
  'uc_berkeley',
  'ucla',
  'university_of_arizona',
  'university_of_chicago',
  'university_of_colorado_boulder',
  'university_of_illinois_urbana_champaign',
  'university_of_iowa',
  'university_of_maryland',
  'university_of_michigan',
  'university_of_minnesota',
  'university_of_nebraska_lincoln',
  'university_of_texas',
  'university_of_virginia',
  'university_of_wisconsin_madison',
]);

/** Explicit overrides for provider names that don't slugify cleanly */
const PROVIDER_OVERRIDES: Record<string, string | null> = {
  uva: 'university_of_virginia',
  'uva libraries': 'university_of_virginia',
  'university of virginia': 'university_of_virginia',
  mit: 'mit',
  'mit libraries': 'mit',
  'geoblacklight community': null,
  'u.s. geological survey, department of the interior': null,
  'american geographical society library – uwm libraries':
    'american_geographical_society_library_uwm_libraries',
  'american geographical society library - uwm libraries':
    'american_geographical_society_library_uwm_libraries',
  'lewis & clark college': 'lewis_&_clark_college',
  'lewis and clark college': 'lewis_&_clark_college',
  'uc berkeley': 'uc_berkeley',
  'university of california berkeley': 'uc_berkeley',
  'university of california, berkeley': 'uc_berkeley',
  'university of illinois at urbana champaign':
    'university_of_illinois_urbana_champaign',
  'uw madison': 'university_of_wisconsin_madison',
  'university of wisconsin madison': 'university_of_wisconsin_madison',
  'university of nebraska lincoln': 'university_of_nebraska_lincoln',
};

function slugify(provider: string): string {
  return provider
    .toLowerCase()
    .trim()
    .replace(/[\u2013\u2014–—-]/g, ' ') // en/em/hyphen to space (so "Urbana-Champaign" -> "urbana_champaign")
    .replace(/[^a-z0-9\s]/g, '') // remove other non-alphanumeric
    .replace(/\s+/g, '_') // spaces to underscore
    .replace(/_+/g, '_') // collapse multiple underscores
    .replace(/^_|_$/g, ''); // trim underscores
}

/**
 * Official school/institution brand colors (primary color) for pill icon backgrounds.
 * Sources: university brand guidelines, brandcolorcode.com
 */
export const PROVIDER_SCHOOL_COLORS: Record<string, string> = {
  american_geographical_society_library_uwm_libraries: '#2C5234', // UWM green
  baruch_cuny: '#0033A0', // CUNY blue
  columbia_university: '#1D4F91', // Columbia Blue
  cornell_university: '#B31B1B', // Carnelian
  esri_globe: '#007AC2', // Esri blue
  george_mason_university: '#006633', // Mason green
  harvard_university: '#A51C30', // Harvard Crimson
  indiana_university: '#990000', // Crimson (IU)
  'lewis_&_clark_college': '#006633', // Pioneer green
  massgis: '#003366', // Mass.gov blue
  michigan_state_university: '#18453B', // Spartan green
  mit: '#750014', // MIT Red
  northwestern_university: '#4E2A84', // Northwestern Purple
  nyu: '#57068C', // NYU Violet
  pennsylvania_state_university: '#041E42', // Penn State Navy
  princeton_university: '#E77500', // Princeton Orange
  purdue_university: '#CEB888', // Purdue Gold (Old Gold)
  rutgers_university: '#CC0033', // Rutgers Scarlet
  stanford_university: '#8C1515', // Stanford Cardinal
  the_ohio_state_university: '#BA0C2F', // Ohio State Scarlet
  tufts_university: '#3E8DD4', // Tufts Blue
  uc_berkeley: '#003262', // Berkeley Blue
  ucla: '#2774AE', // UCLA Blue
  university_of_arizona: '#AB0520', // Arizona Red (primary)
  university_of_chicago: '#800000', // Maroon
  university_of_colorado_boulder: '#CFB87C', // Colorado Gold
  university_of_illinois_urbana_champaign: '#13294B', // Illinois Blue
  university_of_iowa: '#FFCD00', // Iowa Gold
  university_of_maryland: '#E21833', // Maryland Red
  university_of_michigan: '#00274C', // Michigan Blue
  university_of_minnesota: '#7A0019', // Minnesota Maroon
  university_of_nebraska_lincoln: '#D00000', // Nebraska Scarlet
  university_of_texas: '#BF5700', // Texas Burnt Orange
  university_of_virginia: '#E57200', // UVA Orange
  university_of_wisconsin_madison: '#C5050C', // Badger Red
};

/** Display names for provider slugs (for test/fixtures UI) */
export const PROVIDER_DISPLAY_NAMES: Record<string, string> = {
  american_geographical_society_library_uwm_libraries:
    'American Geographical Society Library, UWM Libraries',
  baruch_cuny: 'Baruch CUNY',
  columbia_university: 'Columbia University',
  cornell_university: 'Cornell University',
  esri_globe: 'Esri',
  george_mason_university: 'George Mason University',
  harvard_university: 'Harvard University',
  indiana_university: 'Indiana University',
  'lewis_&_clark_college': 'Lewis & Clark College',
  massgis: 'MassGIS',
  michigan_state_university: 'Michigan State University',
  mit: 'MIT',
  northwestern_university: 'Northwestern University',
  nyu: 'NYU',
  pennsylvania_state_university: 'Pennsylvania State University',
  princeton_university: 'Princeton University',
  purdue_university: 'Purdue University',
  rutgers_university: 'Rutgers University',
  stanford_university: 'Stanford University',
  the_ohio_state_university: 'The Ohio State University',
  tufts_university: 'Tufts University',
  uc_berkeley: 'UC Berkeley',
  ucla: 'UCLA',
  university_of_arizona: 'University of Arizona',
  university_of_chicago: 'University of Chicago',
  university_of_colorado_boulder: 'University of Colorado Boulder',
  university_of_illinois_urbana_champaign:
    'University of Illinois Urbana-Champaign',
  university_of_iowa: 'University of Iowa',
  university_of_maryland: 'University of Maryland',
  university_of_michigan: 'University of Michigan',
  university_of_minnesota: 'University of Minnesota',
  university_of_nebraska_lincoln: 'University of Nebraska-Lincoln',
  university_of_texas: 'University of Texas',
  university_of_virginia: 'University of Virginia',
  university_of_wisconsin_madison: 'University of Wisconsin-Madison',
};

/**
 * Returns the official school brand color (hex) for an icon slug, or a neutral grey fallback.
 */
export function getProviderSchoolColor(iconSlug: string | null): string {
  if (!iconSlug) return '#6B7280'; // gray-500 fallback
  return PROVIDER_SCHOOL_COLORS[iconSlug] ?? '#6B7280';
}

/**
 * Returns the icon slug for a provider name, or null if no icon exists.
 * Icons are served from /icons/{slug}.svg
 */
export function getProviderIconSlug(
  provider: string | undefined | null
): string | null {
  if (!provider || typeof provider !== 'string') return null;
  const trimmed = provider.trim();
  if (!trimmed) return null;

  const lower = trimmed.toLowerCase();
  const override = PROVIDER_OVERRIDES[lower];
  if (override !== undefined) return override; // may be null (no icon)

  const slug = slugify(trimmed);
  if (!slug) return null;
  return VALID_ICON_SLUGS.has(slug) ? slug : null;
}

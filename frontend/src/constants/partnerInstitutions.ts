import { getStaticMapSearchEnvelope } from '../utils/bbox';

export interface PartnerInstitution {
  slug: string;
  name: string;
  iconSlug?: string;
  iconSrc?: string;
  monochrome?: boolean;
  logoClassName?: string;
  campusMap?: {
    latitude: number;
    longitude: number;
    zoom: number;
  };
}

const campusMap = (
  latitude: number,
  longitude: number,
  zoom = 15
): PartnerInstitution['campusMap'] => ({
  latitude,
  longitude,
  zoom,
});

// BTAA Geoportal partner institutions with available logo assets in /public/icons.
export const BTAA_PARTNER_INSTITUTIONS: PartnerInstitution[] = [
  {
    slug: 'indiana-university',
    name: 'Indiana University',
    iconSlug: 'indiana_university',
    logoClassName: 'translate-x-0.5',
    campusMap: campusMap(39.1702, -86.5235),
  },
  {
    slug: 'michigan-state-university',
    name: 'Michigan State University',
    iconSlug: 'michigan_state_university',
    campusMap: campusMap(42.7308, -84.4811),
  },
  {
    slug: 'northwestern-university',
    name: 'Northwestern University',
    iconSlug: 'northwestern_university',
    campusMap: campusMap(42.0566, -87.6753, 16),
  },
  {
    slug: 'the-ohio-state-university',
    name: 'The Ohio State University',
    iconSlug: 'the_ohio_state_university',
    campusMap: campusMap(40.0017, -83.0147, 16),
  },
  {
    slug: 'pennsylvania-state-university',
    name: 'Pennsylvania State University',
    iconSlug: 'pennsylvania_state_university',
    campusMap: campusMap(40.7982, -77.8599, 16),
  },
  {
    slug: 'purdue-university',
    name: 'Purdue University',
    iconSlug: 'purdue_university',
    campusMap: campusMap(40.4277, -86.9139, 16),
  },
  {
    slug: 'rutgers-university',
    name: 'Rutgers University',
    iconSlug: 'rutgers_university',
    campusMap: campusMap(40.5006, -74.4474, 16),
  },
  {
    slug: 'university-of-chicago',
    name: 'University of Chicago',
    iconSlug: 'university_of_chicago',
    campusMap: campusMap(41.7897, -87.5997, 16),
  },
  {
    slug: 'university-of-illinois',
    name: 'University of Illinois',
    iconSlug: 'university_of_illinois_urbana_champaign',
    campusMap: campusMap(40.1097, -88.2272, 16),
  },
  {
    slug: 'university-of-iowa',
    name: 'University of Iowa',
    iconSlug: 'university_of_iowa',
    campusMap: campusMap(41.6611, -91.5341, 16),
  },
  {
    slug: 'university-of-maryland',
    name: 'University of Maryland',
    iconSlug: 'university_of_maryland',
    campusMap: campusMap(38.9869, -76.9446, 16),
  },
  {
    slug: 'university-of-michigan',
    name: 'University of Michigan',
    iconSlug: 'university_of_michigan',
    campusMap: campusMap(42.2762, -83.7382, 16),
  },
  {
    slug: 'university-of-minnesota',
    name: 'University of Minnesota',
    iconSlug: 'university_of_minnesota',
    campusMap: campusMap(44.9737, -93.2355, 16),
  },
  {
    slug: 'university-of-nebraska-lincoln',
    name: 'University of Nebraska-Lincoln',
    iconSlug: 'university_of_nebraska_lincoln',
    campusMap: campusMap(40.8204, -96.7006, 16),
  },
  {
    slug: 'university-of-oregon',
    name: 'University of Oregon',
    iconSlug: 'university_of_oregon',
    campusMap: campusMap(44.0451, -123.0722, 16),
  },
  {
    slug: 'university-of-washington',
    name: 'University of Washington',
    iconSlug: 'university_of_washington',
    campusMap: campusMap(47.6559, -122.308, 16),
  },
  {
    slug: 'university-of-wisconsin-madison',
    name: 'University of Wisconsin-Madison',
    iconSlug: 'university_of_wisconsin_madison',
    campusMap: campusMap(43.0755, -89.4042, 16),
  },
  {
    slug: 'big-ten-academic-alliance',
    name: 'Big Ten Academic Alliance',
    iconSrc: '/btaa-logo.png',
    monochrome: false,
  },
];

export function getPartnerInstitutionBySlug(slug: string): PartnerInstitution | undefined {
  return BTAA_PARTNER_INSTITUTIONS.find(
    (institution) => institution.slug === slug
  );
}

function formatCoordinate(value: number): string {
  return value.toFixed(6);
}

export function getPartnerInstitutionSearchHref(
  institution: PartnerInstitution
): string | null {
  if (!institution.campusMap) return null;

  const envelope = getStaticMapSearchEnvelope(
    institution.campusMap.latitude,
    institution.campusMap.longitude,
    institution.campusMap.zoom
  );
  const params = new URLSearchParams();
  params.set('include_filters[geo][type]', 'bbox');
  params.set('include_filters[geo][field]', 'dcat_bbox');
  params.set(
    'include_filters[geo][top_left][lat]',
    formatCoordinate(envelope.topLeft.lat)
  );
  params.set(
    'include_filters[geo][top_left][lon]',
    formatCoordinate(envelope.topLeft.lon)
  );
  params.set(
    'include_filters[geo][bottom_right][lat]',
    formatCoordinate(envelope.bottomRight.lat)
  );
  params.set(
    'include_filters[geo][bottom_right][lon]',
    formatCoordinate(envelope.bottomRight.lon)
  );

  return `/search?${params.toString()}`;
}

export interface PartnerInstitution {
  name: string;
  iconSlug?: string;
  iconSrc?: string;
  monochrome?: boolean;
}

// BTAA Geoportal partner institutions with available logo assets in /public/icons.
export const BTAA_PARTNER_INSTITUTIONS: PartnerInstitution[] = [
  { name: 'Indiana University', iconSlug: 'indiana_university' },
  {
    name: 'Michigan State University',
    iconSlug: 'michigan_state_university',
  },
  { name: 'Northwestern University', iconSlug: 'northwestern_university' },
  {
    name: 'The Ohio State University',
    iconSlug: 'the_ohio_state_university',
  },
  {
    name: 'Pennsylvania State University',
    iconSlug: 'pennsylvania_state_university',
  },
  { name: 'Purdue University', iconSlug: 'purdue_university' },
  { name: 'Rutgers University', iconSlug: 'rutgers_university' },
  { name: 'University of Chicago', iconSlug: 'university_of_chicago' },
  {
    name: 'University of Illinois',
    iconSlug: 'university_of_illinois_urbana_champaign',
  },
  { name: 'University of Iowa', iconSlug: 'university_of_iowa' },
  { name: 'University of Maryland', iconSlug: 'university_of_maryland' },
  { name: 'University of Michigan', iconSlug: 'university_of_michigan' },
  { name: 'University of Minnesota', iconSlug: 'university_of_minnesota' },
  { name: 'University of Nebraska-Lincoln', iconSlug: 'university_of_nebraska_lincoln' },
  { name: 'University of Oregon', iconSlug: 'university_of_oregon' },
  { name: 'University of Washington', iconSlug: 'university_of_washington' },
  {
    name: 'University of Wisconsin-Madison',
    iconSlug: 'university_of_wisconsin_madison',
  },
  {
    name: 'Big Ten Academic Alliance',
    iconSrc: '/btaa-logo.png',
    monochrome: false,
  },
];

/** Editorial classifications of the saved top queries, inferred from text only. */
const groups: Record<string, string[]> = {
  'Places & regions': [
    'michigan',
    'siberia russia',
    'asia minor',
    'spain',
    'Iran',
    'Vermont',
    'Algiers',
    'Qom',
    'bangladesh',
    '"Great Lakes"',
    'karafuto',
    'PATERSON',
    'Illinois',
    'Soudan mine',
    'west africa',
    'wisconsin',
    'ایران قم سال میلادی1963',
    'africa, west',
    'chicago',
    'egypt',
    'gulf of america',
    'india',
    'antarctica',
    'atlantic city',
    'baku',
    'Carbondale, PA',
    'central asia',
    'austin',
    'Washington county iowa',
    'bloomington',
    'london',
    '"new york city"',
    'iowa',
    'europe',
    'minneapolis',
    'baltimore',
    'maryland',
    'pottstown',
    'austin minnesota',
    'Bay and harbor of New York',
    'Henderson ky',
    'South America',
    'alaska',
    'italia',
    'minnesota',
    'farley iowa',
    'frogtown',
    'indiana',
    'iraq',
  ],
  'Maps & imagery': [
    'turkey maps',
    'caucasus maps',
    'sanborn',
    'russia maps',
    'siberia maps',
    'turkey history ottoman empire, maps',
    'kazakhstan maps',
    'Fire insurance',
    'egypt maps',
    'Aerial photo 08234',
    'armenia maps',
    'central asia maps',
    'iran maps',
    'black sea maps',
    'Iowa City Sanborn, 1883',
    'photos',
    'County map of the states of Iowa and Missouri',
    'crimea maps',
  ],
  'Environment & land use': [
    'water',
    'Land Cover',
    'Wisconsin Cropland Data Layer',
    'Anthracite Surface Mine Permits',
    'wetlands',
    'lakes rivers AND minneapolis',
  ],
  'Society & history': [
    'redlining',
    'crime',
    'business license',
    'archaeological sites',
    'campus',
  ],
  'Transport & infrastructure': ['amtrak stations', 'highways'],
  'People & institutions': [
    'American Geographical Society of New York',
    'Kitchin, Thomas',
  ],
  'Catalogs & tools': ['pasda', 'openindexmap'],
  'Addresses & coordinates': [
    '14.271281, 44.702708',
    '37.117777, 50.081111',
    '81 Fairview Ave edison',
    '32.503232, 44.449000',
    '31.971794,48.809872',
    '9266 town line rd Larsen wi',
    '32.654583, 44.405139',
  ],
  'Mixed or unclear': ['-sanborn', 'indiana field survey iran hardin i 38l'],
};
const normalize = (term: string) =>
  term.trim().replace(/\s+/g, ' ').toLocaleLowerCase('en-US');
const categories = new Map(
  Object.entries(groups).flatMap(([category, terms]) =>
    terms.map((term) => [normalize(term), category] as const)
  )
);

export function queryCategory(term: string) {
  return categories.get(normalize(term)) ?? 'Mixed or unclear';
}

export const queryCategoryMethod =
  'Best-effort editorial categories inferred from query text, not recorded user intent. Each query has one primary category. Explicit maps or imagery take precedence over a place name; topical queries use their topic. Ambiguous or exclusion-only queries remain Mixed or unclear. Case and spacing variants share a category but retain their separate search counts.';

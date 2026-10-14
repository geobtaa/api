export interface DailyActivityPoint {
  day: string;
  requests: number;
  searches: number;
  events: number;
}

export interface ResourceChartEntry {
  id: string;
  title: string;
  provider: string;
  resourceClass: string;
  resourceType: string;
  year?: number;
  views: number;
  actions: number;
  firstHalfEvents: number;
  secondHalfEvents: number;
}

export interface CollectionChartEntry {
  id?: string;
  title: string;
  searches: number;
  kind: 'Collection record' | 'Local collection';
  filterField?: 'b1g_localCollectionLabel_sm';
}

export interface DownloadChartEntry {
  id: string;
  title: string;
  provider: string;
  resourceClass: string;
  formatLabel: string;
  clicks: number;
  engagedVisits: number;
}

export interface MemberPerformanceEntry {
  code: string;
  name: string;
  shortName: string;
  slug: string;
  iconSlug: string;
  catalogRecords: number;
  activeResources: number;
  impressions: number;
  resourceViews: number;
  downloadClicks: number;
  sourceClicks: number;
  topResource: {
    id: string;
    title: string;
  };
}

export const JULY_2026_SUMMARY = {
  month: 'July 2026',
  exportedAt: 'August 20, 2026',
  requests: 613_131,
  searches: 6_457,
  impressions: 99_482,
  events: 16_824,
  resourceViews: 12_200,
  resultClicks: 1_984,
  downloadClicks: 933,
  uniqueEngagedVisits: 7_474,
  zeroResultSearches: 1_098,
  medianResponseMs: 1,
  p95ResponseMs: 29,
  serverErrors: 19,
} as const;

export const MEMBER_JULY_SUMMARY = {
  catalogRecords: 91_784,
  activeResources: 19_113,
  impressions: 69_000,
  resourceViews: 7_911,
  downloadClicks: 589,
  sourceClicks: 712,
} as const;

export const memberPerformance: MemberPerformanceEntry[] = [
  {
    code: '01',
    name: 'Indiana University',
    shortName: 'Indiana',
    slug: 'indiana-university',
    iconSlug: 'indiana_university',
    catalogRecords: 15_775,
    activeResources: 1_687,
    impressions: 3_868,
    resourceViews: 906,
    downloadClicks: 103,
    sourceClicks: 30,
    topResource: {
      id: '02415_1899-0022_mc87pq637',
      title: 'Sanborn Map [Indiana—Michigan City] {1899} sheet 22',
    },
  },
  {
    code: '02',
    name: 'University of Illinois',
    shortName: 'Illinois',
    slug: 'university-of-illinois',
    iconSlug: 'university_of_illinois_urbana_champaign',
    catalogRecords: 2_951,
    activeResources: 735,
    impressions: 3_262,
    resourceViews: 277,
    downloadClicks: 5,
    sourceClicks: 14,
    topResource: {
      id: '8a885da23dfb46caaa1827ad920fb5b1_0',
      title: 'Gateway Traffic Camera Locations [Illinois]',
    },
  },
  {
    code: '03',
    name: 'University of Iowa',
    shortName: 'Iowa',
    slug: 'university-of-iowa',
    iconSlug: 'university_of_iowa',
    catalogRecords: 4_136,
    activeResources: 1_077,
    impressions: 2_998,
    resourceViews: 315,
    downloadClicks: 2,
    sourceClicks: 9,
    topResource: {
      id: '03d-01',
      title: 'University of Iowa Digital Library: Atlases and Maps',
    },
  },
  {
    code: '04',
    name: 'University of Maryland',
    shortName: 'Maryland',
    slug: 'university-of-maryland',
    iconSlug: 'university_of_maryland',
    catalogRecords: 4_234,
    activeResources: 639,
    impressions: 2_282,
    resourceViews: 264,
    downloadClicks: 2,
    sourceClicks: 26,
    topResource: {
      id: 'a31ff4e8951c487ca52ce0a5b11a80d1_3',
      title: 'MD Electric Vehicle Charging Stations [Maryland]',
    },
  },
  {
    code: '05',
    name: 'University of Minnesota',
    shortName: 'Minnesota',
    slug: 'university-of-minnesota',
    iconSlug: 'university_of_minnesota',
    catalogRecords: 12_629,
    activeResources: 3_082,
    impressions: 8_330,
    resourceViews: 946,
    downloadClicks: 81,
    sourceClicks: 70,
    topResource: {
      id: 'p16022coll245:264',
      title:
        'Plat book of the city of Saint Paul, Minn. and suburbs: from official records, private plans and actual surveys',
    },
  },
  {
    code: '06',
    name: 'Michigan State University',
    shortName: 'Michigan State',
    slug: 'michigan-state-university',
    iconSlug: 'michigan_state_university',
    catalogRecords: 4_422,
    activeResources: 1_868,
    impressions: 10_550,
    resourceViews: 922,
    downloadClicks: 138,
    sourceClicks: 62,
    topResource: {
      id: '292ccdb0756448e892929fa4a27b3b1f_1',
      title: 'Lake Clarity — Sechi Depth [Michigan]',
    },
  },
  {
    code: '07',
    name: 'University of Michigan',
    shortName: 'Michigan',
    slug: 'university-of-michigan',
    iconSlug: 'university_of_michigan',
    catalogRecords: 1_502,
    activeResources: 833,
    impressions: 4_704,
    resourceViews: 310,
    downloadClicks: 21,
    sourceClicks: 28,
    topResource: {
      id: '00308e38-fe66-431b-9c8a-9e5a19951a0b',
      title:
        'Nova Poloniae delineatio; ex officina et sumptibus Iudoci Hondii.',
    },
  },
  {
    code: '08',
    name: 'Pennsylvania State University',
    shortName: 'Penn State',
    slug: 'pennsylvania-state-university',
    iconSlug: 'pennsylvania_state_university',
    catalogRecords: 7_183,
    activeResources: 1_483,
    impressions: 5_558,
    resourceViews: 853,
    downloadClicks: 29,
    sourceClicks: 41,
    topResource: {
      id: '95dcf338-fc27-4d3b-8883-967b3223933b',
      title: 'Emporium, Pennsylvania, 1892',
    },
  },
  {
    code: '09',
    name: 'Purdue University',
    shortName: 'Purdue',
    slug: 'purdue-university',
    iconSlug: 'purdue_university',
    catalogRecords: 773,
    activeResources: 114,
    impressions: 234,
    resourceViews: 147,
    downloadClicks: 5,
    sourceClicks: 17,
    topResource: {
      id: 'f189b6132895412381ce72b8a9379843_3',
      title: 'All Vacant and Abandoned Properties [Indiana—South Bend]',
    },
  },
  {
    code: '10',
    name: 'University of Wisconsin-Madison',
    shortName: 'Wisconsin',
    slug: 'university-of-wisconsin-madison',
    iconSlug: 'university_of_wisconsin_madison',
    catalogRecords: 14_400,
    activeResources: 2_689,
    impressions: 11_323,
    resourceViews: 549,
    downloadClicks: 123,
    sourceClicks: 28,
    topResource: {
      id: '000a439884964027914c9878ea4cdeda_0',
      title: 'Coastal Resilient Sites, Northeast U.S. [United States]',
    },
  },
  {
    code: '11',
    name: 'The Ohio State University',
    shortName: 'Ohio State',
    slug: 'the-ohio-state-university',
    iconSlug: 'the_ohio_state_university',
    catalogRecords: 1_363,
    activeResources: 365,
    impressions: 767,
    resourceViews: 247,
    downloadClicks: 1,
    sourceClicks: 17,
    topResource: {
      id: '4d8468466a6c49048fa30b7994aa3e4c_5',
      title: 'School District Boundaries [Ohio—Franklin County]',
    },
  },
  {
    code: '12',
    name: 'University of Chicago',
    shortName: 'Chicago',
    slug: 'university-of-chicago',
    iconSlug: 'university_of_chicago',
    catalogRecords: 10_438,
    activeResources: 2_485,
    impressions: 9_380,
    resourceViews: 1_458,
    downloadClicks: 6,
    sourceClicks: 323,
    topResource: {
      id: 'camel-1022954',
      title:
        'KH-4a: Declassified Satellite Imagery — Series 1 (Corona): DS1024-2104DA160',
    },
  },
  {
    code: '13',
    name: 'University of Nebraska-Lincoln',
    shortName: 'Nebraska',
    slug: 'university-of-nebraska-lincoln',
    iconSlug: 'university_of_nebraska_lincoln',
    catalogRecords: 1_075,
    activeResources: 192,
    impressions: 256,
    resourceViews: 55,
    downloadClicks: 2,
    sourceClicks: 5,
    topResource: {
      id: 'd4a1b8d1caaa495a9750e40b94759414_3',
      title: 'LiDAR Tile Index [Nebraska] {2019}',
    },
  },
  {
    code: '14',
    name: 'Rutgers University',
    shortName: 'Rutgers',
    slug: 'rutgers-university',
    iconSlug: 'rutgers_university',
    catalogRecords: 5_716,
    activeResources: 1_138,
    impressions: 2_769,
    resourceViews: 297,
    downloadClicks: 71,
    sourceClicks: 18,
    topResource: {
      id: '0dd6d6786d724cfbbd3591481c7f81d3_0',
      title: 'Imagery Warehouse — 1930 Aerial Image Grid [New Jersey]',
    },
  },
  {
    code: '15',
    name: 'Northwestern University',
    shortName: 'Northwestern',
    slug: 'northwestern-university',
    iconSlug: 'northwestern_university',
    catalogRecords: 252,
    activeResources: 158,
    impressions: 937,
    resourceViews: 56,
    downloadClicks: 0,
    sourceClicks: 4,
    topResource: {
      id: '6e330605-f83d-4483-8313-7d6b3bd0931e',
      title: 'Central Manufacturing District: the Pershing Road Development',
    },
  },
  {
    code: '16',
    name: 'University of Washington',
    shortName: 'Washington',
    slug: 'university-of-washington',
    iconSlug: 'university_of_washington',
    catalogRecords: 3_673,
    activeResources: 373,
    impressions: 1_068,
    resourceViews: 241,
    downloadClicks: 0,
    sourceClicks: 11,
    topResource: {
      id: '2499235ca6454b149415bb9bb8b94831_0',
      title: 'RTA Boundary [Washington—Pierce County]',
    },
  },
  {
    code: '17',
    name: 'University of Oregon',
    shortName: 'Oregon',
    slug: 'university-of-oregon',
    iconSlug: 'university_of_oregon',
    catalogRecords: 1_262,
    activeResources: 195,
    impressions: 714,
    resourceViews: 68,
    downloadClicks: 0,
    sourceClicks: 9,
    topResource: {
      id: 'c0e6948bb6d54f3884635fcc2f94e581_0',
      title: 'Active Faults [Oregon]',
    },
  },
];

export const dailyActivity: DailyActivityPoint[] = [
  { day: 'Jul 1', requests: 14_500, searches: 251, events: 548 },
  { day: 'Jul 2', requests: 18_058, searches: 240, events: 556 },
  { day: 'Jul 3', requests: 19_271, searches: 88, events: 491 },
  { day: 'Jul 4', requests: 17_324, searches: 138, events: 479 },
  { day: 'Jul 5', requests: 23_920, searches: 335, events: 753 },
  { day: 'Jul 6', requests: 26_125, searches: 268, events: 644 },
  { day: 'Jul 7', requests: 15_274, searches: 297, events: 737 },
  { day: 'Jul 8', requests: 19_603, searches: 270, events: 627 },
  { day: 'Jul 9', requests: 20_371, searches: 215, events: 578 },
  { day: 'Jul 10', requests: 19_647, searches: 214, events: 531 },
  { day: 'Jul 11', requests: 18_676, searches: 91, events: 303 },
  { day: 'Jul 12', requests: 18_102, searches: 189, events: 411 },
  { day: 'Jul 13', requests: 19_529, searches: 185, events: 551 },
  { day: 'Jul 14', requests: 25_249, searches: 352, events: 620 },
  { day: 'Jul 15', requests: 17_005, searches: 244, events: 586 },
  { day: 'Jul 16', requests: 17_708, searches: 243, events: 580 },
  { day: 'Jul 17', requests: 13_992, searches: 125, events: 425 },
  { day: 'Jul 18', requests: 17_919, searches: 125, events: 433 },
  { day: 'Jul 19', requests: 13_946, searches: 123, events: 345 },
  { day: 'Jul 20', requests: 23_369, searches: 271, events: 569 },
  { day: 'Jul 21', requests: 20_306, searches: 213, events: 525 },
  { day: 'Jul 22', requests: 20_967, searches: 185, events: 523 },
  { day: 'Jul 23', requests: 14_219, searches: 183, events: 483 },
  { day: 'Jul 24', requests: 20_570, searches: 323, events: 766 },
  { day: 'Jul 25', requests: 17_082, searches: 225, events: 715 },
  { day: 'Jul 26', requests: 16_635, searches: 60, events: 318 },
  { day: 'Jul 27', requests: 18_716, searches: 222, events: 550 },
  { day: 'Jul 28', requests: 26_918, searches: 202, events: 557 },
  { day: 'Jul 29', requests: 34_574, searches: 250, events: 646 },
  { day: 'Jul 30', requests: 22_452, searches: 101, events: 455 },
  { day: 'Jul 31', requests: 21_104, searches: 229, events: 519 },
];

export const topResources: ResourceChartEntry[] = [
  {
    id: '95dcf338-fc27-4d3b-8883-967b3223933b',
    title: 'Emporium, Pennsylvania, 1892',
    provider: 'Pennsylvania State University',
    resourceClass: 'Maps',
    resourceType: 'Fire insurance maps',
    year: 1892,
    views: 100,
    actions: 0,
    firstHalfEvents: 0,
    secondHalfEvents: 100,
  },
  {
    id: '5F3EEF4C-D1EA-4AC8-A2C5-774D21E78D46',
    title: 'WHAIFinder (Wisconsin Historic Aerial Imagery Finder)',
    provider: 'University of Wisconsin-Madison',
    resourceClass: 'Websites',
    resourceType: 'Digital repositories',
    year: 1937,
    views: 83,
    actions: 12,
    firstHalfEvents: 49,
    secondHalfEvents: 46,
  },
  {
    id: '4d8468466a6c49048fa30b7994aa3e4c_5',
    title: 'School District Boundaries [Ohio--Franklin County]',
    provider: 'Franklin County, Ohio',
    resourceClass: 'Web services',
    resourceType: 'Polygon data',
    year: 2025,
    views: 57,
    actions: 0,
    firstHalfEvents: 24,
    secondHalfEvents: 33,
  },
  {
    id: '292ccdb0756448e892929fa4a27b3b1f_1',
    title: 'Lake Clarity - Sechi Depth [Michigan]',
    provider: 'State of Michigan',
    resourceClass: 'Web services',
    resourceType: 'Polygon data',
    year: 2025,
    views: 50,
    actions: 0,
    firstHalfEvents: 50,
    secondHalfEvents: 0,
  },
  {
    id: '999-0011-new-york',
    title: 'Digital Sanborn Maps (Black & White) [New York] {1867-1970}',
    provider: 'Licensed resources',
    resourceClass: 'Maps',
    resourceType: 'Fire insurance maps',
    year: 1880,
    views: 47,
    actions: 1,
    firstHalfEvents: 32,
    secondHalfEvents: 17,
  },
  {
    id: 'f189b6132895412381ce72b8a9379843_3',
    title: 'All Vacant and Abandoned Properties [Indiana--South Bend]',
    provider: 'South Bend Open Data',
    resourceClass: 'Web services',
    resourceType: 'Open data',
    year: 2025,
    views: 46,
    actions: 3,
    firstHalfEvents: 32,
    secondHalfEvents: 17,
  },
  {
    id: '08d-02',
    title: 'Sanborn Maps: Pennsylvania, 1884-1938',
    provider: 'Pennsylvania State University',
    resourceClass: 'Websites',
    resourceType: 'Digital repositories',
    year: 1884,
    views: 44,
    actions: 5,
    firstHalfEvents: 20,
    secondHalfEvents: 29,
  },
  {
    id: '999-0011-michigan',
    title: 'Digital Sanborn Maps (Black & White) [Michigan] {1867-1970}',
    provider: 'Licensed resources',
    resourceClass: 'Maps',
    resourceType: 'Fire insurance maps',
    year: 1880,
    views: 40,
    actions: 8,
    firstHalfEvents: 35,
    secondHalfEvents: 13,
  },
  {
    id: '999-0011-new-jersey',
    title: 'Digital Sanborn Maps (Black & White) [New Jersey] {1867-1970}',
    provider: 'Licensed resources',
    resourceClass: 'Maps',
    resourceType: 'Fire insurance maps',
    year: 1880,
    views: 40,
    actions: 1,
    firstHalfEvents: 22,
    secondHalfEvents: 21,
  },
  {
    id: '999-0011-california',
    title: 'Digital Sanborn Maps (Black & White) [California] {1867-1970}',
    provider: 'Licensed resources',
    resourceClass: 'Maps',
    resourceType: 'Fire insurance maps',
    year: 1880,
    views: 37,
    actions: 8,
    firstHalfEvents: 18,
    secondHalfEvents: 28,
  },
];

export const topCollections: CollectionChartEntry[] = [
  {
    id: 'b1g_urbanBaseLayers',
    title: 'Urban Base Layers Collection',
    searches: 106,
    kind: 'Collection record',
  },
  {
    id: '12d-04',
    title: 'Center for Ancient Middle Eastern Landscapes',
    searches: 83,
    kind: 'Collection record',
  },
  {
    title: 'Surveyor Maps, 1816–1860',
    searches: 43,
    kind: 'Local collection',
    filterField: 'b1g_localCollectionLabel_sm',
  },
  {
    id: '64bd8c4c-8e60-4956-b43d-bdc3f93db488',
    title: 'BTAA Libraries Historical Maps Collection',
    searches: 42,
    kind: 'Collection record',
  },
  {
    id: '08a-04',
    title: 'PASDA Geospatial Data Archive',
    searches: 37,
    kind: 'Collection record',
  },
  {
    id: 'b35f927e-9051-4d7f-9ca3-ad5b19024e0b',
    title: 'Sanborn Fire Insurance Maps',
    searches: 36,
    kind: 'Collection record',
  },
  {
    id: '08d-02',
    title: 'Sanborn Maps: Pennsylvania, 1884–1938',
    searches: 17,
    kind: 'Collection record',
  },
  {
    id: '77f-0001',
    title: 'General Land Office Township Plats',
    searches: 16,
    kind: 'Collection record',
  },
  {
    title: 'Survey of Egypt',
    searches: 12,
    kind: 'Local collection',
    filterField: 'b1g_localCollectionLabel_sm',
  },
  {
    id: '08d-05',
    title: 'Pennsylvania Aerial Photo Collection',
    searches: 10,
    kind: 'Collection record',
  },
];

export const topDownloadedResources: DownloadChartEntry[] = [
  {
    id: '2f3c06da-21a0-410f-b230-be07165aeb89',
    title:
      "Map of Home Owners' Loan Corporation [Los Angeles, California] {1939}",
    provider: "Home Owners' Loan Corporation",
    resourceClass: 'Maps',
    formatLabel: 'JPG 1 · JPG 2 · JPG 3',
    clicks: 7,
    engagedVisits: 6,
  },
  {
    id: '11651802-8f65-4e7f-9db8-129e7b707038',
    title:
      '01N 05E - Survey Map of Hamburg Township, Livingston County [Michigan]',
    provider: 'Department of Natural Resources',
    resourceClass: 'Maps',
    formatLabel: 'JPEG2000',
    clicks: 6,
    engagedVisits: 2,
  },
  {
    id: '48e5e73f-9087-45bd-b7c1-86edbd50d5b1',
    title:
      '07N 05W - Survey Map of Lyons Township, Ionia County, Page 2 [Michigan]',
    provider: 'Department of Natural Resources',
    resourceClass: 'Maps',
    formatLabel: 'JPEG2000',
    clicks: 6,
    engagedVisits: 3,
  },
  {
    id: 'bb41f39b-2d8a-46f5-81da-aaa0e8b317f3',
    title:
      '07N 05W - Survey Map of Lyons Township, Ionia County, Page 1 [Michigan]',
    provider: 'Department of Natural Resources',
    resourceClass: 'Maps',
    formatLabel: 'JPEG2000',
    clicks: 6,
    engagedVisits: 1,
  },
  {
    id: 'bc98bb75-9144-47f4-88fd-971e6263ded7',
    title: 'HOLC Redlining Maps and Data [North Carolina--Fayetteville]',
    provider: 'Digital Scholarship Lab, University of Richmond',
    resourceClass: 'Datasets',
    formatLabel: 'Maps and data',
    clicks: 5,
    engagedVisits: 5,
  },
  {
    id: 'f126641f-c434-40a1-a0f6-1060af1b4d11',
    title: 'HOLC Redlining Maps and Data [Nebraska--Lincoln]',
    provider: 'Digital Scholarship Lab, University of Richmond',
    resourceClass: 'Datasets',
    formatLabel: 'Maps and data',
    clicks: 5,
    engagedVisits: 2,
  },
  {
    id: 'rutgers-lib:20581',
    title: 'Washington, New Jersey 1972',
    provider: 'Rutgers University-New Brunswick',
    resourceClass: 'Imagery',
    formatLabel: 'JPEG · PDF',
    clicks: 5,
    engagedVisits: 4,
  },
  {
    id: 'stanford-pb503mv7221',
    title:
      'Geological Survey of Uganda [1:250,000 geological series], Maps Index',
    provider: 'Stanford',
    resourceClass: 'Maps',
    formatLabel: 'Zipped object',
    clicks: 5,
    engagedVisits: 4,
  },
  {
    id: 'stanford-rx293pp4560',
    title: 'Second-level Administrative Divisions, Syria, 2015',
    provider: 'Stanford',
    resourceClass: 'Datasets',
    formatLabel: 'Zipped object',
    clicks: 5,
    engagedVisits: 2,
  },
  {
    id: 't039r20w4fi01',
    title:
      'General Land Office Township Plat - Original Survey: Minnesota (T039N R20W), 1851',
    provider: 'Minnesota Geospatial Information Office (MnGeo)',
    resourceClass: 'Maps',
    formatLabel: 'GeoJPEG',
    clicks: 5,
    engagedVisits: 4,
  },
];

export const topSearchTerms = [
  { term: 'turkey maps', count: 72 },
  { term: '-sanborn', count: 36 },
  { term: 'michigan', count: 23 },
  { term: 'siberia russia', count: 22 },
  { term: 'caucasus maps', count: 22 },
  { term: 'pasda', count: 20 },
  { term: 'sanborn', count: 18 },
  { term: 'asia minor', count: 18 },
];

export const topZeroResultQueries = [
  { term: '14.271281, 44.702708', count: 17 },
  { term: '37.117777, 50.081111', count: 10 },
  { term: 'ایران قم سال میلادی1963', count: 9 },
  { term: '81 Fairview Ave edison', count: 5 },
  { term: 'Aerial photo 08234', count: 5 },
  { term: '9419 Hemlock Fontana, California', count: 4 },
  { term: 'harwich ma', count: 4 },
  { term: 'Ohio, Hardin county parcel', count: 4 },
  { term: 'sanborn map knoxville, tn', count: 4 },
  {
    term: 'Sleeping bear beach, township T29N, range 14W, lots 1 and 2, section 22, glen arbor township',
    count: 4,
  },
];

export const resourceClassFilters = [
  { label: 'Maps', count: 755, color: '#003C5B' },
  { label: 'Datasets', count: 345, color: '#1E40AF' },
  { label: 'Imagery', count: 235, color: '#2563EB' },
  { label: 'Web services', count: 92, color: '#3B82F6' },
  { label: 'Websites', count: 75, color: '#60A5FA' },
  { label: 'Collections', count: 27, color: '#93C5FD' },
];

export const discoveryViews = [
  { label: 'Map', count: 5_524, percent: 85.6, color: '#003C5B' },
  { label: 'Gallery', count: 511, percent: 7.9, color: '#2563EB' },
  { label: 'List', count: 422, percent: 6.5, color: '#93C5FD' },
];

export const requestMix = [
  { label: 'API docs', count: 265_179, percent: 43.3, color: '#003C5B' },
  { label: 'Access checks', count: 229_999, percent: 37.5, color: '#2563EB' },
  { label: 'Analytics capture', count: 25_484, percent: 4.2, color: '#60A5FA' },
  { label: 'Everything else', count: 92_469, percent: 15, color: '#BFDBFE' },
];

export const peakApiTrafficBreakdown = [
  {
    label: 'Turnstile status checks',
    count: 20_521,
    percent: 59.4,
    detail: 'Browser and crawler access-status calls',
  },
  {
    label: 'API documentation probes',
    count: 8_554,
    percent: 24.7,
    detail: 'Automated curl health check, roughly every 10 seconds',
  },
  {
    label: 'Resource endpoints',
    count: 1_869,
    percent: 5.4,
    detail: 'Catalog resource calls; 1,809 were rate-limited',
  },
  {
    label: 'Thumbnails',
    count: 1_559,
    percent: 4.5,
    detail: 'Catalog image delivery',
  },
  {
    label: 'Analytics event capture',
    count: 941,
    percent: 2.7,
    detail: 'Tracked product-interaction posts',
  },
  {
    label: 'Robots and sitemaps',
    count: 747,
    percent: 2.2,
    detail: 'Crawler discovery traffic',
  },
  {
    label: 'Everything else',
    count: 383,
    percent: 1.1,
    detail: 'Turnstile verification, static maps, and other routes',
  },
];

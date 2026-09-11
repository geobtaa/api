import {
  memberPerformance as julyMembers,
  type MemberPerformanceEntry,
} from './july2026';
import type { MemberDailySeries, MemberContentEntry } from './memberJuly2026';

export const augustMemberMetrics = [
  {
    code: '01',
    resourceViews: 1066,
    downloadClicks: 116,
    sourceClicks: 12,
    impressions: 4865,
    catalogRecords: 15779,
    activeResources: 2070,
    topResource: {
      id: 'VAC3073-M-01007',
      title:
        'Map of flood-prone areas, Anderson South quadrangle, Indiana-Madison Co. : 7.5 minute series (topographic)',
    },
  },
  {
    code: '02',
    resourceViews: 363,
    downloadClicks: 1,
    sourceClicks: 53,
    impressions: 3008,
    catalogRecords: 2958,
    activeResources: 786,
    topResource: {
      id: 'b35e21c0-c451-0133-1d17-0050569601ca-e',
      title: 'Insurance maps of Monmouth, Warren Co., Illinois, Aug. 1907',
    },
  },
  {
    code: '03',
    resourceViews: 537,
    downloadClicks: 5,
    sourceClicks: 25,
    impressions: 5310,
    catalogRecords: 4188,
    activeResources: 1276,
    topResource: {
      id: 'b1g_03d_264319_51793',
      title: 'Plat Book of Humboldt County, Iowa, 1896 3 Cities and Villages',
    },
  },
  {
    code: '04',
    resourceViews: 463,
    downloadClicks: 0,
    sourceClicks: 12,
    impressions: 2905,
    catalogRecords: 4108,
    activeResources: 493,
    topResource: {
      id: 'b1g_04d_06VVJ6jkp4dM',
      title: 'Map of Germany - Rail Maps - Berlin, 1944',
    },
  },
  {
    code: '05',
    resourceViews: 1331,
    downloadClicks: 89,
    sourceClicks: 41,
    impressions: 15109,
    catalogRecords: 14237,
    activeResources: 4643,
    topResource: {
      id: '7c1a375b08db47e09f855770c59892bc_0',
      title: 'Streets Unformatted [Minnesota--Saint Paul]',
    },
  },
  {
    code: '06',
    resourceViews: 1021,
    downloadClicks: 98,
    sourceClicks: 37,
    impressions: 8797,
    catalogRecords: 4368,
    activeResources: 1305,
    topResource: {
      id: '000b18d6-63b9-4314-9d4f-17c945ea09b7',
      title:
        '48N 18W - Survey Map of Munising Township, Alger County [Michigan]',
    },
  },
  {
    code: '07',
    resourceViews: 299,
    downloadClicks: 0,
    sourceClicks: 27,
    impressions: 4273,
    catalogRecords: 1811,
    activeResources: 755,
    topResource: {
      id: '293f8af9623048dd9fc3b554f662e061_0',
      title: 'Fire Insurance Escrow (FIE) Properties [Michigan--Detroit]',
    },
  },
  {
    code: '08',
    resourceViews: 871,
    downloadClicks: 19,
    sourceClicks: 31,
    impressions: 6507,
    catalogRecords: 15974,
    activeResources: 1991,
    topResource: {
      id: '08d-02',
      title: 'Sanborn Maps: Pennsylvania, 1884-1938',
    },
  },
  {
    code: '09',
    resourceViews: 260,
    downloadClicks: 0,
    sourceClicks: 8,
    impressions: 1218,
    catalogRecords: 839,
    activeResources: 206,
    topResource: {
      id: 'f189b6132895412381ce72b8a9379843_3',
      title: 'All Vacant and Abandoned Properties [Indiana--South Bend]',
    },
  },
  {
    code: '10',
    resourceViews: 884,
    downloadClicks: 68,
    sourceClicks: 28,
    impressions: 8807,
    catalogRecords: 14753,
    activeResources: 1924,
    topResource: {
      id: '342a10f9c5d5430d91b7028f4695f6f8_0',
      title: 'ParksandRecreation OpenData [Wisconsin--Outagamie County]',
    },
  },
  {
    code: '11',
    resourceViews: 344,
    downloadClicks: 0,
    sourceClicks: 3,
    impressions: 411,
    catalogRecords: 1368,
    activeResources: 226,
    topResource: {
      id: '4d8468466a6c49048fa30b7994aa3e4c_5',
      title: 'School District Boundaries [Ohio--Franklin County]',
    },
  },
  {
    code: '12',
    resourceViews: 1912,
    downloadClicks: 7,
    sourceClicks: 174,
    impressions: 7950,
    catalogRecords: 10399,
    activeResources: 2475,
    topResource: {
      id: 'camel-1018330',
      title:
        'KH-4b: Declassified Satellite Imagery - Series 1 ("Corona"): DS1110-1073DA043',
    },
  },
  {
    code: '13',
    resourceViews: 203,
    downloadClicks: 0,
    sourceClicks: 0,
    impressions: 394,
    catalogRecords: 1091,
    activeResources: 182,
    topResource: {
      id: '13c-02',
      title: 'City of Grand Island Public GIS Data Portal',
    },
  },
  {
    code: '14',
    resourceViews: 532,
    downloadClicks: 145,
    sourceClicks: 16,
    impressions: 2475,
    catalogRecords: 5709,
    activeResources: 744,
    topResource: {
      id: 'e1fdf22f4ce04059b2f87dbaa1d727a2_0',
      title: 'New Jersey Standard Route Id And Milepost [New Jersey]',
    },
  },
  {
    code: '15',
    resourceViews: 20,
    downloadClicks: 0,
    sourceClicks: 0,
    impressions: 430,
    catalogRecords: 252,
    activeResources: 117,
    topResource: {
      id: '02b645d4-233e-46fd-a23e-ce17caf89711',
      title:
        "La Spagna : all'illmo. e reumo. Sigre. Monsre. Gio. Battista Febei, referendario dell'una, e l'altra segnatura",
    },
  },
  {
    code: '16',
    resourceViews: 602,
    downloadClicks: 0,
    sourceClicks: 13,
    impressions: 1360,
    catalogRecords: 3462,
    activeResources: 501,
    topResource: {
      id: '6f31b076628d4f8ca5a964cbefd2cccc_0',
      title: 'Washington Large Fires 1973-2025 [Washington (State)]',
    },
  },
  {
    code: '17',
    resourceViews: 142,
    downloadClicks: 0,
    sourceClicks: 4,
    impressions: 645,
    catalogRecords: 1340,
    activeResources: 141,
    topResource: {
      id: '9ab2e66cddab4ad3a2530d9bdb8db017_0',
      title: 'Voter Precincts [Oregon--Portland]',
    },
  },
];

export const augustMembers: MemberPerformanceEntry[] = julyMembers.map(
  (member) => ({
    ...member,
    ...augustMemberMetrics.find((row) => row.code === member.code)!,
  })
);

export const augustMemberSummary = {
  catalogRecords: 102636,
  activeResources: 19835,
  impressions: 74464,
  resourceViews: 10850,
  downloadClicks: 548,
  sourceClicks: 484,
};

export const augustMemberDailySeries: Record<string, MemberDailySeries> = {
  '01': {
    views: [
      22, 42, 45, 34, 65, 27, 63, 88, 70, 24, 23, 31, 61, 35, 26, 44, 26, 16,
      19, 26, 18, 69, 13, 11, 27, 20, 50, 22, 21, 19, 9,
    ],
    downloads: [
      0, 13, 14, 2, 6, 3, 1, 0, 21, 2, 8, 4, 2, 1, 1, 1, 1, 4, 2, 2, 0, 10, 1,
      0, 0, 3, 14, 0, 0, 0, 0,
    ],
  },
  '02': {
    views: [
      7, 6, 6, 7, 26, 15, 31, 27, 5, 9, 8, 4, 14, 8, 10, 3, 4, 23, 4, 14, 16,
      26, 19, 9, 20, 3, 4, 6, 1, 15, 13,
    ],
    downloads: [
      0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0,
      0, 0, 0, 0, 0, 0,
    ],
  },
  '03': {
    views: [
      4, 22, 20, 5, 20, 10, 19, 25, 24, 19, 14, 20, 2, 39, 41, 13, 17, 51, 12,
      18, 11, 9, 23, 16, 31, 9, 23, 2, 9, 3, 6,
    ],
    downloads: [
      0, 0, 3, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0,
      0, 0, 0, 0, 0, 0,
    ],
  },
  '04': {
    views: [
      1, 11, 10, 7, 44, 22, 69, 63, 19, 7, 0, 5, 9, 3, 10, 4, 5, 1, 9, 6, 43, 1,
      1, 5, 62, 24, 6, 3, 11, 1, 1,
    ],
    downloads: [
      0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
      0, 0, 0, 0, 0, 0,
    ],
  },
  '05': {
    views: [
      24, 49, 33, 40, 105, 59, 83, 82, 56, 28, 93, 34, 83, 55, 19, 12, 35, 41,
      54, 44, 25, 21, 29, 56, 49, 21, 38, 12, 13, 16, 22,
    ],
    downloads: [
      5, 2, 1, 1, 0, 2, 1, 1, 6, 2, 9, 7, 4, 6, 1, 0, 3, 1, 1, 5, 4, 1, 6, 1, 8,
      3, 2, 0, 4, 1, 1,
    ],
  },
  '06': {
    views: [
      19, 56, 37, 26, 76, 30, 102, 97, 38, 28, 22, 23, 50, 10, 50, 14, 33, 30,
      20, 16, 65, 12, 7, 9, 18, 20, 21, 21, 17, 17, 37,
    ],
    downloads: [
      3, 7, 0, 2, 3, 0, 1, 4, 5, 9, 1, 1, 7, 0, 7, 0, 2, 3, 3, 2, 5, 0, 1, 2, 3,
      4, 6, 1, 4, 5, 7,
    ],
  },
  '07': {
    views: [
      2, 6, 14, 10, 25, 21, 28, 31, 16, 5, 8, 13, 9, 1, 2, 2, 4, 7, 10, 7, 19,
      5, 8, 5, 4, 3, 21, 3, 1, 0, 9,
    ],
    downloads: [
      0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
      0, 0, 0, 0, 0, 0,
    ],
  },
  '08': {
    views: [
      7, 40, 40, 42, 85, 41, 94, 119, 40, 12, 18, 12, 32, 42, 16, 26, 24, 15,
      16, 17, 14, 11, 3, 9, 7, 23, 21, 12, 17, 8, 8,
    ],
    downloads: [
      1, 1, 3, 0, 0, 0, 2, 2, 0, 0, 0, 0, 0, 3, 0, 1, 0, 0, 0, 0, 0, 0, 0, 2, 3,
      0, 1, 0, 0, 0, 0,
    ],
  },
  '09': {
    views: [
      0, 3, 4, 8, 22, 7, 32, 42, 19, 3, 5, 2, 27, 1, 1, 1, 3, 8, 7, 21, 5, 1, 2,
      1, 3, 5, 4, 2, 4, 4, 13,
    ],
    downloads: [
      0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
      0, 0, 0, 0, 0, 0,
    ],
  },
  '10': {
    views: [
      18, 14, 24, 21, 90, 43, 131, 184, 57, 21, 18, 22, 17, 5, 17, 24, 14, 14,
      6, 10, 28, 16, 9, 5, 21, 11, 9, 13, 3, 8, 11,
    ],
    downloads: [
      2, 2, 1, 1, 0, 1, 4, 8, 0, 5, 1, 1, 8, 1, 0, 4, 2, 1, 1, 1, 4, 5, 0, 0, 1,
      2, 1, 4, 0, 2, 5,
    ],
  },
  '11': {
    views: [
      3, 12, 13, 6, 45, 19, 51, 56, 14, 10, 3, 8, 7, 0, 6, 9, 6, 12, 4, 1, 3, 6,
      3, 7, 8, 14, 8, 1, 3, 1, 5,
    ],
    downloads: [
      0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
      0, 0, 0, 0, 0, 0,
    ],
  },
  '12': {
    views: [
      23, 28, 56, 40, 106, 96, 123, 170, 138, 44, 57, 59, 32, 90, 112, 60, 85,
      81, 103, 69, 40, 27, 21, 29, 41, 19, 33, 25, 44, 43, 18,
    ],
    downloads: [
      0, 0, 1, 0, 2, 0, 1, 0, 0, 0, 0, 0, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
      0, 0, 0, 0, 0, 1,
    ],
  },
  '13': {
    views: [
      0, 11, 5, 10, 33, 9, 46, 49, 13, 0, 3, 3, 2, 1, 3, 2, 1, 1, 0, 1, 1, 0, 0,
      2, 4, 0, 1, 0, 0, 1, 1,
    ],
    downloads: [
      0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
      0, 0, 0, 0, 0, 0,
    ],
  },
  '14': {
    views: [
      2, 10, 34, 67, 48, 23, 55, 72, 17, 7, 5, 6, 5, 4, 2, 15, 13, 12, 11, 10,
      14, 7, 3, 11, 22, 4, 15, 2, 18, 8, 10,
    ],
    downloads: [
      0, 1, 22, 46, 1, 2, 7, 11, 0, 1, 1, 1, 1, 2, 0, 0, 2, 0, 2, 3, 4, 2, 2, 7,
      9, 0, 0, 1, 12, 1, 4,
    ],
  },
  '15': {
    views: [
      1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 0, 5, 0, 1, 0, 1, 1, 1, 0, 4, 0, 0, 1, 1,
      0, 1, 0, 1, 0, 0,
    ],
    downloads: [
      0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
      0, 0, 0, 0, 0, 0,
    ],
  },
  '16': {
    views: [
      6, 17, 26, 17, 90, 33, 135, 129, 44, 14, 6, 10, 7, 6, 0, 10, 9, 2, 3, 2,
      3, 6, 0, 6, 6, 4, 1, 2, 6, 1, 1,
    ],
    downloads: [
      0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
      0, 0, 0, 0, 0, 0,
    ],
  },
  '17': {
    views: [
      0, 0, 3, 7, 26, 9, 28, 29, 10, 1, 3, 0, 2, 2, 0, 1, 1, 4, 1, 1, 1, 0, 0,
      4, 0, 2, 3, 3, 0, 1, 0,
    ],
    downloads: [
      0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
      0, 0, 0, 0, 0, 0,
    ],
  },
};

export const augustMemberTopContent: Record<
  string,
  { viewed: MemberContentEntry[]; downloaded: MemberContentEntry[] }
> = {
  '01': {
    viewed: [
      {
        id: 'VAC3073-M-01007',
        title:
          'Map of flood-prone areas, Anderson South quadrangle, Indiana-Madison Co. : 7.5 minute series (topographic)',
        views: 42,
        downloads: 0,
      },
      {
        id: 'VAC3073-M-00169',
        title:
          'Map of Geist Reservoir, showing depth contours, Marion and Hamilton County',
        views: 22,
        downloads: 0,
      },
      {
        id: 'VAC3073-M-00162',
        title:
          'Map of flood-prone areas, Alexandria quadrangle, Indiana-Madison Co. : 7.5 minute series (topographic)',
        views: 16,
        downloads: 0,
      },
    ],
    downloaded: [
      {
        id: '02352_1887-0002_p8418n49j',
        title: 'Sanborn Map [Indiana--Greencastle] {1887} sheet 2',
        views: 2,
        downloads: 4,
      },
      {
        id: '02352_1887-0003_0z708w54q',
        title: 'Sanborn Map [Indiana--Greencastle] {1887} sheet 3',
        views: 4,
        downloads: 4,
      },
      {
        id: '02352_1892-0003_dz010q26z',
        title: 'Sanborn Map [Indiana--Greencastle] {1892} sheet 3',
        views: 7,
        downloads: 3,
      },
    ],
  },
  '02': {
    viewed: [
      {
        id: 'b35e21c0-c451-0133-1d17-0050569601ca-e',
        title: 'Insurance maps of Monmouth, Warren Co., Illinois, Aug. 1907',
        views: 15,
        downloads: 0,
      },
      {
        id: '474c97d9a5074e8fbe09268f79ee39be_15',
        title: 'Vertical Clearance [Illinois]',
        views: 13,
        downloads: 0,
      },
      {
        id: '8a885da23dfb46caaa1827ad920fb5b1_0',
        title: 'Gateway Traffic Camera Locations [Illinois]',
        views: 12,
        downloads: 0,
      },
    ],
    downloaded: [
      {
        id: '02a-01_imagery-1937-1947-illinois-historical-aerial-photography',
        title: '1937-1947 Illinois Historical Aerial Photography [Illinois]',
        views: 11,
        downloads: 1,
      },
    ],
  },
  '03': {
    viewed: [
      {
        id: 'b1g_03d_264319_51793',
        title: 'Plat Book of Humboldt County, Iowa, 1896 3 Cities and Villages',
        views: 23,
        downloads: 0,
      },
      {
        id: 'b1g_03d_8369_175537',
        title: 'Plat book of Humboldt County, Iowa, 1930',
        views: 20,
        downloads: 0,
      },
      {
        id: 'b1g_03d_371347_130989',
        title: 'Atlas of Humboldt County, Iowa, 1915 2 Township Maps',
        views: 19,
        downloads: 0,
      },
    ],
    downloaded: [
      {
        id: '0d306650-bd46-4588-86b0-ec16a7e06947',
        title: 'General Land Office Plats: Fayette County, Iowa, 1836-1859',
        views: 2,
        downloads: 1,
      },
      {
        id: '14c9d47a-e539-4e44-b8c6-23a11ad00369',
        title: 'General Land Office Plats: Delaware County, Iowa, 1836-1859',
        views: 3,
        downloads: 1,
      },
      {
        id: '48a8a3dc-5b1f-42b0-a36d-06342bec3dbc',
        title: 'General Land Office Plats: Grundy County, Iowa, 1836-1859',
        views: 2,
        downloads: 1,
      },
    ],
  },
  '04': {
    viewed: [
      {
        id: 'b1g_04d_06VVJ6jkp4dM',
        title: 'Map of Germany - Rail Maps - Berlin, 1944',
        views: 18,
        downloads: 0,
      },
      {
        id: 'b1g_04d_00s0hOArjTcy',
        title: 'Map of Slovakia - Senec, 1919',
        views: 17,
        downloads: 0,
      },
      {
        id: '00265863-3c6f-4e83-b9a5-c62e5795e004',
        title: 'Indexed Atlas of the World: Map of Baltimore, 1891',
        views: 15,
        downloads: 0,
      },
    ],
    downloaded: [],
  },
  '05': {
    viewed: [
      {
        id: '7c1a375b08db47e09f855770c59892bc_0',
        title: 'Streets Unformatted [Minnesota--Saint Paul]',
        views: 15,
        downloads: 0,
      },
      {
        id: 'dd135be804bf4939aded5605f405735b_0',
        title: 'School Districts [Minnesota--Clay County]',
        views: 12,
        downloads: 0,
      },
      {
        id: 'f72214b2-672a-4af3-aff6-b35ef4f998f5',
        title:
          'Surficial geology of the Faribault 30 x 60 minute quadrangle, south-central Minnesota, M-130',
        views: 12,
        downloads: 0,
      },
    ],
    downloaded: [
      {
        id: '95199e85-696a-4380-8252-ecbc7b149508',
        title:
          'Bedrock geologic map and mineral exploration data of the western Vermilion district, St Louis and Lake Counties, northeastern Minnesota, M-98',
        views: 5,
        downloads: 5,
      },
      {
        id: 'p16022coll205:1110',
        title: 'Plan de Paris, Métropolitain et Nord-Sud',
        views: 1,
        downloads: 5,
      },
      {
        id: 'p16022coll230:1950',
        title: 'Soil map, Michigan, Allegan Co. sheet',
        views: 4,
        downloads: 4,
      },
    ],
  },
  '06': {
    viewed: [
      {
        id: '000b18d6-63b9-4314-9d4f-17c945ea09b7',
        title:
          '48N 18W - Survey Map of Munising Township, Alger County [Michigan]',
        views: 23,
        downloads: 1,
      },
      {
        id: '5a2ccd86e7574f8eb0e792ba03857c79_0',
        title: 'Part 303 State Wetland Inventory [Michigan]',
        views: 17,
        downloads: 0,
      },
      {
        id: '0dc3d77f-b19c-4a6d-aff1-f0db53a068d1',
        title:
          '35N 26W - Survey Map of Stephenson Township, Menominee County [Michigan]',
        views: 14,
        downloads: 0,
      },
    ],
    downloaded: [
      {
        id: 'd9f12054-ef61-4253-8b84-d6cae51ed52a',
        title:
          '03S 08E - Survey Map of Van Buren Township, Wayne County [Michigan]',
        views: 5,
        downloads: 5,
      },
      {
        id: '87d41e0d-39bb-43fc-87a4-66ee3a72a4ae',
        title:
          '40N 30W - Survey Map of Breitung Township and Lake Antoine Island, Dickinson County, Page 02 [Michigan]',
        views: 4,
        downloads: 3,
      },
      {
        id: '00eff6d1-8899-4c01-8a0e-d40e3ce2e56a',
        title:
          '19N 01E - Survey Map of Secord Township, Gladwin County [Michigan]',
        views: 1,
        downloads: 2,
      },
    ],
  },
  '07': {
    viewed: [
      {
        id: '293f8af9623048dd9fc3b554f662e061_0',
        title: 'Fire Insurance Escrow (FIE) Properties [Michigan--Detroit]',
        views: 13,
        downloads: 0,
      },
      {
        id: 'c1f20e3d-dd13-4a63-b39f-0f3d3975fe08',
        title:
          'Kingdom of Hungary principality of Transylvania, Sclavonia, Croatia, with a part of Valakia, Bulgaria, Bosnia and Servia from the latest surveys ascertained by astronomical observations.',
        views: 13,
        downloads: 0,
      },
      {
        id: '8e532daeec1149879bd5e67fdd9c8be0_0',
        title: 'RMS Crime Incidents [Michigan--Detroit]',
        views: 12,
        downloads: 0,
      },
    ],
    downloaded: [],
  },
  '08': {
    viewed: [
      {
        id: '08d-02',
        title: 'Sanborn Maps: Pennsylvania, 1884-1938',
        views: 33,
        downloads: 0,
      },
      {
        id: '9e0ce87d-07b8-420c-a8aa-9de6104f61d6',
        title: 'Allegheny County Property Sale Transactions',
        views: 26,
        downloads: 0,
      },
      {
        id: '3f7efbda-9d64-43a5-a76e-29657ec048a4',
        title: 'Roscoe, Pennsylvania, 1911',
        views: 19,
        downloads: 0,
      },
    ],
    downloaded: [
      {
        id: 'b1g_jxXQ87T8Owhx',
        title:
          'Aerial Photographs of Southwestern PA-SPRPC [Pennsylvania] {1966}',
        views: 1,
        downloads: 2,
      },
      {
        id: '4988ae5c-a677-4a7f-9bd0-e735c19a8ff3',
        title: 'Allegheny County Addressing Address Points',
        views: 1,
        downloads: 1,
      },
      {
        id: 'b1g_CCoSKglpBDhX',
        title: 'PA Aerial Photos [Pennsylvania--Cambria County] {2001}',
        views: 2,
        downloads: 1,
      },
    ],
  },
  '09': {
    viewed: [
      {
        id: 'f189b6132895412381ce72b8a9379843_3',
        title: 'All Vacant and Abandoned Properties [Indiana--South Bend]',
        views: 18,
        downloads: 0,
      },
      {
        id: '09d-02',
        title: 'Purdue Campus Maps: West Lafayette, Indiana, 1890-2014',
        views: 14,
        downloads: 0,
      },
      {
        id: '7a4f95baa2fc4dcd879d38ab4994c7c0_2',
        title: 'A5Polygon - Neighborhood Communities [Indiana]',
        views: 11,
        downloads: 0,
      },
    ],
    downloaded: [],
  },
  '10': {
    viewed: [
      {
        id: '342a10f9c5d5430d91b7028f4695f6f8_0',
        title: 'ParksandRecreation OpenData [Wisconsin--Outagamie County]',
        views: 15,
        downloads: 0,
      },
      {
        id: '90A80A2D-EBDB-47AB-82C9-64A0C0F16E4E',
        title: 'Zoning Oneida County, WI 2025',
        views: 15,
        downloads: 0,
      },
      {
        id: '5e996fee-9d41-4eea-bad7-2347ba08c1fc',
        title: 'Official State Highway Map, Wisconsin 1920',
        views: 14,
        downloads: 0,
      },
    ],
    downloaded: [
      {
        id: '5f324221-932c-4d6f-b828-30e57ca76bc1',
        title: 'Official State Highway Map, Wisconsin 1984-1985',
        views: 4,
        downloads: 4,
      },
      {
        id: 'IC45-DI',
        title: 'Precambrian Geology of Marathon County, Wisconsin',
        views: 3,
        downloads: 4,
      },
      {
        id: '07B668FC-0C1A-4D80-81AA-FD765A707689',
        title: 'Zoning Kenosha County, WI 2024',
        views: 11,
        downloads: 3,
      },
    ],
  },
  '11': {
    viewed: [
      {
        id: '4d8468466a6c49048fa30b7994aa3e4c_5',
        title: 'School District Boundaries [Ohio--Franklin County]',
        views: 59,
        downloads: 0,
      },
      {
        id: '05c92e9490fa454ca75822836dbf241f_1',
        title: 'County Boundary [Ohio--Franklin County]',
        views: 34,
        downloads: 0,
      },
      {
        id: 'aad4c1fd3f5f408499a748b84d245180_0',
        title: 'Parcel [Ohio--Muskingum County]',
        views: 16,
        downloads: 0,
      },
    ],
    downloaded: [],
  },
  '12': {
    viewed: [
      {
        id: 'camel-1018330',
        title:
          'KH-4b: Declassified Satellite Imagery - Series 1 ("Corona"): DS1110-1073DA043',
        views: 20,
        downloads: 0,
      },
      {
        id: 'camel-1021741',
        title:
          'KH-4b: Declassified Satellite Imagery - Series 1 ("Corona"): DS1107-1089DA050',
        views: 20,
        downloads: 0,
      },
      {
        id: '0240b9e03c384c41bf94cd047b855cf3_0',
        title:
          'Forest Preserve District of Cook County Picnic Groves [Illinois--Cook County]',
        views: 18,
        downloads: 0,
      },
    ],
    downloaded: [
      {
        id: 'f9b09dd4-077e-47fa-b924-01a0261c8606',
        title:
          'Hyde Park Community /prepared by the Department of Sociology, the University of Chicago.',
        views: 15,
        downloads: 2,
      },
      {
        id: '05b5c238-5423-4c5a-a244-4b93c46e6852',
        title: 'Laghi di Messico',
        views: 9,
        downloads: 1,
      },
      {
        id: '2cde519d-a1df-4b02-ab02-b1b575f4044a',
        title:
          'Map no. VII showing places of residence of 7541 alleged male offenders placed in the Cook County jail during the year 1920, 17-75 years of age /prepared by research sociologists; Behavior Research Fund, Chicago.',
        views: 1,
        downloads: 1,
      },
    ],
  },
  '13': {
    viewed: [
      {
        id: '13c-02',
        title: 'City of Grand Island Public GIS Data Portal',
        views: 19,
        downloads: 0,
      },
      {
        id: '870d5e73fd3e43e3b8e5f9a2029b9573_5',
        title: 'Tax Parcels [Nebraska--Sarpy County]',
        views: 15,
        downloads: 0,
      },
      {
        id: '94b9de9e1a474dedada5fe5f6269fbf3_0',
        title: 'Sanitary and Improvement District (SID) [Nebraska--Omaha]',
        views: 12,
        downloads: 0,
      },
    ],
    downloaded: [],
  },
  '14': {
    viewed: [
      {
        id: 'e1fdf22f4ce04059b2f87dbaa1d727a2_0',
        title: 'New Jersey Standard Route Id And Milepost [New Jersey]',
        views: 20,
        downloads: 0,
      },
      {
        id: '0dd6d6786d724cfbbd3591481c7f81d3_0',
        title:
          'Imagery Warehouse - 1930 Aerial Image Grid (Hosted) [New Jersey]',
        views: 16,
        downloads: 0,
      },
      {
        id: 'rutgers-lib:39389',
        title: 'New map of Bayonne, N.J.',
        views: 15,
        downloads: 5,
      },
    ],
    downloaded: [
      {
        id: 'rutgers-lib:28695',
        title: 'Riparian & stream survey',
        views: 5,
        downloads: 5,
      },
      {
        id: 'rutgers-lib:39389',
        title: 'New map of Bayonne, N.J.',
        views: 15,
        downloads: 5,
      },
      {
        id: 'rutgers-lib:63578',
        title:
          'State of New Jersey Department of Environmental Protection Big Creek - Tuckerton',
        views: 6,
        downloads: 5,
      },
    ],
  },
  '15': {
    viewed: [
      {
        id: '02b645d4-233e-46fd-a23e-ce17caf89711',
        title:
          "La Spagna : all'illmo. e reumo. Sigre. Monsre. Gio. Battista Febei, referendario dell'una, e l'altra segnatura",
        views: 2,
        downloads: 0,
      },
      {
        id: '71a39fba-fd5c-40bc-9335-686075b99f68',
        title: "Carte de l'Egypte, de la Nubie de l'Abissinie &c",
        views: 2,
        downloads: 0,
      },
      {
        id: 'c6bcf2be-a569-4149-98d7-b718437498c7',
        title: 'Territoire du Ruanda-Urundi',
        views: 2,
        downloads: 0,
      },
    ],
    downloaded: [],
  },
  '16': {
    viewed: [
      {
        id: '6f31b076628d4f8ca5a964cbefd2cccc_0',
        title: 'Washington Large Fires 1973-2025 [Washington (State)]',
        views: 20,
        downloads: 0,
      },
      {
        id: 'f2fb7086f74448479bdf287313300738_0',
        title: 'Wildfire Smoke Exposure [Washington (State)]',
        views: 15,
        downloads: 0,
      },
      {
        id: '16b-53053',
        title: 'Pierce County Open GeoSpatial Data Portal',
        views: 14,
        downloads: 0,
      },
    ],
    downloaded: [],
  },
  '17': {
    viewed: [
      {
        id: '9ab2e66cddab4ad3a2530d9bdb8db017_0',
        title: 'Voter Precincts [Oregon--Portland]',
        views: 12,
        downloads: 0,
      },
      {
        id: 'f6c921f7183e4f32b39a45f8c7c5610c_0',
        title: 'Law Enforcement Facilities [Oregon]',
        views: 11,
        downloads: 0,
      },
      {
        id: '8d006fb5453c4dbfad476033e847eca8_0',
        title: 'TSP Existing Paths Trails [Oregon--Bend]',
        views: 10,
        downloads: 0,
      },
    ],
    downloaded: [],
  },
};

export const augustTopSearchTerms = [
  {
    term: 'wetlands',
    count: 95,
  },
  {
    term: 'iran maps',
    count: 67,
  },
  {
    term: 'sanborn',
    count: 31,
  },
  {
    term: 'austin',
    count: 21,
  },
  {
    term: 'Washington county iowa',
    count: 20,
  },
  {
    term: 'iran',
    count: 19,
  },
  {
    term: 'redlining',
    count: 17,
  },
  {
    term: 'bloomington',
    count: 16,
  },
];

export const augustTopZeroResultQueries = [
  {
    term: 'indiana field survey iran hardin i 38l',
    count: 9,
  },
  {
    term: '32.503232, 44.449000',
    count: 8,
  },
  {
    term: 'Iowa City Sanborn, 1883',
    count: 8,
  },
  {
    term: '31.971794,48.809872',
    count: 7,
  },
  {
    term: '9266 town line rd Larsen wi',
    count: 7,
  },
  {
    term: '32.654583, 44.405139',
    count: 6,
  },
  {
    term: 'maple range township mi',
    count: 6,
  },
  {
    term: '205 E Sycamore Street Westport, Indiana',
    count: 5,
  },
  {
    term: '3115 hickman rd des moines',
    count: 5,
  },
  {
    term: 'Map of the settled part of Wisconsin and Iowa',
    count: 5,
  },
];

export const augustZeroResultBreakdown = {
  with_query: 1148,
  without_query: 307,
};

export const augustDiscoveryViews = [
  {
    label: 'Map',
    count: 5744,
    percent: 76.1,
    color: '#003C5B',
  },
  {
    label: 'Gallery',
    count: 1240,
    percent: 16.4,
    color: '#1E40AF',
  },
  {
    label: 'List',
    count: 561,
    percent: 7.4,
    color: '#2563EB',
  },
];

export const augustResourceClassFilters = [
  {
    label: 'Maps',
    count: 700,
    color: '#003C5B',
  },
  {
    label: 'Datasets',
    count: 256,
    color: '#1E40AF',
  },
  {
    label: 'Imagery',
    count: 121,
    color: '#2563EB',
  },
  {
    label: 'Web services',
    count: 59,
    color: '#3B82F6',
  },
  {
    label: 'Collections',
    count: 24,
    color: '#60A5FA',
  },
  {
    label: 'Websites',
    count: 13,
    color: '#93C5FD',
  },
  {
    label: 'Other',
    count: 1,
    color: '#BFDBFE',
  },
];

export const augustRequestMix = [
  {
    label: 'API docs',
    count: 262523,
    color: '#003C5B',
    percent: 43.8,
  },
  {
    label: 'Access checks',
    count: 167686,
    color: '#1E40AF',
    percent: 28.0,
  },
  {
    label: 'Analytics capture',
    count: 31337,
    color: '#2563EB',
    percent: 5.2,
  },
  {
    label: 'Everything else',
    count: 137385,
    color: '#3B82F6',
    percent: 22.9,
  },
];

export const augustPeakApiTrafficBreakdown = [
  {
    label: 'Turnstile status checks',
    detail: 'Access-status requests',
    count: 37090,
    percent: 75.3,
  },
  {
    label: 'API documentation probes',
    detail: 'Requests to the API documentation',
    count: 8528,
    percent: 17.3,
  },
  {
    label: 'Resource endpoints',
    detail: 'Requests for catalog resources',
    count: 871,
    percent: 1.8,
  },
  {
    label: 'Thumbnails',
    detail: 'Catalog image delivery',
    count: 1293,
    percent: 2.6,
  },
  {
    label: 'Analytics event capture',
    detail: 'Requests to record product interactions',
    count: 404,
    percent: 0.8,
  },
  {
    label: 'Robots and sitemaps',
    detail: 'Crawler discovery traffic',
    count: 812,
    percent: 1.6,
  },
  {
    label: 'Everything else',
    detail: 'Other recorded endpoints',
    count: 260,
    percent: 0.5,
  },
];

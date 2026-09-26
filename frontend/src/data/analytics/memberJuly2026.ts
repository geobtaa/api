export interface MemberContentEntry {
  id: string;
  title: string;
  views: number;
  downloads: number;
}

export interface MemberDailySeries {
  views: readonly number[];
  downloads: readonly number[];
}

export const memberDailySeries: Record<string, MemberDailySeries> = {
  '01': {
    views: [
      41, 34, 43, 28, 29, 18, 17, 24, 16, 17, 17, 42, 24, 16, 37, 31, 35, 24,
      24, 32, 43, 28, 16, 26, 41, 43, 43, 35, 47, 9, 26,
    ],
    downloads: [
      3, 3, 4, 1, 0, 0, 2, 4, 1, 0, 5, 10, 1, 0, 0, 12, 0, 0, 0, 9, 2, 0, 1, 3,
      3, 7, 4, 7, 18, 1, 2,
    ],
  },
  '02': {
    views: [
      22, 15, 12, 6, 2, 6, 4, 8, 9, 10, 13, 14, 11, 10, 26, 0, 3, 1, 3, 12, 8,
      6, 17, 11, 20, 10, 1, 7, 6, 1, 3,
    ],
    downloads: [
      1, 0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0,
      0, 0, 0, 0, 0, 0,
    ],
  },
  '03': {
    views: [
      8, 11, 11, 23, 1, 21, 19, 1, 14, 12, 1, 4, 11, 8, 19, 5, 8, 8, 7, 8, 14,
      8, 17, 4, 23, 4, 2, 10, 9, 8, 16,
    ],
    downloads: [
      1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
      0, 0, 0, 0, 0, 0,
    ],
  },
  '04': {
    views: [
      9, 7, 6, 4, 4, 9, 11, 9, 12, 10, 6, 6, 10, 11, 18, 14, 5, 2, 7, 11, 8, 8,
      8, 4, 9, 2, 10, 7, 17, 12, 8,
    ],
    downloads: [
      0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
      0, 0, 0, 0, 0, 0,
    ],
  },
  '05': {
    views: [
      32, 38, 21, 23, 26, 35, 33, 50, 48, 29, 22, 17, 31, 31, 39, 32, 17, 20,
      18, 54, 44, 20, 19, 34, 36, 20, 59, 24, 22, 25, 27,
    ],
    downloads: [
      9, 4, 0, 0, 0, 0, 1, 4, 12, 0, 0, 4, 2, 3, 2, 2, 0, 0, 0, 9, 3, 2, 4, 0,
      0, 0, 9, 3, 1, 5, 2,
    ],
  },
  '06': {
    views: [
      31, 20, 35, 40, 41, 54, 32, 32, 22, 42, 22, 29, 35, 26, 14, 31, 11, 15,
      27, 11, 20, 45, 14, 12, 42, 22, 34, 73, 34, 17, 39,
    ],
    downloads: [
      4, 5, 3, 11, 4, 11, 3, 1, 2, 3, 3, 3, 4, 5, 2, 6, 0, 4, 5, 0, 2, 12, 1, 1,
      7, 0, 2, 19, 6, 4, 5,
    ],
  },
  '07': {
    views: [
      9, 11, 10, 3, 8, 3, 14, 13, 8, 3, 7, 3, 9, 40, 6, 11, 3, 23, 5, 22, 14,
      16, 3, 12, 5, 2, 11, 12, 8, 10, 6,
    ],
    downloads: [
      0, 0, 4, 0, 1, 0, 0, 1, 0, 0, 3, 0, 3, 2, 1, 0, 1, 1, 0, 1, 0, 0, 0, 0, 1,
      0, 1, 1, 0, 0, 0,
    ],
  },
  '08': {
    views: [
      18, 31, 29, 45, 50, 33, 33, 26, 21, 17, 5, 21, 33, 32, 23, 31, 11, 14, 6,
      38, 31, 15, 19, 25, 21, 10, 31, 15, 31, 82, 56,
    ],
    downloads: [
      0, 1, 0, 0, 1, 3, 4, 2, 1, 1, 0, 0, 0, 1, 2, 0, 0, 1, 0, 0, 3, 4, 0, 1, 1,
      0, 0, 0, 0, 1, 2,
    ],
  },
  '09': {
    views: [
      8, 5, 12, 2, 9, 7, 10, 5, 4, 4, 0, 3, 5, 3, 5, 3, 12, 3, 2, 4, 3, 4, 6, 0,
      4, 3, 4, 6, 7, 2, 2,
    ],
    downloads: [
      0, 0, 0, 0, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 0, 0, 1, 0, 0, 0, 0, 0,
      0, 0, 0, 0, 0, 0,
    ],
  },
  '10': {
    views: [
      26, 23, 17, 5, 72, 17, 22, 25, 15, 10, 3, 8, 18, 28, 7, 18, 13, 8, 9, 15,
      11, 20, 20, 21, 18, 28, 18, 12, 20, 9, 13,
    ],
    downloads: [
      3, 7, 3, 0, 58, 4, 5, 2, 1, 1, 0, 0, 0, 1, 0, 6, 0, 2, 0, 4, 3, 0, 1, 2,
      6, 9, 0, 2, 2, 0, 1,
    ],
  },
  '11': {
    views: [
      13, 5, 6, 1, 3, 12, 16, 19, 3, 8, 2, 1, 6, 22, 10, 12, 2, 4, 2, 6, 4, 17,
      9, 2, 8, 6, 7, 5, 14, 12, 10,
    ],
    downloads: [
      0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
      1, 0, 0, 0, 0, 0,
    ],
  },
  '12': {
    views: [
      27, 25, 52, 20, 109, 64, 22, 45, 38, 38, 34, 91, 56, 24, 92, 39, 40, 110,
      32, 57, 38, 29, 57, 26, 39, 31, 31, 49, 66, 32, 45,
    ],
    downloads: [
      0, 0, 0, 0, 0, 0, 1, 2, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0,
      0, 1, 0, 0, 0, 0,
    ],
  },
  '13': {
    views: [
      0, 1, 1, 0, 0, 1, 2, 4, 1, 2, 0, 0, 0, 5, 5, 2, 1, 0, 3, 1, 6, 2, 0, 2, 7,
      1, 3, 2, 1, 1, 1,
    ],
    downloads: [
      0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 0, 0, 0, 0,
      0, 0, 0, 0, 0, 0,
    ],
  },
  '14': {
    views: [
      4, 5, 7, 8, 7, 23, 20, 9, 9, 11, 3, 4, 19, 2, 9, 11, 21, 2, 2, 4, 2, 9, 4,
      3, 34, 2, 9, 10, 19, 19, 6,
    ],
    downloads: [
      0, 2, 2, 0, 3, 0, 2, 1, 0, 1, 2, 2, 6, 1, 5, 6, 12, 0, 0, 1, 0, 0, 1, 0,
      0, 0, 3, 6, 10, 5, 0,
    ],
  },
  '15': {
    views: [
      0, 2, 0, 1, 0, 0, 18, 0, 1, 3, 0, 0, 1, 18, 0, 0, 2, 2, 0, 2, 1, 1, 0, 0,
      0, 0, 2, 1, 0, 1, 0,
    ],
    downloads: [
      0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
      0, 0, 0, 0, 0, 0,
    ],
  },
  '16': {
    views: [
      12, 15, 11, 4, 2, 3, 15, 10, 13, 7, 6, 10, 13, 15, 1, 3, 5, 3, 5, 8, 4, 4,
      9, 4, 17, 7, 10, 5, 9, 3, 8,
    ],
    downloads: [
      0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
      0, 0, 0, 0, 0, 0,
    ],
  },
  '17': {
    views: [
      2, 3, 9, 1, 0, 4, 2, 2, 0, 0, 0, 1, 3, 0, 1, 2, 3, 1, 1, 0, 0, 4, 1, 0,
      14, 1, 1, 3, 3, 1, 5,
    ],
    downloads: [
      0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
      0, 0, 0, 0, 0, 0,
    ],
  },
};

export const memberTopContent: Record<
  string,
  { viewed: MemberContentEntry[]; downloaded: MemberContentEntry[] }
> = {
  '01': {
    viewed: [
      {
        id: '02415_1899-0022_mc87pq637',
        title: 'Sanborn Map [Indiana--Michigan City] {1899} sheet 22',
        views: 24,
        downloads: 0,
      },
      {
        id: 'VAC3073-M-00169',
        title:
          'Map of Geist Reservoir, showing depth contours, Marion and Hamilton County',
        views: 21,
        downloads: 0,
      },
      {
        id: 'VAC9619-000190',
        title: 'M-34-36-Г Дубенка (Dubienka, Poland)',
        views: 18,
        downloads: 0,
      },
    ],
    downloaded: [
      {
        id: 'VAC9619-003429',
        title: 'M-38-114 Сталинград (Volgograd, Russia)',
        views: 8,
        downloads: 3,
      },
      {
        id: '750490cd-bcca-4f91-86a5-bc6d341a68fc',
        title:
          'Indiana, the influence of the Indian upon its history: with Indian and French names for natural and cultural locations',
        views: 3,
        downloads: 3,
      },
      {
        id: '02532_1896-0008_q237hs44j',
        title: 'Sanborn Map [Indiana--Washington] {1896} sheet 8',
        views: 3,
        downloads: 3,
      },
    ],
  },
  '02': {
    viewed: [
      {
        id: '8a885da23dfb46caaa1827ad920fb5b1_0',
        title: 'Gateway Traffic Camera Locations [Illinois]',
        views: 26,
        downloads: 0,
      },
      {
        id: '07a2af00-a52d-0134-232b-0050569601ca-e',
        title: 'Insurance maps of Chicago, Illinois, Volume E',
        views: 11,
        downloads: 0,
      },
      {
        id: 'cfbea790-c451-0133-1d17-0050569601ca-d',
        title:
          'Insurance maps of Galesburg, including East Galesburg, Illinois, April 1918',
        views: 11,
        downloads: 0,
      },
    ],
    downloaded: [
      {
        id: 'b3f6286e-ccf7-4cbc-8872-96a367002a61',
        title: 'State Boundary [Illinois]',
        views: 4,
        downloads: 2,
      },
      {
        id: '02a-01_hydrology-potential-agricultural-chemical-contamination-aquifers',
        title:
          'Potential of Agricultural Chemical Contamination of Aquifers [Illinois]',
        views: 3,
        downloads: 1,
      },
      {
        id: '02a-01_geology-bedrock-valleys',
        title: 'Bedrock Valleys [Illinois]',
        views: 1,
        downloads: 1,
      },
    ],
  },
  '03': {
    viewed: [
      {
        id: '03d-01',
        title: 'University of Iowa Digital Library: Atlases and Maps',
        views: 14,
        downloads: 0,
      },
      {
        id: 'b1g_03d_8369_15766',
        title: "Plat book of O'Brien County, Iowa, 1930",
        views: 8,
        downloads: 0,
      },
      {
        id: 'ui_api_223',
        title: 'Boone County, Iowa, 1939, aerial photomosaic index',
        views: 6,
        downloads: 0,
      },
    ],
    downloaded: [
      {
        id: 'f1b57f24-d474-4493-90e1-d3c25f39b65b',
        title:
          'An Illustrated Historical Atlas of Des Moines County, Iowa, 1873',
        views: 2,
        downloads: 1,
      },
      {
        id: '14c9d47a-e539-4e44-b8c6-23a11ad00369',
        title: 'General Land Office Plats: Delaware County, Iowa, 1836-1859',
        views: 2,
        downloads: 1,
      },
    ],
  },
  '04': {
    viewed: [
      {
        id: 'a31ff4e8951c487ca52ce0a5b11a80d1_3',
        title: 'MD Electric Vehicle Charging Stations [Maryland]',
        views: 10,
        downloads: 0,
      },
      {
        id: '72a9f1e7-19ef-43ed-b428-21c3c368b5aa',
        title: "Special Tax Districts: Prince George's County, Maryland",
        views: 9,
        downloads: 0,
      },
      {
        id: 'd30c340fc52e42a5a46287dcad817200_0',
        title:
          'Maryland Correctional Facilities - Federal Correctional Facilities [Maryland]',
        views: 8,
        downloads: 0,
      },
    ],
    downloaded: [
      {
        id: 'vxhp-vpgw',
        title: "Police Beats [Maryland--Prince George's County]",
        views: 6,
        downloads: 1,
      },
      {
        id: '832ca7be-92bf-4869-998d-93ef46041ea0',
        title: "Map of Korea - City Map - P'ohang, South Korea, 1976",
        views: 1,
        downloads: 1,
      },
    ],
  },
  '05': {
    viewed: [
      {
        id: 'p16022coll245:264',
        title:
          'Plat book of the city of Saint Paul, Minn. and suburbs : from official records, private plans and actual surveys',
        views: 22,
        downloads: 0,
      },
      {
        id: 'p16022coll230:1226',
        title:
          'Map of the Theodore Roosevelt International Highway, Portland, Oregon to Portland, Maine',
        views: 17,
        downloads: 0,
      },
      {
        id: 'p16022coll231:698',
        title: 'Plat book of Le Sueur county, Minnesota',
        views: 14,
        downloads: 0,
      },
    ],
    downloaded: [
      {
        id: 't039r20w4fi01',
        title:
          'General Land Office Township Plat - Original Survey: Minnesota (T039N R20W), 1851',
        views: 5,
        downloads: 5,
      },
      {
        id: '96695a9199574b1fa7d0d0b650e68c77_8',
        title: 'Bicycle Count Stations [Minnesota--Hennepin County]',
        views: 6,
        downloads: 4,
      },
      {
        id: 'p16022coll205:757',
        title: 'Plano de Manila y sus arrabales',
        views: 6,
        downloads: 3,
      },
    ],
  },
  '06': {
    viewed: [
      {
        id: '292ccdb0756448e892929fa4a27b3b1f_1',
        title: 'Lake Clarity - Sechi Depth [Michigan]',
        views: 50,
        downloads: 0,
      },
      {
        id: 'c349bc2bb6c2468594d341a09f520ea8_0',
        title: '2026 Voting Precincts [Michigan]',
        views: 23,
        downloads: 0,
      },
      {
        id: 'bb41f39b-2d8a-46f5-81da-aaa0e8b317f3',
        title:
          '07N 05W - Survey Map of Lyons Township, Ionia County, Page 1 [Michigan]',
        views: 17,
        downloads: 6,
      },
    ],
    downloaded: [
      {
        id: 'bb41f39b-2d8a-46f5-81da-aaa0e8b317f3',
        title:
          '07N 05W - Survey Map of Lyons Township, Ionia County, Page 1 [Michigan]',
        views: 17,
        downloads: 6,
      },
      {
        id: '48e5e73f-9087-45bd-b7c1-86edbd50d5b1',
        title:
          '07N 05W - Survey Map of Lyons Township, Ionia County, Page 2 [Michigan]',
        views: 11,
        downloads: 6,
      },
      {
        id: '11651802-8f65-4e7f-9db8-129e7b707038',
        title:
          '01N 05E - Survey Map of Hamburg Township, Livingston County [Michigan]',
        views: 3,
        downloads: 6,
      },
    ],
  },
  '07': {
    viewed: [
      {
        id: '00308e38-fe66-431b-9c8a-9e5a19951a0b',
        title:
          'Nova Poloniae delineatio; ex officina et sumptibus Iudoci Hondii.',
        views: 15,
        downloads: 0,
      },
      {
        id: '0035018d-63a8-4682-95e5-d1c3d4104a7d',
        title: 'Novissima et accuratissima totius Americae descriptio',
        views: 12,
        downloads: 0,
      },
      {
        id: '3c8050c9-397c-49bb-be4d-4472ddceb07e',
        title: 'Plan of Detroit Woodward,Augustus Brevoort.',
        views: 10,
        downloads: 0,
      },
    ],
    downloaded: [
      {
        id: '2f3c06da-21a0-410f-b230-be07165aeb89',
        title:
          "Map of Home Owners' Loan Corporation [Los Angeles, California] {1939}",
        views: 6,
        downloads: 7,
      },
      {
        id: '9bb5c76a-20ce-4235-861d-60c5e20592b7',
        title:
          "Map of Home Owners' Loan Corporation [Lexington, Kentucky] {1936}",
        views: 2,
        downloads: 3,
      },
      {
        id: '3897778e-9694-4316-af5a-fc2dadf8b792',
        title:
          "Map of Home Owners' Loan Corporation [Philadelphia, Pennsylvania] {1937}",
        views: 7,
        downloads: 2,
      },
    ],
  },
  '08': {
    viewed: [
      {
        id: '95dcf338-fc27-4d3b-8883-967b3223933b',
        title: 'Emporium, Pennsylvania, 1892',
        views: 100,
        downloads: 0,
      },
      {
        id: '08d-02',
        title: 'Sanborn Maps: Pennsylvania, 1884-1938',
        views: 44,
        downloads: 0,
      },
      {
        id: 'pasda-1078',
        title: 'PennPilot (Historical Aerial Photo Library) [Pennsylvania]',
        views: 30,
        downloads: 2,
      },
    ],
    downloaded: [
      {
        id: 'pasda-2604',
        title: 'Pennsylvania Stream Polygons 2019 [Pennsylvania] {2019}',
        views: 4,
        downloads: 4,
      },
      {
        id: 'pasda-1078',
        title: 'PennPilot (Historical Aerial Photo Library) [Pennsylvania]',
        views: 30,
        downloads: 2,
      },
      {
        id: 'pasda-316',
        title:
          'Bedrock Surface Topography Digital Elevation Raster of Pennsylvania [Pennsylvania]',
        views: 6,
        downloads: 2,
      },
    ],
  },
  '09': {
    viewed: [
      {
        id: 'f189b6132895412381ce72b8a9379843_3',
        title: 'All Vacant and Abandoned Properties [Indiana--South Bend]',
        views: 46,
        downloads: 0,
      },
      {
        id: '09d-02',
        title: 'Purdue Campus Maps: West Lafayette, Indiana, 1890-2014',
        views: 10,
        downloads: 0,
      },
      {
        id: 'b06d96e4-c917-4afc-a3df-adbbc9a2273c',
        title:
          'National Sediment Inventory (NSI) and Data Summaries, Derived from EPA BASINS 3: Indiana',
        views: 5,
        downloads: 1,
      },
    ],
    downloaded: [
      {
        id: '055b9a57-4eb3-4d64-af8c-f6cd76370187',
        title: 'Bathymetric Contours for Selected Lakes: Indiana',
        views: 2,
        downloads: 2,
      },
      {
        id: '80e4c937-6bfa-4b98-9a16-80cfb20165c1',
        title: 'Bedrock Surface Elevation DEM : Indiana',
        views: 1,
        downloads: 2,
      },
      {
        id: 'b06d96e4-c917-4afc-a3df-adbbc9a2273c',
        title:
          'National Sediment Inventory (NSI) and Data Summaries, Derived from EPA BASINS 3: Indiana',
        views: 5,
        downloads: 1,
      },
    ],
  },
  '10': {
    viewed: [
      {
        id: '000a439884964027914c9878ea4cdeda_0',
        title: 'Coastal Resilient Sites, Northeast U.S. [United States]',
        views: 16,
        downloads: 0,
      },
      {
        id: 'C3PRI5S7BOXTX8V',
        title: 'Original PLSS Plat Map: WI T33N, R21E',
        views: 14,
        downloads: 0,
      },
      {
        id: '2A4A0DE6-4015-4089-9AEA-0E10C6468635',
        title: 'Wisconsin Historic Aerial Photography Photo Centers',
        views: 11,
        downloads: 0,
      },
    ],
    downloaded: [
      {
        id: '6BPFRDZGPNZ4I9C',
        title:
          'Original Public Land Survey System Map: Wisconsin Township 22 North, Range 06 East - Front',
        views: 4,
        downloads: 4,
      },
      {
        id: '88048d89-7d61-4d14-9ff6-2a1a0e28204b',
        title: 'Official State Highway Map, Wisconsin 1975',
        views: 3,
        downloads: 3,
      },
      {
        id: 'RJ7JBI2CP4WS38L',
        title:
          'Original Public Land Survey System Map: Wisconsin Township 01 North, Range 23 East',
        views: 2,
        downloads: 2,
      },
    ],
  },
  '11': {
    viewed: [
      {
        id: '4d8468466a6c49048fa30b7994aa3e4c_5',
        title: 'School District Boundaries [Ohio--Franklin County]',
        views: 57,
        downloads: 0,
      },
      {
        id: '05c92e9490fa454ca75822836dbf241f_1',
        title: 'County Boundary [Ohio--Franklin County]',
        views: 28,
        downloads: 0,
      },
      {
        id: '11b-39063',
        title: 'GIS Data Downloads for Hancock County, Ohio',
        views: 15,
        downloads: 0,
      },
    ],
    downloaded: [
      {
        id: 'f65e0338-426f-4708-80c8-08417bdffc1d',
        title: 'Floodplain: Crawford County, Ohio',
        views: 2,
        downloads: 1,
      },
    ],
  },
  '12': {
    viewed: [
      {
        id: 'camel-1022954',
        title:
          'KH-4a: Declassified Satellite Imagery - Series 1 ("Corona"): DS1024-2104DA160',
        views: 15,
        downloads: 0,
      },
      {
        id: 'camel-1013673',
        title: 'Survey of Egypt: El Bagur',
        views: 14,
        downloads: 0,
      },
      {
        id: 'camel-1010560',
        title:
          'KH-4b: Declassified Satellite Imagery - Series 1 ("Corona"): DS1110-1073DA056',
        views: 13,
        downloads: 0,
      },
    ],
    downloaded: [
      {
        id: '0e442f3a-a4e8-44f1-b8be-cbcd69ef2c44',
        title:
          'High-Resolution Land Cover, NE Illinois and NW Indiana: Chicago, 2010',
        views: 2,
        downloads: 2,
      },
      {
        id: 'b471f239-4fbc-4388-a5ef-db921c7ed672',
        title: 'Homicide counts and rates [Texas--Houston] {1979-1993}',
        views: 6,
        downloads: 1,
      },
      {
        id: '7n8x-uj9u',
        title:
          'Historical - ccgisdata - ESRI Chicago Bldg Footprints [Illinois--Cook County] {2008}',
        views: 2,
        downloads: 1,
      },
    ],
  },
  '13': {
    viewed: [
      {
        id: 'd4a1b8d1caaa495a9750e40b94759414_3',
        title: 'LiDAR Tile Index [Nebraska] {2019}',
        views: 8,
        downloads: 0,
      },
      {
        id: 'cb6ed038bc16467e813e3279feebfc2a_0',
        title: 'Municipal Boundaries [Nebraska]',
        views: 6,
        downloads: 0,
      },
      {
        id: '3d6fea6921d94ce18f9eaf44120564a7_3',
        title: 'Easements in Hall County, Nebraska [Nebraska--Grand Island]',
        views: 2,
        downloads: 0,
      },
    ],
    downloaded: [
      {
        id: '8bcf6d145acf47228f848cf47c761b93_0',
        title: 'Tax Districts [Nebraska] {2023}',
        views: 1,
        downloads: 2,
      },
    ],
  },
  '14': {
    viewed: [
      {
        id: '0dd6d6786d724cfbbd3591481c7f81d3_0',
        title:
          'Imagery Warehouse - 1930 Aerial Image Grid (Hosted) [New Jersey]',
        views: 17,
        downloads: 0,
      },
      {
        id: 'rutgers-lib:20581',
        title: 'Washington, New Jersey 1972',
        views: 11,
        downloads: 5,
      },
      {
        id: '737706d83f3c4c5a88c54807a487c735_0',
        title: 'Marina Resources [New Jersey]',
        views: 11,
        downloads: 0,
      },
    ],
    downloaded: [
      {
        id: 'rutgers-lib:20581',
        title: 'Washington, New Jersey 1972',
        views: 11,
        downloads: 5,
      },
      {
        id: 'rutgers-lib:56888',
        title: 'Map of division of waterfont in Hoboken City, N.J.',
        views: 5,
        downloads: 4,
      },
      {
        id: 'rutgers-lib:36020',
        title:
          'Map of the town of Paterson, N.J., compiled from actual surveys / by U. W. Freeman, surveyor, &c.',
        views: 3,
        downloads: 3,
      },
    ],
  },
  '15': {
    viewed: [
      {
        id: '6e330605-f83d-4483-8313-7d6b3bd0931e',
        title:
          'Central Manufacturing District : the Pershing Road Development.',
        views: 4,
        downloads: 0,
      },
      {
        id: '6cd985a1-1b1f-4d72-be9c-d64e5b3cdb30',
        title: 'Western Africa',
        views: 3,
        downloads: 0,
      },
      {
        id: 'a0984553-00ab-4a04-812f-5249e3a0a5ca',
        title: 'Mauritania nuova tavola.',
        views: 3,
        downloads: 0,
      },
    ],
    downloaded: [],
  },
  '16': {
    viewed: [
      {
        id: '2499235ca6454b149415bb9bb8b94831_0',
        title: 'RTA Boundary [Washington (State)--Pierce County]',
        views: 11,
        downloads: 0,
      },
      {
        id: '0d907da18965462ea2b43fda41271f84_0',
        title: 'Tribal Jurisdiction [Washington (State)--Snohomish County]',
        views: 7,
        downloads: 0,
      },
      {
        id: 'c83fc53d03db43dd861646f8a76bf0bf_0',
        title:
          'WSDOT - Bicycle and Pedestrian Permanent Count Locations [Washington (State)]',
        views: 7,
        downloads: 0,
      },
    ],
    downloaded: [],
  },
  '17': {
    viewed: [
      {
        id: 'c0e6948bb6d54f3884635fcc2f94e581_0',
        title: 'Active Faults [Oregon]',
        views: 11,
        downloads: 0,
      },
      {
        id: '00b99cd9ff1449bf84a3cd83e60463ef_0',
        title: 'Streams (line) [Oregon--Portland]',
        views: 3,
        downloads: 0,
      },
      {
        id: '966b41e587124dd4a74ea00d2a9ed448_0',
        title: 'Eugene Urban Growth Boundary (UGB) - HUB [Oregon--Eugene]',
        views: 3,
        downloads: 0,
      },
    ],
    downloaded: [],
  },
};

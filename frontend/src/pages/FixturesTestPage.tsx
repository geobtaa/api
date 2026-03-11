import {
  ExternalLink,
  FlaskConical,
  Database,
  FileText,
  Globe,
  Layers,
  Image,
  Package,
  Server,
  Shield,
  BookOpen,
  Download,
  MapPin,
  Cpu,
  HardDrive,
  X,
  CheckCircle,
  XCircle,
  Loader,
} from 'lucide-react';
import { useState, useEffect, useMemo } from 'react';
import { Link } from 'react-router';

interface Fixture {
  id: string;
  name: string;
  description: string;
  category: string;
  source: 'gbl' | 'btaa';
}

type FixtureStatus = 'loading' | 'available' | 'unavailable' | 'error';

// GeoBlacklight fixtures (original)
const geoblacklightFixtures: Fixture[] = [
  {
    id: 'mit-001145244',
    name: 'actual-papermap1',
    description: 'Nondigitized paper map with library catalog link',
    category: 'Paper Maps',
    source: 'gbl',
  },
  {
    id: 'nyu-2451-34564',
    name: 'actual-point1',
    description: 'Point dataset with WMS and WFS',
    category: 'Point Data',
    source: 'gbl',
  },
  {
    id: 'tufts-cambridgegrid100-04',
    name: 'actual-polygon1',
    description: 'Polygon dataset with WFS, WMS, and FGDC metadata',
    category: 'Polygon Data',
    source: 'gbl',
  },
  {
    id: 'stanford-dp018hs9766',
    name: 'actual-raster1',
    description: 'Restricted raster layer with WMS and metadata',
    category: 'Raster Data',
    source: 'gbl',
  },
  {
    id: 'nyu_2451_34635',
    name: 'baruch_ancestor1',
    description: 'SQLite Database with documentation download (parent)',
    category: 'Databases',
    source: 'gbl',
  },
  {
    id: 'nyu_2451_34636',
    name: 'baruch_ancestor2',
    description: 'Geodatabase with documentation download (parent)',
    category: 'Databases',
    source: 'gbl',
  },
  {
    id: 'nyu_2451_34502',
    name: 'baruch_documentation_download',
    description:
      'Point dataset with WMS, WFS, documentation download, and parent records',
    category: 'Point Data',
    source: 'gbl',
  },
  {
    id: 'princeton-sx61dn82p',
    name: 'bbox-spans-180',
    description:
      'Scanned map with IIIF and direct TIFF download spanning 180th meridian',
    category: 'Scanned Maps',
    source: 'gbl',
  },
  {
    id: 'c8b46b52-0846-4abb-ba56-b484064f84ac',
    name: 'complex-geom',
    description: 'Scanned map with MULTIPOLYGON locn_geometry value',
    category: 'Scanned Maps',
    source: 'gbl',
  },
  {
    id: 'cugir-007741',
    name: 'cornell_html_metadata',
    description:
      'Point dataset with WMS, WFS, direct download, and FGDC metadata XML and HTML',
    category: 'Point Data',
    source: 'gbl',
  },
  {
    id: '90f14ff4-1359-4beb-b931-5cb41d20ab90',
    name: 'esri-dynamic-layer-all-layers',
    description: 'Esri Rest Web Map Service (top level, no specific layer)',
    category: 'Esri Services',
    source: 'gbl',
  },
  {
    id: '4669301e-b4b2-4c8b-bf40-01b968a2865b',
    name: 'esri-dynamic-layer-single-layer',
    description: 'ArcGIS Dynamic Map Layer with single layer indicated',
    category: 'Esri Services',
    source: 'gbl',
  },
  {
    id: 'f406332e63eb4478a9560ad86ae90327_18',
    name: 'esri-feature-layer',
    description: 'ArcGIS Feature Layer - point dataset',
    category: 'Esri Services',
    source: 'gbl',
  },
  {
    id: '32653ed6-8d83-4692-8a06-bf13ffe2c018',
    name: 'esri-image-map-layer',
    description: 'ArcGIS Image Map Layer with GeoTIFF direct download',
    category: 'Esri Services',
    source: 'gbl',
  },
  {
    id: '31567cf1-bad8-4bc5-8d57-44b96c207ecc',
    name: 'esri-tiled_map_layer',
    description: 'ArcGIS tiled map layer',
    category: 'Esri Services',
    source: 'gbl',
  },
  {
    id: 'purdue-urn-f082acb1-b01e-4a08-9126-fd62a23fd9aa',
    name: 'esri-wms-layer',
    description:
      'Dataset with ArcGIS Dynamic Map Layer, ArcGIS WMS, and direct download',
    category: 'Esri Services',
    source: 'gbl',
  },
  {
    id: 'harvard-g7064-s2-1834-k3',
    name: 'harvard_raster',
    description: 'Georeferenced raster image of historic paper map',
    category: 'Raster Data',
    source: 'gbl',
  },
  {
    id: '57f0f116-b64e-4773-8684-96ba09afb549',
    name: 'iiif-eastern-hemisphere',
    description: 'Eastern hemisphere scanned map with IIIF manifest',
    category: 'Scanned Maps',
    source: 'gbl',
  },
  {
    id: 'cornell-ny-aerial-photos-1960s',
    name: 'index_map_point',
    description: 'GeoJSON index map of points',
    category: 'Index Maps',
    source: 'gbl',
  },
  {
    id: 'cugir-008186-no-downloadurl',
    name: 'index-map-polygon',
    description: 'GeoJSON index map of polygons, with downloadUrl for index',
    category: 'Index Maps',
    source: 'gbl',
  },
  {
    id: 'cugir-008186',
    name: 'index-map-polygon-no-downloadurl',
    description: 'GeoJSON index map of polygons, lacking downloadUrl for index',
    category: 'Index Maps',
    source: 'gbl',
  },
  {
    id: 'stanford-fb897vt9938',
    name: 'index-map-stanford',
    description: 'Old-style (pre-GeoJSON) index map of rectangular polygons',
    category: 'Index Maps',
    source: 'gbl',
  },
  {
    id: 'ark:-77981-gmgscj87k49',
    name: 'index-map-v1-complex',
    description:
      'OpenIndexMap with complex geometry using specification version 1.0.0',
    category: 'Index Maps',
    source: 'gbl',
  },
  {
    id: '05d-p16022coll246-noGeo',
    name: 'metadata_no_geom',
    description: 'Collection level record without spatial coordinates',
    category: 'Collections',
    source: 'gbl',
  },
  {
    id: '99-0001-noprovider',
    name: 'metadata_no_provider',
    description: 'Website record without Provider',
    category: 'Websites',
    source: 'gbl',
  },
  {
    id: 'cugir-007950',
    name: 'multiple-downloads',
    description: 'Test record with additional download formats (PDF, KMZ)',
    category: 'Downloads',
    source: 'gbl',
  },
  {
    id: '05d-03-noGeomType',
    name: 'no_locn_geometry',
    description:
      'Collection level record without spatial coordinates or Geometry Type',
    category: 'Collections',
    source: 'gbl',
  },
  {
    id: 'aster-global-emissivity-dataset-1-kilometer-v003-ag1kmcad20',
    name: 'no_spatial',
    description:
      'File without geometry type or locn_geometry (will cause error)',
    category: 'Error Cases',
    source: 'gbl',
  },
  {
    id: 'stanford-dc482zx1528',
    name: 'oembed',
    description: 'Record with Oembed reference link',
    category: 'Websites',
    source: 'gbl',
  },
  {
    id: 'princeton-n009w382v',
    name: 'princeton-child1',
    description: 'Child record for testing gbl_suppressed_b property',
    category: 'Child Records',
    source: 'gbl',
  },
  {
    id: 'princeton-jq085m62x',
    name: 'princeton-child2',
    description: 'Child record for testing gbl_suppressed_b property',
    category: 'Child Records',
    source: 'gbl',
  },
  {
    id: 'princeton-n009w382v-fake1',
    name: 'princeton-child3',
    description: 'Child record for testing gbl_suppressed_b property',
    category: 'Child Records',
    source: 'gbl',
  },
  {
    id: 'princeton-n009w382v-fake2',
    name: 'princeton-child4',
    description: 'Child record for testing gbl_suppressed_b property',
    category: 'Child Records',
    source: 'gbl',
  },
  {
    id: 'princeton-1r66j405w',
    name: 'princeton-parent',
    description: 'Parent record for testing gbl_suppressed_b property',
    category: 'Parent Records',
    source: 'gbl',
  },
  {
    id: 'stanford-cz128vq0535',
    name: 'public_direct_download',
    description: 'Includes tentative dcat_distribution_sm property',
    category: 'Downloads',
    source: 'gbl',
  },
  {
    id: 'princeton-02870w62c',
    name: 'public_iiif_princeton',
    description: 'Scanned map with IIIF',
    category: 'Scanned Maps',
    source: 'gbl',
  },
  {
    id: 'mit-f6rqs4ucovjk2',
    name: 'public_polygon_mit',
    description: 'Polygon shapefile with WMS and WFS',
    category: 'Polygon Data',
    source: 'gbl',
  },
  {
    id: 'stanford-cg357zz0321',
    name: 'restricted-line',
    description: 'Restricted line layer with WFS, WMS and metadata',
    category: 'Restricted Data',
    source: 'gbl',
  },
  {
    id: 'cugir-007957',
    name: 'tms',
    description: 'Includes reference to TMS web service',
    category: 'Web Services',
    source: 'gbl',
  },
  {
    id: '02236876-9c21-42f6-9870-d2562da8e44f',
    name: 'umn_metro_result1',
    description:
      'Bounding box of metropolitan area and ArcGIS Dynamic Feature Service',
    category: 'Esri Services',
    source: 'gbl',
  },
  {
    id: '2eddde2f-c222-41ca-bd07-2fd74a21f4de',
    name: 'umn_state_result1',
    description: 'Bounding box of state area and static image in references',
    category: 'Raster Data',
    source: 'gbl',
  },
  {
    id: 'e9c71086-6b25-4950-8e1c-84c2794e3382',
    name: 'umn_state_result2',
    description: 'Bounding box of state area and raster download',
    category: 'Raster Data',
    source: 'gbl',
  },
  {
    id: 'uva-Norfolk:police_point',
    name: 'uva_slug_colon',
    description:
      'Multipoint dataset with WMS and WFS and colon in slug and layer ID',
    category: 'Point Data',
    source: 'gbl',
  },
  {
    id: 'princeton-fk4db9hn29',
    name: 'wmts-multiple',
    description:
      'Raster dataset with gbl_wxsIdentifier_s and WMTS service supporting multiple layers',
    category: 'Web Services',
    source: 'gbl',
  },
  {
    id: 'princeton-fk4544658v-wmts',
    name: 'wmts-single-layer',
    description: 'Raster mosaic dataset with WMTS service supporting one layer',
    category: 'Web Services',
    source: 'gbl',
  },
  {
    id: '6f47b103-9955-4bbe-a364-387039623106-xyz',
    name: 'xyz',
    description: 'Line shapefile with XYZ tile service reference',
    category: 'Web Services',
    source: 'gbl',
  },
  {
    id: 'princeton-dc7h14b252v',
    name: 'public-cog-princeton',
    description:
      'Cloud Optimized GeoTIFF (COG) raster dataset with modern web-optimized format',
    category: 'Modern Formats',
    source: 'gbl',
  },
  {
    id: 'princeton-t722hd30j',
    name: 'public-pmtiles-princeton',
    description:
      'PMTiles vector tile dataset - Louisiana voting districts from 2010 Census',
    category: 'Modern Formats',
    source: 'gbl',
  },
];

// BTAA GIN fixtures - All fixtures from btaa_fixtures_list.csv
// Helper function to extract ID from URL
const extractIdFromUrl = (url: string): string => {
  if (!url || !url.trim()) return '';
  const match = url.match(/\/catalog\/([^\/]+)/);
  if (match) return match[1];
  // Handle non-standard URLs like geodata.wisc.edu
  const match2 = url.match(/\/catalog\/([^\/\?]+)/);
  if (match2) return match2[1];
  // Handle resources URLs
  const match3 = url.match(/\/resources\/([^\/\?]+)/);
  if (match3) return match3[1];
  return url;
};

const btaaGinFixtures: Fixture[] = [
  {
    id: '219ffed3-3e58-4fb7-ad82-4c264aae1b17',
    name: 'Multiple data downloads',
    description:
      'V11 Parcels Brown County, WI 2025 - Download function/button with multiple file formats',
    category: 'Downloads',
    source: 'btaa',
  },
  {
    id: 'b1g_BtbnzIbFhMiC',
    name: 'Polygon geometry (not rectangular)',
    description:
      'Zoning Base Districts [Philadelphia--Pennsylvania] {2025} - Geometry value is generalized outline instead of box',
    category: 'Geometry/Spatial Search',
    source: 'btaa',
  },
  {
    id: 'b1g_PJxxfKgpqpUT',
    name: 'Geonames',
    description:
      'Municipal boundary [Pennsylvania--Philadelphia] {2016} - Includes value for city GeoName URI',
    category: 'Geometry/Spatial Search',
    source: 'btaa',
  },
  {
    id: 'p16022coll230:2937',
    name: 'Multiple bounding boxes',
    description:
      'The smaller islands in the British Ocean - Map has multiple insets / panels',
    category: 'Geometry/Spatial Search',
    source: 'btaa',
  },
  {
    id: 'p16022coll230:3666',
    name: 'BBox crossing date line',
    description:
      'Eastern Siberia - Currently does not display correctly - the bbox polygon is backwards',
    category: 'Geometry/Spatial Search',
    source: 'btaa',
  },
  {
    id: '502D1D34-FDB0-456E-BD4A-73299B9C2E5F',
    name: 'Point for BBox',
    description:
      'Bike Elevator City of Madison, WI 2018 - We should be able to handle points in the bbox field',
    category: 'Geometry/Spatial Search',
    source: 'btaa',
  },
  {
    id: '999-0011-california',
    name: 'With dozens/scores of place names in Spatial Coverage',
    description:
      'Digital Sanborn Maps (Black & White) [California] {1867-1970} - hundreds of place names',
    category: 'Metadata Block',
    source: 'btaa',
  },
  {
    id: '0b75937e-2f44-4e49-bd1e-3e3adbed6f84',
    name: 'Arabic script',
    description:
      'Damage assessment in Jandairis, Afrin district, Aleppo governorate on February 11 - Non-Latin script in Description',
    category: 'Metadata Block',
    source: 'btaa',
  },
  {
    id: 'b1g_PJxxfKgpqpUT',
    name: 'Display Note field',
    description:
      'Municipal boundary [Pennsylvania--Philadelphia] {2016} - Highlighted display box',
    category: 'Metadata Block',
    source: 'btaa',
  },
  {
    id: 'pstems_0052767067_brownsville_08_pitt',
    name: 'Very long description fields',
    description:
      'Brownsville-08-Pitt; Brownsville- 8; Pittsburgh - Need to hide some of field under expand more feature',
    category: 'Metadata Block',
    source: 'btaa',
  },
  {
    id: 'rutgers-lib:35507',
    name: 'Chinese/Han script',
    description:
      'Map showing paths for mails and telegrams to and from Puchi (Puqi) Hsien (Xian) [China] - Non-Latin script in Title',
    category: 'Metadata Block',
    source: 'btaa',
  },
  {
    id: 'VAC9619-000022',
    name: 'Cyrillic script',
    description:
      'О-35-33-Г Савиновщина (Savinovshchina, Russia) - Non-Latin script in Title',
    category: 'Metadata Block',
    source: 'btaa',
  },
  {
    id: '14E37141-2059-462E-ABCA-9628E3BFB636',
    name: 'external link in Description field',
    description: 'Aging and Disability Resource Center Regions, Wisconsin 2020',
    category: 'Metadata Block',
  },
  {
    id: '88be737b-4fea-4f23-9433-a008ed6b18b5',
    name: 'HTML metadata',
    description: '10-year Stand Exam List MNDNR [Minnesota] - Render as is',
    category: 'Modal Window',
    source: 'btaa',
  },
  {
    id: '219ffed3-3e58-4fb7-ad82-4c264aae1b17',
    name: 'ISO metadata',
    description: 'V11 Parcels Brown County, WI 2025 - Render as HTML',
    category: 'Modal Window',
    source: 'btaa',
  },
  {
    id: 'cugir-007739',
    name: 'FGDC metadata',
    description: 'Adirondack Park Boundary, 1993 - Render as HTML',
    category: 'Modal Window',
    source: 'btaa',
  },
  {
    id: 'b1g_Jeks5eSaDHp5',
    name: 'Data Dictionary',
    description:
      'Street Centerlines [Philadelphia--Pennsylvania] {2025} - Could have nested values',
    category: 'Modal Window',
  },
  {
    id: '09a-04',
    name: 'Website record with children',
    description: 'IndianaMap - Uses Is Part Of field',
    category: 'Relationships',
    source: 'btaa',
  },
  {
    id: '16465B6B-742A-4335-BBF5-C4F7EC1BA9D4',
    name: 'Part of multiple local collections',
    description:
      'High Quality Streams, Wisconsin 2023 - Item belongs to more than one locally described collection',
    category: 'Relationships',
    source: 'btaa',
  },
  {
    id: '4979dd07507f4155bb92689860dd5089',
    name: 'Standalone website record (no children)',
    description: 'Morrill Reckoning',
    category: 'Resource Class',
    source: 'btaa',
  },
  {
    id: '2787a9e8-0bef-452e-9e5f-e83042c193b4',
    name: 'Collection record',
    description: 'Important Farmlands - Uses Member Of field',
    category: 'Resource Class',
    source: 'btaa',
  },
  {
    id: '8888-002',
    name: '"Other"',
    description:
      'Research Guide to Fire Insurance Maps - Used for tabular data and some text documents; no bbox or geometry',
    category: 'Resource Class',
    source: 'btaa',
  },
  {
    id: '999-0003-007',
    name: 'Licensed data',
    description:
      'Education (PolicyMap) - Shows as restricted with multiple access links',
    category: 'Restricted/Public',
    source: 'btaa',
  },
  {
    id: '4B758FE6-D2B5-463D-8E25-502CB4D90376',
    name: 'Esri FeatureServer',
    description:
      'Parcels Wisconsin (Statewide), 2024 - Very large feature layer - 3.5m polygons',
    category: 'Viewer',
    source: 'btaa',
  },
  {
    id: 'b1e04fea-8a02-426d-94c1-0897707fa563',
    name: 'Geojson index map',
    description:
      'LiDAR-Derived Classified LAS for Door County, WI 2018 - Geojson index map that renders tiles for downloading',
    category: 'Viewer',
    source: 'btaa',
  },
  {
    id: '4cd9f01beba64dce9e8502a7924d0deb_0',
    name: 'Esri MapServer service',
    description: 'Tax Parcels [Wisconsin--Sauk County]',
    category: 'Viewer',
    source: 'btaa',
  },
  {
    id: 'd128aa1618744699be00be0e494d01de_0',
    name: 'Esri service with lots of points',
    description: 'Address Points [Ohio--Columbus] - would need clustering',
    category: 'Viewer',
    source: 'btaa',
  },
  {
    id: 'CityOfWaukesha-3eea70a5e4af40a1a558a43705ff8596',
    name: 'Esri ImageServer',
    description:
      '2024 Aerial, City of Waukesha - To preview imageserver service in viewer',
    category: 'Viewer',
    source: 'btaa',
  },
  {
    id: 'b1g_PJxxfKgpqpUT',
    name: 'PM Tile',
    description:
      'Municipal boundary [Pennsylvania--Philadelphia] {2016} - Part of new Geodata Collection',
    category: 'Viewer',
    source: 'btaa',
  },
  {
    id: 'cugir-007739',
    name: 'OGC web service',
    description: 'Adirondack Park Boundary, 1993',
    category: 'Viewer',
    source: 'btaa',
  },
  {
    id: 'utaustin_121171',
    name: 'COG',
    description:
      'Sanborn Fire Insurance Maps [Austin, Texas, 1921; Sheet 69] - from UT Austin',
    category: 'Viewer',
    source: 'btaa',
  },
  {
    id: '9eccb622-8fe3-4f94-9a5c-e166585eb597',
    name: 'AllMaps',
    description:
      'A correct map of the Pacific Northwest showing rail & steamer lines of the O. R. & N. Co.',
    category: 'Viewer',
    source: 'btaa',
  },
  {
    id: '018b1db0-726a-4727-af0a-5c7e18783ace',
    name: 'Map no IIIF but with static image',
    description: 'The Gulf of Nicoya - Luna viewer, not embeddable',
    category: 'Viewer',
    source: 'btaa',
  },
  {
    id: 'p16022coll230:3666',
    name: 'map with IIIF Manifest single page',
    description: 'Eastern Siberia',
    category: 'Viewer',
    source: 'btaa',
  },
  {
    id: 'p16022coll231:2412',
    name: 'map with IIIF Manifest multiple pages',
    description:
      'Atlas and Farm Directory with Complete Survey in Township Plats, Lincoln County, Minnesota',
    category: 'Viewer',
    source: 'btaa',
  },
  {
    id: 'stanford-bs024ty5255',
    name: 'oemBed',
    description:
      'Bahamas National Hazard Analysis, 2019: InVEST Coastal Vulnerability Model Outputs - These are only from Stanford and generate a different kind of viewer',
    category: 'Viewer',
    source: 'btaa',
  },
  // Additional entries with same IDs but different features
  {
    id: 'b1g_PJxxfKgpqpUT',
    name: 'Display Note field',
    description:
      'Municipal boundary [Pennsylvania--Philadelphia] {2016} - Highlighted display box',
    category: 'Metadata Block',
    source: 'btaa',
  },
  {
    id: '219ffed3-3e58-4fb7-ad82-4c264aae1b17',
    name: 'ISO metadata',
    description: 'V11 Parcels Brown County, WI 2025 - Render as HTML',
    category: 'Modal Window',
    source: 'btaa',
  },
  {
    id: 'b1g_PJxxfKgpqpUT',
    name: 'PM Tile',
    description:
      'Municipal boundary [Pennsylvania--Philadelphia] {2016} - Part of new Geodata Collection',
    category: 'Viewer',
    source: 'btaa',
  },
  {
    id: 'cugir-007739',
    name: 'OGC web service',
    description: 'Adirondack Park Boundary, 1993',
    category: 'Viewer',
  },
  {
    id: 'utaustin_121171',
    name: 'COG',
    description:
      'Sanborn Fire Insurance Maps [Austin, Texas, 1921; Sheet 69] - from UT Austin - could replace with local one eventually',
    category: 'Viewer',
    source: 'btaa',
  },
  {
    id: 'p16022coll230:3666',
    name: 'map with IIIF Manifest single page',
    description: 'Eastern Siberia',
    category: 'Viewer',
    source: 'btaa',
  },
];

// Combine all fixtures from both sources (defined outside component for stability)
const allFixtures: Fixture[] = [...geoblacklightFixtures, ...btaaGinFixtures];

const getCategoryIcon = (category: string) => {
  switch (category) {
    case 'Point Data':
      return <MapPin className="w-4 h-4 text-blue-500" />;
    case 'Polygon Data':
      return <Layers className="w-4 h-4 text-blue-500" />;
    case 'Raster Data':
      return <Image className="w-4 h-4 text-blue-500" />;
    case 'Scanned Maps':
      return <FileText className="w-4 h-4 text-green-500" />;
    case 'Index Maps':
      return <Database className="w-4 h-4 text-purple-500" />;
    case 'Esri Services':
      return <Server className="w-4 h-4 text-orange-500" />;
    case 'Web Services':
      return <Globe className="w-4 h-4 text-cyan-500" />;
    case 'Restricted Data':
      return <Shield className="w-4 h-4 text-red-500" />;
    case 'Databases':
      return <HardDrive className="w-4 h-4 text-indigo-500" />;
    case 'Downloads':
      return <Download className="w-4 h-4 text-emerald-500" />;
    case 'Collections':
      return <Package className="w-4 h-4 text-amber-500" />;
    case 'Websites':
      return <Globe className="w-4 h-4 text-teal-500" />;
    case 'Child Records':
    case 'Parent Records':
      return <BookOpen className="w-4 h-4 text-slate-500" />;
    case 'Error Cases':
      return <Cpu className="w-4 h-4 text-gray-500" />;
    case 'Modern Formats':
      return <Layers className="w-4 h-4 text-violet-500" />;
    // BTAA GIN categories
    case 'Geometry/Spatial Search':
      return <MapPin className="w-4 h-4 text-blue-500" />;
    case 'Metadata Block':
      return <FileText className="w-4 h-4 text-green-500" />;
    case 'Modal Window':
      return <Database className="w-4 h-4 text-purple-500" />;
    case 'Relationships':
      return <BookOpen className="w-4 h-4 text-slate-500" />;
    case 'Resource Class':
      return <Package className="w-4 h-4 text-amber-500" />;
    case 'Restricted/Public':
      return <Shield className="w-4 h-4 text-red-500" />;
    case 'Viewer':
      return <Globe className="w-4 h-4 text-cyan-500" />;
    default:
      return <FlaskConical className="w-4 h-4 text-gray-500" />;
  }
};

const getCategoryColor = (category: string) => {
  switch (category) {
    case 'Point Data':
      return 'bg-blue-50 text-blue-700 border-blue-200';
    case 'Polygon Data':
      return 'bg-indigo-50 text-indigo-700 border-indigo-200';
    case 'Raster Data':
      return 'bg-cyan-50 text-cyan-700 border-cyan-200';
    case 'Scanned Maps':
      return 'bg-green-50 text-green-700 border-green-200';
    case 'Index Maps':
      return 'bg-purple-50 text-purple-700 border-purple-200';
    case 'Esri Services':
      return 'bg-orange-50 text-orange-700 border-orange-200';
    case 'Web Services':
      return 'bg-teal-50 text-teal-700 border-teal-200';
    case 'Restricted Data':
      return 'bg-red-50 text-red-700 border-red-200';
    case 'Databases':
      return 'bg-indigo-50 text-indigo-700 border-indigo-200';
    case 'Downloads':
      return 'bg-emerald-50 text-emerald-700 border-emerald-200';
    case 'Collections':
      return 'bg-amber-50 text-amber-700 border-amber-200';
    case 'Websites':
      return 'bg-teal-50 text-teal-700 border-teal-200';
    case 'Child Records':
    case 'Parent Records':
      return 'bg-slate-50 text-slate-700 border-slate-200';
    case 'Error Cases':
      return 'bg-gray-50 text-gray-700 border-gray-200';
    case 'Modern Formats':
      return 'bg-violet-50 text-violet-700 border-violet-200';
    // BTAA GIN categories
    case 'Geometry/Spatial Search':
      return 'bg-blue-50 text-blue-700 border-blue-200';
    case 'Metadata Block':
      return 'bg-green-50 text-green-700 border-green-200';
    case 'Modal Window':
      return 'bg-purple-50 text-purple-700 border-purple-200';
    case 'Relationships':
      return 'bg-slate-50 text-slate-700 border-slate-200';
    case 'Resource Class':
      return 'bg-amber-50 text-amber-700 border-amber-200';
    case 'Restricted/Public':
      return 'bg-red-50 text-red-700 border-red-200';
    case 'Viewer':
      return 'bg-cyan-50 text-cyan-700 border-cyan-200';
    default:
      return 'bg-gray-50 text-gray-700 border-gray-200';
  }
};

export function FixturesTestPage() {
  // Get categories for each source separately
  const gblCategories = [
    ...new Set(geoblacklightFixtures.map((f) => f.category)),
  ].sort();
  const btaaCategories = [
    ...new Set(btaaGinFixtures.map((f) => f.category)),
  ].sort();

  // Show/hide toggles for each source
  const [showGbl, setShowGbl] = useState<boolean>(true);
  const [showBtaa, setShowBtaa] = useState<boolean>(true);

  // Category filters for each source
  const [selectedGblCategory, setSelectedGblCategory] = useState<string | null>(
    null
  );
  const [selectedBtaaCategory, setSelectedBtaaCategory] = useState<
    string | null
  >(null);

  const [fixtureStatuses, setFixtureStatuses] = useState<
    Record<string, FixtureStatus>
  >({});

  // Helper function to check if a fixture would be visible with given filters
  const wouldFixtureBeVisible = (
    fixture: Fixture,
    sourceVisible: boolean,
    categoryFilter: string | null
  ): boolean => {
    if (!sourceVisible) return false;
    if (categoryFilter !== null && fixture.category !== categoryFilter) {
      return false;
    }
    return true;
  };

  // Filter fixtures based on show/hide state and selected categories
  const filteredFixtures = useMemo(() => {
    return allFixtures.filter((fixture) => {
      if (fixture.source === 'gbl') {
        return wouldFixtureBeVisible(fixture, showGbl, selectedGblCategory);
      } else if (fixture.source === 'btaa') {
        return wouldFixtureBeVisible(fixture, showBtaa, selectedBtaaCategory);
      }
      return false;
    });
  }, [showGbl, showBtaa, selectedGblCategory, selectedBtaaCategory]);

  // Calculate category counts - this simulates what would be shown when that category is selected
  // This ensures the count exactly matches what appears in the filtered results
  const getCategoryCount = (
    source: 'gbl' | 'btaa',
    category: string
  ): number => {
    // Simulate filtering with this specific category selected
    // This gives us the exact count that will appear when the user clicks that category button
    return allFixtures.filter((fixture) => {
      if (fixture.source === 'gbl') {
        // For GBL categories, simulate with this GBL category selected and no BTAA category
        if (!showGbl) return false;
        if (fixture.category !== category) return false;
        return true;
      } else if (fixture.source === 'btaa') {
        // For BTAA categories, simulate with this BTAA category selected and no GBL category
        if (!showBtaa) return false;
        if (fixture.category !== category) return false;
        return true;
      }
      return false;
    }).length;
  };

  // Check fixture availability
  const checkFixtureStatus = async (
    fixtureId: string
  ): Promise<FixtureStatus> => {
    try {
      // Check the API endpoint directly for more reliable detection
      const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || '/api/v1';
      const response = await fetch(
        `${apiBaseUrl}/resources/${fixtureId}?format=json`
      );
      console.log(
        `Checking ${fixtureId}: ${response.status} ${response.statusText}`
      );

      if (response.status === 404) {
        console.log(`❌ ${fixtureId} not found (404)`);
        return 'unavailable';
      }

      if (response.status === 200 || response.status === 304) {
        const contentType = response.headers.get('content-type');
        console.log(`Content-Type for ${fixtureId}: ${contentType}`);

        // Parse JSON response to check for errors
        if (contentType && contentType.includes('application/json')) {
          const data = await response.json();

          // Check if the response contains an error
          if (data.error) {
            console.log(`❌ ${fixtureId} has error: ${data.error}`);
            return 'unavailable';
          }

          // Check if it's a valid JSON:API response with data
          if (data.data && data.data.id) {
            console.log(`✅ ${fixtureId} is available (JSON:API)`);
            return 'available';
          }

          // Fallback: if we got JSON without error, consider it available
          console.log(`✅ ${fixtureId} is available (JSON)`);
          return 'available';
        } else {
          console.log(
            `⚠️ ${fixtureId} returned unexpected content type: ${contentType}`
          );
          return 'unavailable';
        }
      } else {
        console.log(
          `❌ ${fixtureId} returned ${response.status}: ${response.statusText}`
        );
        return 'unavailable';
      }
    } catch (error) {
      console.log(`💥 ${fixtureId} error:`, error);
      return 'error';
    }
  };

  // Check all fixtures on component mount
  useEffect(() => {
    const checkAllFixtures = async () => {
      // Initialize all as loading
      const initialStatuses: Record<string, FixtureStatus> = {};
      allFixtures.forEach((fixture) => {
        initialStatuses[fixture.id] = 'loading';
      });
      setFixtureStatuses(initialStatuses);

      // Check each fixture with a small delay to avoid overwhelming the API
      for (const fixture of allFixtures) {
        const status = await checkFixtureStatus(fixture.id);
        setFixtureStatuses((prev) => ({
          ...prev,
          [fixture.id]: status,
        }));
        // Small delay between requests
        await new Promise((resolve) => setTimeout(resolve, 100));
      }
    };

    checkAllFixtures();
  }, []);

  // Calculate status counts for visible fixtures only
  const statusCounts = {
    available: filteredFixtures.filter(
      (fixture) => fixtureStatuses[fixture.id] === 'available'
    ).length,
    unavailable: filteredFixtures.filter(
      (fixture) => fixtureStatuses[fixture.id] === 'unavailable'
    ).length,
    error: filteredFixtures.filter(
      (fixture) => fixtureStatuses[fixture.id] === 'error'
    ).length,
    loading: filteredFixtures.filter(
      (fixture) => fixtureStatuses[fixture.id] === 'loading'
    ).length,
  };

  return (
    <div className="min-h-screen bg-gray-50 py-4">
      <div className="w-full px-2 sm:px-4 lg:px-6">
        {/* Header */}
        <div className="text-center mb-6">
          <div className="flex items-center justify-center gap-2 mb-3">
            <FlaskConical className="w-6 h-6 text-purple-600" />
            <h1 className="text-3xl font-bold text-gray-900">
              Geoportal Test Fixtures
            </h1>
          </div>

          {/* Show/Hide Toggles */}
          <div className="flex items-center justify-center gap-6 mb-4">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={showGbl}
                onChange={(e) => setShowGbl(e.target.checked)}
                className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
              />
              <span className="text-sm font-medium text-gray-700">
                Show GBL ({geoblacklightFixtures.length})
              </span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={showBtaa}
                onChange={(e) => setShowBtaa(e.target.checked)}
                className="w-4 h-4 text-green-600 border-gray-300 rounded focus:ring-green-500"
              />
              <span className="text-sm font-medium text-gray-700">
                Show BTAA ({btaaGinFixtures.length})
              </span>
            </label>
          </div>

          <p className="text-base text-gray-600 max-w-2xl mx-auto">
            Easter egg page of test fixtures. Click any link to test if that
            resource page renders properly.
          </p>
          <Link
            to="/test/fixtures/providers"
            className="mt-2 inline-block text-sm text-blue-600 hover:text-blue-800"
          >
            View provider institution pills →
          </Link>
          <div className="mt-2 text-sm text-gray-500">
            {selectedGblCategory ||
            selectedBtaaCategory ||
            !showGbl ||
            !showBtaa ? (
              <>
                Showing:{' '}
                <span className="font-semibold">{filteredFixtures.length}</span>{' '}
                of {allFixtures.length} fixtures
                {selectedGblCategory && (
                  <>
                    {' '}
                    | GBL Category:{' '}
                    <span className="font-semibold text-violet-600">
                      {selectedGblCategory}
                    </span>
                  </>
                )}
                {selectedBtaaCategory && (
                  <>
                    {' '}
                    | BTAA Category:{' '}
                    <span className="font-semibold text-violet-600">
                      {selectedBtaaCategory}
                    </span>
                  </>
                )}
              </>
            ) : (
              <>
                Total fixtures:{' '}
                <span className="font-semibold">{allFixtures.length}</span> (
                <span className="font-semibold">
                  {geoblacklightFixtures.length}
                </span>{' '}
                GBL,{' '}
                <span className="font-semibold">{btaaGinFixtures.length}</span>{' '}
                BTAA)
              </>
            )}
          </div>

          {/* Status Summary */}
          {statusCounts.loading === 0 && (
            <div className="mt-3 flex items-center justify-center gap-4 text-xs">
              <div className="flex items-center gap-1">
                <CheckCircle className="w-3 h-3 text-green-600" />
                <span className="text-green-600 font-medium">
                  {statusCounts.available} Available
                </span>
              </div>
              <div className="flex items-center gap-1">
                <XCircle className="w-3 h-3 text-red-600" />
                <span className="text-red-600 font-medium">
                  {statusCounts.unavailable} Not Found
                </span>
              </div>
              {statusCounts.error > 0 && (
                <div className="flex items-center gap-1">
                  <XCircle className="w-3 h-3 text-orange-600" />
                  <span className="text-orange-600 font-medium">
                    {statusCounts.error} Error
                  </span>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Category Filters */}
        <div className="mb-6 space-y-6">
          {/* GBL Categories */}
          {showGbl && (
            <div>
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-xl font-semibold text-gray-900">
                  GBL Test Categories
                </h2>
                {selectedGblCategory && (
                  <button
                    onClick={() => setSelectedGblCategory(null)}
                    className="inline-flex items-center gap-1 px-3 py-1 text-sm font-medium text-gray-600 bg-gray-100 rounded-md hover:bg-gray-200 transition-colors"
                  >
                    <X className="w-4 h-4" />
                    Clear GBL Filter
                  </button>
                )}
              </div>
              <div className="grid grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-2">
                {gblCategories.map((category) => {
                  const count = getCategoryCount('gbl', category);
                  const isSelected = selectedGblCategory === category;
                  return (
                    <button
                      key={`gbl-${category}`}
                      onClick={() => {
                        setSelectedGblCategory(isSelected ? null : category);
                      }}
                      className={`px-3 py-2 rounded border text-sm font-medium transition-all cursor-pointer ${
                        isSelected
                          ? `${getCategoryColor(category)} ring-2 ring-violet-300 shadow-md`
                          : `${getCategoryColor(category)} hover:shadow-sm`
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        {getCategoryIcon(category)}
                        <span className="truncate">{category}</span>
                        <span className="text-sm opacity-75">({count})</span>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* BTAA Categories */}
          {showBtaa && (
            <div>
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-xl font-semibold text-gray-900">
                  BTAA Test Categories
                </h2>
                {selectedBtaaCategory && (
                  <button
                    onClick={() => setSelectedBtaaCategory(null)}
                    className="inline-flex items-center gap-1 px-3 py-1 text-sm font-medium text-gray-600 bg-gray-100 rounded-md hover:bg-gray-200 transition-colors"
                  >
                    <X className="w-4 h-4" />
                    Clear BTAA Filter
                  </button>
                )}
              </div>
              <div className="grid grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-2">
                {btaaCategories.map((category) => {
                  const count = getCategoryCount('btaa', category);
                  const isSelected = selectedBtaaCategory === category;
                  return (
                    <button
                      key={`btaa-${category}`}
                      onClick={() => {
                        setSelectedBtaaCategory(isSelected ? null : category);
                      }}
                      className={`px-3 py-2 rounded border text-sm font-medium transition-all cursor-pointer ${
                        isSelected
                          ? `${getCategoryColor(category)} ring-2 ring-violet-300 shadow-md`
                          : `${getCategoryColor(category)} hover:shadow-sm`
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        {getCategoryIcon(category)}
                        <span className="truncate">{category}</span>
                        <span className="text-sm opacity-75">({count})</span>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* Fixtures Table */}
        <div className="bg-white rounded-lg shadow-md overflow-hidden">
          <div className="px-4 py-3 bg-gray-50 border-b border-gray-200">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-xl font-semibold text-gray-900">
                  {selectedGblCategory ||
                  selectedBtaaCategory ||
                  !showGbl ||
                  !showBtaa
                    ? `Filtered Fixtures (${filteredFixtures.length})`
                    : `All Test Fixtures (${filteredFixtures.length})`}
                </h2>
                <p className="text-base text-gray-600 mt-1">
                  {selectedGblCategory ||
                  selectedBtaaCategory ||
                  !showGbl ||
                  !showBtaa
                    ? `Showing ${filteredFixtures.length} fixture${filteredFixtures.length !== 1 ? 's' : ''} matching selected filters. Click any resource link to test page rendering in a new tab.`
                    : 'Click any resource link to test page rendering in a new tab'}
                </p>
              </div>
              <button
                onClick={() => {
                  const availableFixtures = filteredFixtures.filter(
                    (fixture) => fixtureStatuses[fixture.id] === 'available'
                  );

                  if (availableFixtures.length === 0) {
                    alert(
                      'No available fixtures to open. Please wait for status checks to complete.'
                    );
                    return;
                  }

                  if (availableFixtures.length > 20) {
                    const confirmed = confirm(
                      `This will open ${availableFixtures.length} tabs. Are you sure you want to continue?`
                    );
                    if (!confirmed) return;
                  }

                  availableFixtures.forEach((fixture, index) => {
                    setTimeout(() => {
                      window.open(`/resources/${fixture.id}`, '_blank');
                    }, index * 100); // Stagger opening to avoid browser blocking
                  });

                  console.log(
                    `Opening ${availableFixtures.length} fixture tabs...`
                  );
                }}
                className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-colors"
                title="Open all available fixtures in new tabs"
              >
                <ExternalLink className="w-4 h-4" />
                Open All Available (
                {
                  filteredFixtures.filter(
                    (f) => fixtureStatuses[f.id] === 'available'
                  ).length
                }
                )
              </button>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-3 py-3 text-left text-sm font-medium text-gray-500 uppercase tracking-wider w-24">
                    Source
                  </th>
                  <th className="px-3 py-3 text-left text-sm font-medium text-gray-500 uppercase tracking-wider w-32">
                    Category
                  </th>
                  <th className="px-3 py-3 text-left text-sm font-medium text-gray-500 uppercase tracking-wider w-48">
                    Fixture Name
                  </th>
                  <th className="px-3 py-3 text-left text-sm font-medium text-gray-500 uppercase tracking-wider w-64">
                    Resource ID
                  </th>
                  <th className="px-3 py-3 text-left text-sm font-medium text-gray-500 uppercase tracking-wider w-28">
                    Thumbnail
                  </th>
                  <th className="px-3 py-3 text-left text-sm font-medium text-gray-500 uppercase tracking-wider w-28">
                    Static Map
                  </th>
                  <th className="px-3 py-3 text-left text-sm font-medium text-gray-500 uppercase tracking-wider">
                    Description
                  </th>
                  <th className="px-3 py-3 text-left text-sm font-medium text-gray-500 uppercase tracking-wider w-24">
                    Status
                  </th>
                  <th className="px-3 py-3 text-left text-sm font-medium text-gray-500 uppercase tracking-wider w-32">
                    Test Link
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {filteredFixtures.map((fixture, index) => (
                  <tr
                    key={`${fixture.source}-${fixture.id}-${fixture.category}-${index}`}
                    className={index % 2 === 0 ? 'bg-white' : 'bg-gray-50'}
                  >
                    <td className="px-3 py-3 whitespace-nowrap">
                      <span
                        className={`inline-flex items-center px-2 py-1 rounded text-xs font-medium ${
                          fixture.source === 'gbl'
                            ? 'bg-blue-100 text-blue-800'
                            : 'bg-green-100 text-green-800'
                        }`}
                      >
                        {fixture.source === 'gbl' ? 'GBL' : 'BTAA'}
                      </span>
                    </td>
                    <td className="px-3 py-3 whitespace-nowrap">
                      <div className="flex items-center gap-2">
                        {getCategoryIcon(fixture.category)}
                        <span className="text-sm font-medium text-gray-900 truncate">
                          {fixture.category}
                        </span>
                      </div>
                    </td>
                    <td className="px-3 py-3 whitespace-nowrap">
                      <div
                        className="text-sm font-mono text-gray-900 truncate"
                        title={fixture.name}
                      >
                        {fixture.name}
                      </div>
                    </td>
                    <td className="px-3 py-3 whitespace-nowrap">
                      <div
                        className="text-sm text-gray-600 font-mono truncate"
                        title={fixture.id}
                      >
                        {fixture.id}
                      </div>
                    </td>
                    <td className="px-3 py-3 whitespace-nowrap">
                      <div className="w-20 h-16 border border-gray-200 rounded bg-gray-50 flex items-center justify-center overflow-hidden">
                        <img
                          src={`/resources/${fixture.id}/thumbnail`}
                          alt=""
                          className="w-full h-full object-cover"
                          loading="lazy"
                          onError={(e) => {
                            // If thumbnail fails, keep the cell but avoid broken image icon
                            (
                              e.currentTarget as HTMLImageElement
                            ).style.display = 'none';
                          }}
                        />
                      </div>
                    </td>
                    <td className="px-3 py-3 whitespace-nowrap">
                      <div className="w-20 h-16 border border-gray-200 rounded bg-gray-50 flex items-center justify-center overflow-hidden">
                        <img
                          src={`/resources/${fixture.id}/static-map`}
                          alt=""
                          className="w-full h-full object-cover"
                          loading="lazy"
                          onError={(e) => {
                            (
                              e.currentTarget as HTMLImageElement
                            ).style.display = 'none';
                          }}
                        />
                      </div>
                    </td>
                    <td className="px-3 py-3">
                      <div
                        className="text-sm text-gray-700 line-clamp-2"
                        title={fixture.description}
                      >
                        {fixture.description}
                      </div>
                    </td>
                    <td className="px-3 py-3 whitespace-nowrap">
                      <div className="flex items-center gap-2">
                        {fixtureStatuses[fixture.id] === 'loading' && (
                          <div className="flex items-center gap-1 text-gray-500">
                            <Loader className="w-4 h-4 animate-spin" />
                            <span className="text-xs">Checking...</span>
                          </div>
                        )}
                        {fixtureStatuses[fixture.id] === 'available' && (
                          <div className="flex items-center gap-1 text-green-600">
                            <CheckCircle className="w-4 h-4" />
                            <span className="text-xs font-medium">
                              Available
                            </span>
                          </div>
                        )}
                        {fixtureStatuses[fixture.id] === 'unavailable' && (
                          <div className="flex items-center gap-1 text-red-600">
                            <XCircle className="w-4 h-4" />
                            <span className="text-xs font-medium">
                              Not Found
                            </span>
                          </div>
                        )}
                        {fixtureStatuses[fixture.id] === 'error' && (
                          <div className="flex items-center gap-1 text-orange-600">
                            <XCircle className="w-4 h-4" />
                            <span className="text-xs font-medium">Error</span>
                          </div>
                        )}
                      </div>
                    </td>
                    <td className="px-3 py-3 whitespace-nowrap">
                      <a
                        href={`/resources/${fixture.id}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className={`inline-flex items-center gap-1 px-3 py-2 border border-transparent text-sm font-medium rounded transition-colors ${
                          fixtureStatuses[fixture.id] === 'unavailable' ||
                          fixtureStatuses[fixture.id] === 'error'
                            ? 'text-gray-400 bg-gray-200 cursor-not-allowed'
                            : 'text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500'
                        }`}
                        onClick={(e) => {
                          if (
                            fixtureStatuses[fixture.id] === 'unavailable' ||
                            fixtureStatuses[fixture.id] === 'error'
                          ) {
                            e.preventDefault();
                          } else {
                            console.log(
                              `Testing fixture: ${fixture.name} (${fixture.id})`
                            );
                          }
                        }}
                      >
                        <ExternalLink className="w-4 h-4" />
                        Test
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Footer */}
        <div className="mt-8 text-center text-sm text-gray-500">
          <p>
            🔬 This is an easter egg page for development and testing purposes
          </p>
          <p className="mt-1">
            Use the browser console script{' '}
            <code className="bg-gray-100 px-1 rounded">
              check-all-fixtures.js
            </code>{' '}
            for automated testing
          </p>
        </div>
      </div>
    </div>
  );
}

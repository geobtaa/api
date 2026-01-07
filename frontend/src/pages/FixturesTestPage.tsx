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
import { useState, useEffect } from 'react';

interface Fixture {
  id: string;
  name: string;
  description: string;
  category: string;
}

type FixtureStatus = 'loading' | 'available' | 'unavailable' | 'error';

const allFixtures: Fixture[] = [
  {
    id: 'mit-001145244',
    name: 'actual-papermap1',
    description: 'Nondigitized paper map with library catalog link',
    category: 'Paper Maps',
  },
  {
    id: 'nyu-2451-34564',
    name: 'actual-point1',
    description: 'Point dataset with WMS and WFS',
    category: 'Point Data',
  },
  {
    id: 'tufts-cambridgegrid100-04',
    name: 'actual-polygon1',
    description: 'Polygon dataset with WFS, WMS, and FGDC metadata',
    category: 'Polygon Data',
  },
  {
    id: 'stanford-dp018hs9766',
    name: 'actual-raster1',
    description: 'Restricted raster layer with WMS and metadata',
    category: 'Raster Data',
  },
  {
    id: 'nyu_2451_34635',
    name: 'baruch_ancestor1',
    description: 'SQLite Database with documentation download (parent)',
    category: 'Databases',
  },
  {
    id: 'nyu_2451_34636',
    name: 'baruch_ancestor2',
    description: 'Geodatabase with documentation download (parent)',
    category: 'Databases',
  },
  {
    id: 'nyu_2451_34502',
    name: 'baruch_documentation_download',
    description:
      'Point dataset with WMS, WFS, documentation download, and parent records',
    category: 'Point Data',
  },
  {
    id: 'princeton-sx61dn82p',
    name: 'bbox-spans-180',
    description:
      'Scanned map with IIIF and direct TIFF download spanning 180th meridian',
    category: 'Scanned Maps',
  },
  {
    id: 'c8b46b52-0846-4abb-ba56-b484064f84ac',
    name: 'complex-geom',
    description: 'Scanned map with MULTIPOLYGON locn_geometry value',
    category: 'Scanned Maps',
  },
  {
    id: 'cugir-007741',
    name: 'cornell_html_metadata',
    description:
      'Point dataset with WMS, WFS, direct download, and FGDC metadata XML and HTML',
    category: 'Point Data',
  },
  {
    id: '90f14ff4-1359-4beb-b931-5cb41d20ab90',
    name: 'esri-dynamic-layer-all-layers',
    description: 'Esri Rest Web Map Service (top level, no specific layer)',
    category: 'Esri Services',
  },
  {
    id: '4669301e-b4b2-4c8b-bf40-01b968a2865b',
    name: 'esri-dynamic-layer-single-layer',
    description: 'ArcGIS Dynamic Map Layer with single layer indicated',
    category: 'Esri Services',
  },
  {
    id: 'f406332e63eb4478a9560ad86ae90327_18',
    name: 'esri-feature-layer',
    description: 'ArcGIS Feature Layer - point dataset',
    category: 'Esri Services',
  },
  {
    id: '32653ed6-8d83-4692-8a06-bf13ffe2c018',
    name: 'esri-image-map-layer',
    description: 'ArcGIS Image Map Layer with GeoTIFF direct download',
    category: 'Esri Services',
  },
  {
    id: '31567cf1-bad8-4bc5-8d57-44b96c207ecc',
    name: 'esri-tiled_map_layer',
    description: 'ArcGIS tiled map layer',
    category: 'Esri Services',
  },
  {
    id: 'purdue-urn-f082acb1-b01e-4a08-9126-fd62a23fd9aa',
    name: 'esri-wms-layer',
    description:
      'Dataset with ArcGIS Dynamic Map Layer, ArcGIS WMS, and direct download',
    category: 'Esri Services',
  },
  {
    id: 'harvard-g7064-s2-1834-k3',
    name: 'harvard_raster',
    description: 'Georeferenced raster image of historic paper map',
    category: 'Raster Data',
  },
  {
    id: '57f0f116-b64e-4773-8684-96ba09afb549',
    name: 'iiif-eastern-hemisphere',
    description: 'Eastern hemisphere scanned map with IIIF manifest',
    category: 'Scanned Maps',
  },
  {
    id: 'cornell-ny-aerial-photos-1960s',
    name: 'index_map_point',
    description: 'GeoJSON index map of points',
    category: 'Index Maps',
  },
  {
    id: 'cugir-008186-no-downloadurl',
    name: 'index-map-polygon',
    description: 'GeoJSON index map of polygons, with downloadUrl for index',
    category: 'Index Maps',
  },
  {
    id: 'cugir-008186',
    name: 'index-map-polygon-no-downloadurl',
    description: 'GeoJSON index map of polygons, lacking downloadUrl for index',
    category: 'Index Maps',
  },
  {
    id: 'stanford-fb897vt9938',
    name: 'index-map-stanford',
    description: 'Old-style (pre-GeoJSON) index map of rectangular polygons',
    category: 'Index Maps',
  },
  {
    id: 'ark:-77981-gmgscj87k49',
    name: 'index-map-v1-complex',
    description:
      'OpenIndexMap with complex geometry using specification version 1.0.0',
    category: 'Index Maps',
  },
  {
    id: '05d-p16022coll246-noGeo',
    name: 'metadata_no_geom',
    description: 'Collection level record without spatial coordinates',
    category: 'Collections',
  },
  {
    id: '99-0001-noprovider',
    name: 'metadata_no_provider',
    description: 'Website record without Provider',
    category: 'Websites',
  },
  {
    id: 'cugir-007950',
    name: 'multiple-downloads',
    description: 'Test record with additional download formats (PDF, KMZ)',
    category: 'Downloads',
  },
  {
    id: '05d-03-noGeomType',
    name: 'no_locn_geometry',
    description:
      'Collection level record without spatial coordinates or Geometry Type',
    category: 'Collections',
  },
  {
    id: 'aster-global-emissivity-dataset-1-kilometer-v003-ag1kmcad20',
    name: 'no_spatial',
    description:
      'File without geometry type or locn_geometry (will cause error)',
    category: 'Error Cases',
  },
  {
    id: 'stanford-dc482zx1528',
    name: 'oembed',
    description: 'Record with Oembed reference link',
    category: 'Websites',
  },
  {
    id: 'princeton-n009w382v',
    name: 'princeton-child1',
    description: 'Child record for testing gbl_suppressed_b property',
    category: 'Child Records',
  },
  {
    id: 'princeton-jq085m62x',
    name: 'princeton-child2',
    description: 'Child record for testing gbl_suppressed_b property',
    category: 'Child Records',
  },
  {
    id: 'princeton-n009w382v-fake1',
    name: 'princeton-child3',
    description: 'Child record for testing gbl_suppressed_b property',
    category: 'Child Records',
  },
  {
    id: 'princeton-n009w382v-fake2',
    name: 'princeton-child4',
    description: 'Child record for testing gbl_suppressed_b property',
    category: 'Child Records',
  },
  {
    id: 'princeton-1r66j405w',
    name: 'princeton-parent',
    description: 'Parent record for testing gbl_suppressed_b property',
    category: 'Parent Records',
  },
  {
    id: 'stanford-cz128vq0535',
    name: 'public_direct_download',
    description: 'Includes tentative dcat_distribution_sm property',
    category: 'Downloads',
  },
  {
    id: 'princeton-02870w62c',
    name: 'public_iiif_princeton',
    description: 'Scanned map with IIIF',
    category: 'Scanned Maps',
  },
  {
    id: 'mit-f6rqs4ucovjk2',
    name: 'public_polygon_mit',
    description: 'Polygon shapefile with WMS and WFS',
    category: 'Polygon Data',
  },
  {
    id: 'stanford-cg357zz0321',
    name: 'restricted-line',
    description: 'Restricted line layer with WFS, WMS and metadata',
    category: 'Restricted Data',
  },
  {
    id: 'cugir-007957',
    name: 'tms',
    description: 'Includes reference to TMS web service',
    category: 'Web Services',
  },
  {
    id: '02236876-9c21-42f6-9870-d2562da8e44f',
    name: 'umn_metro_result1',
    description:
      'Bounding box of metropolitan area and ArcGIS Dynamic Feature Service',
    category: 'Esri Services',
  },
  {
    id: '2eddde2f-c222-41ca-bd07-2fd74a21f4de',
    name: 'umn_state_result1',
    description: 'Bounding box of state area and static image in references',
    category: 'Raster Data',
  },
  {
    id: 'e9c71086-6b25-4950-8e1c-84c2794e3382',
    name: 'umn_state_result2',
    description: 'Bounding box of state area and raster download',
    category: 'Raster Data',
  },
  {
    id: 'uva-Norfolk:police_point',
    name: 'uva_slug_colon',
    description:
      'Multipoint dataset with WMS and WFS and colon in slug and layer ID',
    category: 'Point Data',
  },
  {
    id: 'princeton-fk4db9hn29',
    name: 'wmts-multiple',
    description:
      'Raster dataset with gbl_wxsIdentifier_s and WMTS service supporting multiple layers',
    category: 'Web Services',
  },
  {
    id: 'princeton-fk4544658v-wmts',
    name: 'wmts-single-layer',
    description: 'Raster mosaic dataset with WMTS service supporting one layer',
    category: 'Web Services',
  },
  {
    id: '6f47b103-9955-4bbe-a364-387039623106-xyz',
    name: 'xyz',
    description: 'Line shapefile with XYZ tile service reference',
    category: 'Web Services',
  },
  {
    id: 'princeton-cog-example',
    name: 'public-cog-princeton',
    description:
      'Cloud Optimized GeoTIFF (COG) raster dataset with modern web-optimized format',
    category: 'Modern Formats',
  },
  {
    id: 'princeton-t722hd30j',
    name: 'public-pmtiles-princeton',
    description:
      'PMTiles vector tile dataset - Louisiana voting districts from 2010 Census',
    category: 'Modern Formats',
  },
];

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
    default:
      return 'bg-gray-50 text-gray-700 border-gray-200';
  }
};

export function FixturesTestPage() {
  const categories = [...new Set(allFixtures.map((f) => f.category))].sort();
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [fixtureStatuses, setFixtureStatuses] = useState<
    Record<string, FixtureStatus>
  >({});

  // Filter fixtures based on selected category
  const filteredFixtures = selectedCategory
    ? allFixtures.filter((fixture) => fixture.category === selectedCategory)
    : allFixtures;

  // Check fixture availability
  const checkFixtureStatus = async (
    fixtureId: string
  ): Promise<FixtureStatus> => {
    try {
      // Check the actual resource page endpoint, not the API endpoint
      const response = await fetch(
        `${window.location.origin}/resources/${fixtureId}`
      );
      console.log(
        `Checking ${fixtureId}: ${response.status} ${response.statusText}`
      );

      // Get the response text to check for error content
      const responseText = await response.text();
      console.log(
        `Response content for ${fixtureId}: ${responseText.substring(0, 100)}...`
      );

      // Check if the response contains error content regardless of status code
      if (
        responseText.includes('"error":"Resource not found"') ||
        responseText.includes('Resource not found') ||
        responseText.includes('404') ||
        responseText.includes('Not Found')
      ) {
        console.log(
          `❌ ${fixtureId} contains error content (status: ${response.status})`
        );
        return 'unavailable';
      }

      if (response.status === 200 || response.status === 304) {
        const contentType = response.headers.get('content-type');
        console.log(`Content-Type for ${fixtureId}: ${contentType}`);

        // If it's HTML and returns 200/304, the page renders successfully
        if (contentType && contentType.includes('text/html')) {
          console.log(`✅ ${fixtureId} is available (page renders)`);
          return 'available';
        } else if (contentType && contentType.includes('application/json')) {
          console.log(`✅ ${fixtureId} is available (JSON)`);
          return 'available';
        } else {
          console.log(
            `⚠️ ${fixtureId} returned unexpected content type: ${contentType}`
          );
          return 'unavailable';
        }
      } else if (response.status === 404) {
        console.log(`❌ ${fixtureId} not found (404)`);
        return 'unavailable';
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

  // Calculate status counts
  const statusCounts = {
    available: Object.values(fixtureStatuses).filter(
      (status) => status === 'available'
    ).length,
    unavailable: Object.values(fixtureStatuses).filter(
      (status) => status === 'unavailable'
    ).length,
    error: Object.values(fixtureStatuses).filter((status) => status === 'error')
      .length,
    loading: Object.values(fixtureStatuses).filter(
      (status) => status === 'loading'
    ).length,
  };

  // Debug: Log that the component is rendering
  console.log(
    'FixturesTestPage rendering with',
    allFixtures.length,
    'fixtures'
  );

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
          <p className="text-base text-gray-600 max-w-2xl mx-auto">
            Easter egg page of test fixtures. Click any link to test if that
            resource page renders properly.
          </p>
          <div className="mt-2 text-sm text-gray-500">
            {selectedCategory ? (
              <>
                Showing:{' '}
                <span className="font-semibold">{filteredFixtures.length}</span>{' '}
                of {allFixtures.length} fixtures | Category:{' '}
                <span className="font-semibold text-violet-600">
                  {selectedCategory}
                </span>
              </>
            ) : (
              <>
                Total fixtures:{' '}
                <span className="font-semibold">{allFixtures.length}</span> |
                Categories:{' '}
                <span className="font-semibold">{categories.length}</span>
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

        {/* Category Summary */}
        <div className="mb-6">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-xl font-semibold text-gray-900">Categories</h2>
            {selectedCategory && (
              <button
                onClick={() => setSelectedCategory(null)}
                className="inline-flex items-center gap-1 px-3 py-1 text-sm font-medium text-gray-600 bg-gray-100 rounded-md hover:bg-gray-200 transition-colors"
              >
                <X className="w-4 h-4" />
                Clear Filter
              </button>
            )}
          </div>
          <div className="grid grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-2">
            {categories.map((category) => {
              const count = allFixtures.filter(
                (f) => f.category === category
              ).length;
              const isSelected = selectedCategory === category;
              return (
                <button
                  key={category}
                  onClick={() =>
                    setSelectedCategory(isSelected ? null : category)
                  }
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

        {/* Fixtures Table */}
        <div className="bg-white rounded-lg shadow-md overflow-hidden">
          <div className="px-4 py-3 bg-gray-50 border-b border-gray-200">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-xl font-semibold text-gray-900">
                  {selectedCategory
                    ? `${selectedCategory} Fixtures`
                    : 'All Test Fixtures'}
                </h2>
                <p className="text-base text-gray-600 mt-1">
                  {selectedCategory
                    ? `Showing ${filteredFixtures.length} fixture${filteredFixtures.length !== 1 ? 's' : ''} in ${selectedCategory} category. Click any resource link to test page rendering in a new tab.`
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
                  <th className="px-3 py-3 text-left text-sm font-medium text-gray-500 uppercase tracking-wider w-32">
                    Category
                  </th>
                  <th className="px-3 py-3 text-left text-sm font-medium text-gray-500 uppercase tracking-wider w-48">
                    Fixture Name
                  </th>
                  <th className="px-3 py-3 text-left text-sm font-medium text-gray-500 uppercase tracking-wider w-64">
                    Resource ID
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
                    key={fixture.id}
                    className={index % 2 === 0 ? 'bg-white' : 'bg-gray-50'}
                  >
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
                          fixtureStatuses[fixture.id] === 'available'
                            ? 'text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500'
                            : 'text-gray-400 bg-gray-200 cursor-not-allowed'
                        }`}
                        onClick={(e) => {
                          if (fixtureStatuses[fixture.id] !== 'available') {
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

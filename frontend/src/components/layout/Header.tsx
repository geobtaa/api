import {
  Link,
  useLocation,
  useNavigate,
  useSearchParams,
} from 'react-router';
import { Globe2 } from 'lucide-react';
import { SearchField } from '../SearchField';
import { ResourceClassFilterTabs } from '../search/ResourceClassFilterTabs';

export function Header() {
  const location = useLocation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const isHomePage = location.pathname === '/';

  const handleSearch = (query: string) => {
    const newParams = new URLSearchParams();
    newParams.set('q', query);

    // Preserve geo filters from current URL
    const geoType = searchParams.get('include_filters[geo][type]');
    if (geoType === 'bbox') {
      const topLeftLat = searchParams.get(
        'include_filters[geo][top_left][lat]'
      );
      const topLeftLon = searchParams.get(
        'include_filters[geo][top_left][lon]'
      );
      const bottomRightLat = searchParams.get(
        'include_filters[geo][bottom_right][lat]'
      );
      const bottomRightLon = searchParams.get(
        'include_filters[geo][bottom_right][lon]'
      );

      if (topLeftLat && topLeftLon && bottomRightLat && bottomRightLon) {
        newParams.set('include_filters[geo][type]', 'bbox');
        newParams.set('include_filters[geo][field]', 'dcat_bbox');
        newParams.set('include_filters[geo][top_left][lat]', topLeftLat);
        newParams.set('include_filters[geo][top_left][lon]', topLeftLon);
        newParams.set(
          'include_filters[geo][bottom_right][lat]',
          bottomRightLat
        );
        newParams.set(
          'include_filters[geo][bottom_right][lon]',
          bottomRightLon
        );
      }
    }

    // Preserve category filters from current URL
    const categoryFilters = searchParams.getAll(
      'include_filters[gbl_resourceClass_sm][]'
    );
    const legacyCategoryFilters = searchParams.getAll(
      'fq[gbl_resourceClass_sm][]'
    );

    // Use include_filters format (preferred)
    if (categoryFilters.length > 0) {
      categoryFilters.forEach((value) => {
        newParams.append('include_filters[gbl_resourceClass_sm][]', value);
      });
    } else if (legacyCategoryFilters.length > 0) {
      // Fall back to legacy format if present
      legacyCategoryFilters.forEach((value) => {
        newParams.append('include_filters[gbl_resourceClass_sm][]', value);
      });
    }

    navigate(`/search?${newParams.toString()}`);
  };

  const handleAdvancedSearchClick = () => {
    const newParams = new URLSearchParams(searchParams);

    // If we're on the search page, toggle the showAdvanced param
    if (location.pathname === '/search') {
      const currentShowAdvanced = newParams.get('showAdvanced') === 'true';
      if (currentShowAdvanced) {
        // If it's open, close it by removing the param
        newParams.delete('showAdvanced');
      } else {
        // If it's closed, open it by setting the param
        newParams.set('showAdvanced', 'true');
      }
    } else {
      // Not on search page - navigate to search with advanced open
      newParams.set('showAdvanced', 'true');
    }

    navigate(`/search?${newParams.toString()}`);
  };

  return (
    <header className="sticky top-0 z-50 bg-white shadow">
      <div className="w-full px-4 sm:px-6 lg:px-8">
        <div className="min-h-16 py-2 grid grid-cols-12 items-center gap-8">
          {/* Branding - matches facets column width */}
          <div className="col-span-2 flex items-center gap-3">
            <Globe2 className="h-8 w-8 text-blue-500" />
            <Link to="/" className="text-xl font-bold text-gray-900">
              BTAA Geoportal
            </Link>
          </div>

          {/* Search Field - matches results column width */}
          <div className="col-span-6 flex items-center">
            {!isHomePage && (
              <div className="w-full">
                <SearchField
                  placeholder="Search for maps, data, imagery..."
                  onSearch={handleSearch}
                  showAdvancedButton={true}
                  onAdvancedSearchClick={handleAdvancedSearchClick}
                />
              </div>
            )}
          </div>

          {/* Navigation - matches map column width */}
          <nav className="col-span-4 flex items-center justify-end space-x-4">
            <Link
              to="/map"
              className="text-gray-600 hover:text-gray-900 px-3 py-2 rounded-md text-sm font-medium"
            >
              Map
            </Link>
            <Link
              to="/bookmarks"
              className="text-gray-600 hover:text-gray-900 px-3 py-2 rounded-md text-sm font-medium"
            >
              Bookmarks
            </Link>
            <Link
              to="/"
              className="text-gray-600 hover:text-gray-900 px-3 py-2 rounded-md text-sm font-medium"
            >
              Search
            </Link>
          </nav>
        </div>
        {/* Resource Class Filter Tabs - positioned below search input, aligned with col-span-6 */}
        {!isHomePage && (
          <div className="grid grid-cols-12 gap-8 pb-0">
            <div className="col-span-2"></div>
            <div className="col-span-6">
              <ResourceClassFilterTabs />
            </div>
            <div className="col-span-4"></div>
          </div>
        )}
      </div>
    </header>
  );
}

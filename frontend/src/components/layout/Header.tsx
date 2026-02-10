import { Link, useLocation, useNavigate, useSearchParams } from 'react-router';
import { SearchField } from '../SearchField';
import { ResourceClassFilterTabs } from '../search/ResourceClassFilterTabs';
import { useTheme } from '../../hooks/useTheme';

export function Header() {
  const location = useLocation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { theme } = useTheme();
  const isHomePage = location.pathname === '/';
  const headerCfg = theme.institution?.header;

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
    <header className="sticky top-0 z-50 bg-brand text-white shadow-[0_2px_10px_rgba(0,0,0,0.15)]">
      <div className="w-full px-4 sm:px-6 lg:px-8">
        {/* Two-row header grid: row 1 = search, row 2 = resource class tabs.
            Logo spans both rows so it appears centered within the full header height. */}
        <div className="pt-2 pb-0 grid grid-cols-12 grid-rows-2 gap-x-8 gap-y-4 items-center">
          {/* Branding - matches facets column width (spans both rows) */}
          <div className="col-span-3 row-span-2 flex items-center justify-start">
            <Link
              to="/"
              className={`text-xl font-bold text-white flex items-center${
                headerCfg?.lockup_gap_rem == null ? ' gap-2' : ''
              }`}
              style={
                headerCfg?.lockup_gap_rem == null
                  ? undefined
                  : { gap: `${headerCfg.lockup_gap_rem}rem` }
              }
            >
              <img
                src={theme.institution.logo_url}
                alt={`${theme.institution.name} Logo`}
                className={
                  headerCfg?.logo_height_rem == null
                    ? 'h-12 sm:h-14 lg:h-16 w-auto object-contain'
                    : 'w-auto object-contain'
                }
                style={
                  headerCfg?.logo_height_rem == null
                    ? undefined
                    : { height: `${headerCfg.logo_height_rem}rem` }
                }
              />

              {theme.institution.logo_lockup?.right_text && (
                <>
                  {theme.institution.logo_lockup.separator !== 'none' && (
                    <span
                      aria-hidden="true"
                      className="inline-block w-px shrink-0 bg-white/70"
                      style={{
                        height: `${
                          headerCfg?.lockup_separator_height_rem ?? 2
                        }rem`,
                      }}
                    />
                  )}
                  <span
                    className={`text-white font-semibold tracking-wide${
                      headerCfg?.lockup_text_size_rem == null
                        ? ' text-lg sm:text-xl'
                        : ''
                    }`}
                    style={{
                      fontFamily:
                        theme.institution.logo_lockup.right_text_style
                          ?.font_family,
                      fontWeight:
                        theme.institution.logo_lockup.right_text_style
                          ?.font_weight,
                      letterSpacing:
                        theme.institution.logo_lockup.right_text_style
                          ?.letter_spacing,
                      fontSize:
                        headerCfg?.lockup_text_size_rem == null
                          ? undefined
                          : `${headerCfg.lockup_text_size_rem}rem`,
                    }}
                  >
                    {theme.institution.logo_lockup.right_text}
                  </span>
                </>
              )}
              {/* Keep name for accessibility, but hide it visually */}
              <span className="sr-only">{theme.institution.name}</span>
            </Link>
          </div>

          {/* Search (center column) */}
          <div className="col-span-6 flex items-center justify-center">
            {!isHomePage && (
              <div className="w-full relative top-4">
                <SearchField
                  placeholder="Search for maps, data, imagery..."
                  onSearch={handleSearch}
                  showAdvancedButton={true}
                  onAdvancedSearchClick={handleAdvancedSearchClick}
                />
              </div>
            )}
          </div>

          {/* Links (right column) */}
          <nav className="col-span-3 flex items-center justify-end pt-2">
            <Link
              to="/bookmarks"
              className="text-white/95 hover:text-white px-3 py-2 rounded-md text-sm font-medium"
            >
              Bookmarks
            </Link>
          </nav>

          {/* Resource Class Filter Tabs (row 2, centered column) */}
          {!isHomePage && (
            <div className="col-span-6 col-start-4 self-end">
              <ResourceClassFilterTabs variant="header" />
            </div>
          )}
        </div>
      </div>
    </header>
  );
}

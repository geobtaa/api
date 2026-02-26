import { useState, useEffect, useRef } from 'react';
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router';
import { Menu, X } from 'lucide-react';
import { SearchField } from '../SearchField';
import { ResourceClassFilterTabs } from '../search/ResourceClassFilterTabs';
import { useTheme } from '../../hooks/useTheme';

const NAV_LINKS = [
  {
    href: 'https://gin.btaa.org/about/about-us/',
    label: 'About',
    external: true,
  },
  { href: 'https://geo.btaa.org/feedback', label: 'Feedback', external: true },
  { href: '/bookmarks', label: 'Bookmarks', external: false },
];

export function Header() {
  const location = useLocation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { theme } = useTheme();
  const headerCfg = theme.institution?.header;
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const navPanelRef = useRef<HTMLDivElement>(null);

  // Close mobile nav on route or query change (e.g. clicking Bookmarks, selecting resource type)
  useEffect(() => {
    setMobileNavOpen(false);
  }, [location.pathname, location.search]);

  // Escape key to close mobile nav
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setMobileNavOpen(false);
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, []);

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
      <div className="w-full px-4 sm:px-6 lg:px-8 pb-4 xl:pb-0">
        {/* Responsive grid: desktop 3-6-3, tablet/mobile restacks with hamburger */}
        <div className="pt-2 pb-0 grid grid-cols-12 grid-rows-2 gap-x-4 md:gap-x-8 gap-y-1 xl:gap-y-4 items-center min-w-0">
          {/* Branding - responsive col span; lg+ spans both rows */}
          <div className="col-span-6 xl:col-span-3 row-span-2 flex items-center justify-start min-w-0">
            <Link
              to="/"
              className={`text-xl font-bold text-white flex items-center min-w-0 shrink-0${
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
                    ? 'h-8 sm:h-10 md:h-12 lg:h-14 xl:h-16 w-auto object-contain shrink-0'
                    : 'w-auto object-contain shrink-0'
                }
                style={
                  headerCfg?.logo_height_rem == null
                    ? undefined
                    : {
                        height: `clamp(3.5rem, 4vw, ${headerCfg.logo_height_rem}rem)`,
                      }
                }
              />
              {theme.institution.logo_lockup?.right_text && (
                <>
                  {theme.institution.logo_lockup.separator !== 'none' && (
                    <span
                      aria-hidden="true"
                      className="inline-block w-px shrink-0 bg-white/70"
                      style={{
                        height: `clamp(2rem, 2.5vw, ${
                          headerCfg?.lockup_separator_height_rem ?? 2
                        }rem)`,
                      }}
                    />
                  )}
                  <span
                    className={`inline-block font-semibold tracking-wide px-1 py-0.5 rounded-sm header-logo-lockup-text${
                      headerCfg?.lockup_text_size_rem == null
                        ? ' text-sm sm:text-base md:text-lg lg:text-xl'
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
                          : `clamp(1.5rem, 1.8vw, ${headerCfg.lockup_text_size_rem}rem)`,
                      // Keep contrast deterministic for Pa11y/axe.
                      backgroundColor: '#ffffff',
                      color: '#0b2942',
                    }}
                  >
                    {theme.institution.logo_lockup.right_text}
                  </span>
                </>
              )}
              <span className="sr-only">{theme.institution.name}</span>
            </Link>
          </div>

          {/* Search - full width on tablet/mobile, 6 cols on lg+ */}
          <div className="col-span-12 xl:col-span-6 flex items-center justify-center order-3 xl:order-none min-w-0">
            <div className="w-full relative top-0 xl:top-4">
              <SearchField
                placeholder="Search for maps, data, imagery..."
                onSearch={handleSearch}
                showAdvancedButton={true}
                onAdvancedSearchClick={handleAdvancedSearchClick}
              />
            </div>
          </div>

          {/* Desktop nav links (lg+) */}
          <nav
            className="hidden xl:flex col-span-3 items-center justify-end gap-2 pt-2"
            aria-label="Primary navigation"
          >
            {NAV_LINKS.map((link) =>
              link.external ? (
                <a
                  key={link.label}
                  href={link.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-white/95 hover:text-white px-3 py-2 rounded-md text-sm font-medium whitespace-nowrap"
                >
                  {link.label}
                </a>
              ) : (
                <Link
                  key={link.label}
                  to={link.href}
                  className="text-white/95 hover:text-white px-3 py-2 rounded-md text-sm font-medium whitespace-nowrap"
                >
                  {link.label}
                </Link>
              )
            )}
          </nav>

          {/* Hamburger (below lg) */}
          <div className="col-span-6 flex justify-end xl:hidden">
            <button
              type="button"
              onClick={() => setMobileNavOpen((o) => !o)}
              className="p-2 -mr-2 text-white/95 hover:text-white rounded-md focus:outline-none focus:ring-2 focus:ring-white/70"
              aria-expanded={mobileNavOpen}
              aria-controls="mobile-nav-panel"
              aria-label={mobileNavOpen ? 'Close menu' : 'Open menu'}
            >
              {mobileNavOpen ? (
                <X className="w-6 h-6" aria-hidden />
              ) : (
                <Menu className="w-6 h-6" aria-hidden />
              )}
            </button>
          </div>

          {/* Resource Class Filter Tabs (row 2) — desktop only */}
          <div className="hidden xl:block col-span-6 col-start-4 self-end min-w-0">
            <ResourceClassFilterTabs variant="header" />
          </div>
        </div>
      </div>

      {/* Mobile nav slide-out panel */}
      <div
        id="mobile-nav-panel"
        ref={navPanelRef}
        role="dialog"
        aria-modal="true"
        aria-label="Navigation menu"
        className={`fixed inset-y-0 right-0 z-[60] w-64 max-w-[85vw] bg-brand shadow-xl transform transition-transform duration-200 ease-out xl:hidden flex flex-col ${
          mobileNavOpen ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        <div className="flex items-center justify-between px-4 py-4 border-b border-white/20 shrink-0">
          <span className="text-white font-medium">Menu</span>
          <button
            type="button"
            onClick={() => setMobileNavOpen(false)}
            className="p-2 -mr-2 text-white/95 hover:text-white rounded-md focus:outline-none focus:ring-2 focus:ring-white/70"
            aria-label="Close menu"
          >
            <X className="w-6 h-6" aria-hidden />
          </button>
        </div>
        <nav
          className="flex flex-col flex-1 overflow-y-auto px-4 py-4 gap-1"
          aria-label="Primary navigation"
        >
          {NAV_LINKS.map((link) =>
            link.external ? (
              <a
                key={link.label}
                href={link.href}
                target="_blank"
                rel="noopener noreferrer"
                className="text-white/95 hover:text-white px-4 py-3 rounded-md text-base font-medium"
                onClick={() => setMobileNavOpen(false)}
              >
                {link.label}
              </a>
            ) : (
              <Link
                key={link.label}
                to={link.href}
                className="text-white/95 hover:text-white px-4 py-3 rounded-md text-base font-medium"
                onClick={() => setMobileNavOpen(false)}
              >
                {link.label}
              </Link>
            )
          )}
        </nav>
        <div className="px-4 py-4 border-t border-white/20">
          <ResourceClassFilterTabs variant="header" layout="vertical" />
        </div>
      </div>

      {/* Backdrop when mobile nav open */}
      {mobileNavOpen && (
        <button
          type="button"
          className="fixed inset-0 z-[55] bg-black/40 xl:hidden"
          aria-label="Close menu"
          onClick={() => setMobileNavOpen(false)}
        />
      )}
    </header>
  );
}

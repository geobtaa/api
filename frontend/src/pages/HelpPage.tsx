import { ArrowRight } from 'lucide-react';
import { Link } from 'react-router';
import { Header } from '../components/layout/Header';
import { Footer } from '../components/layout/Footer';
import { Seo } from '../components/Seo';

const mapControls = [
  'Turn the hexagon layer on or off',
  'Search for a place name',
  'Change the base map',
  'Zoom in or out',
];

const filters = [
  {
    name: 'Year',
    description: 'Limit results by date or date range.',
  },
  {
    name: 'Place',
    description: 'Show resources associated with selected place names.',
  },
  {
    name: 'Resource Class',
    description:
      'Limit results to broad categories such as Datasets, Maps, Web Services, Imagery, Websites, Collections, or Other.',
  },
  {
    name: 'Resource Type',
    description:
      'Narrow results by more specific types, such as dataset geometry or map genre.',
  },
  {
    name: 'Language',
    description: 'Show resources by language.',
  },
  {
    name: 'Creator',
    description:
      'Show resources by the person, organization, agency, or office that created them.',
  },
  {
    name: 'Publisher',
    description: 'Show resources by source, host, or distributor.',
  },
  {
    name: 'Provider',
    description:
      'Show resources contributed by a BTAA institution or repository.',
  },
  {
    name: 'Access',
    description: 'Limit results by public or restricted access.',
  },
  {
    name: 'Map Overlay',
    description:
      'Find scanned maps that use IIIF manifests, including maps with georeferencing information from AllMaps.',
  },
];

const resourceLinks = [
  'Download a file',
  'View an web service definition',
  'View additional metadata',
  'View a data dictionary',
  'Open a web map in ArcGIS Online',
  'Visit the original provider page',
];

const panelClass = 'border border-gray-200 bg-gray-50 p-5';
const listMarkerClass = 'mt-2.5 h-2 w-2 shrink-0 bg-brand';

export function HelpPage() {
  return (
    <div className="min-h-screen flex flex-col bg-white">
      <Seo
        title="Help"
        description="Learn how to search, filter, view resources, and use bookmarks in the Big Ten Academic Alliance Geoportal."
      />
      <Header />
      <main className="flex-1">
        <section className="bg-white border-b border-gray-200">
          <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6 sm:py-16 lg:px-8">
            <h1 className="text-4xl font-semibold text-gray-950 sm:text-5xl">
              Help
            </h1>
            <p className="mt-6 max-w-5xl text-lg leading-8 text-gray-700">
              Use the BTAA Geoportal to find maps, geospatial datasets, imagery,
              web services, and related geospatial resources from participating
              institutions.
            </p>
          </div>
        </section>

        <section className="border-b border-gray-200 bg-white">
          <div className="mx-auto max-w-6xl space-y-8 px-4 py-10 sm:px-6 lg:px-8">
            <section className="max-w-5xl">
              <h2 className="text-2xl font-semibold text-gray-950">
                Search the Geoportal
              </h2>
              <p className="mt-4 text-base leading-7 text-gray-700">
                You can search by keyword, location, map area, or filters. You
                can also browse all resources without entering a search term.
              </p>
            </section>

            <div className="grid gap-5 lg:grid-cols-2">
              <section className={panelClass}>
                <div>
                  <h3 className="text-xl font-semibold text-gray-950">
                    Search bar
                  </h3>
                  <p className="mt-4 text-base leading-7 text-gray-700">
                    The main search bar appears throughout the Geoportal.
                  </p>
                  <ul className="mt-4 space-y-3 text-base leading-7 text-gray-700">
                    <li className="flex gap-3">
                      <span className={listMarkerClass} aria-hidden />
                      <span>
                        To search by keyword, enter a word or phrase and press
                        Enter. You may also select a suggested term from the
                        dropdown list.
                      </span>
                    </li>
                    <li className="flex gap-3">
                      <span className={listMarkerClass} aria-hidden />
                      <span>
                        To search by location, enter a place name and select a
                        suggested location from the dropdown list. The Geoportal
                        will use that location to focus your search.
                      </span>
                    </li>
                    <li className="flex gap-3">
                      <span className={listMarkerClass} aria-hidden />
                      <span>
                        To browse all resources, leave the search box blank and
                        select Search.
                      </span>
                    </li>
                  </ul>
                </div>

                <div className="mt-6 border-t border-gray-200 pt-6">
                  <h3 className="text-xl font-semibold text-gray-950">
                    Advanced search
                  </h3>
                  <p className="mt-4 text-base leading-7 text-gray-700">
                    Use Advanced Search to build a more specific search.
                  </p>
                  <ul className="mt-4 space-y-3 text-base leading-7 text-gray-700">
                    <li className="flex gap-3">
                      <span className={listMarkerClass} aria-hidden />
                      <span>
                        Select the gear icon at the end of the search bar to
                        open the advanced search builder.
                      </span>
                    </li>
                    <li className="flex gap-3">
                      <span className={listMarkerClass} aria-hidden />
                      <span>
                        Choose metadata fields, enter search terms, and combine
                        terms with AND, OR, or NOT.
                      </span>
                    </li>
                  </ul>
                </div>
              </section>

              <section className={panelClass}>
                <h3 className="text-xl font-semibold text-gray-950">
                  Map search
                </h3>
                <div className="mt-4 space-y-4 text-base leading-7 text-gray-700">
                  <p>Use the map on the homepage to search by location.</p>
                  <p>
                    The hexagon layer shows where resources are concentrated.
                    Darker hexagons indicate more resources. Select a hexagon to
                    search for resources with centerpoints in or near that area.
                  </p>
                  <div>
                    <p>Map controls allow you to:</p>
                    <ul className="mt-3 space-y-2">
                      {mapControls.map((item) => (
                        <li key={item} className="flex gap-3">
                          <span className={listMarkerClass} aria-hidden />
                          <span>{item}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                  <p>
                    On the search results page, you can also use the map to
                    limit results by area. Choose <strong>Within</strong> to
                    find resources contained within the selected area, or{' '}
                    <strong>Overlap</strong> to find resources that intersect
                    with the selected area.
                  </p>
                </div>
              </section>

              <section className={`${panelClass} lg:col-span-2`}>
                <h3 className="text-xl font-semibold text-gray-950">Filters</h3>
                <div className="mt-4 space-y-4 text-base leading-7 text-gray-700">
                  <p>
                    Use filters to narrow your search results. Select{' '}
                    <strong>more</strong> within a filter to view additional
                    options. Depending on the filter, you may be able to search
                    within values, include or exclude values, or sort the list.
                  </p>
                  <p>
                    Use the options on the search results page to narrow your
                    results. Filters include:
                  </p>
                  <ul className="space-y-4">
                    {filters.map((filter) => (
                      <li
                        key={filter.name}
                        className="border-l-4 border-brand pl-4"
                      >
                        <strong className="block text-gray-950">
                          {filter.name}
                        </strong>
                        <span>{filter.description}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </section>
            </div>
          </div>
        </section>

        <section className="border-b border-gray-200 bg-white">
          <div className="mx-auto max-w-6xl space-y-8 px-4 py-10 sm:px-6 lg:px-8">
            <section>
              <h2 className="text-2xl font-semibold text-gray-950">
                View a Resource
              </h2>
              <div className="mt-4 space-y-6 text-base leading-7 text-gray-700">
                <p className="max-w-5xl">
                  Open a search result to view its description, access links,
                  download options, map previews, citation information, and full
                  metadata.
                </p>
                <div className={panelClass}>
                  <p>The resource page may include links to:</p>
                  <ul className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                    {resourceLinks.map((item) => (
                      <li key={item} className="flex gap-3">
                        <span className={listMarkerClass} aria-hidden />
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                </div>
                <div className="max-w-5xl">
                  <p>
                    The <strong>View Source</strong> button opens the original
                    source or partner repository page when one exists. Use this
                    link when you need the most recent version of a resource or
                    to search for additional information.
                  </p>
                </div>
              </div>
            </section>

            <section className={panelClass}>
              <h2 className="text-2xl font-semibold text-gray-950">
                Bookmarks
              </h2>
              <ul className="mt-4 grid gap-3 text-base leading-7 text-gray-700 sm:grid-cols-2">
                <li className="flex gap-3">
                  <span className={listMarkerClass} aria-hidden />
                  <span>
                    Use bookmarks to keep a temporary list of resources while
                    you browse.
                  </span>
                </li>
                <li className="flex gap-3">
                  <span className={listMarkerClass} aria-hidden />
                  <span>
                    Bookmarks stay in your browser. They do not sync across
                    devices or browsers.
                  </span>
                </li>
              </ul>
            </section>
          </div>
        </section>

        <section className="bg-white">
          <div className="mx-auto flex max-w-6xl flex-col gap-4 px-4 py-10 sm:px-6 sm:flex-row sm:items-center sm:justify-between lg:px-8">
            <div>
              <h2 className="text-2xl font-semibold text-gray-950">
                Need More Help?
              </h2>
              <p className="mt-2 text-base leading-7 text-gray-700">
                Contact us with questions, corrections, comments, or suggestions
                about the Geoportal.
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              <Link
                to="/feedback"
                className="inline-flex min-h-11 items-center justify-center gap-2 bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-[#002f47] focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-active focus-visible:ring-offset-2"
              >
                Contact us
                <ArrowRight className="h-4 w-4" aria-hidden />
              </Link>
              <Link
                to="/search?q="
                className="inline-flex min-h-11 items-center justify-center border border-gray-300 bg-white px-4 py-2 text-sm font-semibold text-gray-800 hover:border-brand-active hover:text-brand focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-active focus-visible:ring-offset-2"
              >
                Browse all resources
              </Link>
            </div>
          </div>
        </section>
      </main>
      <Footer />
    </div>
  );
}

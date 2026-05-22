import { ArrowRight } from 'lucide-react';
import { Link } from 'react-router';
import { Header } from '../components/layout/Header';
import { Footer } from '../components/layout/Footer';
import { Seo } from '../components/Seo';

const helpSections = [
  {
    title: 'Search',
    body: 'Enter keywords in the search box to find resources by title, subject, place, institution, publisher, or other metadata. Leave the search box blank and search to browse all resources.',
  },
  {
    title: 'Filter Results',
    body: 'Use the filters on search results to narrow by resource type, institution, subject, place, format, time period, and other available facets.',
  },
  {
    title: 'View a Resource',
    body: 'Open a result to see the resource description, access links, download options, map previews, citation information, and full metadata. Some resources link out to partner repositories for authoritative access.',
  },
  {
    title: 'Bookmarks',
    body: 'Use bookmarks to keep a temporary list of resources while you browse. Bookmarks are stored in your browser and are not synced across devices.',
  },
];

export function HelpPage() {
  return (
    <div className="min-h-screen flex flex-col bg-gray-50">
      <Seo
        title="Help"
        description="Learn how to search, filter, view resources, and use bookmarks in the Big Ten Academic Alliance Geoportal."
      />
      <Header />
      <main className="flex-1">
        <section className="bg-white border-b border-gray-200">
          <div className="max-w-5xl px-4 py-12 sm:px-6 sm:py-16 lg:px-8">
            <p className="text-sm font-semibold uppercase text-brand">
              BTAA Geoportal
            </p>
            <h1 className="mt-3 text-4xl font-semibold text-gray-950 sm:text-5xl">
              Help
            </h1>
            <p className="mt-6 max-w-3xl text-lg leading-8 text-gray-700">
              Use the BTAA Geoportal to search for maps, geospatial datasets,
              imagery, and related resources from participating institutions.
            </p>
          </div>
        </section>

        <section className="border-b border-gray-200 bg-gray-50">
          <div className="max-w-5xl px-4 py-10 sm:px-6 lg:px-8">
            <div className="grid gap-8 md:grid-cols-2">
              {helpSections.map((section) => (
                <section key={section.title}>
                  <h2 className="text-2xl font-semibold text-gray-950">
                    {section.title}
                  </h2>
                  <p className="mt-4 text-base leading-7 text-gray-700">
                    {section.body}
                  </p>
                </section>
              ))}
            </div>
          </div>
        </section>

        <section className="bg-white">
          <div className="flex max-w-5xl flex-col gap-4 px-4 py-10 sm:px-6 sm:flex-row sm:items-center sm:justify-between lg:px-8">
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

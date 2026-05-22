import { ArrowRight } from 'lucide-react';
import { Link } from 'react-router';
import { Header } from '../components/layout/Header';
import { Footer } from '../components/layout/Footer';
import { Seo } from '../components/Seo';

export function AboutPage() {
  return (
    <div className="min-h-screen flex flex-col bg-gray-50">
      <Seo
        title="About"
        description="Learn about the Big Ten Academic Alliance Geoportal and the collections it helps users discover."
      />
      <Header />
      <main className="flex-1">
        <section className="bg-white border-b border-gray-200">
          <div className="max-w-5xl px-4 py-12 sm:px-6 sm:py-16 lg:px-8">
            <p className="text-sm font-semibold uppercase text-brand">
              BTAA Geoportal
            </p>
            <h1 className="mt-3 max-w-3xl text-4xl font-semibold text-gray-950 sm:text-5xl">
              About the BTAA Geoportal
            </h1>
            <div className="mt-8 max-w-4xl space-y-6 text-lg leading-8 text-gray-700">
              <p>
                The Big Ten Academic Alliance (BTAA) Geoportal helps users find
                geospatial resources from BTAA member libraries and public data
                sources.
              </p>
              <p>
                The Geoportal brings together maps, geospatial datasets, aerial
                imagery, scanned historical maps, web services, and related
                documentation so users can search across institutions without
                leaving the Geoportal.
              </p>
              <p>
                Most resources in the Geoportal link to data stored by
                libraries, government agencies, and other trusted partners. Some
                resources are also stored and shared directly through the
                Geoportal as part of a growing BTAA effort to collect and
                preserve geospatial data.
              </p>
            </div>
          </div>
        </section>

        <section className="border-b border-gray-200 bg-gray-50">
          <div className="max-w-5xl px-4 py-10 sm:px-6 lg:px-8">
            <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(18rem,0.6fr)]">
              <div>
                <h2 className="text-2xl font-semibold text-gray-950">
                  How the Portal Works
                </h2>
                <p className="mt-6 text-base leading-7 text-gray-700">
                  The Geoportal indexes descriptive metadata from participating
                  institutions and presents it through a shared search
                  interface. When a resource is hosted by a partner institution,
                  the record links users to the original download, viewer,
                  service endpoint, or catalog page.
                </p>
              </div>
              <div>
                <h2 className="text-2xl font-semibold text-gray-950">
                  Who Maintains It
                </h2>
                <p className="mt-6 text-base leading-7 text-gray-700">
                  The BTAA Geoportal is maintained by the Big Ten Academic
                  Alliance Geospatial Information Network, a collaborative
                  program focused on discovery, access, and preservation for
                  geospatial information.
                </p>
                <a
                  href="https://gin.btaa.org"
                  className="mt-5 inline-flex items-center gap-2 text-sm font-semibold text-brand hover:text-brand-active"
                >
                  Visit BTAA GIN
                  <ArrowRight className="h-4 w-4" aria-hidden />
                </a>
              </div>
            </div>
          </div>
        </section>

        <section className="border-b border-gray-200 bg-white">
          <div className="max-w-5xl px-4 py-10 sm:px-6 lg:px-8">
            <h2 className="text-2xl font-semibold text-gray-950">
              What You Can Find
            </h2>
            <ul className="mt-6 grid gap-3 text-base leading-7 text-gray-700 sm:grid-cols-2 lg:grid-cols-3">
              {[
                'GIS datasets',
                'Scanned maps',
                'Historical and public domain maps',
                'Aerial photos',
                'Web mapping services',
                'Interactive maps and websites',
              ].map((item) => (
                <li key={item} className="flex gap-3">
                  <span
                    className="mt-2.5 h-2 w-2 shrink-0 bg-brand"
                    aria-hidden="true"
                  />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section className="bg-gray-50">
          <div className="flex max-w-5xl flex-col gap-4 px-4 py-10 sm:px-6 sm:flex-row sm:items-center sm:justify-between lg:px-8">
            <div>
              <h2 className="text-2xl font-semibold text-gray-950">
                Start Exploring
              </h2>
              <p className="mt-2 text-base leading-7 text-gray-700">
                Search the full Geoportal collection or send feedback to the
                project team.
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              <Link
                to="/search?q="
                className="inline-flex min-h-11 items-center justify-center gap-2 bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-[#002f47] focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-active focus-visible:ring-offset-2"
              >
                Browse resources
                <ArrowRight className="h-4 w-4" aria-hidden />
              </Link>
              <Link
                to="/feedback"
                className="inline-flex min-h-11 items-center justify-center border border-gray-300 bg-white px-4 py-2 text-sm font-semibold text-gray-800 hover:border-brand-active hover:text-brand focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-active focus-visible:ring-offset-2"
              >
                Share feedback
              </Link>
            </div>
          </div>
        </section>
      </main>
      <Footer />
    </div>
  );
}

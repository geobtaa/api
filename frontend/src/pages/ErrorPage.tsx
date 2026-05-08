import { ArrowRight, Home, Mail, RefreshCw, Search } from 'lucide-react';
import { isRouteErrorResponse, Link, useRouteError } from 'react-router';
import { Seo } from '../components/Seo';
import { getErrorPageContent } from './errorPageContent';

const buttonBaseClass =
  'inline-flex min-h-11 items-center justify-center gap-2 px-4 py-2 text-sm font-semibold transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-active focus-visible:ring-offset-2';
const primaryButtonClass = `${buttonBaseClass} bg-brand text-white hover:bg-[#002f47]`;
const secondaryButtonClass = `${buttonBaseClass} border border-gray-300 bg-white text-gray-800 hover:border-brand-active hover:text-brand`;

function routeErrorDetails(error: unknown): string | undefined {
  if (!import.meta.env.DEV) return undefined;

  if (isRouteErrorResponse(error)) {
    return typeof error.data === 'string' ? error.data : undefined;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return undefined;
}

export function GeoportalRouteErrorBoundary() {
  const error = useRouteError();
  const status = isRouteErrorResponse(error) ? error.status : 500;
  const statusText = isRouteErrorResponse(error) ? error.statusText : undefined;

  return (
    <GeoportalErrorPage
      status={status}
      statusText={statusText}
      details={routeErrorDetails(error)}
    />
  );
}

export function GeoportalErrorPage({
  status,
  statusText,
  details,
  onRetry,
}: {
  status?: number | null;
  statusText?: string;
  details?: string;
  onRetry?: () => void;
}) {
  const content = getErrorPageContent(status, statusText);
  const Icon = content.Icon;

  return (
    <div className="flex min-h-screen flex-col bg-gray-50 text-gray-900">
      <Seo title={content.seoTitle} />
      <header className="bg-brand text-white shadow-[0_2px_10px_rgba(0,0,0,0.15)]">
        <div className="flex w-full flex-wrap items-center justify-between gap-4 px-4 py-4 sm:px-6 lg:px-8">
          <Link
            to="/"
            className="flex min-w-0 items-center gap-3 text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2 focus-visible:ring-offset-brand"
          >
            <img
              src="/btaa-logo.png"
              alt="Big Ten Academic Alliance"
              className="h-10 w-auto shrink-0 object-contain sm:h-12"
            />
            <span className="border-l border-white/65 pl-3 text-xl font-semibold sm:text-2xl">
              Geoportal
            </span>
          </Link>
          <nav
            className="flex flex-wrap items-center gap-2 text-sm font-medium"
            aria-label="Error page navigation"
          >
            <Link
              to="/search"
              className="px-3 py-2 text-white/90 hover:text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-white"
            >
              Search
            </Link>
            <a
              href="https://geo.btaa.org/feedback"
              className="px-3 py-2 text-white/90 hover:text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-white"
            >
              Feedback
            </a>
          </nav>
        </div>
      </header>

      <main className="flex flex-1 flex-col">
        <section className="relative flex-1 overflow-hidden bg-gray-50">
          <div className="absolute inset-x-0 top-0 h-32 bg-brand" />
          <div className="relative w-full px-4 py-10 sm:px-6 sm:py-14 lg:px-8 lg:py-16">
            <div className="grid min-h-[28rem] border-y border-gray-200 bg-white shadow-sm lg:grid-cols-[minmax(0,1.08fr)_minmax(18rem,0.92fr)]">
              <div className="flex flex-col justify-center px-6 py-10 sm:px-10 lg:px-14">
                <div className="mb-6 flex items-center gap-4">
                  <span className="inline-flex h-14 w-14 shrink-0 items-center justify-center bg-brand text-white">
                    <Icon className="h-7 w-7" aria-hidden />
                  </span>
                  <div>
                    <p className="text-sm font-semibold text-brand-active">
                      Error {content.status}
                    </p>
                    <p className="mt-1 text-sm text-gray-600">
                      {content.eyebrow}
                    </p>
                  </div>
                </div>

                <h1 className="max-w-3xl text-3xl font-semibold text-gray-950 sm:text-4xl lg:text-5xl">
                  {content.title}
                </h1>
                <p className="mt-5 max-w-2xl text-base leading-7 text-gray-700 sm:text-lg">
                  {content.description}
                </p>
                <p className="mt-4 max-w-2xl border-l-4 border-brand-active bg-blue-50 px-4 py-3 text-sm leading-6 text-gray-700">
                  {content.note}
                </p>

                {details && (
                  <p className="mt-4 max-w-2xl border border-gray-200 bg-gray-50 px-4 py-3 font-mono text-xs leading-5 text-gray-600">
                    {details}
                  </p>
                )}

                <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:flex-wrap">
                  {onRetry ? (
                    <button
                      type="button"
                      onClick={onRetry}
                      className={primaryButtonClass}
                    >
                      <RefreshCw className="h-4 w-4" aria-hidden />
                      Try again
                    </button>
                  ) : (
                    <Link to="/search" className={primaryButtonClass}>
                      <Search className="h-4 w-4" aria-hidden />
                      Search Geoportal
                    </Link>
                  )}
                  <Link to="/" className={secondaryButtonClass}>
                    <Home className="h-4 w-4" aria-hidden />
                    Geoportal home
                  </Link>
                  <a
                    href="https://geo.btaa.org/feedback"
                    className={secondaryButtonClass}
                  >
                    <Mail className="h-4 w-4" aria-hidden />
                    Contact us
                  </a>
                </div>
              </div>

              <div className="relative hidden min-h-[24rem] overflow-hidden bg-brand md:block">
                <img
                  src="/urban-base-layers-featured.png"
                  alt=""
                  aria-hidden="true"
                  className="absolute inset-0 h-full w-full object-cover opacity-75 mix-blend-luminosity"
                />
                <div className="absolute inset-0 bg-brand/70" />
                <div className="absolute right-6 top-6 border border-white/35 bg-white/10 px-5 py-4 text-white backdrop-blur-sm">
                  <span className="block text-sm font-semibold">
                    Status code
                  </span>
                  <span className="mt-1 block text-5xl font-bold">
                    {content.status}
                  </span>
                </div>
                <div className="absolute inset-x-0 bottom-0 p-6 text-white sm:p-8">
                  <div className="border-l-4 border-white pl-4">
                    <p className="text-lg font-semibold">BTAA Geoportal</p>
                    <p className="mt-2 max-w-sm text-sm leading-6 text-white/85">
                      Discover maps, data, imagery, and geospatial collections
                      from the Big Ten Academic Alliance and OpenGeoMetadata
                      community.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>
      </main>

      <footer className="bg-brand text-white">
        <div className="flex w-full flex-col gap-5 px-4 py-6 sm:px-6 lg:flex-row lg:items-center lg:justify-between lg:px-8">
          <div className="flex items-center gap-4">
            <img
              src="/gin-white.png"
              alt="Big Ten Academic Alliance Geospatial Information Network"
              className="h-10 w-auto"
            />
            <p className="text-sm text-white/75">
              Big Ten Academic Alliance Geoportal
            </p>
          </div>
          <a
            href="https://gin.btaa.org/guides/"
            className="inline-flex items-center gap-2 text-sm font-semibold text-white/85 hover:text-white"
          >
            Help guides
            <ArrowRight className="h-4 w-4" aria-hidden />
          </a>
        </div>
      </footer>
    </div>
  );
}

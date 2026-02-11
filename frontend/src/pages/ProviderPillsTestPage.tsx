import { Link } from 'react-router';
import { ResultCardPill } from '../components/search/ResultCardPill';
import {
  PROVIDER_DISPLAY_NAMES,
  PROVIDER_SCHOOL_COLORS,
} from '../utils/providerIcons';

const PROVIDER_SLUGS = Object.keys(PROVIDER_SCHOOL_COLORS).sort();

export function ProviderPillsTestPage() {
  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-4xl">
        <div className="mb-8">
          <Link
            to="/test/fixtures"
            className="text-sm text-blue-600 hover:text-blue-800"
          >
            ← Back to Test Fixtures
          </Link>
          <h1 className="mt-2 text-2xl font-bold text-gray-900">
            Provider Institution Pills
          </h1>
          <p className="mt-1 text-sm text-gray-600">
            Review all institution pills with their school colors. Each provider
            shows two variants: with year, and resource-class only.
          </p>
        </div>

        <div className="space-y-6">
          {PROVIDER_SLUGS.map((slug) => {
            const displayName = PROVIDER_DISPLAY_NAMES[slug] ?? slug;
            const color = PROVIDER_SCHOOL_COLORS[slug];

            return (
              <div
                key={slug}
                className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm"
              >
                <div className="flex flex-wrap items-center gap-4">
                  <div className="min-w-[200px]">
                    <p className="text-sm font-medium text-gray-900">
                      {displayName}
                    </p>
                    <p className="text-xs text-gray-500 font-mono">{slug}</p>
                    <p className="mt-1 text-xs text-gray-500">
                      {color}
                      <span
                        className="ml-2 inline-block h-3 w-6 rounded border border-gray-300"
                        style={{ backgroundColor: color }}
                        aria-hidden
                      />
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-6">
                    <div>
                      <p className="mb-1 text-xs font-medium uppercase tracking-wide text-gray-400">
                        With year
                      </p>
                      <ResultCardPill
                        indexYear={2024}
                        resourceClass="Datasets"
                        provider={displayName}
                      />
                    </div>
                    <div>
                      <p className="mb-1 text-xs font-medium uppercase tracking-wide text-gray-400">
                        Resource class only
                      </p>
                      <ResultCardPill
                        resourceClass="Maps"
                        provider={displayName}
                      />
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        <div className="mt-12 rounded-lg border border-amber-200 bg-amber-50 p-4">
          <h2 className="text-sm font-semibold text-amber-900">
            No icon / fallback
          </h2>
          <p className="mt-1 text-xs text-amber-800">
            Providers without a matching icon (e.g. &quot;GeoBlacklight
            Community&quot;) render as grey pills without the school badge.
          </p>
          <div className="mt-3 flex gap-6">
            <div>
              <p className="mb-1 text-xs font-medium uppercase tracking-wide text-amber-700">
                With year
              </p>
              <ResultCardPill
                indexYear={2020}
                resourceClass="Datasets"
                provider="GeoBlacklight Community"
              />
            </div>
            <div>
              <p className="mb-1 text-xs font-medium uppercase tracking-wide text-amber-700">
                Resource class only
              </p>
              <ResultCardPill
                resourceClass="Maps"
                provider="Unknown Institution"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

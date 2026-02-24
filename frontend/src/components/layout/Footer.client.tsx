import React from 'react';
import { ExternalLink } from 'lucide-react';
import { useApi } from '../../context/ApiContext';
import { useTheme } from '../../hooks/useTheme';

interface FooterProps {
  id?: string;
}

function BtaaFooter({ id }: FooterProps) {
  const { lastApiUrl } = useApi();
  const { themeId, themes, setThemeId } = useTheme();

  return (
    <footer className="bg-[#003C5B] text-white print:hidden">
      <div className="w-full px-4 sm:px-6 lg:px-8 py-12">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-12">
          {/* Left Column: Logos & Links */}
          <div className="space-y-8">
            {/* Logo Section */}
            <div>
              <a href="https://gin.btaa.org">
                <img
                  src="/gin-white.png"
                  alt="Big Ten Academic Alliance Geospatial Information Network"
                  className="h-16 w-auto mb-4 rounded"
                />
              </a>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-8 text-sm">
              {/* About & Help */}
              <div>
                <h3 className="font-bold text-lg mb-3 text-blue-100">
                  About & Help
                </h3>
                <ul className="space-y-2">
                  <li>
                    <a
                      href="https://gin.btaa.org/about/about-us/"
                      className="hover:text-blue-200 hover:underline"
                    >
                      About Us
                    </a>
                  </li>
                  <li>
                    <a
                      href="https://gin.btaa.org/updates"
                      className="hover:text-blue-200 hover:underline"
                    >
                      Program Updates
                    </a>
                  </li>
                  <li>
                    <a
                      href="https://geo.btaa.org/feedback"
                      className="hover:text-blue-200 hover:underline"
                    >
                      Contact Us
                    </a>
                  </li>
                  <li>
                    <a
                      href="https://gin.btaa.org/guides/"
                      className="hover:text-blue-200 hover:underline"
                    >
                      Help Guides
                    </a>
                  </li>
                  <li>
                    <a
                      href="https://gin.btaa.org/tutorials"
                      className="hover:text-blue-200 hover:underline"
                    >
                      Tutorials
                    </a>
                  </li>
                </ul>
              </div>

              {/* Policies */}
              <div>
                <h3 className="font-bold text-lg mb-3 text-blue-100">
                  Policies
                </h3>
                <ul className="space-y-2">
                  <li>
                    <a
                      href="https://gin.btaa.org/policies/harmful-language"
                      className="hover:text-blue-200 hover:underline"
                    >
                      Harmful Language Statement
                    </a>
                  </li>
                  <li>
                    <a
                      href="https://btaa.org/privacy"
                      className="hover:text-blue-200 hover:underline"
                    >
                      Privacy Statement
                    </a>
                  </li>
                  <li>
                    <a
                      href="https://gin.btaa.org/policies/collection-development"
                      className="hover:text-blue-200 hover:underline"
                    >
                      Collection Development
                    </a>
                  </li>
                </ul>
              </div>

              {/* Sponsors */}
              <div>
                <h3 className="font-bold text-lg mb-3 text-blue-100">
                  Sponsors
                </h3>
                <ul className="space-y-2">
                  <li>
                    <a
                      href="https://btaa.org/"
                      className="hover:text-blue-200 hover:underline"
                    >
                      Big Ten Academic Alliance
                    </a>
                  </li>
                  <li>
                    <a
                      href="https://gin.btaa.org/"
                      className="hover:text-blue-200 hover:underline"
                    >
                      BTAA Geospatial Information Network
                    </a>
                  </li>
                  <li>
                    <a
                      href="https://lib.umn.edu/"
                      className="hover:text-blue-200 hover:underline"
                    >
                      University of Minnesota Libraries
                    </a>
                  </li>
                </ul>
              </div>
            </div>
          </div>

          {/* Right Column: Stories & Members */}
          <div className="space-y-8">
            {/* Stories */}
            <div>
              <h3 className="font-bold text-lg mb-3 text-blue-100">
                BTAA Geoportal Collection Stories
              </h3>
              <div className="bg-blue-900/30 rounded p-4 border border-blue-800/50">
                <p className="text-sm italic text-blue-200 mb-2">
                  Check out the latest stories from our blog:
                </p>
                <a
                  href="https://gin.btaa.org/blog"
                  className="text-sm font-semibold text-white hover:text-blue-200 hover:underline flex items-center gap-1"
                >
                  View Collection Stories <ExternalLink size={12} />
                </a>
              </div>
            </div>

            {/* Member Libraries */}
            <div>
              <h4 className="font-bold text-base mb-3 text-blue-100">
                BTAA Member Libraries
              </h4>
              <ul className="text-xs text-blue-200 grid grid-cols-2 gap-x-4 gap-y-1">
                <li>Indiana University</li>
                <li>Michigan State University</li>
                <li>Northwestern University</li>
                <li>Pennsylvania State University</li>
                <li>Purdue University</li>
                <li>Rutgers University</li>
                <li>The Ohio State University</li>
                <li>University of Chicago</li>
                <li>University of Illinois</li>
                <li>University of Iowa</li>
                <li>University of Maryland</li>
                <li>University of Michigan</li>
                <li>University of Minnesota</li>
                <li>University of Nebraska-Lincoln</li>
                <li>University of Oregon</li>
                <li>University of Washington</li>
                <li>University of Wisconsin-Madison</li>
              </ul>
            </div>
          </div>
        </div>

        {/* Divider */}
        <hr className="border-blue-800 my-8" />

        {/* Bottom Section: App Controls & Copyright */}
        <div className="flex flex-col md:flex-row justify-between items-end gap-6 text-sm">
          {/* Copyright & API Info */}
          <div className="flex flex-col gap-4 w-full md:w-auto">
            <div className="text-blue-200">
              © {new Date().getFullYear()} Big Ten Academic Alliance. All rights
              reserved.
            </div>

            {/* API Debug Info */}
            {lastApiUrl ? (
              <div className="flex items-center gap-2 bg-[#002a41] rounded px-3 py-1.5 border border-blue-900/50 w-full md:w-fit">
                <span className="text-xs uppercase tracking-wider font-semibold text-blue-400 shrink-0">
                  API:
                </span>
                <a
                  href={lastApiUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="truncate text-xs font-mono text-blue-300 hover:text-white transition-colors flex items-center gap-1 group"
                >
                  <span className="truncate max-w-[200px] sm:max-w-[400px]">
                    {lastApiUrl}
                  </span>
                  <ExternalLink
                    size={10}
                    className="shrink-0 opacity-50 group-hover:opacity-100"
                  />
                </a>
              </div>
            ) : (
              <div className="text-xs text-blue-400 italic">
                No API requests yet
              </div>
            )}
          </div>

          {/* App Tools (Theme) */}
          <div className="flex flex-wrap items-center gap-6 bg-[#002a41] px-4 py-3 rounded-lg border border-blue-900/30">
            {/* Theme Selector */}
            <div className="flex items-center gap-2">
              <label
                className="text-xs text-blue-300 uppercase font-semibold tracking-wider"
                htmlFor="theme-select"
              >
                Theme:
              </label>
              <select
                id="theme-select"
                value={themeId}
                onChange={(e) => {
                  const next = e.target.value;
                  if (next === themeId) return;
                  setThemeId(next);
                  window.location.reload();
                }}
                className="text-xs bg-[#004d73] border border-blue-700 text-white rounded px-2 py-1 focus:ring-1 focus:ring-white outline-none"
              >
                {themes.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.label}
                  </option>
                ))}
              </select>
            </div>

            {/* View in Portal Link (Contextual) */}
            {id && (
              <>
                <div className="h-4 w-px bg-blue-800"></div>
                <a
                  href={`https://geo.btaa.org/catalog/${id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-blue-300 hover:text-white transition-colors flex items-center gap-1 uppercase font-semibold tracking-wider"
                >
                  View Original
                  <ExternalLink size={10} />
                </a>
              </>
            )}
          </div>
        </div>
      </div>
    </footer>
  );
}

function DefaultFooter({ id }: FooterProps) {
  const { lastApiUrl } = useApi();
  const { themeId, themes, setThemeId } = useTheme();

  return (
    <footer className="bg-white shadow-sm print:hidden">
      <div className="w-full px-4 sm:px-6 lg:px-8 py-6">
        <div className="flex flex-col space-y-4">
          {/* Links Row */}
          <div className="flex flex-col md:flex-row items-center justify-between gap-4">
            <div className="text-sm text-gray-500">
              © {new Date().getFullYear()} Big Ten Academic Alliance. All rights
              reserved.
            </div>
            <div className="flex flex-wrap items-center justify-center gap-4">
              <div className="flex items-center gap-2">
                <label
                  className="text-sm text-gray-500"
                  htmlFor="theme-select-default"
                >
                  Theme
                </label>
                <select
                  id="theme-select-default"
                  value={themeId}
                  onChange={(e) => {
                    const next = e.target.value;
                    if (next === themeId) return;
                    setThemeId(next);
                    window.location.reload();
                  }}
                  className="text-sm border border-gray-300 rounded px-2 py-1"
                >
                  {themes.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.label}
                    </option>
                  ))}
                </select>
              </div>
              {id && (
                <a
                  href={`https://geo.btaa.org/catalog/${id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-gray-500 hover:text-gray-900 flex items-center gap-1"
                >
                  View in BTAA Geoportal
                  <ExternalLink size={14} />
                </a>
              )}
              <a
                href="https://gin.btaa.org/"
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-gray-500 hover:text-gray-900"
              >
                About
              </a>
              <a
                href="https://geo.btaa.org/docs"
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-gray-500 hover:text-gray-900"
              >
                Documentation
              </a>
            </div>
          </div>

          {/* API URL Row */}
          {lastApiUrl ? (
            <div className="text-sm text-gray-500">
              <p className="mb-2">Last API Request:</p>
              <a
                href={lastApiUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="group block"
              >
                <div className="flex items-center gap-2 p-2 bg-gray-50 rounded border border-gray-200 hover:border-blue-300 hover:shadow-sm transition-all">
                  <code className="flex-1 overflow-x-auto text-blue-600">
                    {lastApiUrl}
                  </code>
                  <ExternalLink
                    size={14}
                    className="text-gray-400 group-hover:text-blue-500"
                  />
                </div>
              </a>
            </div>
          ) : (
            <div className="text-sm text-gray-400">
              <p className="mb-2">Last API Request:</p>
              <div className="p-2 bg-gray-50 rounded border border-gray-200">
                <code className="block overflow-x-auto">None yet</code>
              </div>
            </div>
          )}
        </div>
      </div>
    </footer>
  );
}

export function Footer({ id }: FooterProps) {
  const { themeId } = useTheme();

  if (themeId === 'btaa') {
    return <BtaaFooter id={id} />;
  }

  return <DefaultFooter id={id} />;
}

export default Footer;

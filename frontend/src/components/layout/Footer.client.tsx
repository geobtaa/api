import React from "react";
import { ExternalLink } from "lucide-react";
import { useApi } from "../../context/ApiContext";
import { useDebug } from "../../context/DebugContext";
import { useTheme } from "../../hooks/useTheme";

interface FooterProps {
  id?: string; // Make optional since not all pages will have an ID
}

export function Footer({ id }: FooterProps) {
  const { lastApiUrl } = useApi();
  const { showDetails, toggleDetails } = useDebug();
  const { themeId, themes, setThemeId } = useTheme();

  return (
    <footer className="bg-white shadow-sm">
      <div className="w-full px-4 sm:px-6 lg:px-8 py-6">
        <div className="flex flex-col space-y-4">
          {/* Links Row */}
          <div className="flex items-center justify-between">
            <div className="text-sm text-gray-500">
              © {new Date().getFullYear()} Big Ten Academic Alliance. All rights
              reserved.
            </div>
            <div className="flex items-center space-x-4">
              <div className="flex items-center gap-2">
                <label className="text-sm text-gray-500" htmlFor="theme-select">
                  Theme
                </label>
                <select
                  id="theme-select"
                  value={themeId}
                  onChange={(e) => {
                    const next = e.target.value;
                    if (next === themeId) return;
                    // Persist theme selection and hard-reload so SSR loaders pick up the cookie.
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
              <button
                onClick={toggleDetails}
                className="text-sm text-gray-500 hover:text-gray-900"
              >
                {showDetails ? "Hide Details" : "Show Details"}
              </button>
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

export default Footer;


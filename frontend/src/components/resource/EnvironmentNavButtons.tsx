import { useState, useEffect } from 'react';
import { ExternalLink } from 'lucide-react';

interface EnvironmentNavButtonsProps {
  resourceId: string;
}

export function EnvironmentNavButtons({
  resourceId,
}: EnvironmentNavButtonsProps) {
  const [isMounted, setIsMounted] = useState(false);

  useEffect(() => {
    setIsMounted(true);
  }, []);

  // Don't render during SSR
  if (!isMounted) {
    return null;
  }

  // Detect current environment
  const currentHost = window.location.hostname.toLowerCase();
  const isLocalhost =
    currentHost === 'localhost' || currentHost === '127.0.0.1';
  const isDevServer =
    currentHost === 'lib-btaageoapi-dev-app-01.oit.umn.edu';

  // Don't show buttons on production
  if (!isLocalhost && !isDevServer) {
    return null;
  }

  // Build URLs
  const devUrl = `https://lib-btaageoapi-dev-app-01.oit.umn.edu/resources/${resourceId}`;
  const prodUrl = `https://geo.btaa.org/catalog/${resourceId}`;

  return (
    <nav
      className="fixed bottom-6 right-6 z-50 flex flex-col gap-3"
      aria-label="Environment shortcuts"
    >
      {isLocalhost && (
        <>
          <a
            href={devUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 px-4 py-2 bg-blue-700 text-white text-base font-semibold rounded-lg shadow-lg hover:bg-blue-800 transition-colors"
            title="View on Dev Server"
          >
            <ExternalLink className="w-4 h-4 shrink-0" aria-hidden />
            Dev Server
          </a>
          <a
            href={prodUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 px-4 py-2 bg-green-700 text-white text-base font-semibold rounded-lg shadow-lg hover:bg-green-800 transition-colors"
            title="View on Production Server"
          >
            <ExternalLink className="w-4 h-4 shrink-0" aria-hidden />
            Production
          </a>
        </>
      )}
      {isDevServer && (
        <a
          href={prodUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 px-4 py-2 bg-green-700 text-white text-base font-semibold rounded-lg shadow-lg hover:bg-green-800 transition-colors"
          title="View on Production Server"
        >
          <ExternalLink className="w-4 h-4 shrink-0" aria-hidden />
          Production
        </a>
      )}
    </nav>
  );
}

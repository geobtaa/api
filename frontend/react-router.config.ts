import type { Config } from '@react-router/dev/config';

export default {
  // Enable server-side rendering
  ssr: true,
  // The browser-facing origin can differ from the SSR server behind a proxy
  // or Docker port mapping. Analytics actions also check the exact origin.
  allowedActionOrigins:
    process.env.ANALYTICS_BASE_URL || process.env.VITE_API_BASE_URL
      ? [
          new URL(
            process.env.ANALYTICS_BASE_URL || process.env.VITE_API_BASE_URL!
          ).host,
        ]
      : [],
  // Routes are automatically discovered from app/routes/ directory
  // React Router v7 uses file-based routing
} satisfies Config;

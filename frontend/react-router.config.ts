import type { Config } from '@react-router/dev/config';

export default {
  // Enable server-side rendering
  ssr: true,
  // TLS terminates before the HTTP-only SSR server. Allow only the configured
  // public host; analytics actions additionally require its exact HTTPS origin.
  allowedActionOrigins: process.env.VITE_API_BASE_URL
    ? [new URL(process.env.VITE_API_BASE_URL).host]
    : [],
  // Routes are automatically discovered from app/routes/ directory
  // React Router v7 uses file-based routing
} satisfies Config;

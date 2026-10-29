import { reactRouter } from '@react-router/dev/vite';
import { existsSync } from 'node:fs';
import { defineConfig } from 'vite';
import path from 'node:path';

// https://vitejs.dev/config/
// Force restart: 1
export default defineConfig({
  plugins: [
    {
      name: 'private-analytics-data',
      enforce: 'pre',
      buildStart() {
        if (existsSync(path.resolve(__dirname, 'public/analytics-reports'))) {
          throw new Error(
            'Analytics downloads must stay outside the public asset directory'
          );
        }
      },
      transform(_code, id, options) {
        if (!options?.ssr && /\/src\/data\/analytics\//.test(id)) {
          throw new Error(
            'Analytics snapshots must only be imported by the authenticated server loader: ' +
              id
          );
        }
      },
    },
    reactRouter({
      // React Router v7 configuration
      // Server-side rendering enabled by default
    }),
  ],
  server: {
    port: 3000,
    allowedHosts: ['btaa-geoportal.ngrok.io'],
  },
  worker: {
    // The GeoTIFF worker used by ogm-viewer imports decoder chunks.
    format: 'es',
  },
  resolve: {
    alias: {
      // Some dependencies (e.g. html-parse-stringify) expect `void-elements` to have a default export.
      // The upstream package is CommonJS; this shim provides a stable ESM default export for Vite.
      'void-elements': path.resolve(__dirname, 'src/shims/void-elements.ts'),
      // Note: react-helmet-async is handled via optimizeDeps.include and ssr.noExternal
      // No need for a hardcoded alias - let Vite resolve it naturally
    },
    // Ensure a single React instance (prevents "Invalid hook call").
    dedupe: [
      'react',
      'react-dom',
      'react-dom/client',
      'react/jsx-runtime',
      'react/jsx-dev-runtime',
    ],
  },
  optimizeDeps: {
    // These deps either ship complex mixed-module code or are sensitive to React dedupe.
    // Let Vite handle them without esbuild pre-bundling to avoid "Invalid hook call".
    exclude: [
      'lucide-react',
      'maplibre-gl',
      // OGM Viewer resolves its theme and icon assets relative to its module.
      // Keep it out of Vite's dev prebundle so those URLs retain the package path.
      'ogm-viewer',
      'ogm-viewer/lib',
    ],
    include: [
      'react-helmet-async',
      'h3-js',
      'js-yaml',
      'js-cookie',
      '@marsidev/react-turnstile',
      'recharts',
    ],
  },
  ssr: {
    noExternal: ['react-helmet-async'],
  },
});

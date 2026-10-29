import { reactRouter } from '@react-router/dev/vite';
import { existsSync, readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';
import { defineConfig } from 'vite';
import path from 'node:path';
import { BASEMAP_STYLES } from './src/config/mapStyles';

// A vendor backport changes without a package-lock update. Include its content
// in Vite's plugin identity so browser dependency URLs get a fresh cache key.
const viewerBackportHash = createHash('sha256')
  .update(
    readFileSync(
      new URL('./vendor/ogm-viewer/preview-events.js', import.meta.url)
    )
  )
  .digest('hex')
  .slice(0, 12);

// https://vitejs.dev/config/
// Force restart: 1
export default defineConfig({
  plugins: [
    {
      name: `ogm-viewer-assets-and-basemaps-${viewerBackportHash}`,
      enforce: 'pre',
      transform(source, id) {
        if (!id.includes('/ogm-viewer/dist/components/')) return;
        source = source
          .replaceAll(
            'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
            BASEMAP_STYLES.liberty
          )
          .replaceAll(
            'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
            BASEMAP_STYLES.dark
          );
        if (!source.includes('"lerc-wasm.wasm"')) return source;
        const require = createRequire(import.meta.url);
        const viewerDirectory = path.dirname(
          require.resolve('ogm-viewer/package.json')
        );
        const wasm = require.resolve('lerc/lerc-wasm.wasm', {
          paths: [viewerDirectory],
        });
        return source.replaceAll('"lerc-wasm.wasm"', JSON.stringify(wasm));
      },
    },
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
      // ogm-viewer's COG bundle inlines @developmentseed/geotiff's worker URL,
      // leaving it relative to the ogm-viewer chunk instead of the dependency
      // that ships the worker. Point Vite at the packaged worker explicitly.
      [path.resolve(
        __dirname,
        'node_modules/ogm-viewer/dist/components/worker.js'
      )]: path.resolve(
        __dirname,
        'node_modules/@developmentseed/geotiff/dist/pool/worker.js'
      ),
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

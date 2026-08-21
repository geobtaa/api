import { reactRouter } from '@react-router/dev/vite';
import { readdir, readFile } from 'node:fs/promises';
import { defineConfig, type Plugin } from 'vite';
import path from 'node:path';

const ogmViewerAssetsDirectory = path.resolve(
  __dirname,
  'node_modules/ogm-viewer/dist/components/assets'
);
const ogmViewerAssetDirectory = 'ogm-viewer';
const ogmViewerAssetBase = `/${ogmViewerAssetDirectory}/`;

async function assetFiles(directory: string, prefix = ''): Promise<string[]> {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = await Promise.all(
    entries.map(async (entry) => {
      const relativePath = path.join(prefix, entry.name);
      return entry.isDirectory()
        ? assetFiles(path.join(directory, entry.name), relativePath)
        : [relativePath];
    })
  );

  return files.flat();
}

function ogmViewerAssets(): Plugin {
  let isBuild = false;
  let isSsrBuild = false;

  return {
    name: 'ogm-viewer-assets',
    configResolved(config) {
      isBuild = config.command === 'build';
      isSsrBuild = Boolean(config.build.ssr);
    },
    configureServer(server) {
      server.middlewares.use(async (request, response, next) => {
        const assetPrefix = `${ogmViewerAssetBase}assets/`;
        const requestPath = request.url?.split('?', 1)[0];

        if (!requestPath?.startsWith(assetPrefix)) return next();

        const relativePath = decodeURIComponent(
          requestPath.slice(assetPrefix.length)
        );
        if (relativePath.split('/').includes('..')) return next();

        try {
          const source = await readFile(
            path.join(ogmViewerAssetsDirectory, relativePath)
          );
          const contentTypes: Record<string, string> = {
            '.css': 'text/css; charset=utf-8',
            '.ico': 'image/x-icon',
            '.json': 'application/json; charset=utf-8',
            '.svg': 'image/svg+xml',
          };

          response.statusCode = 200;
          response.setHeader(
            'Content-Type',
            contentTypes[path.extname(relativePath)] ??
              'application/octet-stream'
          );
          response.setHeader('Cache-Control', 'no-cache');
          response.end(source);
        } catch {
          next();
        }
      });
    },
    async buildStart() {
      if (!isBuild || isSsrBuild) return;

      for (const relativePath of await assetFiles(ogmViewerAssetsDirectory)) {
        this.emitFile({
          type: 'asset',
          fileName: path.posix.join(
            ogmViewerAssetDirectory,
            'assets',
            relativePath.split(path.sep).join('/')
          ),
          source: await readFile(
            path.join(ogmViewerAssetsDirectory, relativePath)
          ),
        });
      }
    },
  };
}

// https://vitejs.dev/config/
// Force restart: 1
export default defineConfig({
  plugins: [
    ogmViewerAssets(),
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
      // The homepage's featured-resource map still uses GeoBlacklight's
      // Leaflet layer factories, including the local OpenIndexMap normalizer.
      'geoblacklight/leaflet/layer_index_map': path.resolve(
        __dirname,
        'src/geoblacklight/layer_index_map.ts'
      ),
      geoblacklight: path.resolve(
        __dirname,
        'node_modules/@geoblacklight/frontend/app/javascript/geoblacklight'
      ),
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
      '@geoblacklight/frontend',
      // OGM Viewer resolves its theme and icon assets relative to its module.
      // Keep it out of Vite's dev prebundle so those URLs retain the package path.
      'ogm-viewer',
      'ogm-viewer/lib',
      'ogm-viewer/components/p-BbMGvQFJ.js',
    ],
    include: ['react-helmet-async', 'h3-js'],
  },
  ssr: {
    noExternal: ['react-helmet-async'],
  },
});

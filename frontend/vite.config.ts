import { reactRouter } from '@react-router/dev/vite';
import { defineConfig } from 'vite';
import path from "node:path";

// https://vitejs.dev/config/
// Force restart: 1
export default defineConfig({
  plugins: [
    reactRouter({
      // React Router v7 configuration
      // Server-side rendering enabled by default
    }),
  ],
  server: {
    port: 3000,
  },
  resolve: {
    // GeoBlacklight's source files import internal modules via `geoblacklight/...`.
    // Map that prefix to the package's source directory so Vite can resolve them.
    alias: {
      geoblacklight: path.resolve(
        __dirname,
        "node_modules/@geoblacklight/frontend/app/javascript/geoblacklight",
      ),
      // Some dependencies (e.g. html-parse-stringify) expect `void-elements` to have a default export.
      // The upstream package is CommonJS; this shim provides a stable ESM default export for Vite.
      "void-elements": path.resolve(__dirname, "src/shims/void-elements.ts"),
      // Force resolution to the ESM entry point to prevent dual-package hazards (CJS vs ESM)
      "react-helmet-async": path.resolve(__dirname, "node_modules/react-helmet-async/lib/index.esm.js"),
    },
    // Ensure a single React instance (prevents "Invalid hook call").
    dedupe: [
      "react",
      "react-dom",
      "react-dom/client",
      "react/jsx-runtime",
      "react/jsx-dev-runtime",
    ],
  },
  optimizeDeps: {
    // These deps either ship complex mixed-module code or are sensitive to React dedupe.
    // Let Vite handle them without esbuild pre-bundling to avoid "Invalid hook call".
    exclude: [
      "lucide-react",
      "@geoblacklight/frontend",
      // These are resolved via our `geoblacklight` alias and can be sensitive to pre-bundling.
      "geoblacklight/controllers/leaflet_viewer_controller",
      "geoblacklight/controllers/openlayers_viewer_controller",
      "geoblacklight/controllers/oembed_viewer_controller",
      "geoblacklight/controllers/search_results_controller",
      "geoblacklight/controllers/downloads_controller",
      "geoblacklight/controllers/clipboard_controller",
    ],
    include: ["react-helmet-async"],
  },
  ssr: {
    noExternal: ["react-helmet-async"],
  },
});

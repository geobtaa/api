import { reactRouter } from '@react-router/dev/vite';
import { VitePWA } from 'vite-plugin-pwa';
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
    VitePWA({
      registerType: 'autoUpdate',
      devOptions: { enabled: true },
      // Use development mode to avoid terser/rollup plugin conflict during SW generation
      workbox: {
        mode: 'development',
      },
      manifest: {
        name: 'BTAA Geoportal',
        short_name: 'BTAA Geoportal',
        description: 'Geospatial discovery platform for Big Ten Academic Alliance libraries',
        start_url: '/',
        display: 'standalone',
        theme_color: '#003C5B',
        background_color: '#003C5B',
        icons: [
          { src: '/pwa-64x64.png', sizes: '64x64', type: 'image/png' },
          { src: '/pwa-192x192.png', sizes: '192x192', type: 'image/png' },
          { src: '/pwa-512x512.png', sizes: '512x512', type: 'image/png' },
        ],
      },
    }),
  ],
  server: {
    port: 3000,
    allowedHosts: ['btaa-geoportal.ngrok.io'],
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
      // Note: react-helmet-async is handled via optimizeDeps.include and ssr.noExternal
      // No need for a hardcoded alias - let Vite resolve it naturally
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
    include: ["react-helmet-async", "h3-js"],
  },
  ssr: {
    noExternal: ["react-helmet-async"],
  },
});

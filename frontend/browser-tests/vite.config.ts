import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const root = path.dirname(fileURLToPath(import.meta.url));
export default defineConfig({
  root,
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 4180,
    strictPort: true,
    fs: { allow: [path.resolve(root, '..')] },
  },
  preview: { host: '127.0.0.1', port: 4181, strictPort: true },
  build: { outDir: '../.viewer-browser-build', emptyOutDir: true },
  optimizeDeps: { exclude: ['ogm-viewer', 'ogm-viewer/lib'] },
  worker: { format: 'es' },
});

/// <reference types="vite/client" />
/// <reference types="vitest/globals" />

interface ImportMetaEnv {
  readonly VITE_CSRF_TOKEN: string;
  readonly VITE_ENFORCE_HTTPS: string;
  readonly VITE_USE_JSONP: string;
  readonly VITE_API_BASE_URL: string;
  readonly VITE_WMS_BASE_URL: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

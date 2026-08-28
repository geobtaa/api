/// <reference types="vite/client" />
/// <reference types="vitest/globals" />

interface ImportMetaEnv {
  readonly VITE_CSRF_TOKEN: string;
  readonly VITE_ENFORCE_HTTPS: string;
  readonly VITE_USE_JSONP: string;
  readonly VITE_API_BASE_URL: string;
  readonly VITE_WMS_BASE_URL: string;
  readonly VITE_TURNSTILE_ACTION: string;
  readonly VITE_TURNSTILE_ENABLED: string;
  readonly VITE_TURNSTILE_ENABLE_LOCAL: string;
  readonly VITE_TURNSTILE_SITE_KEY: string;
  readonly VITE_GTM_ID: string;
  readonly VITE_KAMAL_DEST: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

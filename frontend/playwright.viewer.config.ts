import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './browser-tests',
  timeout: 30000,
  expect: { timeout: 10000 },
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  use: {
    viewport: { width: 1280, height: 900 },
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    launchOptions: {
      args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'],
    },
  },
  projects: [
    { name: 'development', use: { baseURL: 'http://127.0.0.1:4180' } },
    { name: 'production', use: { baseURL: 'http://127.0.0.1:4181' } },
  ],
  webServer: [
    {
      command: 'npx vite --config browser-tests/vite.config.ts',
      url: 'http://127.0.0.1:4180',
      reuseExistingServer: false,
    },
    {
      command:
        'npx vite build --config browser-tests/vite.config.ts && npx vite preview --config browser-tests/vite.config.ts',
      url: 'http://127.0.0.1:4181',
      reuseExistingServer: false,
      timeout: 120000,
    },
  ],
});

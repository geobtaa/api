/// <reference types="vitest" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import a11yReporter from './vitest-a11y-reporter'

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'happy-dom',
    setupFiles: ['./src/setupTests.ts'],
    css: true,
    reporters: ['default', a11yReporter],
    coverage: {
      provider: 'v8', // Use v8 provider for Vitest 3.x
      reporter: ['text', 'json', 'html'],
      exclude: [
        'node_modules/',
        'src/setupTests.ts',
        '**/*.d.ts',
        '**/*.config.*',
        'dist/',
        'build/',
        'coverage/',
        '**/*.test.*',
        '**/*.spec.*',
        // React application scaffolding
        'src/App.tsx',
        'src/main.tsx',
        // Test infrastructure
        'src/__mocks__/**',
        // Type definitions
        'src/types/**',
        // Demo/test pages
        'src/pages/FixturesTestPage.tsx',
        // Configuration files
        '.eslintrc.js',
        'check-all-fixtures.js',
        // Server code
        'server/**',
      ],
      thresholds: {
        global: {
          branches: 80,
          functions: 80,
          lines: 80,
          statements: 80,
        },
      },
    },
  },
})

# Frontend Documentation

The frontend is the React/TypeScript public Geoportal interface for this
repository. It runs locally as the `frontend` Docker Compose service on host
port 5173, or directly with npm on port 3000 from `frontend/`.

## Available Documentation

Testing:

- [Testing Guide](testing.md) - test suite, coverage, accessibility checks, and
  test-writing patterns.
- [Testing Quick Reference](testing-quick-reference.md) - common testing
  commands and snippets.

Code quality:

- [Linting and Formatting](linting-and-formatting.md) - ESLint, Prettier, and
  local workflow.
- [Linting Quick Reference](linting-quick-reference.md) - short command and
  troubleshooting reference.

Features:

- [Homepage Map Visualization](homepage-map.md) - H3 hex map, featured carousel,
  preview layers, and Allmaps behavior.

Configuration:

- Deployed analytics and tag-manager configuration is restricted operations
  material. See [../analytics.md](../analytics.md) for the public stub.

## Project Overview

The frontend stack currently uses:

- React 19 and React DOM 19.
- React Router 7 for routing, loaders, SSR, build, and production serving.
- TypeScript, Vite 7, and React Router dev tooling.
- Vitest 3, Testing Library, `happy-dom`, axe, and pa11y for tests and
  accessibility checks.
- Material UI 7, Tailwind, Leaflet, GeoBlacklight frontend components, Allmaps,
  H3, Recharts, and Lucide icons.

## Unfiltered Search

The `/search` page browses the full catalog when no query or filters are present,
including URLs containing only presentation parameters such as
`/search?view=gallery&per_page=20`. Removing the last filter starts an unfiltered
search without requiring an explicit `q=` parameter. Results and facets load
through the browser search request; the map loads independently. The results
area shows a loading state until the current request settles, rather than
reporting zero results while the request is pending.

## Quick Commands

Run from `frontend/`:

```bash
# Development and production build checks
npm run dev
npm run build
npm run start

# Testing
npm test
npm run test:watch
npm run test:coverage
npm run test:a11y

# Code quality
npm run lint
npm run lint:fix
npm run format
npm run format:check
```

Run from the repository root after frontend dependency or Vite config changes:

```bash
make frontend-reset
```

Then hard-refresh the browser or use a private/incognito window to avoid stale
chunk URLs.

## Maintenance Checklist

- Update this file when `frontend/package.json` scripts or major dependencies
  change.
- Update testing docs when Vitest, Testing Library, axe, pa11y, or test setup
  changes.
- Update feature docs when homepage map, featured resource, preview-layer, or
  Allmaps behavior changes.
- Run `npm run lint`, `npm run format:check`, and `npm test` before merging
  frontend behavior changes.

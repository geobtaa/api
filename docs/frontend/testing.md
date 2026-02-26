# Testing Documentation

This document provides comprehensive information about the test suite and coverage for the RUI (Research University Interface) project.

## Overview

The project uses **Vitest** as the testing framework, which provides fast unit testing with built-in TypeScript support and excellent developer experience. We've migrated from Jest to Vitest for better performance and Vite integration.

## Test Framework

- **Testing Framework**: Vitest v3.2.4
- **Test Environment**: happy-dom (lightweight DOM implementation)
- **Assertion Library**: @testing-library/jest-dom
- **User Interaction**: @testing-library/user-event
- **Coverage Provider**: @vitest/coverage-v8

## Available Test Commands

### Basic Testing

```bash
# Run all tests once
npm test

# Run tests in watch mode (re-runs on file changes)
npm run test:watch

# Run tests with UI interface
npm run test:ui
```

### Coverage Testing

```bash
# Run tests with coverage report
npm run test:coverage

# Run tests with coverage and UI interface
npm run test:coverage:ui
```

## Test Structure

### Test Files Location
```
src/
├── __tests__/
│   ├── components/
│   │   └── LinksTable.test.tsx
│   └── pages/
│       ├── Home.test.tsx
│       ├── ResourceView.test.tsx
│       └── SearchResults.test.tsx
├── pages/
│   └── FixturesTestPage.tsx  # Test fixtures utility page
└── setupTests.ts
```

### Test Fixtures Page

The project includes a special testing utility page at `/test/fixtures` that provides:

- **Fixture Validation**: Checks the availability of test data records
- **Category Organization**: Groups fixtures by data type (Point Data, Polygon Data, Raster Data, etc.)
- **Status Monitoring**: Shows real-time availability status of each fixture
- **Development Testing**: Helps developers verify that test data is accessible

**Access the fixtures page**: Navigate to `http://localhost:5173/test/fixtures` in your browser.

**Fixture Categories Include**:
- Point Data
- Polygon Data  
- Raster Data
- Scanned Maps
- Esri Services
- Databases
- Index Maps
- Collections
- Websites
- Downloads
- Child/Parent Records
- Error Cases

This page is essential for:
- Verifying test data availability during development
- Debugging issues with specific data types
- Understanding what test fixtures are available
- Monitoring the health of test data endpoints

### Test File Naming Convention
- Test files should end with `.test.tsx` or `.test.ts`
- Place test files in the same directory as the component or in a `__tests__` directory
- Use descriptive test names that explain what is being tested

## Test Configuration

### Vitest Configuration (`vitest.config.ts`)
```typescript
export default defineConfig({
  test: {
    globals: true,           // Global test functions (describe, it, expect)
    environment: 'happy-dom', // DOM environment for React components
    setupFiles: ['./src/setupTests.ts'], // Global test setup
    css: true,               // Process CSS imports
    coverage: {
      provider: 'v8',        // Coverage provider
      reporter: ['text', 'json', 'html'], // Coverage report formats
      exclude: [             // Files to exclude from coverage
        'node_modules/',
        'src/setupTests.ts',
        '**/*.d.ts',
        '**/*.config.*',
        'dist/',
        'coverage/',
        '**/*.test.*',
        '**/*.spec.*',
      ],
      thresholds: {          // Coverage thresholds
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
```

### Test Setup (`src/setupTests.ts`)
The setup file includes:
- Jest DOM matchers for better assertions
- API function mocks to prevent network calls during testing
- Mock data for consistent test results

## Writing Tests

### Basic Test Structure
```typescript
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { ComponentName } from '../ComponentName';
import { ApiProvider } from '../../context/ApiContext';
import { DebugProvider } from '../../context/DebugContext';

describe('ComponentName', () => {
  const renderComponent = () => {
    render(
      <BrowserRouter>
        <ApiProvider>
          <DebugProvider>
            <ComponentName />
          </DebugProvider>
        </ApiProvider>
      </BrowserRouter>
    );
  };

  it('renders correctly', () => {
    renderComponent();
    expect(screen.getByText('Expected Text')).toBeInTheDocument();
  });
});
```

### Required Providers
Most components need to be wrapped with these providers:
- `BrowserRouter` - For React Router functionality
- `ApiProvider` - For API context
- `DebugProvider` - For debug context (used by Footer and other components)

### Common Testing Patterns

#### Testing User Interactions
```typescript
it('handles user input', async () => {
  renderComponent();
  const input = screen.getByPlaceholderText(/search/i);
  await userEvent.type(input, 'test query');
  expect(input).toHaveValue('test query');
});
```

#### Testing Async Operations
```typescript
it('loads data asynchronously', async () => {
  renderComponent();
  await waitFor(() => {
    expect(screen.getByText('Loaded Data')).toBeInTheDocument();
  });
});
```

#### Testing Component State
```typescript
it('shows loading state', () => {
  renderComponent();
  expect(screen.getByText(/loading/i)).toBeInTheDocument();
});
```

## Accessibility Testing

The project uses **axe-core** and **vitest-axe** to run automated accessibility checks in unit tests. The goal is to maintain **WCAG 2.2 AA** compliance for key features (H3 hex grid, Featured carousel, SearchResults, Pagination, FacetList, LinksTable).

### Running accessibility tests

Accessibility tests run as part of the normal Vitest suite:

```bash
npm test
```

To run only axe-focused a11y tests:

```bash
npm run test:a11y
```

Tests that use axe (vitest-axe) include:

- `src/__tests__/components/map/H3HexDataTable.test.tsx` — H3 hex data table (region, caption, headers, links)
- `src/__tests__/components/home/HomePageHexMapBackground.carousel-a11y.test.tsx` — Featured carousel (region, roledescription, controls)
- `src/__tests__/components/SearchResults.test.tsx` — Search results (with data and empty state)
- `src/__tests__/components/Pagination.test.tsx` — Pagination controls
- `src/__tests__/components/LinksTable.test.tsx` — Links table
- `src/__tests__/components/FacetList.test.tsx` — Facet list filters

### Using vitest-axe in a test

1. Extend Vitest matchers in `src/setupTests.ts` (already done):

   ```typescript
   import * as matchers from 'vitest-axe/matchers';
   import { expect } from 'vitest';
   expect.extend(matchers);
   ```

2. Use the shared `axeWithWCAG22` helper (targets WCAG 2.0, 2.1, and 2.2 Level A and AA):

   ```typescript
   import { axeWithWCAG22 } from '../../test-utils/axe';

   it('has no accessibility violations', async () => {
     const { container } = render(<MyComponent />);
     const results = await axeWithWCAG22(container);
     expect(results).toHaveNoViolations();
   });
   ```

   The helper lives in `src/test-utils/axe.ts` and configures axe to run WCAG 2.2 rules.

3. To restrict checks to a region (e.g. carousel only), pass that element:

   ```typescript
   const carousel = screen.getByRole('region', { name: /Featured resources/i });
   const results = await axeWithWCAG22(carousel);
   expect(results).toHaveNoViolations();
   ```

### Full-page Pa11y scans

Run axe against built pages with Pa11y CI. First build and start the preview server:

```bash
npm run build && npm run preview
```

In another terminal, run:

```bash
npm run test:a11y:pa11y
```

Or use the combined script (builds, starts server, runs pa11y, then stops):

```bash
npm run test:a11y:pa11y:ci
```

To run Pa11y on a single resource page in local dev:

```bash
npm run test:a11y:pa11y:item
```

Pa11y CI tests `/`, `/search`, and `/resources/p16022coll583:2574` by default (preview server on port `4173`). Configure URLs and options in `frontend/.pa11yci.json`. The config uses system Chrome on macOS (`/Applications/Google Chrome.app`). On Linux or if Chrome is elsewhere, set `PUPPETEER_EXECUTABLE_PATH` to your Chrome binary path, or run `npx puppeteer browsers install chrome` and remove the `executablePath` from the config.

The config includes narrow `hideElements` selectors for known false-positive contrast findings (header lockup text, timeline chart tick labels, full-details metadata panel, and Leaflet map card) so we can keep `color-contrast` enabled for the rest of each page. The resource page also ignores `frame-tested` for the sandboxed Mirador iframe.

### Common axe violations and fixes

| Violation | Typical fix |
|-----------|-------------|
| Missing form label | Add `aria-label` or associate a `<label>` with the control (or `aria-labelledby`). |
| Image missing alt | Use `alt="..."` for meaningful images; use `alt=""` for decorative images. |
| Color contrast | Increase contrast ratio (e.g. text/background) to meet WCAG AA (4.5:1 for normal text). |
| Missing button/link name | Add `aria-label` or visible text so the control has an accessible name. |
| Region/landmark without name | Add `aria-label` or `aria-labelledby` to regions (e.g. carousel, table wrapper). |
| Progress bar not exposed | Use `role="progressbar"` with `aria-valuenow`, `aria-valuemin`, `aria-valuemax`, and `aria-label`. |

### Manual accessibility checklist

Use this checklist for manual verification (keyboard, screen reader, zoom). Reference: [WCAG 2.2 AA](https://www.w3.org/WAI/WCAG22/quickref/?levels=aaa&currentsidebar=%23col_customize).

**Keyboard (WCAG 2.1.1 Keyboard, 2.1.2 No Keyboard Trap)**

- Tab through the homepage: search, map area, “View hex data as table” details, carousel (Home, Play/Pause, thumbnails, Previous, Next). Confirm all controls are reachable and focus order is logical.
- With focus in the carousel: Arrow Left / Arrow Right move to previous/next item; Home / End jump to first/last. Confirm no keyboard trap (Tab and Shift+Tab leave the carousel).

**Screen reader**

- Navigate the Featured carousel with NVDA (Windows) or VoiceOver (macOS). Confirm the region is announced (“Featured resources”), the description is available, and the active slide change is announced (live region).
- Open “View hex data as table” on the homepage and search page. Confirm the table is announced (caption, column headers, “Search this hex” links).

**Zoom (WCAG 1.4.4 Resize Text)**

- Set browser zoom to 200%. Confirm layout and controls (search, carousel, hex table) remain usable and no content is clipped or overlapping in a way that blocks use.

## Coverage Reports

### Understanding Coverage Metrics

When you run `npm run test:coverage`, you'll see output like this:

```
 % Coverage report from v8
-------------------|---------|----------|---------|---------|-------------------
File               | % Stmts | % Branch | % Funcs | % Lines | Uncovered Line #s
-------------------|---------|---------|---------|---------|-------------------
All files          |   85.2  |   78.9  |   82.1  |   84.7  |
 src/App.tsx       |   100   |   100   |   100   |   100   |
 src/components/   |   82.1  |   75.0  |   80.0  |   81.5  | 45,67,89
-------------------|---------|---------|---------|---------|-------------------
```

**Metrics Explained:**
- **Statements**: Percentage of code statements executed
- **Branches**: Percentage of conditional branches taken
- **Functions**: Percentage of functions called
- **Lines**: Percentage of lines executed

### Coverage Thresholds
The project has minimum coverage thresholds:
- **Branches**: 80%
- **Functions**: 80%
- **Lines**: 80%
- **Statements**: 80%

If coverage falls below these thresholds, the test run will fail.

### Coverage Reports

#### Terminal Report
The coverage command displays a summary in the terminal with:
- Overall coverage percentages
- Per-file coverage breakdown
- Uncovered line numbers

#### HTML Report
A detailed HTML report is generated in the `coverage/` directory:
- Open `coverage/index.html` in your browser
- Interactive coverage visualization
- Click on files to see line-by-line coverage
- Red lines indicate uncovered code

#### JSON Report
A machine-readable JSON report is saved as `coverage/coverage-final.json` for CI/CD integration.

#### Accessibility (AXE) Report

When you run tests (including `npm run test:coverage`), a custom reporter generates accessibility test results alongside the coverage report:

- **`coverage/a11y-report.json`** — Machine-readable summary of all accessibility-related tests (axe and manual a11y checks)
- **`coverage/a11y-report.html`** — Human-readable HTML report with pass/fail status for each a11y test

Open `coverage/a11y-report.html` in a browser to view the accessibility test summary. The report includes all tests whose name or file path mentions "accessibility", "a11y", "violations", or "axe".

## Test Data and Fixtures

### Using Test Fixtures

The project includes a comprehensive set of test fixtures (sample data records) that represent different types of geospatial data. These fixtures are essential for testing various data scenarios.

**Available Fixture Types:**
- **Point Data**: Individual point locations with WMS/WFS services
- **Polygon Data**: Area-based datasets with various service types
- **Raster Data**: Image-based geospatial data
- **Scanned Maps**: Historical maps with IIIF support
- **Esri Services**: ArcGIS-based map services
- **Databases**: SQLite and Geodatabase files
- **Index Maps**: GeoJSON index maps for data discovery
- **Collections**: Collection-level metadata records
- **Websites**: Web-based resources
- **Downloads**: Files with direct download links
- **Child/Parent Records**: Hierarchical data relationships
- **Error Cases**: Records that test error handling

**Accessing Fixtures:**
- **Fixtures Page**: Visit `/test/fixtures` to see all available fixtures and their status
- **Fixture IDs**: Use fixture IDs in tests (e.g., `'mit-001145244'`, `'nyu-2451-34564'`)
- **API Endpoints**: Fixtures are accessible via `/resources/{fixture-id}` endpoints

**Using Fixtures in Tests:**
```typescript
// Test with a specific fixture
const fixtureId = 'mit-001145244'; // actual-papermap1
render(<ResourceView />);
// Mock the API to return fixture data
```

## Mocking

### API Mocks
The test setup includes comprehensive API mocks in `src/setupTests.ts`:

```typescript
vi.mock('./services/api', () => ({
  fetchSearchResults: vi.fn().mockResolvedValue({
    data: [],
    meta: { total: 0, page: 1, per_page: 10 },
    included: []
  }),
  fetchResourceDetails: vi.fn().mockResolvedValue({
    // Mock resource data
  }),
  // ... other API functions
}));
```

### Router Mocks
For components that use React Router hooks:

```typescript
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    useParams: () => ({ id: 'test-id' }),
  };
});
```

## Best Practices

### 1. Test Organization
- Group related tests using `describe` blocks
- Use descriptive test names that explain the expected behavior
- Keep tests focused on a single behavior

### 2. Test Data
- Use consistent mock data across tests
- Keep test data simple and focused
- Avoid testing implementation details

### 3. Assertions
- Use semantic queries (`getByRole`, `getByLabelText`) over generic ones
- Test user-visible behavior, not internal state
- Use `waitFor` for async operations

### 4. Coverage
- Aim for high coverage but focus on meaningful tests
- Don't test trivial getters/setters
- Test error conditions and edge cases

### 5. Performance
- Use `happy-dom` for faster test execution
- Mock external dependencies
- Keep tests isolated and independent

## Troubleshooting

### Common Issues

#### "useDebug must be used within a DebugProvider"
**Solution**: Wrap your test component with `DebugProvider`:
```typescript
<DebugProvider>
  <YourComponent />
</DebugProvider>
```

#### "jest is not defined"
**Solution**: Use `vi` instead of `jest` for Vitest:
```typescript
import { vi } from 'vitest';
vi.mock('module-name');
```

#### Tests timing out
**Solution**: Use `waitFor` for async operations:
```typescript
await waitFor(() => {
  expect(screen.getByText('Expected Text')).toBeInTheDocument();
});
```

#### Coverage not working
**Solution**: Ensure the coverage provider is installed:
```bash
npm install --save-dev @vitest/coverage-v8
```

## Continuous Integration

### GitHub Actions Example
```yaml
- name: Run tests with coverage
  run: npm run test:coverage

- name: Upload coverage to Codecov
  uses: codecov/codecov-action@v3
  with:
    file: ./coverage/coverage-final.json
```

## Resources

- [Vitest Documentation](https://vitest.dev/)
- [Testing Library Documentation](https://testing-library.com/)
- [React Testing Best Practices](https://kentcdodds.com/blog/common-mistakes-with-react-testing-library)
- [Coverage Best Practices](https://github.com/gotwarlost/istanbul/blob/master/ignoring-code-for-coverage.md)

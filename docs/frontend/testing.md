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

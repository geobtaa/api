# Testing Quick Reference

## Commands

```bash
# Run all tests
npm test

# Run tests in watch mode
npm run test:watch

# Run tests with coverage
npm run test:coverage

# Run tests with UI
npm run test:ui

# Run tests with coverage and UI
npm run test:coverage:ui
```

## Test Fixtures Page

Access the test fixtures utility at: `http://localhost:5173/test/fixtures`

**What it does:**
- Validates availability of test data records
- Shows real-time status of fixtures
- Organizes fixtures by data type
- Helps debug data-related issues

**Use cases:**
- Verify test data is accessible
- Debug specific data type issues
- Monitor test data health
- Understand available test fixtures

## Test File Template

```typescript
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { vi } from 'vitest';
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

  it('handles user interaction', async () => {
    renderComponent();
    const button = screen.getByRole('button', { name: /click me/i });
    await userEvent.click(button);
    expect(screen.getByText('Clicked!')).toBeInTheDocument();
  });
});
```

## Common Queries

```typescript
// By role (preferred)
screen.getByRole('button', { name: /submit/i })
screen.getByRole('textbox', { name: /email/i })
screen.getByRole('heading', { name: /welcome/i })

// By text
screen.getByText('Hello World')
screen.getByText(/hello world/i) // case insensitive

// By placeholder
screen.getByPlaceholderText(/enter your name/i)

// By label
screen.getByLabelText(/email address/i)

// By test id (last resort)
screen.getByTestId('submit-button')
```

## Common Assertions

```typescript
// Element exists
expect(element).toBeInTheDocument()

// Element has text
expect(element).toHaveTextContent('Hello')

// Element has value
expect(input).toHaveValue('test@example.com')

// Element is visible/hidden
expect(element).toBeVisible()
expect(element).not.toBeVisible()

// Element is enabled/disabled
expect(button).toBeEnabled()
expect(button).toBeDisabled()

// Element has class
expect(element).toHaveClass('active')
```

## Async Testing

```typescript
// Wait for element to appear
await waitFor(() => {
  expect(screen.getByText('Loaded!')).toBeInTheDocument();
});

// Wait for element to disappear
await waitFor(() => {
  expect(screen.queryByText('Loading...')).not.toBeInTheDocument();
});

// Wait for multiple elements
await waitFor(() => {
  expect(screen.getByText('Title')).toBeInTheDocument();
  expect(screen.getByText('Description')).toBeInTheDocument();
});
```

## User Interactions

```typescript
// Type in input
await userEvent.type(input, 'Hello World');

// Click button
await userEvent.click(button);

// Select option
await userEvent.selectOptions(select, 'option-value');

// Check checkbox
await userEvent.click(checkbox);

// Focus element
await userEvent.tab(); // or userEvent.click(input)
```

## Mocking

```typescript
// Mock module
vi.mock('./api', () => ({
  fetchData: vi.fn().mockResolvedValue({ data: 'test' })
}));

// Mock function
const mockFn = vi.fn();
mockFn.mockReturnValue('mocked value');
mockFn.mockResolvedValue({ data: 'async data' });

// Mock router params
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    useParams: () => ({ id: '123' }),
  };
});
```

## Coverage Thresholds

- **Statements**: 80%
- **Branches**: 80%
- **Functions**: 80%
- **Lines**: 80%

## Coverage Reports

- **Terminal**: Summary with percentages
- **HTML**: `coverage/index.html` - Interactive report
- **JSON**: `coverage/coverage-final.json` - Machine readable

## Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| `useDebug must be used within a DebugProvider` | Wrap component with `<DebugProvider>` |
| `jest is not defined` | Use `vi` instead of `jest` |
| Tests timing out | Use `waitFor()` for async operations |
| Coverage not working | Install `@vitest/coverage-v8` |
| Router errors | Wrap with `<BrowserRouter>` |
| API calls failing | Check mocks in `setupTests.ts` |

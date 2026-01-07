# Linting and Formatting Documentation

This document provides comprehensive information about the linting and formatting tools used in the RUI project to maintain code quality and consistency.

## Overview

The project uses **ESLint** for code linting and **Prettier** for code formatting. These tools work together to ensure consistent code style, catch potential bugs, and enforce best practices across the codebase.

## Tools

### ESLint
- **Purpose**: Static code analysis and linting
- **Configuration**: `eslint.config.js` (flat config format)
- **Focus**: Code quality, TypeScript rules, React best practices

### Prettier
- **Purpose**: Code formatting and style consistency
- **Configuration**: Default settings with custom file patterns
- **Focus**: Consistent code formatting across all file types

## Available Commands

### ESLint Commands

```bash
# Check for linting errors and warnings
npm run lint

# Fix auto-fixable linting errors
npm run lint:fix
```

### Prettier Commands

```bash
# Format all code files
npm run format

# Check if code is properly formatted (without changing files)
npm run format:check
```

### Combined Workflow

```bash
# Complete code cleanup workflow
npm run lint:fix    # Fix linting issues
npm run format      # Format code
npm test            # Run tests to ensure nothing broke
```

## ESLint Configuration

### Configuration File: `eslint.config.js`

```javascript
import js from '@eslint/js';
import globals from 'globals';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  { ignores: ['dist'] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      'react-refresh/only-export-components': [
        'warn',
        { allowConstantExport: true },
      ],
    },
  }
);
```

### ESLint Plugins

The project includes several ESLint plugins for comprehensive code analysis:

#### Core Plugins
- **`@typescript-eslint/eslint-plugin`** - TypeScript-specific rules
- **`@typescript-eslint/parser`** - TypeScript parser for ESLint
- **`eslint-plugin-react`** - React-specific linting rules
- **`eslint-plugin-react-hooks`** - React hooks best practices
- **`eslint-plugin-react-refresh`** - Fast refresh compatibility

#### Additional Plugins
- **`eslint-plugin-jsx-a11y`** - Accessibility rules for JSX
- **`eslint-plugin-import`** - Import/export statement rules
- **`eslint-plugin-unused-imports`** - Detect and remove unused imports
- **`eslint-plugin-prettier`** - Integrate Prettier with ESLint

### Key ESLint Rules

#### TypeScript Rules
- **`@typescript-eslint/no-explicit-any`** - Prevents use of `any` type
- **`@typescript-eslint/no-unused-vars`** - Detects unused variables
- **`@typescript-eslint/explicit-function-return-type`** - Requires explicit return types

#### React Rules
- **`react-hooks/rules-of-hooks`** - Enforces React hooks rules
- **`react-hooks/exhaustive-deps`** - Ensures complete dependency arrays
- **`react-refresh/only-export-components`** - Fast refresh compatibility

#### Import Rules
- **`import/no-unused-modules`** - Detects unused modules
- **`import/order`** - Enforces import order

## Prettier Configuration

### Supported File Types
- **TypeScript**: `.ts`, `.tsx`
- **CSS**: `.css`
- **Markdown**: `.md`
- **JSON**: `.json`

### Default Settings
Prettier uses sensible defaults for:
- **Indentation**: 2 spaces
- **Quotes**: Single quotes for strings
- **Semicolons**: Always add semicolons
- **Trailing Commas**: Add where valid in ES5
- **Print Width**: 80 characters
- **Tab Width**: 2 spaces

## Common Linting Issues and Solutions

### TypeScript Issues

#### `@typescript-eslint/no-explicit-any`
**Problem**: Using `any` type
```typescript
// ❌ Bad
const data: any = fetchData();

// ✅ Good
const data: ApiResponse = fetchData();
```

#### `@typescript-eslint/no-unused-vars`
**Problem**: Unused variables or imports
```typescript
// ❌ Bad
import { useState, useEffect } from 'react';
const unusedVar = 'hello';

// ✅ Good
import { useState } from 'react';
// Remove unused imports and variables
```

### React Issues

#### `react-hooks/exhaustive-deps`
**Problem**: Missing dependencies in useEffect
```typescript
// ❌ Bad
useEffect(() => {
  fetchData(userId);
}, []); // Missing userId dependency

// ✅ Good
useEffect(() => {
  fetchData(userId);
}, [userId]); // Include all dependencies
```

#### `react-refresh/only-export-components`
**Problem**: Mixing component exports with other exports
```typescript
// ❌ Bad
export const MyComponent = () => <div>Hello</div>;
export const CONSTANT = 'value';

// ✅ Good
export const MyComponent = () => <div>Hello</div>;
// Move constants to separate file
```

### Import Issues

#### Unused Imports
**Problem**: Importing modules that aren't used
```typescript
// ❌ Bad
import { useState, useEffect } from 'react';
// Only using useState

// ✅ Good
import { useState } from 'react';
```

## IDE Integration

### VS Code Setup

#### Recommended Extensions
- **ESLint** - ESLint integration
- **Prettier - Code formatter** - Prettier integration
- **TypeScript Importer** - Auto-import TypeScript modules

#### VS Code Settings
Add to your `settings.json`:

```json
{
  "editor.formatOnSave": true,
  "editor.defaultFormatter": "esbenp.prettier-vscode",
  "editor.codeActionsOnSave": {
    "source.fixAll.eslint": true,
    "source.organizeImports": true
  },
  "eslint.validate": [
    "javascript",
    "javascriptreact",
    "typescript",
    "typescriptreact"
  ]
}
```

### Other IDEs
- **WebStorm**: Built-in ESLint and Prettier support
- **Sublime Text**: Install ESLint and Prettier packages
- **Vim/Neovim**: Use ALE or similar plugins

## Pre-commit Hooks

### Recommended Setup
Use tools like `husky` and `lint-staged` to run linting before commits:

```bash
npm install --save-dev husky lint-staged
```

Add to `package.json`:
```json
{
  "lint-staged": {
    "src/**/*.{ts,tsx}": [
      "eslint --fix",
      "prettier --write"
    ]
  },
  "husky": {
    "hooks": {
      "pre-commit": "lint-staged"
    }
  }
}
```

## CI/CD Integration

### GitHub Actions Example
```yaml
name: Lint and Format Check

on: [push, pull_request]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '18'
      - run: npm ci
      - run: npm run lint
      - run: npm run format:check
```

## Best Practices

### 1. Regular Maintenance
- Run `npm run lint` before committing
- Fix linting issues immediately
- Use `npm run lint:fix` for auto-fixable issues

### 2. Code Quality
- Avoid `any` types - use proper TypeScript types
- Remove unused imports and variables
- Follow React hooks rules
- Use meaningful variable names

### 3. Formatting
- Let Prettier handle all formatting
- Don't manually format code
- Use `npm run format` before committing

### 4. Team Workflow
- Agree on linting rules as a team
- Use pre-commit hooks
- Include linting in CI/CD pipeline
- Document any custom rules

## Troubleshooting

### Common Issues

#### ESLint Not Working
**Solution**: Check if ESLint is properly installed and configured
```bash
npm install --save-dev eslint @typescript-eslint/eslint-plugin
```

#### Prettier Conflicts with ESLint
**Solution**: Install `eslint-config-prettier` to disable conflicting rules
```bash
npm install --save-dev eslint-config-prettier
```

#### TypeScript Errors in ESLint
**Solution**: Ensure TypeScript parser is configured
```javascript
// In eslint.config.js
import tseslint from 'typescript-eslint';
```

#### Formatting Not Applied
**Solution**: Check Prettier configuration and file patterns
```bash
npm run format:check  # Check what needs formatting
npm run format        # Apply formatting
```

### Performance Issues

#### Slow Linting
**Solutions**:
- Use `.eslintignore` to exclude unnecessary files
- Configure ESLint to only lint changed files
- Use `--cache` flag for faster subsequent runs

#### Large File Issues
**Solutions**:
- Break large files into smaller components
- Use ESLint disable comments for specific lines
- Consider file size limits

## Resources

- [ESLint Documentation](https://eslint.org/)
- [Prettier Documentation](https://prettier.io/)
- [TypeScript ESLint](https://typescript-eslint.io/)
- [React ESLint Plugin](https://github.com/jsx-eslint/eslint-plugin-react)
- [VS Code ESLint Extension](https://marketplace.visualstudio.com/items?itemName=dbaeumer.vscode-eslint)
- [VS Code Prettier Extension](https://marketplace.visualstudio.com/items?itemName=esbenp.prettier-vscode)

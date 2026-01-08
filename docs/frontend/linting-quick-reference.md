# Linting and Formatting Quick Reference

## Commands

```bash
# ESLint
npm run lint          # Check for linting errors
npm run lint:fix      # Fix auto-fixable errors

# Prettier
npm run format        # Format all code files
npm run format:check  # Check formatting without changing files

# Complete workflow
npm run lint:fix && npm run format && npm test
```

## Common Issues & Quick Fixes

### TypeScript Issues

| Issue | Quick Fix |
|-------|-----------|
| `@typescript-eslint/no-explicit-any` | Replace `any` with proper type |
| `@typescript-eslint/no-unused-vars` | Remove unused variables/imports |
| Missing return type | Add explicit return type annotation |

### React Issues

| Issue | Quick Fix |
|-------|-----------|
| `react-hooks/exhaustive-deps` | Add missing dependencies to useEffect |
| `react-refresh/only-export-components` | Move non-component exports to separate file |
| Missing key prop | Add `key` prop to list items |

### Import Issues

| Issue | Quick Fix |
|-------|-----------|
| Unused imports | Remove unused import statements |
| Import order | Use IDE auto-organize imports |
| Missing imports | Add missing import statements |

## VS Code Integration

### Settings
```json
{
  "editor.formatOnSave": true,
  "editor.defaultFormatter": "esbenp.prettier-vscode",
  "editor.codeActionsOnSave": {
    "source.fixAll.eslint": true,
    "source.organizeImports": true
  }
}
```

### Extensions
- **ESLint** - ESLint integration
- **Prettier** - Code formatter
- **TypeScript Importer** - Auto-import modules

## File Patterns

### ESLint
- `src/**/*.{ts,tsx}` - TypeScript and TSX files
- Ignores: `dist/`, `node_modules/`, `coverage/`

### Prettier
- `src/**/*.{ts,tsx,css,md,json}` - All source files
- Ignores: `dist/`, `node_modules/`, `coverage/`

## Quick Fixes

### Auto-fixable ESLint Rules
- Unused imports
- Missing semicolons
- Quote consistency
- Import order
- Unused variables

### Prettier Formatting
- Indentation (2 spaces)
- Line breaks
- Quote style (single quotes)
- Semicolons
- Trailing commas

## Pre-commit Workflow

```bash
# Before committing
npm run lint:fix    # Fix linting issues
npm run format      # Format code
npm test            # Run tests
git add .
git commit -m "Your commit message"
```

## CI/CD Commands

```bash
# In CI pipeline
npm run lint         # Check for errors
npm run format:check # Verify formatting
npm test            # Run tests
```

## Common Patterns

### TypeScript Types
```typescript
// ❌ Avoid
const data: any = fetchData();

// ✅ Use proper types
interface ApiResponse {
  data: unknown;
  status: number;
}
const data: ApiResponse = fetchData();
```

### React Hooks
```typescript
// ❌ Missing dependencies
useEffect(() => {
  fetchData(userId);
}, []);

// ✅ Complete dependencies
useEffect(() => {
  fetchData(userId);
}, [userId]);
```

### Imports
```typescript
// ❌ Unused imports
import { useState, useEffect } from 'react';
// Only using useState

// ✅ Clean imports
import { useState } from 'react';
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| ESLint not working | Check `eslint.config.js` exists |
| Prettier conflicts | Install `eslint-config-prettier` |
| TypeScript errors | Ensure TypeScript parser is configured |
| Formatting not applied | Check file patterns in package.json |
| Slow linting | Use `.eslintignore` for large files |

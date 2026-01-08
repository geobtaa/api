# RUI Documentation

This directory contains documentation for the Research University Interface (RUI) project.

## Available Documentation

### Testing
- **[Testing Guide](testing.md)** - Comprehensive guide to the test suite, coverage, and best practices
- **[Testing Quick Reference](testing-quick-reference.md)** - Quick reference for common testing patterns and commands

### Code Quality
- **[Linting and Formatting](linting-and-formatting.md)** - Guide to ESLint, Prettier, and code quality tools
- **[Linting Quick Reference](linting-quick-reference.md)** - Quick reference for linting commands and common issues

### Images
- **rui.png** - Project logo/icon

## Getting Started

### For Developers
1. Read the [Testing Guide](testing.md) to understand the test suite
2. Use the [Testing Quick Reference](testing-quick-reference.md) for day-to-day testing tasks
3. Run `npm run test:coverage` to see current test coverage

### For Contributors
1. Ensure all tests pass: `npm test`
2. Maintain coverage above 80%: `npm run test:coverage`
3. Follow testing best practices outlined in the documentation

## Project Overview

The RUI project is a React-based interface for research data discovery and visualization. It uses:

- **Frontend**: React + TypeScript + Vite
- **Testing**: Vitest + Testing Library
- **Styling**: Tailwind CSS
- **Maps**: Leaflet
- **State Management**: React Context

## Quick Commands

```bash
# Development
npm run dev          # Start development server
npm run build        # Build for production

# Testing
npm test             # Run tests
npm run test:watch   # Run tests in watch mode
npm run test:coverage # Run tests with coverage

# Code Quality
npm run lint         # Run ESLint
npm run lint:fix     # Fix ESLint issues
npm run format       # Format code with Prettier
npm run format:check # Check code formatting
```

## Contributing

When contributing to this project:

1. **Write Tests**: Add tests for new features and bug fixes
2. **Maintain Coverage**: Keep test coverage above 80%
3. **Follow Patterns**: Use the established testing patterns and component structure
4. **Document Changes**: Update documentation when adding new features

## Support

For questions about testing or development:

1. Check the [Testing Guide](testing.md) for detailed information
2. Use the [Testing Quick Reference](testing-quick-reference.md) for common patterns
3. Review existing test files for examples
4. Check the main project README for general setup instructions

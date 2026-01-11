# Frontend Scripts

## Update React Router Imports

Migration scripts for updating imports from `react-router-dom` to `react-router` for React Router v7.

### Interactive Script (Recommended)

Shows a preview of all changes before applying them:

```bash
npm run update-imports
# or
node scripts/update-react-router-imports.js
```

This script will:
1. Scan all `.ts`, `.tsx`, `.js`, `.jsx` files in `src/` and `app/` directories
2. Show a preview of all files that will be changed
3. Ask for confirmation before making changes
4. Update all imports from `react-router-dom` to `react-router`

### Simple Script (Direct Update)

Directly updates files without confirmation:

```bash
./scripts/update-react-router-imports-simple.sh
```

**Warning:** This script directly modifies files without asking for confirmation. Make sure you have committed your changes or have a backup.

### What Gets Updated

The scripts update these import patterns:
- `import { ... } from 'react-router-dom'` → `import { ... } from 'react-router'`
- `import type { ... } from 'react-router-dom'` → `import type { ... } from 'react-router'`
- `import 'react-router-dom'` → `import 'react-router'`
- Both single and double quotes are handled

### Files Scanned

The scripts scan these directories:
- `src/` - Source files
- `app/` - React Router v7 app directory

Excluded directories:
- `node_modules/`
- `dist/`
- `build/`
- `coverage/`
- Any hidden directories (starting with `.`)

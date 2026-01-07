# React Router v7 Migration Guide

This document provides detailed information about migrating from React Router v6 to React Router v7 with Server-Side Rendering (SSR) in this project.

## Overview

The application has been migrated from:
- **React Router v6** (client-side only SPA)
- **FastAPI serving static files** from `frontend/dist`
- **NGINX BFF proxy** for API key injection

To:
- **React Router v7** (SSR with server-side rendering)
- **React Router v7 running in Docker** container
- **Server-side API calls** with API key hidden in environment variables

## Why React Router v7?

1. **Direct upgrade path**: Minimal code changes needed from React Router v6
2. **Built-in SSR**: Server-side rendering support (formerly Remix, now merged into React Router)
3. **Web standards**: Uses Fetch API - simpler than Next.js abstractions
4. **Progressive enhancement**: Forms work without JavaScript
5. **Security**: API keys never exposed to client - all API calls happen server-side
6. **Performance**: Server-side rendering improves SEO and initial page load

## Key Differences from React Router v6

### Package Changes

**Before (v6):**
```json
{
  "dependencies": {
    "react-router-dom": "^6.22.3"
  }
}
```

**After (v7):**
```json
{
  "dependencies": {
    "react-router": "^7.11.0",
    "@react-router/node": "^7.11.0",
    "@react-router/serve": "^7.11.0"
  },
  "devDependencies": {
    "@react-router/dev": "^7.11.0"
  }
}
```

### Import Changes

**Before (v6):**
```typescript
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
```

**After (v7):**
```typescript
import { Link, useNavigate, useSearchParams } from 'react-router';
```

**Note**: All imports now come from `react-router` instead of `react-router-dom`. The `react-router-dom` package is no longer needed in v7.

### New Architecture

#### File-Based Routing

React Router v7 uses file-based routing similar to Next.js or Remix. Routes are defined by creating files in the `app/routes/` directory:

```
frontend/app/
├── root.tsx              # Root layout component
├── entry.client.tsx      # Client-side entry point
├── entry.server.tsx      # Server-side entry point
├── routes/
│   ├── _index.tsx        # Home page (/)
│   ├── search.tsx        # Search page (/search)
│   ├── resources.$id.tsx # Resource detail (/resources/:id)
│   └── ...
└── lib/
    └── server-api.ts     # Server-side API utilities
```

#### Server-Side Data Loading

React Router v7 introduces **loaders** - functions that run on the server to fetch data before rendering:

```typescript
// app/routes/search.tsx
export async function loader({ request }: LoaderFunctionArgs) {
  const url = new URL(request.url);
  const searchParams = url.searchParams;
  
  // Fetch data server-side with API key from environment
  const response = await serverFetch(`/search?${searchParams.toString()}`);
  const data = await response.json();
  
  return json({ searchResults: data });
}

export default function Search() {
  const { searchResults } = useLoaderData<typeof loader>();
  // Component receives pre-loaded data
  return <SearchPage />;
}
```

**Benefits:**
- API key is never exposed to client
- Faster initial page load (data fetched server-side)
- Better SEO (content available on first render)
- Progressive enhancement (works without JavaScript)

#### Server-Side API Utilities

All API calls that need the API key should use the `serverFetch` utility from `app/lib/server-api.ts`:

```typescript
import { serverFetch } from "~/lib/server-api";

// This runs ONLY on the server
export async function loader({ request }: LoaderFunctionArgs) {
  const response = await serverFetch("/search?q=test");
  // API key is automatically added from BTAA_GEOSPATIAL_API_KEY env var
  return json(await response.json());
}
```

## Migration Steps

### 1. Update Dependencies

```bash
cd frontend
npm install react-router@^7.11.0 @react-router/node@^7.11.0 @react-router/serve@^7.11.0
npm install -D @react-router/dev@^7.11.0
```

### 2. Update Imports

All imports from `react-router-dom` should be changed to `react-router`:

```bash
# Automated script is available:
npm run update-imports
```

Or manually update:
```typescript
// Before
import { Link } from 'react-router-dom';

// After
import { Link } from 'react-router';
```

### 3. Create Route Files

Convert React Router v6 route definitions to file-based routes:

**Before (v6):**
```typescript
// src/App.tsx
<Route path="/search" element={<SearchPage />} />
```

**After (v7):**
```typescript
// app/routes/search.tsx
export default function Search() {
  return <SearchPage />;
}
```

### 4. Add Server-Side Loaders

For routes that fetch data, add loader functions:

```typescript
// app/routes/search.tsx
export async function loader({ request }: LoaderFunctionArgs) {
  // Fetch data server-side
  const data = await serverFetch("/search");
  return json({ data });
}

export default function Search() {
  const { data } = useLoaderData<typeof loader>();
  return <SearchPage initialData={data} />;
}
```

### 5. Update Forms (Optional but Recommended)

React Router v7 provides a `Form` component with progressive enhancement:

**Before:**
```typescript
<form onSubmit={handleSubmit}>
  <input name="q" />
  <button type="submit">Search</button>
</form>
```

**After:**
```typescript
import { Form } from "react-router";

<Form method="get" action="/search">
  <input name="q" />
  <button type="submit">Search</button>
</Form>
```

**Benefits:**
- Works without JavaScript
- Automatic form validation
- Built-in loading states
- Better accessibility

## Component Compatibility

Most React Router v6 components and hooks work the same in v7:

### Compatible Hooks

- `useNavigate()` - Works the same
- `useSearchParams()` - Works the same
- `useLocation()` - Works the same
- `useParams()` - Works the same
- `useLoaderData()` - **New in v7** - Access data from loader functions

### Compatible Components

- `<Link>` - Works the same
- `<Navigate>` - Works the same
- `<Outlet>` - Works the same
- `<Form>` - **Enhanced in v7** - Progressive enhancement features

## Environment Variables

### Frontend Service (React Router v7)

```bash
# API base URL for server-side calls
API_BASE_URL=http://api:8000/api/v1

# API key (never exposed to client)
BTAA_GEOSPATIAL_API_KEY=your-api-key-here
```

### Client-Side Environment Variables (deprecated)

The following environment variables are no longer used for API calls:
- `VITE_API_BASE_URL` - Not needed (API calls are server-side)

## Development Workflow

### Local Development

1. Start all services:
   ```bash
   docker compose up -d
   ```

2. Access the application:
   - Frontend: http://localhost:3000
   - API: http://localhost:8000/docs

3. Frontend development:
   ```bash
   cd frontend
   npm run dev
   ```

### Building for Production

```bash
cd frontend
npm run build
```

The build output will be in `frontend/build/` with separate `client/` and `server/` directories.

### Running in Production

```bash
cd frontend
npm start
```

This starts the React Router v7 server on port 3000.

## Docker Configuration

The frontend now runs as a separate Docker service:

```yaml
frontend:
  build:
    context: ./frontend
    dockerfile: Dockerfile
  environment:
    - API_BASE_URL=http://api:8000/api/v1
    - BTAA_GEOSPATIAL_API_KEY=${BTAA_GEOSPATIAL_API_KEY:-}
  ports:
    - "127.0.0.1:3000:3000"
```

## Troubleshooting

### Import Errors

If you see errors about `react-router-dom`, make sure all imports have been updated:

```bash
npm run update-imports
```

### API Key Not Working

Ensure `BTAA_GEOSPATIAL_API_KEY` is set in your environment:
- `.env` file for local development
- Docker environment variables for containerized deployment

### Loader Not Running

Loaders only run on the server. Make sure:
1. The route file exports a `loader` function
2. The component uses `useLoaderData()` to access the data
3. You're accessing the route through the React Router v7 server (not direct file access)

### Build Errors

If you encounter build errors:
1. Clear `node_modules` and reinstall: `rm -rf node_modules package-lock.json && npm install`
2. Clear build directory: `rm -rf build`
3. Rebuild: `npm run build`

## Migration Checklist

- [x] Update package.json dependencies
- [x] Update all imports from `react-router-dom` to `react-router`
- [x] Create `app/` directory structure
- [x] Create route files in `app/routes/`
- [x] Add server-side loaders for data fetching
- [x] Create server-side API utilities
- [x] Update Vite configuration
- [x] Create Dockerfile for frontend
- [x] Update docker-compose.yml
- [x] Remove NGINX BFF proxy
- [x] Update FastAPI to stop serving static files
- [x] Update documentation

## Additional Resources

- [React Router v7 Documentation](https://reactrouter.com/)
- [React Router v7 Upgrade Guide](https://reactrouter.com/upgrading/v7)
- [Server-Side Rendering Guide](https://reactrouter.com/start/overview#server-side-rendering)

## Support

For questions or issues related to the migration, please refer to:
- React Router v7 documentation
- Project README.md
- Issue tracker

# React Router v7 Form Component Examples

This document shows how to use React Router v7's enhanced `Form` component for progressive enhancement and better user experience.

## Basic Form Example

React Router v7's `Form` component works like a regular HTML form but with enhanced features:

```typescript
import { Form } from "react-router";
import { useSearchParams } from "react-router";

export function SearchForm() {
  const [searchParams] = useSearchParams();
  const currentQuery = searchParams.get("q") || "";

  return (
    <Form method="get" action="/search">
      <input
        type="search"
        name="q"
        defaultValue={currentQuery}
        placeholder="Search..."
      />
      <button type="submit">Search</button>
    </Form>
  );
}
```

## Benefits of React Router v7 Form

1. **Progressive Enhancement**: Works without JavaScript
2. **Automatic Navigation**: Handles form submission and navigation automatically
3. **Built-in Loading States**: Can show loading indicators during submission
4. **Better Accessibility**: Proper form semantics and keyboard navigation

## Search Form with URL Parameters

For search forms that need to preserve existing URL parameters:

```typescript
import { Form, useSearchParams } from "react-router";

export function AdvancedSearchForm() {
  const [searchParams] = useSearchParams();

  // Preserve existing search params
  const preserveParams = (key: string) => {
    return searchParams.get(key) || "";
  };

  return (
    <Form method="get" action="/search">
      {/* Preserve existing query */}
      {preserveParams("q") && (
        <input type="hidden" name="q" value={preserveParams("q")} />
      )}
      
      {/* New filter */}
      <select name="include_filters[gbl_resourceClass_sm][]">
        <option value="">All Types</option>
        <option value="Dataset">Datasets</option>
        <option value="Map">Maps</option>
      </select>
      
      <button type="submit">Apply Filter</button>
    </Form>
  );
}
```

## Form with Server Action

For forms that need to submit data to the server (e.g., creating a bookmark):

```typescript
// app/routes/bookmarks.tsx
import { Form, redirect, type ActionFunctionArgs } from "react-router";

export async function action({ request }: ActionFunctionArgs) {
  const formData = await request.formData();
  const resourceId = formData.get("resourceId");
  
  // Server-side processing (e.g., save to database)
  // This runs on the server with API key available
  
  return redirect("/bookmarks");
}

export default function Bookmarks() {
  return (
    <Form method="post">
      <input type="hidden" name="resourceId" value="123" />
      <button type="submit">Add Bookmark</button>
    </Form>
  );
}
```

## Using Current Forms

The existing forms in the codebase (SearchField, FacetMoreModal) use client-side navigation with `useNavigate()`. These work fine and don't need to be changed unless you want progressive enhancement.

### Current Approach (Works Fine)

```typescript
// Current: Client-side navigation
const handleSubmit = (e: React.FormEvent) => {
  e.preventDefault();
  navigate(`/search?q=${query}`);
};
```

### Enhanced Approach (Optional)

```typescript
// Enhanced: Progressive enhancement with React Router v7 Form
import { Form } from "react-router";

<Form method="get" action="/search">
  <input name="q" defaultValue={query} />
  <button type="submit">Search</button>
</Form>
```

## When to Use React Router v7 Form

**Use React Router v7 Form when:**
- Form submits data to a server action
- You want progressive enhancement (works without JavaScript)
- Form navigation should work with browser back/forward buttons
- You need built-in loading states

**Continue using client-side forms when:**
- Form needs complex client-side logic (autocomplete, dynamic validation)
- Form updates multiple URL parameters dynamically
- Form has complex state management
- Form requires immediate client-side feedback

## Migration Notes

- Existing forms work as-is - no breaking changes
- React Router v7 Form is optional enhancement
- Both approaches can coexist in the same application
- Gradually migrate forms when beneficial

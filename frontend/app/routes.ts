import type { RouteConfig } from "@react-router/dev/routes";
import { index, route } from "@react-router/dev/routes";

export default [
  index("routes/_index.tsx"),
  route("search", "routes/search.tsx"),
  route("resources/:id", "routes/resources.$id.tsx"),
  // Resource routes (return non-HTML responses via loaders)
  route("resources/:id/static-map", "routes/resources.$id.static-map.ts"),
  route("resources/:id/thumbnail", "routes/resources.$id.thumbnail.ts"),
  route("thumbnails/placeholder", "routes/thumbnails.placeholder.ts"),
  route("thumbnails/:image_hash", "routes/thumbnails.$image_hash.ts"),
  route("iiif/manifest", "routes/iiif.manifest.ts"),
  route("suggest", "routes/suggest.ts"),
  route("bookmarks", "routes/bookmarks.tsx"),
  route("map", "routes/map.tsx"),
  route("test", "routes/test.tsx"),
  route("test/fixtures", "routes/test.fixtures.tsx"),
  route("*", "routes/$.tsx"),
] satisfies RouteConfig;

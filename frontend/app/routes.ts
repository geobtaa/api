import type { RouteConfig } from "@react-router/dev/routes";
import { index, route } from "@react-router/dev/routes";

export default [
  index("routes/_index.tsx"),
  route("search", "routes/search.tsx"),
  route("resources/:id", "routes/resources.$id.tsx"),
  // Resource routes (return non-HTML responses via loaders)
  route("resources/:id/static-map", "routes/resources.$id.static-map.ts"),
  route("static-maps/:id", "routes/static-maps.$id.ts"),
  route("static-maps/:id/geometry", "routes/static-maps.$id.geometry.ts"),
  route(
    "static-maps/:id/resource-class-icon",
    "routes/static-maps.$id.resource-class-icon.ts",
  ),
  route(
    "institutions/:slug/static-map",
    "routes/institutions.$slug.static-map.ts",
  ),
  route(
    "resources/:id/static-map/no-cache",
    "routes/resources.$id.static-map.no-cache.ts",
  ),
  route("resources/:id/thumbnail", "routes/resources.$id.thumbnail.ts"),
  route(
    "resources/:id/thumbnail/no-cache",
    "routes/resources.$id.thumbnail.no-cache.ts",
  ),
  route("thumbnails/placeholder", "routes/thumbnails.placeholder.ts"),
  route("thumbnails/:image_hash", "routes/thumbnails.$image_hash.ts"),
  route("iiif/manifest", "routes/iiif.manifest.ts"),
  route("robots.txt", "routes/robots-txt.ts"),
  route("suggest", "routes/suggest.ts"),
  route("search/facets/:facetName", "routes/api.search.facets.ts"),
  route("map/h3", "routes/api.map.h3.ts"),
  route("home/blog-posts", "routes/api.home.blog-posts.ts"),
  route("bookmarks", "routes/bookmarks.tsx"),
  route("map", "routes/map.tsx"),
  route("test", "routes/test.tsx"),
  route("test/fixtures", "routes/test.fixtures.tsx"),
  route("test/fixtures/providers", "routes/test.fixtures.providers.tsx"),
  route("*", "routes/$.tsx"),
] satisfies RouteConfig;

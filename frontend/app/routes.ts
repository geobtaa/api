import type { RouteConfig } from "@react-router/dev/routes";
import { index, route } from "@react-router/dev/routes";

export default [
  index("routes/_index.tsx"),
  route("search", "routes/search.tsx"),
  route("resources/:id", "routes/resources.$id.tsx"),
  route("resources/:id/static-map", "routes/resources.$id.static-map.ts"),
  route("iiif/manifest", "routes/iiif.manifest.ts"),
  route("suggest", "routes/suggest.ts"),
  route("bookmarks", "routes/bookmarks.tsx"),
  route("map", "routes/map.tsx"),
  route("test", "routes/test.tsx"),
  route("test/fixtures", "routes/test.fixtures.tsx"),
  route("*", "routes/$.tsx"),
] satisfies RouteConfig;

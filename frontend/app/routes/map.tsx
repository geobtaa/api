import { MapPage } from "../../src/pages/MapPage";
import { buildSeoMeta } from "../../src/config/seo";

/**
 * Map page.
 */
export default function Map() {
  return <MapPage />;
}

export function meta() {
  return buildSeoMeta({ title: "Map", url: "/map" });
}

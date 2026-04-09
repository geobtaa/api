import { buildRobotsTxt } from "../lib/search-engine-indexing.server";

export async function loader() {
  return new Response(buildRobotsTxt(), {
    status: 200,
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "Cache-Control": "public, max-age=3600",
    },
  });
}

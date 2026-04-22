import { beforeEach, describe, expect, it, vi } from "vitest";
import type { LoaderFunctionArgs } from "react-router";
import { loader } from "../static-maps.$id.resource-class-icon";

vi.mock("../../lib/server-api", () => ({
  serverFetch: vi.fn(),
}));

import { serverFetch } from "../../lib/server-api";

describe("static-maps resource-class-icon loader", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("preserves upstream asset redirects for the browser", async () => {
    vi.mocked(serverFetch).mockResolvedValue(
      new Response(null, {
        status: 302,
        headers: {
          Location: "/api/v1/static-map-assets/deadbeef",
          "Cache-Control": "public, max-age=0, s-maxage=60, stale-while-revalidate=60",
        },
      })
    );

    const response = await loader({
      params: { id: "result-1" },
      request: new Request(
        "https://lib-geoportal-prd-web-01.oit.umn.edu/static-maps/result-1/resource-class-icon"
      ),
    } as LoaderFunctionArgs);

    expect(serverFetch).toHaveBeenCalledWith(
      "/static-maps/result-1/resource-class-icon",
      {
        headers: { Accept: "image/*,*/*;q=0.8" },
        redirect: "manual",
      }
    );
    expect(response.status).toBe(302);
    expect(response.headers.get("location")).toBe(
      "/api/v1/static-map-assets/deadbeef"
    );
    expect(response.headers.get("cache-control")).toBe(
      "public, max-age=0, s-maxage=60, stale-while-revalidate=60"
    );
  });

  it("rewrites static-map asset redirects for local development", async () => {
    vi.mocked(serverFetch).mockResolvedValue(
      new Response(null, {
        status: 302,
        headers: {
          Location: "/api/v1/static-map-assets/deadbeef",
          "Cache-Control": "public, max-age=0, s-maxage=60, stale-while-revalidate=60",
        },
      })
    );

    const response = await loader({
      params: { id: "result-1" },
      request: new Request(
        "http://localhost:3000/static-maps/result-1/resource-class-icon"
      ),
    } as LoaderFunctionArgs);

    expect(response.status).toBe(302);
    expect(response.headers.get("location")).toBe(
      "http://localhost:8000/api/v1/static-map-assets/deadbeef"
    );
  });
});

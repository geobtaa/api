import { beforeEach, describe, expect, it, vi } from "vitest";
import type { LoaderFunctionArgs } from "react-router";

vi.mock("../../lib/server-api", () => ({
  serverFetchJsonWithTheme: vi.fn(),
}));

import { loader } from "../api.map.h3";
import { serverFetchJsonWithTheme } from "../../lib/server-api";

describe("api.map.h3 loader", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("forwards adv_q and filter params to the upstream API", async () => {
    vi.mocked(serverFetchJsonWithTheme).mockResolvedValue({
      resolution: 5,
      hexes: [["85283473fffffff", 2]],
      globalCount: 2,
    });

    const advQuery = encodeURIComponent(
      JSON.stringify([
        { op: "AND", f: "dct_title_s", q: "water" },
        { op: "AND", f: "dct_spatial_sm", q: "Pennsylvania" },
      ]),
    );
    const includeFilter = encodeURIComponent("include_filters[dct_spatial_sm][]");
    const mockRequest = new Request(
      `https://example.com/map/h3?q=&resolution=5&adv_q=${advQuery}&${includeFilter}=Pennsylvania`,
    );
    const loaderArgs = { request: mockRequest } as LoaderFunctionArgs;

    await loader(loaderArgs);

    expect(serverFetchJsonWithTheme).toHaveBeenCalledTimes(1);
    expect(vi.mocked(serverFetchJsonWithTheme).mock.calls[0][0]).toBe(mockRequest);
    const pathAndQuery = vi.mocked(serverFetchJsonWithTheme).mock.calls[0][1];
    expect(pathAndQuery).toContain("/map/h3?");
    expect(pathAndQuery).toContain("adv_q=");
    expect(pathAndQuery).toContain("include_filters%5Bdct_spatial_sm%5D%5B%5D=Pennsylvania");
  });

  it("lets browsers keep non-empty hex responses briefly while shared caches keep them hot", async () => {
    vi.mocked(serverFetchJsonWithTheme).mockResolvedValue({
      resolution: 5,
      hexes: [["85283473fffffff", 2]],
      globalCount: 2,
    });

    const mockRequest = new Request("https://example.com/map/h3?q=&resolution=5");
    const loaderArgs = { request: mockRequest } as LoaderFunctionArgs;

    const response = await loader(loaderArgs);

    expect(response.headers.get("Cache-Control")).toContain("max-age=300");
    expect(response.headers.get("Cache-Control")).toContain("s-maxage=86400");
  });
});

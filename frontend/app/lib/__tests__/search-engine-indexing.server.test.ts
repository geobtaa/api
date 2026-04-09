import { afterEach, describe, expect, it, vi } from "vitest";

import {
  buildRobotsTxt,
  buildXRobotsTag,
  searchEngineIndexingEnabled,
} from "../search-engine-indexing.server";

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("search-engine-indexing.server", () => {
  it("disables indexing by default", () => {
    expect(searchEngineIndexingEnabled()).toBe(false);
    expect(buildXRobotsTag()).toBe("noindex, nofollow, noarchive, nosnippet");
    expect(buildRobotsTxt("https://geo.example.org")).toBe(
      [
        "# Block all search engine bots from indexing",
        "User-agent: *",
        "Disallow: /",
        "",
        "# Explicitly block major bots",
        "User-agent: Googlebot",
        "Disallow: /",
        "",
        "User-agent: Bingbot",
        "Disallow: /",
        "",
        "User-agent: Slurp",
        "Disallow: /",
        "",
        "User-agent: DuckDuckBot",
        "Disallow: /",
        "",
        "User-agent: Baiduspider",
        "Disallow: /",
        "",
        "User-agent: YandexBot",
        "Disallow: ",
        "",
      ].join("\n"),
    );
  });

  it("allows indexing and advertises the sitemap when enabled", () => {
    vi.stubEnv("SEARCH_ENGINE_INDEXING_ENABLED", "true");

    expect(searchEngineIndexingEnabled()).toBe(true);
    expect(buildXRobotsTag()).toBeNull();
    const robotsTxt = buildRobotsTxt("https://geo.example.org");

    expect(robotsTxt).toContain("Disallow: /search?");
    expect(robotsTxt).toContain("Disallow: /search?include_filters");
    expect(robotsTxt).toContain("Disallow: /search?view=");
    expect(robotsTxt).toContain("Sitemap: https://geo.example.org/sitemap.xml");
  });

  it("strips the api suffix from APPLICATION_URL when building the sitemap URL", () => {
    vi.stubEnv("SEARCH_ENGINE_INDEXING_ENABLED", "true");
    vi.stubEnv("APPLICATION_URL", "https://geo.example.org/api/v1/");

    expect(buildRobotsTxt()).toContain("Sitemap: https://geo.example.org/sitemap.xml");
  });
});

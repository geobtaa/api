declare const process: { env: Record<string, string | undefined> };

const NOINDEX_ROBOTS_TAG = "noindex, nofollow, noarchive, nosnippet";

function parseBooleanFlag(rawValue: string | undefined): boolean | undefined {
  if (rawValue === undefined) {
    return undefined;
  }

  const normalized = rawValue.trim().toLowerCase();
  if (["1", "true", "yes", "on"].includes(normalized)) {
    return true;
  }
  if (["0", "false", "no", "off"].includes(normalized)) {
    return false;
  }

  return undefined;
}

function applicationUrl(baseUrl?: string): string {
  const value = (
    baseUrl ||
    process.env.GEOPORTAL_BASE_URL ||
    process.env.APPLICATION_URL ||
    "http://localhost:8000"
  ).trim();
  const normalized = value.replace(/\/+$/, "") || "http://localhost:8000";
  return normalized.replace(/\/api\/v1$/, "");
}

function buildSiteUrl(baseUrl: string, path: string): string {
  return new URL(path, `${baseUrl}/`).toString();
}

export function searchEngineIndexingEnabled(): boolean {
  return parseBooleanFlag(process.env.SEARCH_ENGINE_INDEXING_ENABLED) ?? false;
}

export function buildXRobotsTag(): string | null {
  if (searchEngineIndexingEnabled()) {
    return null;
  }

  return NOINDEX_ROBOTS_TAG;
}

export function buildRobotsTxt(baseUrl?: string): string {
  if (!searchEngineIndexingEnabled()) {
    return [
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
    ].join("\n");
  }

  const appUrl = applicationUrl(baseUrl);
  return [
    "# Production robots rules for the BTAA Geoportal.",
    "User-agent: *",
    "Allow: /",
    "Disallow: /api/",
    "Disallow: /bookmarks",
    "Disallow: /home/blog-posts",
    "Disallow: /iiif/manifest",
    "Disallow: /map/h3",
    "# Search result pages and faceted/paginated variants.",
    "Disallow: /search?",
    "Disallow: /search?q=",
    "Disallow: /search?adv_q=",
    "Disallow: /search?include_filters",
    "Disallow: /search?exclude_filters",
    "Disallow: /search?fq[",
    "Disallow: /search?page=",
    "Disallow: /search?per_page=",
    "Disallow: /search?sort=",
    "Disallow: /search?view=",
    "Disallow: /search?showAdvanced=",
    "Disallow: /search/facets/",
    "Disallow: /suggest",
    "Disallow: /test",
    `Sitemap: ${buildSiteUrl(appUrl, "/sitemap.xml")}`,
    "",
  ].join("\n");
}

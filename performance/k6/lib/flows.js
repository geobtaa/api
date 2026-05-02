import http from "k6/http";
import { check, fail, sleep } from "k6";
import exec from "k6/execution";

import { config } from "./config.js";
import { recordSearchDiagnostics } from "./search_diagnostics.js";

const HTML_HEADERS = {
  Accept: "text/html,application/xhtml+xml",
};

const JSON_HEADERS = {
  Accept: "application/vnd.api+json, application/json",
};

const ASSET_HEADERS = {
  Accept: "*/*",
};

const FACET_PREFERENCE_ORDER = [
  "gbl_resourceClass_sm",
  "gbl_resourceType_sm",
  "dct_spatial_sm",
  "schema_provider_s",
  "dct_accessRights_s",
  "dct_publisher_sm",
];

function contentType(response) {
  return String(
    response.headers["Content-Type"] || response.headers["content-type"] || "",
  ).toLowerCase();
}

function checkHtml(response, label) {
  check(response, {
    [`${label} returned 200`]: (res) => res.status === 200,
    [`${label} returned html`]: (res) => contentType(res).includes("text/html"),
    [`${label} returned body`]: (res) =>
      Boolean(res.body && res.body.length > 0),
  });
}

function checkJson(response, label) {
  check(response, {
    [`${label} returned 200`]: (res) => res.status === 200,
    [`${label} returned json`]: (res) =>
      contentType(res).includes("application/json"),
    [`${label} returned body`]: (res) =>
      Boolean(res.body && res.body.length > 0),
  });
}

function checkAsset(response, label) {
  check(response, {
    [`${label} returned 200`]: (res) => res.status === 200,
    [`${label} returned body`]: (res) =>
      Boolean(res.body && res.body.length > 0),
  });
}

function sortFacetCandidates(left, right) {
  const leftIndex = FACET_PREFERENCE_ORDER.indexOf(left.id);
  const rightIndex = FACET_PREFERENCE_ORDER.indexOf(right.id);
  const normalizedLeft =
    leftIndex === -1 ? FACET_PREFERENCE_ORDER.length : leftIndex;
  const normalizedRight =
    rightIndex === -1 ? FACET_PREFERENCE_ORDER.length : rightIndex;

  return normalizedLeft - normalizedRight;
}

function buildFacetSelections(payload) {
  const included = Array.isArray(payload && payload.included)
    ? payload.included
    : [];
  const candidates = included
    .filter(
      (item) =>
        item &&
        item.type === "facet" &&
        item.id &&
        Array.isArray(item.attributes && item.attributes.items) &&
        item.attributes.items.length > 0,
    )
    .map((item) => {
      const firstItem = item.attributes.items[0];
      return {
        id: String(item.id),
        value: firstItem ? String(firstItem[0]) : "",
      };
    })
    .filter((item) => item.value.length > 0)
    .sort(sortFacetCandidates);

  return candidates.slice(0, 2);
}

function buildFacetQueryString(seed) {
  if (!seed.facetSelections || seed.facetSelections.length === 0) {
    return "";
  }

  return seed.facetSelections
    .map(
      (selection) =>
        `include_filters[${selection.id}][]=${encodeURIComponent(selection.value)}`,
    )
    .join("&");
}

function buildCacheBustToken(label) {
  return [
    config.cacheBustSeed,
    exec.scenario.name || "scenario",
    exec.vu.idInTest || 0,
    exec.scenario.iterationInTest || 0,
    label,
  ].join("-");
}

function withSearchCacheBust(url, label) {
  if (!config.cacheBustSearch) {
    return url;
  }

  const separator = url.includes("?") ? "&" : "?";
  const token = encodeURIComponent(buildCacheBustToken(label));
  return `${url}${separator}k6cb=${token}`;
}

function buildFrontendSearchResultsUrl(encodedQuery, facetQueryString = "") {
  const filters = facetQueryString ? `&${facetQueryString}` : "";
  return `${config.baseUrl}/search/results?format=json&search_field=all_fields&q=${encodedQuery}&page=1&per_page=${config.searchPerPage}${filters}`;
}

export function setupSeed() {
  if (config.resourceId) {
    return {
      resourceId: config.resourceId,
      encodedResourceId: encodeURIComponent(config.resourceId),
      facetSelections: [],
    };
  }

  const searchUrl = `${config.baseUrl}/api/v1/search?per_page=1&q=${encodeURIComponent(
    config.query,
  )}`;
  const response = http.get(searchUrl, {
    headers: JSON_HEADERS,
    tags: { name: "seed_search", surface: "api" },
  });

  checkJson(response, "seed search");

  const payload = response.json();
  const firstResult = payload && payload.data && payload.data[0];
  if (!firstResult || !firstResult.id) {
    fail(`Unable to discover a resource id from ${searchUrl}`);
  }

  const facetSelections = buildFacetSelections(payload);

  return {
    resourceId: String(firstResult.id),
    encodedResourceId: encodeURIComponent(String(firstResult.id)),
    facetSelections,
  };
}

export function frontendFlow(seed) {
  const encodedQuery = encodeURIComponent(config.query);
  const facetQueryString = buildFacetQueryString(seed);
  const homeResponse = http.get(`${config.baseUrl}/`, {
    headers: HTML_HEADERS,
    tags: { name: "frontend_home_page", surface: "frontend" },
  });
  checkHtml(homeResponse, "frontend home page");

  const assetResponses = http.batch([
    [
      "GET",
      `${config.baseUrl}/manifest.webmanifest`,
      null,
      {
        headers: ASSET_HEADERS,
        tags: { name: "frontend_manifest", surface: "frontend" },
      },
    ],
    [
      "GET",
      `${config.baseUrl}/registerSW.js`,
      null,
      {
        headers: ASSET_HEADERS,
        tags: { name: "frontend_service_worker", surface: "frontend" },
      },
    ],
  ]);
  checkAsset(assetResponses[0], "frontend manifest");
  checkAsset(assetResponses[1], "frontend service worker");

  const searchPageResponse = http.get(
    withSearchCacheBust(
      `${config.baseUrl}/search?q=${encodedQuery}`,
      "frontend-search-page",
    ),
    {
      headers: HTML_HEADERS,
      tags: { name: "frontend_search_page", surface: "frontend" },
    },
  );
  checkHtml(searchPageResponse, "frontend search page");

  const searchResultsResponse = http.get(
    withSearchCacheBust(
      buildFrontendSearchResultsUrl(encodedQuery),
      "frontend-search-results-api",
    ),
    {
      headers: JSON_HEADERS,
      tags: { name: "frontend_search_results_api", surface: "frontend" },
    },
  );
  recordSearchDiagnostics(searchResultsResponse, "frontend_search_results_api");
  checkJson(searchResultsResponse, "frontend search results api");

  if (facetQueryString) {
    const facetedSearchPageResponse = http.get(
      withSearchCacheBust(
        `${config.baseUrl}/search?q=${encodedQuery}&${facetQueryString}`,
        "frontend-faceted-search-page",
      ),
      {
        headers: HTML_HEADERS,
        tags: { name: "frontend_faceted_search_page", surface: "frontend" },
      },
    );
    checkHtml(facetedSearchPageResponse, "frontend faceted search page");

    const facetedSearchResultsResponse = http.get(
      withSearchCacheBust(
        buildFrontendSearchResultsUrl(encodedQuery, facetQueryString),
        "frontend-faceted-search-results-api",
      ),
      {
        headers: JSON_HEADERS,
        tags: {
          name: "frontend_faceted_search_results_api",
          surface: "frontend",
        },
      },
    );
    recordSearchDiagnostics(
      facetedSearchResultsResponse,
      "frontend_faceted_search_results_api",
    );
    checkJson(
      facetedSearchResultsResponse,
      "frontend faceted search results api",
    );
  }

  const resourcePageResponse = http.get(
    `${config.baseUrl}/resources/${seed.encodedResourceId}`,
    {
      headers: HTML_HEADERS,
      tags: { name: "frontend_resource_page", surface: "frontend" },
    },
  );
  checkHtml(resourcePageResponse, "frontend resource page");

  sleep(config.frontendThinkTimeSeconds);
}

export function apiFlow(seed) {
  const encodedQuery = encodeURIComponent(config.query);
  const encodedSuggestQuery = encodeURIComponent(config.suggestQuery);
  const facetQueryString = buildFacetQueryString(seed);

  const searchResponse = http.get(
    withSearchCacheBust(
      `${config.baseUrl}/api/v1/search?per_page=${config.searchPerPage}&q=${encodedQuery}`,
      "api-search",
    ),
    {
      headers: JSON_HEADERS,
      tags: { name: "api_search", surface: "api" },
    },
  );
  recordSearchDiagnostics(searchResponse, "api_search");
  checkJson(searchResponse, "api search");
  check(searchResponse, {
    "api search returned data array": (res) => {
      const payload = res.json();
      return Boolean(payload && Array.isArray(payload.data));
    },
  });

  if (facetQueryString) {
    const facetedSearchResponse = http.get(
      withSearchCacheBust(
        `${config.baseUrl}/api/v1/search?per_page=${config.searchPerPage}&q=${encodedQuery}&${facetQueryString}`,
        "api-faceted-search",
      ),
      {
        headers: JSON_HEADERS,
        tags: { name: "api_faceted_search", surface: "api" },
      },
    );
    recordSearchDiagnostics(facetedSearchResponse, "api_faceted_search");
    checkJson(facetedSearchResponse, "api faceted search");
  }

  const suggestResponse = http.get(
    `${config.baseUrl}/api/v1/suggest?q=${encodedSuggestQuery}`,
    {
      headers: JSON_HEADERS,
      tags: { name: "api_suggest", surface: "api" },
    },
  );
  checkJson(suggestResponse, "api suggest");

  const resourceListResponse = http.get(
    `${config.baseUrl}/api/v1/resources/?page=1&per_page=${config.searchPerPage}`,
    {
      headers: JSON_HEADERS,
      tags: { name: "api_resource_list", surface: "api" },
    },
  );
  checkJson(resourceListResponse, "api resource list");

  const resourceDetailResponse = http.get(
    `${config.baseUrl}/api/v1/resources/${seed.encodedResourceId}`,
    {
      headers: JSON_HEADERS,
      tags: { name: "api_resource_detail", surface: "api" },
    },
  );
  checkJson(resourceDetailResponse, "api resource detail");

  if (seed.facetSelections && seed.facetSelections.length > 0) {
    const filterSelection = seed.facetSelections[0];
    const facetValueSelection =
      seed.facetSelections[1] || seed.facetSelections[0];
    const facetValueFilter =
      filterSelection.id === facetValueSelection.id
        ? ""
        : `&include_filters[${filterSelection.id}][]=${encodeURIComponent(
            filterSelection.value,
          )}`;
    const facetValuesResponse = http.get(
      withSearchCacheBust(
        `${config.baseUrl}/api/v1/search/facets/${encodeURIComponent(
          facetValueSelection.id,
        )}?q=${encodedQuery}${facetValueFilter}`,
        "api-facet-values",
      ),
      {
        headers: JSON_HEADERS,
        tags: { name: "api_facet_values", surface: "api" },
      },
    );
    recordSearchDiagnostics(facetValuesResponse, "api_facet_values", {
      expectSemanticCache: false,
    });
    checkJson(facetValuesResponse, "api facet values");
  }

  const blogResponse = http.get(
    `${config.baseUrl}/api/v1/home/blog-posts?limit=3&theme=btaa`,
    {
      headers: JSON_HEADERS,
      tags: { name: "api_home_blog", surface: "api" },
    },
  );
  checkJson(blogResponse, "api home blog posts");

  sleep(config.apiThinkTimeSeconds);
}

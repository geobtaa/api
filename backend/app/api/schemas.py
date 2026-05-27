from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel


class PublicAPIModel(BaseModel):
    """Permissive public API schema used to document stable envelopes."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)


class JSONAPIResource(PublicAPIModel):
    type: str
    id: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    links: dict[str, Any] | None = None
    meta: dict[str, Any] | None = None
    relationships: dict[str, Any] | None = None


class JSONAPIResponse(PublicAPIModel):
    jsonapi: dict[str, Any] | None = None
    links: dict[str, Any] | None = None
    meta: dict[str, Any] | None = None
    data: JSONAPIResource | list[JSONAPIResource] | dict[str, Any] | list[dict[str, Any]] | None = (
        None
    )
    included: list[dict[str, Any]] | None = None


class APIInfoAttributes(PublicAPIModel):
    api: str
    version: str
    description: str
    endpoints: list[str] = Field(default_factory=list)


class APIInfoResource(JSONAPIResource):
    type: Literal["api_info"] = "api_info"
    id: str = "root"
    attributes: APIInfoAttributes


class APIRootResponse(JSONAPIResponse):
    data: APIInfoResource


class ResourceResponse(JSONAPIResponse):
    data: JSONAPIResource


class ResourceCollectionResponse(JSONAPIResponse):
    data: list[JSONAPIResource] = Field(default_factory=list)


class SearchMeta(PublicAPIModel):
    totalCount: int | None = None
    totalPages: int | None = None
    currentPage: int | None = None
    perPage: int | None = None
    query: str | None = None
    sort: str | None = None
    queryTime: dict[str, Any] | None = None
    spellingSuggestions: list[Any] = Field(default_factory=list)


class SearchResponse(JSONAPIResponse):
    meta: SearchMeta | None = None
    data: list[JSONAPIResource] = Field(default_factory=list)


class SuggestionAttributes(PublicAPIModel):
    text: str
    score: float | int | None = None


class SuggestionResource(JSONAPIResource):
    type: Literal["suggestion"] = "suggestion"
    id: str
    attributes: SuggestionAttributes


class SuggestResponse(JSONAPIResponse):
    data: list[SuggestionResource] = Field(default_factory=list)


class FacetValueAttributes(PublicAPIModel):
    value: str | int | float | bool | None = None
    hits: int = 0


class FacetValueResource(JSONAPIResource):
    type: Literal["facet_value"] = "facet_value"
    id: str
    attributes: FacetValueAttributes


class FacetMeta(PublicAPIModel):
    totalCount: int
    totalPages: int
    currentPage: int
    perPage: int
    facetName: str
    sort: str


class FacetResponse(JSONAPIResponse):
    meta: FacetMeta
    data: list[FacetValueResource] = Field(default_factory=list)


class HomeBlogPost(PublicAPIModel):
    slug: str | None = None
    url: str | None = None
    title: str | None = None
    excerpt: str | None = None
    published_at: datetime | str | None = None
    category: str | None = None
    authors: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    image_url: str | None = None
    image_alt: str | None = None


class HomeBlogMeta(PublicAPIModel):
    pinned_slugs: list[str] = Field(default_factory=list)
    total_count: int = 0
    fetched_at: datetime | str | None = None


class HomeBlogPostsResponse(PublicAPIModel):
    data: list[HomeBlogPost] = Field(default_factory=list)
    meta: HomeBlogMeta = Field(default_factory=HomeBlogMeta)


class MapH3Response(PublicAPIModel):
    resolution: int
    hexes: list[tuple[str, int]] = Field(default_factory=list)
    globalCount: int = 0


class CitationStyles(PublicAPIModel):
    apa: str
    mla: str
    chicago: str


class ResourceCitationResponse(PublicAPIModel):
    id: str
    citation: str
    citations: CitationStyles


class SchemaOrgEntity(PublicAPIModel):
    context: str | None = Field(default=None, alias="@context")
    type: str | None = Field(default=None, alias="@type")
    id: str | None = Field(default=None, alias="@id")


class SchemaOrgCitationResponse(SchemaOrgEntity):
    url: str | list[str] | None = None
    name: str | None = None
    description: str | None = None
    datePublished: str | None = None
    keywords: str | None = None
    spatialCoverage: list[dict[str, Any]] | None = None
    temporalCoverage: str | None = None
    inLanguage: str | None = None
    license: str | None = None
    identifier: str | list[str] | None = None
    author: list[dict[str, Any]] | None = None
    publisher: dict[str, Any] | None = None
    encodingFormat: str | None = None
    accessMode: str | None = None
    includedInDataCatalog: dict[str, Any] | None = None
    distribution: list[dict[str, Any]] | None = None


class DownloadOption(PublicAPIModel):
    label: str | None = None
    url: str | None = None
    type: str | None = None
    format: str | None = None
    generated: bool | None = None
    download_type: str | None = None
    generation_path: str | None = None


class ResourceDownloadsResponse(PublicAPIModel):
    id: str
    downloads: list[DownloadOption] = Field(default_factory=list)


class GeneratedDownloadResponse(PublicAPIModel):
    download_type: str
    file_name: str
    file_path: str
    content_type: str
    download_url: str


class DistributionRecord(PublicAPIModel):
    id: int | None = None
    resource_id: str | None = None
    url: str | None = None
    label: str | None = None
    position: int | None = None
    created_at: datetime | str | None = None
    updated_at: datetime | str | None = None
    import_distribution_id: str | int | None = None
    distribution_type_id: int | None = None
    distribution_type_name: str | None = None
    distribution_type: str | None = None
    distribution_uri: str | None = None
    distribution_note: str | None = None


class ResourceDistributionsResponse(PublicAPIModel):
    id: str
    distributions: list[DistributionRecord] = Field(default_factory=list)


class ResourceLink(PublicAPIModel):
    label: str | None = None
    url: str | None = None
    format: str | None = None
    service_type: str | None = None


class ResourceLinksResponse(PublicAPIModel):
    id: str
    links: dict[str, list[ResourceLink]] = Field(default_factory=dict)


class ResourceRelationship(PublicAPIModel):
    resource_id: str
    resource_title: str | None = None
    link: str | None = None


class ResourceRelationshipsResponse(PublicAPIModel):
    id: str
    relationships: dict[str, list[ResourceRelationship]] = Field(default_factory=dict)


class SimilarItem(PublicAPIModel):
    id: str
    title: str | None = None
    temporal_coverage: list[str] = Field(default_factory=list)
    thumbnail_url: str | None = None
    gbl_indexYear_im: list[int] = Field(default_factory=list)
    gbl_resourceClass_sm: list[str] = Field(default_factory=list)


class ResourceSimilarItemsResponse(PublicAPIModel):
    id: str
    similar_items: list[SimilarItem] = Field(default_factory=list)


class ResourceSpatialFacetsResponse(PublicAPIModel):
    id: str
    spatial_facets: dict[str, Any] = Field(default_factory=dict)


class ResourceViewer(PublicAPIModel):
    protocol: str | None = None
    endpoint: str | None = None
    geometry: Any | None = None


class ResourceViewerResponse(PublicAPIModel):
    id: str
    viewer: ResourceViewer | None = None


class ResourceMetadataResponse(PublicAPIModel):
    ogm: dict[str, Any] | None = None
    b1g: dict[str, Any] | None = None


class MetadataBlockResponse(RootModel[dict[str, Any]]):
    """Extensible OGM or B1G metadata field block."""


class DataDictionaryEntry(PublicAPIModel):
    id: int
    resource_data_dictionary_id: int
    friendlier_id: str
    field_name: str
    field_type: str | None = None
    values: str | None = None
    definition: str | None = None
    definition_source: str | None = None
    parent_field_name: str | None = None
    position: int = 0
    created_at: datetime | str | None = None
    updated_at: datetime | str | None = None


class DataDictionary(PublicAPIModel):
    id: int
    friendlier_id: str
    name: str | None = None
    description: str | None = None
    staff_notes: str | None = None
    tags: str = ""
    position: int = 0
    created_at: datetime | str | None = None
    updated_at: datetime | str | None = None
    entries: list[DataDictionaryEntry] = Field(default_factory=list)


class DataDictionaryListResponse(RootModel[list[DataDictionary]]):
    """Resource data dictionary list."""


class OGCLink(PublicAPIModel):
    href: str
    rel: str
    type: str | None = None
    title: str | None = None


class OGCLandingPageResponse(PublicAPIModel):
    title: str
    description: str
    links: list[OGCLink] = Field(default_factory=list)


class OGCConformanceResponse(PublicAPIModel):
    conformsTo: list[str] = Field(default_factory=list)


class OGCCollectionResponse(PublicAPIModel):
    id: str
    title: str
    description: str | None = None
    itemType: str | None = None
    links: list[OGCLink] = Field(default_factory=list)


class OGCCollectionsResponse(PublicAPIModel):
    collections: list[OGCCollectionResponse] = Field(default_factory=list)
    links: list[OGCLink] = Field(default_factory=list)


class OGCQueryablesResponse(PublicAPIModel):
    schema_: str = Field(alias="$schema")
    id_: str = Field(alias="$id")
    type: Literal["object"] = "object"
    title: str
    properties: dict[str, Any] = Field(default_factory=dict)


class OGCSortablesResponse(OGCQueryablesResponse):
    pass


class OGCFeatureProperties(PublicAPIModel):
    id: str | None = None
    title: str | None = None
    description: str | None = None
    resourceClass: list[str] = Field(default_factory=list)
    resourceType: list[str] = Field(default_factory=list)
    provider: str | None = None
    spatial: list[str] = Field(default_factory=list)
    subject: list[str] = Field(default_factory=list)
    accessRights: str | None = None
    modified: datetime | str | None = None
    dateAccessioned: str | None = None
    publicationState: str | None = None
    accrualMethod: str | None = None


class OGCFeatureResponse(PublicAPIModel):
    type: Literal["Feature"] = "Feature"
    id: str | None = None
    geometry: dict[str, Any] | None = None
    properties: OGCFeatureProperties
    links: list[OGCLink] = Field(default_factory=list)


class OGCFeatureCollectionResponse(PublicAPIModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    timeStamp: datetime | str | int | float | None = None
    numberMatched: int = 0
    numberReturned: int = 0
    features: list[OGCFeatureResponse] = Field(default_factory=list)
    links: list[OGCLink] = Field(default_factory=list)


class OGMRepoSummary(PublicAPIModel):
    ogm_repo_name: str | None = None
    ogm_enabled: bool | None = None
    ogm_watch_mode: str | None = None
    last_crawl_started_at: datetime | str | None = None
    last_crawl_completed_at: datetime | str | None = None
    last_crawl_status: str | None = None
    last_run_id: int | None = None
    harvested_success_count: int = 0
    harvested_failure_count: int = 0
    harvest_failure_samples: list[Any] = Field(default_factory=list)


class OGMRepoSummariesResponse(PublicAPIModel):
    repos: list[OGMRepoSummary] = Field(default_factory=list)


class OGMHarvestFailure(PublicAPIModel):
    ogm_id: int | None = None
    ogm_repo_name: str | None = None
    ogm_trigger: str | None = None
    ogm_started_at: datetime | str | None = None
    ogm_completed_at: datetime | str | None = None
    ogm_status: str | None = None
    ogm_stats_json: dict[str, Any] | None = None
    ogm_dump_dir: str | None = None
    ogm_error: str | None = None
    import_error_count: int = 0
    imported_count: int = 0
    error_samples: list[Any] = Field(default_factory=list)
    error_signatures: list[Any] = Field(default_factory=list)
    failure_reason: str | None = None


class OGMHarvestFailuresResponse(PublicAPIModel):
    failures: list[OGMHarvestFailure] = Field(default_factory=list)
    repo_name: str | None = None
    include_with_errors: bool


class MCPInfoConnection(PublicAPIModel):
    type: str
    command: str | None = None
    args: list[str] | None = None
    url: str | None = None


class MCPInfoResponse(PublicAPIModel):
    name: str
    version: str
    description: str
    protocol: str
    transports: list[str] = Field(default_factory=list)
    capabilities: dict[str, Any] = Field(default_factory=dict)
    connections: dict[str, MCPInfoConnection] = Field(default_factory=dict)
    documentation: dict[str, Any] = Field(default_factory=dict)


class JSONRPCError(PublicAPIModel):
    code: int
    message: str


class JSONRPCResponse(PublicAPIModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: str | int | None = None
    result: dict[str, Any] | None = None
    error: JSONRPCError | None = None


class GenericObjectResponse(RootModel[dict[str, Any]]):
    """Compatibility JSON object for non-public or intentionally opaque responses."""


class GenericArrayResponse(RootModel[list[dict[str, Any]]]):
    """Compatibility JSON array for non-public or intentionally opaque responses."""

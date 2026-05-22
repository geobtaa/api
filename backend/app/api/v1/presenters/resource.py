"""Resource presentation for the public JSON:API contract."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from app.services.distribution_repository import DistributionContext
from app.services.ogm_field_mapper import OGMFieldMapper

logger = logging.getLogger(__name__)

RESOURCE_PRESENTATION_UNSET = object()


@dataclass(slots=True)
class ResourceHydrationContext:
    """Preloaded data used to render a resource without extra per-item lookups."""

    distribution_context: DistributionContext | None = None
    ui_downloads: list[dict[str, Any]] | None = None
    bridge_asset_download_rows: Any = None
    licensed_accesses_payload: list[dict[str, Any]] | None | object = RESOURCE_PRESENTATION_UNSET
    ui_relationships: dict[str, Any] | None = None
    ui_relationship_counts: dict[str, int] | None = None
    ui_relationship_browse_links: dict[str, str] | None = None
    allmaps_attributes: dict[str, Any] | None = None
    data_dictionaries_payload: list[dict[str, Any]] | None | object = RESOURCE_PRESENTATION_UNSET
    thumbnail_asset_url: str | None | object = RESOURCE_PRESENTATION_UNSET


class ResourcePresenter:
    """Build stable resource response objects from raw resource rows."""

    ui_field_names = {
        "ui_thumbnail_url",
        "ui_resource_class_icon_url",
        "ui_citation",
        "ui_citations",
        "ui_downloads",
        "ui_licensed_accesses",
        "ui_links",
        "ui_viewer_protocol",
        "ui_viewer_endpoint",
        "ui_viewer_geometry",
        "ui_relationships",
        "ui_relationship_counts",
        "ui_relationship_browse_links",
        "ui_summaries",
        "ai_summaries",
        "suggest",
    }

    def __init__(self, session=None):
        self.session = session

    @staticmethod
    def serialize_jsonapi_resource(resource_data, request_url=None):
        """Create the JSON:API resource object for a resource attribute payload."""
        api_utils = _api_utils()

        ui_fields = {}
        core_attributes = {}

        for key, value in resource_data.items():
            if key in ResourcePresenter.ui_field_names:
                ui_fields[key] = value
            elif value is not None:
                core_attributes[key] = value

        core_attributes = api_utils.filter_empty_values(core_attributes)

        resource_id = core_attributes.get("id") or resource_data.get("id", "")

        ogm_fields = {}
        b1g_fields = {}
        ogm_aardvark_field_set = OGMFieldMapper.get_ogm_aardvark_fields()

        for key, value in core_attributes.items():
            if key in ogm_aardvark_field_set:
                ogm_fields[key] = value
            else:
                b1g_fields[key] = value

        ogm_fields = api_utils.filter_empty_values(ogm_fields)
        b1g_fields = api_utils.filter_empty_values(b1g_fields)

        nested_attributes = {}
        if ogm_fields:
            nested_attributes["ogm"] = ogm_fields
        if b1g_fields:
            nested_attributes["b1g"] = b1g_fields

        restructured_ui = {}

        if "ui_thumbnail_url" in ui_fields and ui_fields["ui_thumbnail_url"] is not None:
            thumbnail_url = ui_fields["ui_thumbnail_url"]
            restructured_ui["thumbnail_url"] = thumbnail_url
            if "/thumbnails/placeholder" in str(thumbnail_url):
                restructured_ui["thumbnail_placeholder"] = True
        if (
            "ui_resource_class_icon_url" in ui_fields
            and ui_fields["ui_resource_class_icon_url"] is not None
        ):
            restructured_ui["resource_class_icon_url"] = ui_fields["ui_resource_class_icon_url"]
        if "ui_citation" in ui_fields:
            restructured_ui["citation"] = ui_fields["ui_citation"]
        if "ui_citations" in ui_fields:
            restructured_ui["citations"] = ui_fields["ui_citations"]
        if "ui_downloads" in ui_fields:
            restructured_ui["downloads"] = ui_fields["ui_downloads"]
        if "ui_licensed_accesses" in ui_fields:
            restructured_ui["licensed_accesses"] = ui_fields["ui_licensed_accesses"]
        if "ui_links" in ui_fields:
            restructured_ui["links"] = ui_fields["ui_links"]
        if "ui_relationships" in ui_fields:
            restructured_ui["relationships"] = ui_fields["ui_relationships"]
        if "ui_relationship_counts" in ui_fields:
            restructured_ui["relationship_counts"] = ui_fields["ui_relationship_counts"]
        if "ui_relationship_browse_links" in ui_fields:
            restructured_ui["relationship_browse_links"] = ui_fields["ui_relationship_browse_links"]
        if "ui_summaries" in ui_fields:
            restructured_ui["summaries"] = ui_fields["ui_summaries"]
        if "ai_summaries" in ui_fields:
            restructured_ui["ai_summaries"] = ui_fields["ai_summaries"]
        if "suggest" in ui_fields:
            restructured_ui["suggest"] = ui_fields["suggest"]

        viewer_fields = {}
        if "ui_viewer_protocol" in ui_fields:
            viewer_fields["protocol"] = ui_fields["ui_viewer_protocol"]
        if "ui_viewer_endpoint" in ui_fields:
            viewer_fields["endpoint"] = ui_fields["ui_viewer_endpoint"]
        if "ui_viewer_geometry" in ui_fields:
            viewer_fields["geometry"] = ui_fields["ui_viewer_geometry"]

        if viewer_fields:
            restructured_ui["viewer"] = viewer_fields

        return {
            "type": "resource",
            "id": str(resource_id),
            "attributes": nested_attributes if nested_attributes else {},
            "meta": {
                "@context": "https://gin.btaa.org/ld/contexts/ogm-aardvark-btaa.context.jsonld",
                "@type": "BtaaAardvarkRecord",
                "ui": restructured_ui,
            },
        }

    async def present_full(
        self,
        resource_dict,
        *,
        apply_field_mapping: bool = True,
        include_similar_items: bool = True,
        hot_only_thumbnail_url: bool = False,
        hydration: ResourceHydrationContext | None = None,
    ):
        """Render the full resource profile used by resource detail and list paths."""
        from app.services.citation_service import CitationService
        from app.services.download_service import DownloadService
        from app.services.link_service import LinkService
        from app.services.relationship_service import RelationshipService
        from app.services.viewer_service import ViewerService

        api_utils = _api_utils()
        hydration = hydration or ResourceHydrationContext()

        if apply_field_mapping:
            resource_dict = OGMFieldMapper.map_resource_fields(resource_dict)

        distribution_context = hydration.distribution_context
        if distribution_context is None:
            distribution_context = await api_utils.fetch_distribution_context(
                resource_dict["id"],
                session=self.session,
            )

        thumbnail_kwargs: dict[str, Any] = {"distribution_context": distribution_context}
        if hot_only_thumbnail_url:
            thumbnail_kwargs["hot_only"] = True
        resource_dict = api_utils.add_thumbnail_url(resource_dict, **thumbnail_kwargs)
        if not resource_dict.get("ui_thumbnail_url"):
            resource_dict["ui_resource_class_icon_url"] = api_utils._hot_resource_class_icon_url(
                resource_dict
            )

        citation_service = CitationService(resource_dict, distribution_context=distribution_context)
        ui_citations = citation_service.get_all_citations()
        ui_citation = ui_citations["apa"]

        viewer_service = ViewerService(resource_dict, distribution_context=distribution_context)
        viewer_attributes = viewer_service.get_viewer_attributes()

        download_service = DownloadService(resource_dict, distribution_context=distribution_context)
        ui_downloads = hydration.ui_downloads
        if ui_downloads is None:
            ui_downloads = await download_service.get_download_options_with_bridge_asset_downloads(
                hydration.bridge_asset_download_rows
            )

        link_service = LinkService(resource_dict, distribution_context=distribution_context)
        ui_links = link_service.get_links()

        ui_relationships = hydration.ui_relationships
        if ui_relationships is None:
            ui_relationships = await RelationshipService.get_resource_relationships(
                resource_dict["id"]
            )

        allmaps_attributes = hydration.allmaps_attributes
        if allmaps_attributes is None:
            allmaps_attributes = await api_utils._fetch_allmaps_attributes_for_resource(
                resource_dict, self.session
            )

        attributes = {
            **resource_dict,
            "ui_citation": ui_citation,
            "ui_citations": ui_citations,
            "ui_thumbnail_url": resource_dict.get("ui_thumbnail_url"),
            "ui_resource_class_icon_url": resource_dict.get("ui_resource_class_icon_url"),
            "ui_viewer_endpoint": viewer_attributes.get("ui_viewer_endpoint"),
            "ui_viewer_geometry": viewer_attributes.get("ui_viewer_geometry"),
            "ui_viewer_protocol": viewer_attributes.get("ui_viewer_protocol"),
            "ui_downloads": ui_downloads,
            "ui_links": ui_links,
            "ui_relationships": ui_relationships,
        }
        if hydration.ui_relationship_counts:
            attributes["ui_relationship_counts"] = hydration.ui_relationship_counts
        if hydration.ui_relationship_browse_links:
            attributes["ui_relationship_browse_links"] = hydration.ui_relationship_browse_links

        await self._attach_data_dictionaries(attributes, resource_dict, hydration)
        await self._attach_licensed_accesses(attributes, resource_dict, hydration)
        self._attach_legacy_references(attributes, distribution_context)
        self._merge_viewer_attributes(attributes, viewer_attributes)

        resource = self.serialize_jsonapi_resource(attributes)

        await self._apply_thumbnail_asset(
            resource,
            resource_dict,
            distribution_context=distribution_context,
            thumbnail_asset_url=hydration.thumbnail_asset_url,
            allow_resource_fallback=True,
        )
        self._attach_allmaps(resource, allmaps_attributes)
        self._attach_static_map(resource, resource_dict)

        if include_similar_items:
            resource = await api_utils.add_similar_items_to_resource(
                resource, resource_dict, self.session
            )

        return resource

    async def present_homepage(
        self,
        resource_dict,
        *,
        apply_field_mapping: bool = True,
        hydration: ResourceHydrationContext | None = None,
    ):
        """Render the lightweight profile used by homepage previews."""
        from app.services.viewer_service import ViewerService

        api_utils = _api_utils()
        hydration = hydration or ResourceHydrationContext()

        if apply_field_mapping:
            resource_dict = OGMFieldMapper.map_resource_fields(resource_dict)

        distribution_context = hydration.distribution_context
        if distribution_context is None:
            distribution_context = await api_utils.fetch_distribution_context(
                resource_dict["id"],
                session=self.session,
            )

        resource_dict = api_utils.add_thumbnail_url(
            resource_dict, distribution_context=distribution_context
        )

        viewer_service = ViewerService(resource_dict, distribution_context=distribution_context)
        viewer_attributes = viewer_service.get_viewer_attributes()

        allmaps_attributes = hydration.allmaps_attributes
        if allmaps_attributes is None:
            allmaps_attributes = await api_utils._fetch_allmaps_attributes_for_resource(
                resource_dict, self.session
            )

        attributes = {
            **resource_dict,
            "ui_thumbnail_url": resource_dict.get("ui_thumbnail_url"),
            "ui_viewer_endpoint": viewer_attributes.get("ui_viewer_endpoint"),
            "ui_viewer_geometry": viewer_attributes.get("ui_viewer_geometry"),
            "ui_viewer_protocol": viewer_attributes.get("ui_viewer_protocol"),
        }

        self._merge_viewer_attributes(attributes, viewer_attributes)

        resource = self.serialize_jsonapi_resource(attributes)

        await self._apply_thumbnail_asset(
            resource,
            resource_dict,
            distribution_context=distribution_context,
            thumbnail_asset_url=hydration.thumbnail_asset_url,
            allow_resource_fallback=True,
        )
        self._attach_allmaps(resource, allmaps_attributes)

        return resource

    async def present_search_result(
        self,
        resource_dict,
        allmaps_attributes,
        *,
        apply_field_mapping: bool = True,
        hot_only_thumbnail_url: bool = False,
    ):
        """Render the legacy optimized search-result profile."""
        from app.services.citation_service import CitationService
        from app.services.download_service import DownloadService
        from app.services.link_service import LinkService
        from app.services.relationship_service import RelationshipService
        from app.services.viewer_service import ViewerService

        api_utils = _api_utils()

        if apply_field_mapping:
            resource_dict = OGMFieldMapper.map_resource_fields(resource_dict)

        distribution_context = await api_utils.fetch_distribution_context(resource_dict["id"])

        thumbnail_kwargs: dict[str, Any] = {"distribution_context": distribution_context}
        if hot_only_thumbnail_url:
            thumbnail_kwargs["hot_only"] = True
        resource_dict = api_utils.add_thumbnail_url(resource_dict, **thumbnail_kwargs)
        if hot_only_thumbnail_url and not resource_dict.get("ui_thumbnail_url"):
            resource_dict["ui_resource_class_icon_url"] = api_utils._hot_resource_class_icon_url(
                resource_dict
            )

        citation_service = CitationService(resource_dict, distribution_context=distribution_context)
        ui_citations = citation_service.get_all_citations()
        ui_citation = ui_citations["apa"]

        viewer_service = ViewerService(resource_dict, distribution_context=distribution_context)
        viewer_attributes = viewer_service.get_viewer_attributes()

        download_service = DownloadService(resource_dict, distribution_context=distribution_context)
        ui_downloads = await download_service.get_download_options_with_bridge_asset_downloads()

        link_service = LinkService(resource_dict, distribution_context=distribution_context)
        ui_links = link_service.get_links()

        ui_relationships = await RelationshipService.get_resource_relationships(resource_dict["id"])

        attributes = {
            **resource_dict,
            "ui_citation": ui_citation,
            "ui_citations": ui_citations,
            "ui_thumbnail_url": resource_dict.get("ui_thumbnail_url"),
            "ui_resource_class_icon_url": resource_dict.get("ui_resource_class_icon_url"),
            "ui_viewer_endpoint": viewer_attributes.get("ui_viewer_endpoint"),
            "ui_viewer_geometry": viewer_attributes.get("ui_viewer_geometry"),
            "ui_viewer_protocol": viewer_attributes.get("ui_viewer_protocol"),
            "ui_downloads": ui_downloads,
            "ui_links": ui_links,
            "ui_relationships": ui_relationships,
        }

        self._attach_legacy_references(attributes, distribution_context)
        self._merge_viewer_attributes(attributes, viewer_attributes)

        resource = self.serialize_jsonapi_resource(attributes)

        await self._apply_thumbnail_asset(
            resource,
            resource_dict,
            distribution_context=distribution_context,
            thumbnail_asset_url=RESOURCE_PRESENTATION_UNSET,
            allow_resource_fallback=not hot_only_thumbnail_url,
        )
        self._attach_allmaps(resource, allmaps_attributes)
        self._attach_static_map(resource, resource_dict)

        return resource

    async def _attach_data_dictionaries(
        self,
        attributes: dict[str, Any],
        resource_dict: dict[str, Any],
        hydration: ResourceHydrationContext,
    ) -> None:
        api_utils = _api_utils()
        data_dictionaries_payload = hydration.data_dictionaries_payload

        if data_dictionaries_payload is RESOURCE_PRESENTATION_UNSET:
            try:
                data_dictionaries_payload = (
                    await api_utils._fetch_data_dictionaries_payload_for_resource(
                        resource_dict["id"],
                        self.session,
                    )
                )
                if data_dictionaries_payload:
                    attributes["data_dictionaries"] = data_dictionaries_payload
            except Exception as e:
                logger.warning(
                    "Failed to load data dictionaries for resource %s: %s",
                    resource_dict.get("id"),
                    str(e),
                )
        elif data_dictionaries_payload:
            attributes["data_dictionaries"] = api_utils.sanitize_for_json(data_dictionaries_payload)

    async def _attach_licensed_accesses(
        self,
        attributes: dict[str, Any],
        resource_dict: dict[str, Any],
        hydration: ResourceHydrationContext,
    ) -> None:
        api_utils = _api_utils()
        licensed_accesses_payload = hydration.licensed_accesses_payload

        if licensed_accesses_payload is RESOURCE_PRESENTATION_UNSET:
            try:
                licensed_accesses_payload = (
                    await api_utils._fetch_licensed_accesses_payload_for_resource(
                        resource_dict["id"],
                        self.session,
                    )
                )
            except Exception as e:
                logger.warning(
                    "Failed to load licensed accesses for resource %s: %s",
                    resource_dict.get("id"),
                    str(e),
                )
                licensed_accesses_payload = None

        if licensed_accesses_payload:
            attributes["ui_licensed_accesses"] = api_utils.sanitize_for_json(
                licensed_accesses_payload
            )

    def _attach_legacy_references(
        self, attributes: dict[str, Any], distribution_context: DistributionContext
    ) -> None:
        try:
            legacy_refs = distribution_context.legacy_reference_payload
            if legacy_refs:
                attributes["dct_references_s"] = json.dumps(legacy_refs)
        except Exception as e:
            logger.warning("Failed to serialize legacy references: %s", str(e))

    def _merge_viewer_attributes(
        self, attributes: dict[str, Any], viewer_attributes: dict[str, Any]
    ) -> None:
        for key, value in viewer_attributes.items():
            if key not in attributes:
                attributes[key] = value

    async def _apply_thumbnail_asset(
        self,
        resource: dict[str, Any],
        resource_dict: dict[str, Any],
        *,
        distribution_context: DistributionContext,
        thumbnail_asset_url: str | None | object,
        allow_resource_fallback: bool,
    ) -> None:
        api_utils = _api_utils()

        thumb_asset_url = (
            await api_utils._get_thumbnail_asset_url(resource_dict["id"])
            if thumbnail_asset_url is RESOURCE_PRESENTATION_UNSET
            else thumbnail_asset_url
        )
        current_thumbnail_url = ((resource.get("meta") or {}).get("ui") or {}).get("thumbnail_url")
        if thumb_asset_url and not api_utils._is_immutable_thumbnail_url(current_thumbnail_url):
            hot_thumbnail_url = api_utils._hot_thumbnail_url_for_resource(
                resource_dict,
                distribution_context=distribution_context,
                thumbnail_asset_url=thumb_asset_url,
            )
            if hot_thumbnail_url or allow_resource_fallback:
                resource.setdefault("meta", {})
                resource["meta"].setdefault("ui", {})
                resource["meta"]["ui"]["thumbnail_url"] = (
                    hot_thumbnail_url
                    or api_utils._build_resource_thumbnail_url(resource_dict["id"])
                )

    def _attach_allmaps(
        self, resource: dict[str, Any], allmaps_attributes: dict[str, Any] | None
    ) -> None:
        if not allmaps_attributes:
            return

        resource.setdefault("meta", {})
        resource["meta"].setdefault("ui", {})
        resource["meta"]["ui"]["allmaps"] = allmaps_attributes

    def _attach_static_map(self, resource: dict[str, Any], resource_dict: dict[str, Any]) -> None:
        api_utils = _api_utils()
        geometry = resource_dict.get("locn_geometry") or resource_dict.get("dcat_bbox")
        if not geometry:
            return

        static_map_url = api_utils._hot_static_map_url(
            resource_dict
        ) or api_utils._build_static_map_url(resource_dict["id"])

        resource.setdefault("meta", {})
        resource["meta"].setdefault("ui", {})
        resource["meta"]["ui"]["static_map"] = static_map_url


def _api_utils():
    from app.api.v1 import utils as api_utils

    return api_utils

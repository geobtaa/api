"""Small public viewer contract, separate from internal delivery/job manifests."""

PUBLIC_FIELDS = (
    "version",
    "status",
    "scope",
    "source_url",
    "source_fingerprint",
    "processing_version",
    "generated_at",
    "transformations",
    "detail",
    "thumbnail_status",
    "thumbnail_scope",
    "thumbnail_url",
)
LAYER_FIELDS = (
    "id",
    "name",
    "url",
    "format",
    "source_layer",
    "bounds",
    "recipe",
    "byte_size",
    "columns",
    "row_count",
)


def public_preview(manifest):
    """Never send tile registries, private review images, or tool logs to clients."""
    result = {key: manifest[key] for key in PUBLIC_FIELDS if key in manifest}
    result["layers"] = [
        {key: layer[key] for key in LAYER_FIELDS if key in layer}
        for layer in manifest.get("layers", [])
    ]
    return result


# Match the media types served by our asset routes. Service endpoints and
# externally hosted images do not have a single known response media type.
MEDIA_TYPES = {
    "cog": "image/tiff",
    "pmtiles": "application/vnd.pmtiles",
    "parquet": "application/vnd.apache.parquet",
    "geojson": "application/geo+json",
    "iiif": "application/json",
    "iiif-manifest": "application/json",
}


def public_assets(manifest, coverage):
    """Discover published assets without depending on Geoportal UI fields."""
    catalog = {"version": "1", "items": [], "coverage": coverage}
    if not manifest:
        return catalog
    preview = public_preview(manifest)
    catalog["provenance"] = {
        key: preview[key]
        for key in (
            "source_url",
            "source_fingerprint",
            "processing_version",
            "generated_at",
            "transformations",
        )
        if key in preview
    }
    if manifest.get("status") == "ready":
        for layer in preview["layers"]:
            item = {
                **layer,
                "id": f"layer:{layer['id']}",
                "layer_id": layer["id"],
                "roles": ["table" if layer["format"] == "parquet" else "visualization"],
                "scope": manifest.get("scope", "resource"),
            }
            if layer["format"] in MEDIA_TYPES:
                item["media_type"] = MEDIA_TYPES[layer["format"]]
            # Zero is the internal default for unknown size (e.g. live services).
            if not item.get("byte_size"):
                item.pop("byte_size", None)
            catalog["items"].append(item)
        if manifest.get("thumbnail_status") == "ready" and manifest.get("thumbnail_url"):
            catalog["items"].append(
                {
                    "id": "thumbnail",
                    "roles": ["thumbnail"],
                    "format": "image",
                    "media_type": "image/png",
                    "url": manifest["thumbnail_url"],
                    "scope": manifest.get("thumbnail_scope", "resource"),
                }
            )
    if manifest.get("coverage_url") and coverage.get("kind") != "unavailable":
        catalog["items"].append(
            {
                "id": "coverage-map",
                "roles": ["coverage-map"],
                "format": "image",
                "media_type": "image/png",
                "url": manifest["coverage_url"],
                "scope": "resource",
            }
        )
    return catalog

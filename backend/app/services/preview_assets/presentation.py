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

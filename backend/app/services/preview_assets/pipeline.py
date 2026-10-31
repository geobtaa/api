"""One preparation pipeline, consumed by the background worker and audit CLI."""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import unquote, urlsplit

from PIL import Image, ImageDraw
from urllib3.exceptions import HTTPError

from .convert import GDAL_VERSION, TIPPECANOE_VERSION, convert_raster, convert_vector, raster_recipe
from .geometry import (
    display_coverage,
    index_coverage,
    metadata_coverage,
    representative_members,
    validate_index_content,
)
from .io import Budget, RangeReader, download, extract_zip
from .models import (
    PIPELINE_VERSION,
    Layer,
    Limits,
    Manifest,
    Outcome,
    PreviewError,
    Recipe,
    eligible,
    fingerprint,
)
from .render import quality, render_raster, render_vector
from .sources import (
    Source,
    arcgis_export,
    discover,
    iiif_manifest_image,
    query_url,
    urls,
    wms_image,
)
from .storage import asset_url

CURATION_RECIPE = (
    "https://github.com/geobtaa/curation/tree/72cf908eb82c1e2c9187178b5c93410f0efb0b22"
)


class Pipeline:
    def __init__(
        self,
        store,
        limits=None,
        fetch=download,
        child_lookup=None,
        coverage_renderer=None,
        work_root=None,
        range_open=None,
    ):
        self.work_root = work_root
        self.store = store
        self.coverage_renderer = coverage_renderer
        self.limits = limits or Limits.from_env()
        self.fetch = fetch
        self.child_lookup = child_lookup
        self.range_open = range_open or (RangeReader if fetch is download else None)

    def prepare(self, record, *, source=None, recipe=None, selected_layer=None):
        with TemporaryDirectory(prefix="btaa-preview-", dir=self.work_root) as name:
            directory = Path(name)
            budget = Budget(self.limits, directory)
            result = Manifest(status=Outcome.UNSUPPORTED, coverage=metadata_coverage(record))
            try:
                if not eligible(record):
                    raise PreviewError(Outcome.UNAVAILABLE, "Resource is not public and published")
                candidates = [source] if source else discover(record)
                if not candidates:
                    raise PreviewError(Outcome.UNSUPPORTED, "No supported source reference")
                attempts = []
                for i, candidate in enumerate(candidates[:8]):
                    work = directory / str(i)
                    work.mkdir()
                    try:
                        result = self._source(
                            record,
                            candidate,
                            work,
                            budget,
                            recipe,
                            selected_layer,
                            {record["id"]},
                            0,
                        )
                        break
                    except (OSError, HTTPError) as exc:
                        attempts.append(
                            {
                                "kind": candidate.kind,
                                "url": candidate.url,
                                "status": "unavailable",
                                "detail": str(exc),
                            }
                        )
                        result.status, result.detail = Outcome.UNAVAILABLE, str(exc)
                    except PreviewError as exc:
                        attempts.append(
                            {
                                "kind": candidate.kind,
                                "url": candidate.url,
                                "status": exc.status.value,
                                "detail": str(exc),
                            }
                        )
                        result.status, result.detail = exc.status, str(exc)
                        if exc.status == Outcome.OVER_LIMIT:
                            break
                result.metrics["source_attempts"] = attempts
            except PreviewError as exc:
                result.status, result.detail = exc.status, str(exc)
            except (OSError, ValueError, KeyError, TypeError) as exc:
                result.status, result.detail = Outcome.INVALID, str(exc)
            result.coverage = display_coverage(result.coverage)
            if self.coverage_renderer and result.coverage and result.coverage.geometry:
                try:
                    target = directory / "coverage.png"
                    if self.coverage_renderer(result.coverage, target, budget):
                        result.coverage_key = self._put(target, budget)
                        result.coverage_url = asset_url(record["id"], result.coverage_key)
                except Exception as exc:
                    result.metrics["coverage_error"] = str(exc)
            result.generated_at = datetime.now(timezone.utc).isoformat()
            result.metrics.update(
                seconds=round(time.monotonic() - budget.started, 3),
                bytes_read=budget.bytes_read,
                output_bytes=budget.output_bytes,
                tools={"gdal": GDAL_VERSION, "tippecanoe": TIPPECANOE_VERSION},
                recipe_reference=CURATION_RECIPE,
            )
            return result

    def _source(self, record, source, directory, budget, recipe, selected_layer, visited, depth):
        coverage = metadata_coverage(record)
        if source.kind == "index":
            local = directory / "index.json"
            index_hash = self.fetch(source.url, local, budget)
            collection = json.loads(local.read_text())
            coverage = index_coverage(collection)
            errors = []
            for i, member in enumerate(representative_members(collection)):
                props = member.get("properties") or {}
                work = directory / f"member-{i}"
                work.mkdir()
                try:
                    direct = next(
                        iter(
                            urls(props.get("downloadUrl"))
                            or urls(props.get("thumbnailUrl"))
                            or urls(props.get("imageUrl"))
                        ),
                        None,
                    )
                    if direct:
                        child = {
                            **record,
                            "locn_geometry": member["geometry"],
                            "dcat_bbox": None,
                            "_preview_sample": True,
                        }
                        prepared = self._source(
                            child,
                            Source(direct, "download"),
                            work,
                            budget,
                            recipe,
                            selected_layer,
                            visited,
                            depth,
                        )
                    elif props.get("recordIdentifier"):
                        identifier = str(props["recordIdentifier"])
                        if identifier in visited:
                            raise PreviewError(Outcome.INVALID, "Index reference cycle")
                        if depth >= 1:
                            raise PreviewError(
                                Outcome.UNSUPPORTED, "Index child-record hop limit exceeded"
                            )
                        if not self.child_lookup:
                            raise PreviewError(
                                Outcome.UNAVAILABLE, "Child record snapshot unavailable"
                            )
                        child = self.child_lookup(identifier)
                        if not child or not eligible(child):
                            raise PreviewError(Outcome.UNAVAILABLE, "Child record unavailable")
                        child = {**child, "_preview_sample": True}
                        sources = discover(child)
                        if not sources:
                            raise PreviewError(
                                Outcome.UNSUPPORTED, "Child has no renderable source"
                            )
                        prepared = self._source(
                            child,
                            sources[0],
                            work,
                            budget,
                            recipe,
                            selected_layer,
                            visited | {identifier},
                            depth + 1,
                        )
                        from .repository import record_signature

                        prepared.dependencies.append(
                            {"resource_id": identifier, "signature": record_signature(child)}
                        )
                    else:
                        raise PreviewError(
                            Outcome.UNSUPPORTED,
                            "Index member has no direct data or resolvable child",
                        )
                    if prepared.status != Outcome.READY:
                        raise PreviewError(
                            prepared.status, prepared.detail or "Member preview failed"
                        )
                    validate_index_content(record, member, prepared)
                    prepared.scope = "sample"
                    # Derivatives are published under the collection's manifest,
                    # even when discovery followed a child catalog record.
                    for layer in prepared.layers:
                        member_label = props.get("label") or props.get("title")
                        if member_label:
                            layer.name = str(member_label)
                        if layer.asset_key:
                            layer.url = asset_url(record["id"], layer.asset_key)
                    if prepared.thumbnail_key:
                        prepared.thumbnail_url = asset_url(record["id"], prepared.thumbnail_key)
                    prepared.coverage = coverage
                    if coverage.label.endswith("(incomplete)"):
                        prepared.detail = coverage.provenance
                    prepared.source_fingerprint = fingerprint(
                        [index_hash, prepared.source_fingerprint]
                    )
                    prepared.transformations.append(
                        "Representative index member; not complete collection coverage"
                    )
                    return prepared
                except (OSError, HTTPError, PreviewError) as exc:
                    errors.append(str(exc))
                    if getattr(exc, "status", None) == Outcome.OVER_LIMIT:
                        raise
            return Manifest(
                status=Outcome.NEEDS_REVIEW,
                source_url=source.url,
                source_fingerprint=index_hash,
                coverage=coverage,
                detail="; ".join(errors),
            )
        if source.kind in {"arcgis", "wms", "iiif", "iiif-manifest"}:
            return self._service(record, source, directory, budget)
        suffix = Path(urlsplit(source.url).path).suffix.lower()
        supplied = Recipe.model_validate(recipe) if isinstance(recipe, dict) else recipe
        if self.range_open and (
            source.kind in {"cog", "pmtiles"} or suffix in {".tif", ".tiff", ".pmtiles"}
        ):
            from .native import inspect_cog, inspect_pmtiles

            try:
                with self.range_open(source.url, budget) as stream:
                    thumbnail = directory / "thumbnail.png"
                    if source.kind == "pmtiles" or suffix == ".pmtiles":
                        layers, coverage, status = inspect_pmtiles(
                            stream, thumbnail, budget, supplied, selected_layer
                        )
                    else:
                        layers, coverage, status = inspect_cog(stream, thumbnail, supplied)
                    result = Manifest(
                        status=Outcome.READY,
                        source_url=source.url,
                        source_fingerprint=fingerprint(
                            {
                                "source": stream.fingerprint,
                                "recipes": [
                                    layer.recipe.model_dump(mode="json") for layer in layers
                                ],
                                "version": PIPELINE_VERSION,
                            }
                        ),
                        coverage=coverage,
                        layers=layers,
                        transformations=[
                            "Reused source asset through validated HTTP partial reads"
                        ],
                        metrics={
                            "source_bytes": stream.size,
                            "source_etag": stream.etag,
                            "source_access": "http-range",
                        },
                    )
                    if thumbnail.is_file():
                        self._thumbnail(record, thumbnail, status, result, budget)
                    else:
                        result.thumbnail_status = status
                        result.detail = (
                            "No usable bounded PMTiles overview; content thumbnail needs review"
                        )
                    return result
            except PreviewError as exc:
                if exc.status != Outcome.UNSUPPORTED:
                    raise
                # Unsupported range/validator/COG layout may still be converted
                # safely, subject to the original full-download limits.
        if suffix not in {
            ".tif",
            ".tiff",
            ".zip",
            ".gpkg",
            ".geojson",
            ".json",
            ".pmtiles",
            ".png",
            ".jpg",
            ".jpeg",
        }:
            raise PreviewError(Outcome.UNSUPPORTED, "Download format is not supported")
        local = directory / ("source" + suffix)
        source_hash = self.fetch(source.url, local, budget)
        if suffix in {".png", ".jpg", ".jpeg"}:
            image = directory / "thumbnail.png"
            with Image.open(local) as src:
                src.thumbnail((512, 512))
                src.convert("RGBA").save(image)
            result = Manifest(
                status=Outcome.READY,
                source_url=source.url,
                source_fingerprint=source_hash,
                coverage=coverage,
                layers=[Layer(id="image", name="Source image", url=source.url, format="image")],
            )
            self._thumbnail(record, image, quality(image), result, budget)
            return result
        if suffix == ".pmtiles":
            import mmap
            from types import SimpleNamespace

            from .native import inspect_pmtiles

            thumbnail = directory / "thumbnail.png"
            with local.open("rb") as stream:
                with mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                    reader = SimpleNamespace(
                        url=source.url,
                        size=len(mm),
                        read_at=lambda offset, length: mm[offset : offset + length],
                    )
                    layers, coverage, status = inspect_pmtiles(
                        reader, thumbnail, budget, supplied, selected_layer
                    )
            result = Manifest(
                status=Outcome.READY,
                source_url=source.url,
                source_fingerprint=source_hash,
                coverage=coverage,
                layers=layers,
                transformations=[
                    "Reused native PMTiles; thumbnail uses generalized overview tiles"
                ],
            )
            if thumbnail.is_file():
                self._thumbnail(record, thumbnail, status, result, budget)
            else:
                result.thumbnail_status = status
            return result
        if source.kind == "cog":
            import rasterio
            from rasterio.warp import transform_bounds

            with rasterio.open(local, driver="GTiff") as existing:
                if existing.crs and existing.tags(ns="IMAGE_STRUCTURE").get("LAYOUT") == "COG":
                    native_recipe = raster_recipe(existing, supplied)
                    bounds = list(transform_bounds(existing.crs, "EPSG:4326", *existing.bounds))
                    thumbnail = directory / "thumbnail.png"
                    status = render_raster(local, native_recipe, thumbnail)
                    result = Manifest(
                        status=Outcome.READY,
                        source_url=source.url,
                        source_fingerprint=source_hash,
                        coverage=coverage,
                        layers=[
                            Layer(
                                id="native",
                                name="Source COG",
                                url=source.url,
                                format="cog",
                                recipe=native_recipe,
                                bounds=bounds,
                            )
                        ],
                    )
                    self._thumbnail(record, thumbnail, status, result, budget)
                    return result
        if suffix == ".zip":
            contents = extract_zip(local, directory / "unpacked", budget)
            inputs = sorted(
                path
                for path in contents
                if path.suffix.lower() in {".tif", ".tiff", ".shp", ".gpkg", ".geojson"}
            )
            if not inputs:
                raise PreviewError(
                    Outcome.UNSUPPORTED, "Archive contains no supported spatial files"
                )
            if selected_layer:
                import fiona

                inputs = [
                    path
                    for path in inputs
                    if (
                        path.stem == selected_layer
                        if path.suffix.lower() in {".tif", ".tiff"}
                        else selected_layer in fiona.listlayers(path)
                    )
                ]
                if not inputs:
                    raise PreviewError(Outcome.NEEDS_REVIEW, "Selected layer not found")
            if len(inputs) > self.limits.layers:
                raise PreviewError(Outcome.OVER_LIMIT, "Archive spatial layer limit exceeded")
            layers, coverages, changes = [], [], []
            for index, path in enumerate(inputs):
                if path.suffix.lower() == ".shp":
                    extensions = {
                        p.suffix.lower()
                        for p in contents
                        if p.parent == path.parent and p.stem.lower() == path.stem.lower()
                    }
                    if not {".shp", ".shx", ".dbf", ".prj"} <= extensions:
                        raise PreviewError(
                            Outcome.NEEDS_REVIEW, "Shapefile companion files or CRS missing"
                        )
                work = directory / f"file-{index}"
                work.mkdir()
                if path.suffix.lower() in {".tif", ".tiff"}:
                    prepared, area, edits = convert_raster(
                        path, work / "preview.tif", budget, supplied
                    )
                else:
                    prepared, area, edits = convert_vector(
                        path, work, budget, selected_layer, supplied
                    )
                for layer in prepared:
                    layer["id"] = f"file-{index}-" + layer["id"]
                layers.extend(prepared)
                coverages.append(area)
                changes.extend(edits)
            if len(layers) > self.limits.layers:
                raise PreviewError(Outcome.OVER_LIMIT, "Archive spatial layer limit exceeded")
            from shapely.geometry import mapping, shape
            from shapely.ops import unary_union

            coverage = coverages[0].model_copy(
                update={
                    "geometry": mapping(unary_union([shape(c.geometry) for c in coverages])),
                    "provenance": "Union of extracted spatial layer extents",
                }
            )
            changes = list(dict.fromkeys(changes))
        elif suffix in {".tif", ".tiff"}:
            layers, coverage, changes = convert_raster(
                local, directory / "preview.tif", budget, supplied
            )
        else:
            layers, coverage, changes = convert_vector(
                local, directory, budget, selected_layer, supplied
            )
        if sum(layer["path"].stat().st_size for layer in layers) > self.limits.output_bytes:
            raise PreviewError(Outcome.OVER_LIMIT, "Derivative output limit exceeded")
        signature = fingerprint(
            {
                "source": source_hash,
                "recipes": [layer["recipe"].model_dump(mode="json") for layer in layers],
                "transformations": changes,
                "version": PIPELINE_VERSION,
                "gdal": GDAL_VERSION,
                "tippecanoe": TIPPECANOE_VERSION,
            }
        )
        result = Manifest(
            status=Outcome.READY,
            source_url=source.url,
            source_fingerprint=signature,
            coverage=coverage,
            transformations=changes,
            thumbnail_scope="sample" if len(layers) > 1 else "resource",
        )
        thumbnail = directory / "thumbnail.png"
        first = layers[0]
        if first["format"] == "cog":
            thumbnail_status = render_raster(first["path"], first["recipe"], thumbnail)
        else:
            thumbnail_status = render_vector(
                first["sequence"], first["recipe"], first["bounds"], thumbnail, budget
            )
        for layer in layers:
            budget.check()
            key = self._put(layer["path"], budget)
            result.layers.append(
                Layer(
                    id=layer["id"],
                    name=(
                        Path(unquote(urlsplit(source.url).path)).stem
                        if layer["name"] == "source"
                        else layer["name"]
                    ),
                    url=asset_url(record["id"], key),
                    asset_key=key,
                    byte_size=layer["path"].stat().st_size,
                    format=layer["format"],
                    bounds=layer["bounds"],
                    recipe=layer["recipe"],
                )
            )
        self._thumbnail(record, thumbnail, thumbnail_status, result, budget)
        return result

    def _put(self, path, budget):
        budget.publish(path.stat().st_size)
        return self.store.put(path)

    def _thumbnail(self, record, path, status, manifest, budget):
        if record.get("_preview_sample"):
            manifest.scope = "sample"
        detail = any(layer.recipe and layer.recipe.thumbnail_bounds for layer in manifest.layers)
        if manifest.scope == "sample" or detail or manifest.thumbnail_scope == "sample":
            manifest.thumbnail_scope = "sample"
            label = "Representative detail" if detail else "Representative member"
            if len(manifest.layers) > 1 and manifest.scope != "sample":
                label = "Representative layer"
            # Put the scope on the image itself so search/gallery consumers of
            # the legacy thumbnail URL cannot mistake a detail for full coverage.
            with Image.open(path) as original:
                content = original.convert("RGBA")
                content.thumbnail((512, 480))
                labeled = Image.new(
                    "RGBA", (max(160, content.width), content.height + 28), "#f5f7fa"
                )
                labeled.paste(content, ((labeled.width - content.width) // 2, 0))
                ImageDraw.Draw(labeled).text((8, content.height + 7), label, fill="#334155")
                labeled.save(path, optimize=True)
            quality(path)  # Enforce the byte/dimension limits after adding the label.
        manifest.thumbnail_status = status
        if status == Outcome.NEEDS_REVIEW:
            # Retain evidence privately; this key is deliberately not served by
            # the public asset route or offered as a replacement thumbnail.
            manifest.metrics["review_thumbnail_key"] = self._put(path, budget)
        if status == Outcome.READY:
            key = self._put(path, budget)
            manifest.thumbnail_key = key
            manifest.thumbnail_url = asset_url(record["id"], key)

    def _service(self, record, source, directory, budget):
        origin = source
        sample, manifest_hash = False, None
        if source.kind == "iiif-manifest":
            manifest_path = directory / "manifest.json"
            manifest_hash = self.fetch(source.url, manifest_path, budget)
            source, sample = iiif_manifest_image(json.loads(manifest_path.read_text()))
        thumb_url = source.url
        if source.kind == "wms":
            thumb_url = wms_image(source, record)
        elif source.kind == "arcgis":
            metadata_path = directory / "service.json"
            self.fetch(query_url(source.url, {"f": "pjson"}), metadata_path, budget)
            thumb_url = arcgis_export(source.url, json.loads(metadata_path.read_text()))
        elif source.kind == "iiif":
            thumb_url = (
                source.url.rstrip("/").removesuffix("/info.json") + "/full/!512,512/0/default.jpg"
            )
        target = directory / "response-image"
        digest = self.fetch(thumb_url, target, budget)
        thumbnail = directory / "thumbnail.png"
        with Image.open(target) as image:
            image.thumbnail((512, 512))
            image.convert("RGBA").save(thumbnail)
        result = Manifest(
            status=Outcome.READY,
            source_url=origin.url,
            source_fingerprint=fingerprint([manifest_hash, digest]) if manifest_hash else digest,
            scope="sample" if sample else "resource",
            transformations=["First IIIF canvas is representative content"] if sample else [],
            coverage=metadata_coverage(record),
            layers=[
                Layer(
                    id=source.layer or "source",
                    name=source.layer or "Source layer",
                    url=source.url,
                    format=source.kind,
                )
            ],
        )
        self._thumbnail(record, thumbnail, quality(thumbnail), result, budget)
        return result

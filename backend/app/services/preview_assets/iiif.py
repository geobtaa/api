"""Bounded, static IIIF Image API 2 level 0 derivatives and manifest snapshots.

No provider requests occur at delivery time. Presentation structure is preserved;
complex painting compositions are rejected rather than flattened incorrectly.
"""

import json
import math

from PIL import Image

from .models import Layer, Manifest, Outcome, PreviewError, fingerprint
from .sources import iiif_manifest_image
from .storage import asset_url, file_key

VERSION = "iiif-static-2"
PROFILE = "http://iiif.io/api/image/2/level0.json"
CONTEXT = "http://iiif.io/api/image/2/context.json"


def fail(message):
    raise PreviewError(Outcome.NEEDS_REVIEW, message)


def canvas_images(document):
    """Return all simple embedded canvases; keep actual bodies for rewriting."""
    sequences = document.get("sequences")
    if sequences is not None:
        if len(sequences) != 1:
            fail("IIIF requires exactly one embedded sequence")
        canvases = sequences[0].get("canvases", [])
    else:
        canvases = document.get("items", [])
    if not canvases:
        fail("IIIF manifest has no embedded canvases")
    result = []
    for canvas in canvases:
        wrapper = {"sequences": [{"canvases": [canvas]}]} if sequences else {"items": [canvas]}
        source, _ = iiif_manifest_image(wrapper)
        annotations = (
            canvas.get("images", [])
            if sequences
            else [
                a
                for page in canvas.get("items", [])
                for a in page.get("items", [])
                if a.get("motivation") == "painting"
            ]
        )
        annotation = annotations[0]
        target = annotation.get("on") if sequences else annotation.get("target")
        identifier = canvas.get("@id") or canvas.get("id")
        if not identifier or target != identifier:
            fail("IIIF painting must cover the complete canvas without selectors")
        body = annotation.get("resource") if sequences else annotation.get("body")
        if body.get("service"):
            services = body["service"]
            for service in services if isinstance(services, list) else [services]:
                if service.get("service") or "auth" in str(service.get("profile", "")):
                    fail("IIIF authenticated image services require review")
        result.append((canvas, body, source))
    return result


def prepare_iiif(pipeline, record, source, directory, budget):
    document = None
    digests = []
    if source.kind == "iiif-manifest":
        path = directory / "source-manifest.json"
        digests.append(pipeline.fetch(source.url, path, budget))
        document = json.loads(path.read_text())
        entries = canvas_images(document)
    else:
        entries = [(None, None, source)]
    if len(entries) > budget.limits.iiif_canvases:
        raise PreviewError(Outcome.OVER_LIMIT, "IIIF canvas limit exceeded")
    inputs = []
    source_metadata = []
    for index, (_canvas, _body, candidate) in enumerate(entries):
        expected = None
        info = {}
        if candidate.kind == "iiif":
            base = candidate.url.rstrip("/").removesuffix("/info.json")
            info_path = directory / f"source-info-{index}.json"
            digests.append(pipeline.fetch(base + "/info.json", info_path, budget))
            info = json.loads(info_path.read_text())
            if info.get("service"):
                fail("IIIF image has additional services requiring review")
            width, height = info.get("width"), info.get("height")
            if not isinstance(width, int) or not isinstance(height, int) or min(width, height) < 1:
                fail("IIIF image dimensions missing or invalid")
            expected = (width, height)
            if width * height > budget.limits.iiif_pixels:
                raise PreviewError(Outcome.OVER_LIMIT, "IIIF image pixel limit exceeded")
            v3 = "image/3" in str(info.get("@context")) or info.get("type") == "ImageService3"
            url = base + ("/full/max/0/default.jpg" if v3 else "/full/full/0/default.jpg")
        else:
            url = candidate.url
        path = directory / f"source-image-{index}"
        digests.append(pipeline.fetch(url, path, budget))
        with Image.open(path) as image:
            if image.width * image.height > budget.limits.iiif_pixels:
                raise PreviewError(Outcome.OVER_LIMIT, "IIIF image pixel limit exceeded")
            if expected and image.size != expected:
                fail("IIIF source returned reduced or inconsistent dimensions")
            if image.mode not in {"RGB", "L"}:
                fail("IIIF image requires explicit color or transparency conversion")
            if getattr(image, "n_frames", 1) != 1:
                fail("IIIF animated or multi-frame painting image")
            if image.getexif().get(274, 1) != 1:
                fail("IIIF orientation requires review")
            image.verify()
        inputs.append(path)
        source_metadata.append(
            {k: info[k] for k in ("attribution", "license", "logo") if k in info}
        )
        if info.get("rights"):
            source_metadata[-1]["license"] = info["rights"]
    bundle = fingerprint(
        [
            VERSION,
            budget.limits.iiif_jpeg_quality,
            source.url,
            digests,
            record.get("_preview_owner_id", record["id"]),
        ]
    )
    root = asset_url(record.get("_preview_owner_id", record["id"]), bundle)
    files = {}
    pending = []

    def save(relative, image=None, data=None):
        path = directory / "output" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if image is not None:
            image.save(
                path,
                format="JPEG",
                quality=budget.limits.iiif_jpeg_quality,
                optimize=True,
                progressive=True,
                subsampling=0,
                icc_profile=image.info.get("icc_profile"),
            )
            # For full-size derivatives, reuse a smaller original JPEG verbatim.
            # It has already passed dimension, orientation and color checks.
            if (
                relative.endswith((f"full/{image.width},/0/default.jpg", "full/full/0/default.jpg"))
                and image.size == source_size
            ):
                if source_format == "JPEG" and source_path.stat().st_size < path.stat().st_size:
                    path.write_bytes(source_path.read_bytes())
            with Image.open(path) as check:
                check.verify()
        else:
            path.write_text(json.dumps(data, ensure_ascii=False))
        if len(pending) >= budget.limits.iiif_files:
            raise PreviewError(Outcome.OVER_LIMIT, "IIIF output file limit exceeded")
        budget.publish(path.stat().st_size)
        pending.append((bundle + "/" + relative, path))

    first_info = None
    for index, path in enumerate(inputs):
        service = f"{root}/image-{index}"
        prefix = f"image-{index}/"
        with Image.open(path) as image:
            image.load()
            source_path, source_size, source_format = path, image.size, image.format
            width, height = image.size
            factors = [1]
            while math.ceil(max(width, height) / factors[-1]) > 512:
                factors.append(factors[-1] * 2)
            sizes = []
            for factor in factors:
                w, h = math.ceil(width / factor), math.ceil(height / factor)
                scaled = image.resize((w, h), Image.Resampling.LANCZOS)
                sizes.append({"width": w, "height": h})
                save(prefix + f"full/{w},/0/default.jpg", image=scaled)
                for y in range(0, height, 512 * factor):
                    for x in range(0, width, 512 * factor):
                        rw, rh = min(512 * factor, width - x), min(512 * factor, height - y)
                        tw, th = math.ceil(rw / factor), math.ceil(rh / factor)
                        tile = scaled.crop(
                            (x // factor, y // factor, x // factor + tw, y // factor + th)
                        )
                        save(prefix + f"{x},{y},{rw},{rh}/{tw},/0/default.jpg", image=tile)
            save(prefix + "full/full/0/default.jpg", image=image)
            info = {
                "@context": CONTEXT,
                "@id": service,
                "protocol": "http://iiif.io/api/image",
                "width": width,
                "height": height,
                "profile": [PROFILE],
                "tiles": [{"width": 512, "scaleFactors": factors}],
                "sizes": list(reversed(sizes)),
            }
            info.update(source_metadata[index])
            save(prefix + "info.json", data=info)
            if index == 0:
                first_info = service + "/info.json"
                image.thumbnail((512, 512))
                image.convert("RGBA").save(directory / "thumbnail.png")
            canvas, body, _ = entries[index]
            if body is not None:
                key = "@id" if "@id" in body else "id"
                body[key] = service + "/full/full/0/default.jpg"
                body["format"] = "image/jpeg"
                body["width"], body["height"] = width, height
                body["service"] = {"@context": CONTEXT, "@id": service, "profile": PROFILE}
                if "id" in body:
                    body["service"] = [{"id": service, "type": "ImageService2", "profile": PROFILE}]
                # Stale upstream thumbnails would reintroduce browser dependencies.
                for item in (body, canvas):
                    item.pop("thumbnail", None)
    if document is not None:
        manifest_url = root + "/manifest.json"
        document["@id" if "@id" in document else "id"] = manifest_url
        document.pop("thumbnail", None)
        # Canvas, annotation and range identifiers remain stable intentionally;
        # embedded structure, labels, rights and attribution are preserved.
        save("manifest.json", data=document)
        url, kind = manifest_url, "iiif-manifest"
    else:
        url, kind = first_info, "iiif"
    # Publish only after every page and advertised tile is generated/validated.
    unique_objects = {}
    for relative, path in pending:
        budget.check()
        key = file_key(path)
        if key not in unique_objects:
            pipeline.store.put(path)
            unique_objects[key] = path.stat().st_size
        files[relative] = key
    result = Manifest(
        status=Outcome.READY,
        thumbnail_scope="sample" if len(entries) > 1 else "resource",
        source_url=source.url,
        source_fingerprint=bundle,
        iiif_assets=files,
        layers=[Layer(id="iiif", name="Hosted IIIF", url=url, format=kind)],
        transformations=[
            "Static IIIF Image API 2 level 0; "
            f"optimized progressive JPEG quality {budget.limits.iiif_jpeg_quality}; "
            "4:4:4 color; smaller full source JPEG reused when possible; pixel dimensions retained"
        ],
        metrics={
            "iiif_canvases": len(entries),
            "iiif_files": len(files),
            "iiif_unique_objects": len(unique_objects),
            "iiif_stored_bytes": sum(unique_objects.values()),
            "iiif_bytes": sum(p.stat().st_size for _, p in pending),
        },
    )
    from .geometry import metadata_coverage
    from .render import quality

    result.coverage = metadata_coverage(record)
    pipeline._thumbnail(
        record, directory / "thumbnail.png", quality(directory / "thumbnail.png"), result, budget
    )
    if len(entries) > 1:
        result.thumbnail_scope = "sample"
    return result

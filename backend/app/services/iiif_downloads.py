"""Pure IIIF download extraction; never fetch individual canvases or image services."""

import math
import re
from urllib.parse import urlsplit, urlunsplit


def objects(value):
    return [
        item for item in (value if isinstance(value, list) else [value]) if isinstance(item, dict)
    ]


def http_url(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = urlsplit(value)
        if parsed.scheme in ("http", "https") and parsed.hostname and not parsed.username:
            return value
    except ValueError:
        pass
    return None


def identifier(value):
    return http_url(value.get("id") or value.get("@id"))


def label(value, fallback):
    if isinstance(value, str) and value.strip():
        return re.sub(r"<[^>]+>", "", value).strip() or fallback
    if isinstance(value, list):
        return next((label(item, "") for item in value if label(item, "")), fallback)
    if isinstance(value, dict):
        if "@value" in value:
            return label(value["@value"], fallback)
        for language in ("en", "none", *value):
            text = label(value.get(language), "")
            if text:
                return text
    return fallback


def positive(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value > 0
    )


def service_base(url):
    """Normalize info.json and image requests without losing encoded identifiers/query strings."""
    parsed = urlsplit(url)
    path = parsed.path.rstrip("/")
    path = re.sub(r"/info\.json$", "", path)
    path = re.sub(
        r"/(?:full|square|pct:[\d.,]+|\d+,\d+,\d+,\d+)/[^/]+/!?[\d.]+/[^/]+\.[a-zA-Z0-9]+$",
        "",
        path,
    )
    return urlunsplit(parsed._replace(path=path, fragment=""))


def image_request(base, size, quality="default"):
    parsed = urlsplit(base)
    return urlunsplit(parsed._replace(path=f"{parsed.path}/full/{size}/0/{quality}.jpg"))


def option(name, url, mime="image/jpeg", **metadata):
    return {"label": name, "url": url, "type": mime, "format": mime, "source": "iiif", **metadata}


def image_downloads(url, service=None, body=None):
    """Use declared version, compliance and limits; width-only sizes preserve aspect ratio."""
    if not http_url(url):
        return []
    service = service or {}
    body = body or {}
    base = service_base(url)
    signature = str([service.get("type"), service.get("@context"), service.get("profile")])
    version = 3 if "ImageService3" in signature or "/image/3/" in signature else 2
    if "/image/1" in signature or "/image-api/1" in signature or "ImageService1" in signature:
        version = 1
    quality = "native" if version == 1 else "default"
    limits = {**service}
    for profile in objects(service.get("profile")):
        limits.update(profile)
    width = service.get("width") or body.get("width")
    height = service.get("height") or body.get("height")
    scale = 1.0
    if positive(width) and positive(height):
        max_width = limits.get("maxWidth")
        max_height = limits.get("maxHeight") or max_width
        max_area = limits.get("maxArea")
        if positive(max_width):
            scale = min(scale, max_width / width)
        if positive(max_height):
            scale = min(scale, max_height / height)
        if positive(max_area):
            scale = min(scale, math.sqrt(max_area / (width * height)))

    downloads = []
    seen = set()

    def add(name, size):
        link = image_request(base, size, quality)
        if link not in seen:
            downloads.append(option(name, link, image_source=base))
            seen.add(link)
        elif name == "Largest Available Image":
            next(download for download in downloads if download["url"] == link)["label"] = name

    if "level0" in signature:
        for size in objects(service.get("sizes")):
            if positive(size.get("width")) and positive(size.get("height")):
                w, h = int(size["width"]), int(size["height"])
                add(f"Image ({w} × {h})", f"{w},{h}" if version == 3 else f"{w},")
    else:
        for name, bound in (("Thumb", 150), ("Small", 800), ("Medium", 1200), ("Large", 2000)):
            # Width syntax is required at level 1; !w,h is only required at level 2.
            w = bound
            if positive(width) and positive(height):
                w = max(1, int(width * min(scale, bound / max(width, height))))
            add(f"{name} Image", f"{w},")

    if version == 3 or (version == 2 and "level0" in signature and scale < 1):
        add("Largest Available Image", "max")
    elif scale < 1 and positive(width):
        add("Largest Available Image", f"{max(1, int(width * scale))},")
    else:
        add("Full Resolution Image", "full")
    return downloads


def renderings(node, **metadata):
    result = []
    for rendering in objects(node.get("rendering")):
        url = identifier(rendering)
        if url:
            mime = rendering.get("format") or "application/octet-stream"
            result.append(
                option(label(rendering.get("label"), "Download file"), url, mime, **metadata)
            )
    return result


def image_bodies(value):
    for body in objects(value):
        kind = body.get("type") or body.get("@type")
        if kind in ("Choice", "oa:Choice"):
            yield from image_bodies(body.get("default"))
            yield from image_bodies(body.get("items") or body.get("item"))
        elif kind == "SpecificResource":
            yield from image_bodies(body.get("source"))
        elif kind in ("Image", "dctypes:Image") or str(body.get("format", "")).startswith("image/"):
            yield body


def manifest_downloads(manifest, manifest_url):
    """Read v2's sequences or v3's ordered canvases and their painting images."""
    if not isinstance(manifest, dict):
        return []
    downloads = renderings(manifest)
    sequences = objects(manifest.get("sequences"))
    canvases = (
        [canvas for sequence in sequences for canvas in objects(sequence.get("canvases"))]
        if sequences
        else objects(manifest.get("items"))
    )
    occurrences = {}
    for index, canvas in enumerate(canvases, 1):
        metadata = {
            "canvas_id": identifier(canvas) or f"{manifest_url}#canvas-{index}",
            "canvas_label": label(canvas.get("label"), f"Page {index}"),
        }
        downloads.extend(renderings(canvas, **metadata))
        annotations = objects(canvas.get("images"))
        for page in objects(canvas.get("items")):
            annotations.extend(objects(page.get("items")))
        bodies = []
        for annotation in annotations:
            motivation = annotation.get("motivation", "painting")
            motivations = motivation if isinstance(motivation, list) else [motivation]
            if not any(m in ("painting", "sc:painting") for m in motivations):
                continue
            bodies.extend(image_bodies(annotation.get("body") or annotation.get("resource")))
        for number, body in enumerate(bodies, 1):
            services = objects(body.get("service"))
            images = []
            for service in services:
                signature = str(
                    [service.get("type"), service.get("@context"), service.get("profile")]
                )
                if "ImageService" not in signature and "/image/" not in signature:
                    continue
                url = identifier(service)
                if url:
                    images = image_downloads(url, service, body)
                    break
            if not images and identifier(body):
                images = [
                    option(
                        "Download Image",
                        identifier(body),
                        body.get("format") or "image/jpeg",
                        image_source=identifier(body),
                    )
                ]
            source = images[0]["image_source"] if images else None
            occurrence = occurrences.get(source, 0)
            if source:
                occurrences[source] = occurrence + 1
            for image in images:
                image["image_occurrences"] = [occurrence]
                if len(bodies) > 1:
                    image["label"] = f"Image {number}: {image['label']}"
                downloads.append({**image, **metadata})
    seen = {}
    unique = []
    for download in downloads:
        key = (download.get("canvas_id"), download["url"])
        if key not in seen:
            unique.append({**download, "iiif_resource_url": manifest_url})
            seen[key] = unique[-1]
        elif download.get("image_occurrences"):
            seen[key].setdefault("image_occurrences", []).extend(download["image_occurrences"])
    return unique

import html
from urllib.parse import quote


def resource_viewer_html(base_url: str, resource_id: str, embed: bool) -> str:
    base_url = base_url.rstrip("/").removesuffix("/api/v1")
    record_url = f"{base_url}/api/v1/resources/{quote(resource_id, safe='')}/metadata/ogm"
    escaped_record_url = html.escape(record_url, quote=True)
    escaped_id = html.escape(resource_id)

    script_url = html.escape(f"{base_url}/api/v1/viewer-assets/ogm-viewer.js", quote=True)

    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OGM Viewer - Resource {escaped_id}</title>
    <style>
        body {{
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }}
        .viewer-container {{
            width: 100vw;
            height: 100vh;
        }}
        {".viewer-container { height: 600px; }" if embed else ""}
    </style>
</head>
<body>
    <div class="viewer-container">
        <ogm-viewer light-basemap="https://tiles.openfreemap.org/styles/positron" dark-basemap="https://tiles.openfreemap.org/styles/positron"
            record-url="{escaped_record_url}"
            >
        </ogm-viewer>
    </div>

    <!-- Load the OGM Viewer web component -->
    <script type="module" src="{script_url}"></script>
</body>
</html>
"""

from pathlib import Path

import requests
import urllib3


def _plugin_version() -> str:
    metadata_path = Path(__file__).with_name("metadata.txt")
    try:
        for line in metadata_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("version="):
                return line.split("=", 1)[1].strip()
    except OSError:
        pass
    return "unknown"


class BtaaApiClient:
    def __init__(self, base_url="https://lib-btaageoapi-dev-app-01.oit.umn.edu/api/v1"):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        plugin_version = _plugin_version()
        self.session.headers.update(
            {
                "User-Agent": f"BTAA-QGIS-Plugin/{plugin_version}",
                "X-BTAA-Client-Name": "qgis-plugin",
                "X-BTAA-Client-Version": plugin_version,
                "X-BTAA-Client-Channel": "desktop",
            }
        )

        # Disable SSL verification for local dev or misconfigured servers safely
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        self.session.verify = False

    def get_facets(self):
        url = f"{self.base_url}/search"
        response = self.session.get(
            url, params={"q": "", "per_page": 1, "include_filters[dct_accessRights_s][]": "Public"}
        )
        response.raise_for_status()
        return response.json()

    def search(self, params):
        url = f"{self.base_url}/search"
        if "include_filters[dct_accessRights_s][]" not in params:
            params["include_filters[dct_accessRights_s][]"] = "Public"
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def get_thumbnail(self, url):
        response = self.session.get(url)
        response.raise_for_status()
        return response.content

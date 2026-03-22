import requests
import urllib3

class BtaaApiClient:
    def __init__(self, base_url="https://lib-btaageoapi-dev-app-01.oit.umn.edu/api/v1"):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        
        # Disable SSL verification for local dev or misconfigured servers safely
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        self.session.verify = False

    def get_facets(self):
        url = f"{self.base_url}/search"
        response = self.session.get(url, params={"q": "", "per_page": 1})
        response.raise_for_status()
        return response.json()

    def search(self, params):
        url = f"{self.base_url}/search"
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()
        
    def get_thumbnail(self, url):
        response = self.session.get(url)
        response.raise_for_status()
        return response.content

import requests
import json
from IPython.display import HTML, display

url = 'https://lib-btaageoapi-dev-app-01.oit.umn.edu/api/v1/search'
headers = {'accept': 'application/json'}

# ============================================================================
# Step 1: Start with a simple text search
# ============================================================================
print("=" * 70)
print("STEP 1: Text search for 'maps'")
print("=" * 70)

params_step1 = {
    'q': 'maps',
    'page': 1,
    'per_page': 10
}

response_step1 = requests.get(url, params=params_step1, headers=headers)

if response_step1.status_code == 200:
    data_step1 = response_step1.json()
    total_count_step1 = data_step1.get('meta', {}).get('totalCount', 'N/A')
    
    print(f"\nQuery: q='maps'")
    print(f"\nTotal number of resources found: {total_count_step1}")
    
    titles_step1 = [item['attributes'].get('dct_title_s', 'N/A') for item in data_step1.get('data', [])]
    
    html_list_step1 = "<ol>\n"
    for title in titles_step1:
        html_list_step1 += f"  <li>{title}</li>\n"
    html_list_step1 += "</ol>"
    
    print("\nList of titles:")
    display(HTML(html_list_step1))
else:
    print(f"Error: {response_step1.status_code}")
    print(response_step1.text)

# ============================================================================
# Step 2: Add bbox (bounding box) filter for Minnesota state boundaries
# ============================================================================
print("\n\n" + "=" * 70)
print("STEP 2: Add bbox filter - Limit results to Minnesota state boundaries")
print("=" * 70)

# Minnesota state bounding box (approximate)
# Top-left (northwest): ~49.0°N, -97.2°W
# Bottom-right (southeast): ~43.5°N, -89.5°W

params_step2 = {
    'q': 'maps',  # Same text search
    'include_filters[geo][type]': 'bbox',
    'include_filters[geo][field]': 'dcat_bbox',
    'include_filters[geo][top_left][lat]': '49.0',  # Northwest corner
    'include_filters[geo][top_left][lon]': '-97.2',
    'include_filters[geo][bottom_right][lat]': '43.5',  # Southeast corner
    'include_filters[geo][bottom_right][lon]': '-89.5',
    'page': 1,
    'per_page': 10
}

response_step2 = requests.get(url, params=params_step2, headers=headers)

if response_step2.status_code == 200:
    data_step2 = response_step2.json()
    total_count_step2 = data_step2.get('meta', {}).get('totalCount', 'N/A')
    
    print(f"\nQuery: q='maps'")
    print(f"Geo filter: Bounding box covering Minnesota state")
    print(f"  - Type: bbox")
    print(f"  - Field: dcat_bbox")
    print(f"  - Top-left (NW): 49.0°N, -97.2°W")
    print(f"  - Bottom-right (SE): 43.5°N, -89.5°W")
    print(f"\nTotal number of resources found: {total_count_step2}")
    
    # Show comparison with previous step
    if isinstance(total_count_step1, int) and isinstance(total_count_step2, int):
        difference = total_count_step1 - total_count_step2
        percentage = (difference / total_count_step1 * 100) if total_count_step1 > 0 else 0
        print(f"Results narrowed by: {difference} resources ({percentage:.1f}% reduction)")
        print(f"  (from {total_count_step1} to {total_count_step2})")
    
    titles_step2 = [item['attributes'].get('dct_title_s', 'N/A') for item in data_step2.get('data', [])]
    
    html_list_step2 = "<ol>\n"
    for title in titles_step2:
        html_list_step2 += f"  <li>{title}</li>\n"
    html_list_step2 += "</ol>"
    
    print("\nList of titles:")
    display(HTML(html_list_step2))
else:
    print(f"Error: {response_step2.status_code}")
    print(response_step2.text)

# ============================================================================
# Summary
# ============================================================================
print("\n\n" + "=" * 70)
print("SUMMARY: BBox Spatial Filtering")
print("=" * 70)
print(f"Step 1 (text search only):        {total_count_step1} results")
print(f"Step 2 (text + bbox filter):        {total_count_step2} results")
print("\nThe bbox filter narrows results to resources whose bounding boxes")
print("intersect with the specified rectangular area (Minnesota state)!")


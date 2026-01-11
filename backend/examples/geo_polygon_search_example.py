import requests
import json
from IPython.display import HTML, display

url = 'https://lib-btaageoapi-dev-app-01.oit.umn.edu/api/v1/search'
headers = {'accept': 'application/json'}

# ============================================================================
# Step 1: Start with a simple text search
# ============================================================================
print("=" * 70)
print("STEP 1: Text search for 'water'")
print("=" * 70)

params_step1 = {
    'q': 'water',
    'page': 1,
    'per_page': 10
}

response_step1 = requests.get(url, params=params_step1, headers=headers)

if response_step1.status_code == 200:
    data_step1 = response_step1.json()
    total_count_step1 = data_step1.get('meta', {}).get('totalCount', 'N/A')
    
    print(f"\nQuery: q='water'")
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
# Step 2: Add geo polygon filter for Colorado state boundaries
# ============================================================================
print("\n\n" + "=" * 70)
print("STEP 2: Add geo polygon filter - Limit results to Colorado state")
print("=" * 70)

# Colorado state boundaries (rectangular approximation)
# Northwest: 41.0°N, -109.0°W
# Northeast: 41.0°N, -102.0°W
# Southeast: 37.0°N, -102.0°W
# Southwest: 37.0°N, -109.0°W

params_step2 = {
    'q': 'water',  # Same text search
    'include_filters[geo][type]': 'polygon',
    'include_filters[geo][field]': 'locn_geometry',
    'include_filters[geo][relation]': 'intersects',
    # Polygon points (must be in order to form a closed polygon)
    'include_filters[geo][points][0][lat]': '41.0',  # Northwest corner
    'include_filters[geo][points][0][lon]': '-109.0',
    'include_filters[geo][points][1][lat]': '41.0',  # Northeast corner
    'include_filters[geo][points][1][lon]': '-102.0',
    'include_filters[geo][points][2][lat]': '37.0',  # Southeast corner
    'include_filters[geo][points][2][lon]': '-102.0',
    'include_filters[geo][points][3][lat]': '37.0',  # Southwest corner
    'include_filters[geo][points][3][lon]': '-109.0',
    'page': 1,
    'per_page': 10
}

response_step2 = requests.get(url, params=params_step2, headers=headers)

if response_step2.status_code == 200:
    data_step2 = response_step2.json()
    total_count_step2 = data_step2.get('meta', {}).get('totalCount', 'N/A')
    
    print(f"\nQuery: q='water'")
    print(f"Geo filter: Polygon covering Colorado state boundaries")
    print(f"  - Type: polygon")
    print(f"  - Field: locn_geometry")
    print(f"  - Relation: intersects")
    print(f"  - Bounding box: 37°N to 41°N, -109°W to -102°W")
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
print("SUMMARY: Progressive Spatial Filtering")
print("=" * 70)
print(f"Step 1 (text search only):        {total_count_step1} results")
print(f"Step 2 (text + geo polygon):       {total_count_step2} results")
print("\nThe geo polygon filter narrows results to resources that intersect")
print("with the specified geographic area (Colorado state boundaries)!")


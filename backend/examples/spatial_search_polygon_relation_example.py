import requests
import json
from IPython.display import HTML, display

url = 'https://lib-btaageoapi-dev-app-01.oit.umn.edu/api/v1/search'
headers = {'accept': 'application/json'}

# ============================================================================
# Step 1: Start with a simple text search
# ============================================================================
print("=" * 70)
print("STEP 1: Text search for 'geology'")
print("=" * 70)

params_step1 = {
    'q': 'geology',
    'page': 1,
    'per_page': 10
}

response_step1 = requests.get(url, params=params_step1, headers=headers)

if response_step1.status_code == 200:
    data_step1 = response_step1.json()
    total_count_step1 = data_step1.get('meta', {}).get('totalCount', 'N/A')
    
    print(f"\nQuery: q='geology'")
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
# Step 2: Add polygon filter with "within" relation
# ============================================================================
print("\n\n" + "=" * 70)
print("STEP 2: Add polygon filter with 'within' relation - Wisconsin state")
print("=" * 70)

# Wisconsin state boundaries (rectangular approximation)
# Northwest: 47.0°N, -92.9°W
# Northeast: 47.0°N, -86.8°W
# Southeast: 42.5°N, -86.8°W
# Southwest: 42.5°N, -92.9°W
# 
# Relation options: intersects (default), within, contains, disjoint
# "within" means the resource geometry must be completely inside the polygon

params_step2 = {
    'q': 'geology',  # Same text search
    'include_filters[geo][type]': 'polygon',
    'include_filters[geo][field]': 'locn_geometry',
    'include_filters[geo][relation]': 'within',  # Resource must be within the polygon
    # Polygon points (must be in order to form a closed polygon)
    'include_filters[geo][points][0][lat]': '47.0',  # Northwest corner
    'include_filters[geo][points][0][lon]': '-92.9',
    'include_filters[geo][points][1][lat]': '47.0',  # Northeast corner
    'include_filters[geo][points][1][lon]': '-86.8',
    'include_filters[geo][points][2][lat]': '42.5',  # Southeast corner
    'include_filters[geo][points][2][lon]': '-86.8',
    'include_filters[geo][points][3][lat]': '42.5',  # Southwest corner
    'include_filters[geo][points][3][lon]': '-92.9',
    'page': 1,
    'per_page': 10
}

response_step2 = requests.get(url, params=params_step2, headers=headers)

if response_step2.status_code == 200:
    data_step2 = response_step2.json()
    total_count_step2 = data_step2.get('meta', {}).get('totalCount', 'N/A')
    
    print(f"\nQuery: q='geology'")
    print(f"Geo filter: Polygon covering Wisconsin state boundaries")
    print(f"  - Type: polygon")
    print(f"  - Field: locn_geometry")
    print(f"  - Relation: within (resource geometry must be completely inside polygon)")
    print(f"  - Bounding box: 42.5°N to 47.0°N, -92.9°W to -86.8°W")
    print(f"\nNote: Relation options include:")
    print(f"  - 'intersects' (default): Resource overlaps with polygon")
    print(f"  - 'within': Resource is completely inside polygon")
    print(f"  - 'contains': Resource completely contains polygon")
    print(f"  - 'disjoint': Resource does not overlap with polygon")
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
print("SUMMARY: Polygon Spatial Filtering with Relation")
print("=" * 70)
print(f"Step 1 (text search only):        {total_count_step1} results")
print(f"Step 2 (text + polygon 'within'):  {total_count_step2} results")
print("\nThe polygon filter with 'within' relation narrows results to")
print("resources whose geometries are completely contained within the")
print("specified polygon (Wisconsin state boundaries)!")


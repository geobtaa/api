import requests
import json
from IPython.display import HTML, display

url = 'https://lib-btaageoapi-dev-app-01.oit.umn.edu/api/v1/search'
headers = {'accept': 'application/json'}

# ============================================================================
# Step 1: Start with a simple text search
# ============================================================================
print("=" * 70)
print("STEP 1: Text search for 'census'")
print("=" * 70)

params_step1 = {
    'q': 'census',
    'page': 1,
    'per_page': 10
}

response_step1 = requests.get(url, params=params_step1, headers=headers)

if response_step1.status_code == 200:
    data_step1 = response_step1.json()
    total_count_step1 = data_step1.get('meta', {}).get('totalCount', 'N/A')
    
    print(f"\nQuery: q='census'")
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
# Step 2: Add shape envelope filter for Illinois state
# ============================================================================
print("\n\n" + "=" * 70)
print("STEP 2: Add shape envelope filter - Limit results to Illinois state")
print("=" * 70)

# Illinois state bounding box (envelope format)
# Top-left (northwest): ~42.5°N, -91.5°W
# Bottom-right (southeast): ~37.0°N, -87.5°W
#
# Shape envelope uses coordinates in [lon, lat] format
# Envelope coordinates: [[top_left_lon, top_left_lat], [bottom_right_lon, bottom_right_lat]]

params_step2 = {
    'q': 'census',  # Same text search
    'include_filters[geo][type]': 'shape',
    'include_filters[geo][field]': 'locn_geometry',
    'include_filters[geo][relation]': 'intersects',
    # Shape envelope coordinates: [lon, lat] format
    'include_filters[geo][shape][type]': 'envelope',
    'include_filters[geo][shape][coordinates][0][0]': '-91.5',  # Top-left lon
    'include_filters[geo][shape][coordinates][0][1]': '42.5',   # Top-left lat
    'include_filters[geo][shape][coordinates][1][0]': '-87.5',   # Bottom-right lon
    'include_filters[geo][shape][coordinates][1][1]': '37.0',    # Bottom-right lat
    'page': 1,
    'per_page': 10
}

response_step2 = requests.get(url, params=params_step2, headers=headers)

if response_step2.status_code == 200:
    data_step2 = response_step2.json()
    total_count_step2 = data_step2.get('meta', {}).get('totalCount', 'N/A')
    
    print(f"\nQuery: q='census'")
    print(f"Geo filter: Shape envelope covering Illinois state")
    print(f"  - Type: shape")
    print(f"  - Shape type: envelope")
    print(f"  - Field: locn_geometry")
    print(f"  - Relation: intersects")
    print(f"  - Envelope coordinates:")
    print(f"    - Top-left: [-91.5°W, 42.5°N]")
    print(f"    - Bottom-right: [-87.5°W, 37.0°N]")
    print(f"\nNote: Shape envelope is similar to bbox but uses [lon, lat] coordinate")
    print(f"format and is processed as a geo_shape query rather than geo_bounding_box.")
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
print("SUMMARY: Shape/Envelope Spatial Filtering")
print("=" * 70)
print(f"Step 1 (text search only):        {total_count_step1} results")
print(f"Step 2 (text + shape envelope):    {total_count_step2} results")
print("\nThe shape envelope filter narrows results to resources that intersect")
print("with the specified envelope area (Illinois state boundaries)!")


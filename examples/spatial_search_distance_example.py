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
# Step 2: Add distance (radius) filter from Minneapolis center
# ============================================================================
print("\n\n" + "=" * 70)
print("STEP 2: Add distance filter - 50km radius from Minneapolis center")
print("=" * 70)

# Minneapolis center coordinates: ~44.9778°N, -93.2650°W
# Distance: 50km radius

params_step2 = {
    'q': 'water',  # Same text search
    'include_filters[geo][type]': 'distance',
    'include_filters[geo][field]': 'dcat_centroid',
    'include_filters[geo][center][lat]': '44.9778',  # Minneapolis center
    'include_filters[geo][center][lon]': '-93.2650',
    'include_filters[geo][distance]': '50km',  # 50 kilometer radius
    'page': 1,
    'per_page': 10
}

response_step2 = requests.get(url, params=params_step2, headers=headers)

if response_step2.status_code == 200:
    data_step2 = response_step2.json()
    total_count_step2 = data_step2.get('meta', {}).get('totalCount', 'N/A')
    
    print(f"\nQuery: q='water'")
    print(f"Geo filter: Distance/radius search from Minneapolis")
    print(f"  - Type: distance")
    print(f"  - Field: dcat_centroid")
    print(f"  - Center: 44.9778°N, -93.2650°W (Minneapolis)")
    print(f"  - Distance: 50km radius")
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
print("SUMMARY: Distance/Radius Spatial Filtering")
print("=" * 70)
print(f"Step 1 (text search only):        {total_count_step1} results")
print(f"Step 2 (text + distance filter):   {total_count_step2} results")
print("\nThe distance filter narrows results to resources whose centroids")
print("are within the specified radius (50km) from the center point!")


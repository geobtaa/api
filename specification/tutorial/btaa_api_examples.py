import requests
import json
import argparse
import sys

BASE_URL = "https://lib-btaageoapi-dev-app-01.oit.umn.edu/api/v1"

def example_1():
    """1. Simple Search"""
    print("\n--- Example 1: Simple Search ---\n")
    # Step 1: Text search for 'water'
    params = {
        'q': 'water',
        'page': 1,
        'per_page': 10
    }

    print(f"Requesting: {BASE_URL}/search with params: {params}")
    response = requests.get(f"{BASE_URL}/search", params=params)
    data = response.json()

    print(f"Total number of resources found: {data.get('meta', {}).get('totalCount')}")

    print("\nList of titles:")
    for item in data.get('data', []):
        print(f"  - {item['attributes'].get('ogm', {}).get('dct_title_s', 'N/A')}")

def example_2():
    """2. Obtain a Resource"""
    print("\n--- Example 2: Obtain a Resource ---\n")
    # Step 2: Fetch a specific resource
    resource_id = "ark28722-s7vs38"
    print(f"Requesting: {BASE_URL}/resources/{resource_id}")
    response = requests.get(f"{BASE_URL}/resources/{resource_id}")
    data = response.json()

    attrs = data['data']['attributes']['ogm']
    print(f"Title: {attrs.get('dct_title_s', 'N/A')}")
    print(f"Description: {attrs.get('dct_description_sm', ['N/A'])[0]}")

    # Show references
    if 'dct_references_s' in attrs:
        refs = json.loads(attrs['dct_references_s'])
        for key, value in refs.items():
            print(f"{key}: {value}")

def example_3():
    """3. Boolean Search"""
    print("\n--- Example 3: Boolean Search ---\n")
    # Step 3: Boolean search
    params = {
        'q': '(water AND ice) NOT Forest',
        'page': 1,
        'per_page': 10
    }

    print(f"Requesting: {BASE_URL}/search with params: {params}")
    response = requests.get(f"{BASE_URL}/search", params=params)
    data = response.json()

    print(f"Total number of resources found: {data.get('meta', {}).get('totalCount')}")

    print("\nList of titles:")
    for item in data.get('data', []):
        print(f"  - {item['attributes'].get('ogm', {}).get('dct_title_s', 'N/A')}")

def example_4():
    """4. Field-Directed Search"""
    print("\n--- Example 4: Field-Directed Search ---\n")
    # Step 4: Field-directed search
    params = {
        'q': 'Transportation',
        'search_field': 'dct_subject_sm',
        'page': 1,
        'per_page': 10
    }

    print(f"Requesting: {BASE_URL}/search with params: {params}")
    response = requests.get(f"{BASE_URL}/search", params=params)
    data = response.json()

    print(f"Total number of resources found: {data.get('meta', {}).get('totalCount')}")

    print("\nList of titles:")
    for item in data.get('data', []):
        print(f"  - {item['attributes'].get('ogm', {}).get('dct_title_s', 'N/A')}")

def example_5():
    """5. Faceted Search"""
    print("\n--- Example 5: Faceted Search (Maps) ---\n")
    # Step 5: Faceted search (Maps only)
    params = {
        'q': 'seattle',
        'include_filters[gbl_resourceClass_sm][]': 'Maps',
        'page': 1,
        'per_page': 10
    }

    print(f"Requesting: {BASE_URL}/search with params: {params}")
    response = requests.get(f"{BASE_URL}/search", params=params)
    data = response.json()

    print(f"Total Maps Found: {data.get('meta', {}).get('totalCount')}")

    print("\nList of titles:")
    for item in data.get('data', []):
        print(f"  - {item['attributes'].get('ogm', {}).get('dct_title_s', 'N/A')}")

def example_6():
    """6. Faceted Search (Includes)"""
    print("\n--- Example 6: Faceted Search (Maps + Washington) ---\n")
    # Step 6: Faceted search (Maps + Washington)
    params = {
        'q': 'seattle',
        'include_filters[gbl_resourceClass_sm][]': 'Maps',
        'include_filters[dct_spatial_sm][]': 'Washington',
        'page': 1,
        'per_page': 10
    }

    print(f"Requesting: {BASE_URL}/search with params: {params}")
    response = requests.get(f"{BASE_URL}/search", params=params)
    data = response.json()

    print(f"Total Found: {data.get('meta', {}).get('totalCount')}")

    print("\nList of titles:")
    for item in data.get('data', []):
        print(f"  - {item['attributes'].get('ogm', {}).get('dct_title_s', 'N/A')}")

def example_7():
    """7. Faceted Search (Excludes)"""
    print("\n--- Example 7: Faceted Search (Maps + Washington - PSU) ---\n")
    # Step 7: Faceted search (Maps + Washington - PSU)
    params = {
        'q': 'seattle',
        'include_filters[gbl_resourceClass_sm][]': 'Maps',
        'include_filters[dct_spatial_sm][]': 'Washington',
        'exclude_filters[schema_provider_s][]': 'Pennsylvania State University',
        'page': 1,
        'per_page': 10
    }

    print(f"Requesting: {BASE_URL}/search with params: {params}")
    response = requests.get(f"{BASE_URL}/search", params=params)
    data = response.json()

    print(f"Total Found: {data.get('meta', {}).get('totalCount')}")

    print("\nList of titles:")
    for item in data.get('data', []):
        print(f"  - {item['attributes'].get('ogm', {}).get('dct_title_s', 'N/A')}")

def example_8():
    """8. Spatial Search (BBox)"""
    print("\n--- Example 8: Spatial Search (BBox) ---\n")
    # Step 8: Bounding Box Search (Minnesota)
    params = {
        'q': 'maps',
        'include_filters[geo][type]': 'bbox',
        'include_filters[geo][field]': 'dcat_bbox',
        'include_filters[geo][top_left][lat]': '49.0',
        'include_filters[geo][top_left][lon]': '-97.2',
        'include_filters[geo][bottom_right][lat]': '43.5',
        'include_filters[geo][bottom_right][lon]': '-89.5',
        'page': 1,
        'per_page': 10
    }

    print(f"Requesting: {BASE_URL}/search with params: {params}")
    response = requests.get(f"{BASE_URL}/search", params=params)
    data = response.json()

    print(f"Total Found: {data.get('meta', {}).get('totalCount')}")

    print("\nList of titles:")
    for item in data.get('data', []):
        print(f"  - {item['attributes'].get('dct_title_s', 'N/A')}")

def example_9():
    """9. Spatial Search (Distance)"""
    print("\n--- Example 9: Spatial Search (Distance) ---\n")
    # Step 9: Distance Search (50km from Minneapolis)
    params = {
        'q': 'parks',
        'include_filters[geo][type]': 'distance',
        'include_filters[geo][field]': 'dcat_centroid',
        'include_filters[geo][center][lat]': '44.9778',
        'include_filters[geo][center][lon]': '-93.2650',
        'include_filters[geo][distance]': '50km',
        'page': 1,
        'per_page': 10
    }

    print(f"Requesting: {BASE_URL}/search with params: {params}")
    response = requests.get(f"{BASE_URL}/search", params=params)
    data = response.json()

    print(f"Total Found: {data.get('meta', {}).get('totalCount')}")

    print("\nList of titles:")
    for item in data.get('data', []):
        print(f"  - {item['attributes'].get('dct_title_s', 'N/A')}")

def example_10():
    """10. Spatial Search (Polygon)"""
    print("\n--- Example 10: Spatial Search (Polygon) ---\n")
    # Step 10: Polygon Search (Colorado)
    params = {
        'q': 'water',
        'include_filters[geo][type]': 'polygon',
        'include_filters[geo][field]': 'locn_geometry',
        'include_filters[geo][relation]': 'intersects',
        'include_filters[geo][points][0][lat]': '41.0',
        'include_filters[geo][points][0][lon]': '-109.0',
        'include_filters[geo][points][1][lat]': '41.0',
        'include_filters[geo][points][1][lon]': '-102.0',
        'include_filters[geo][points][2][lat]': '37.0',
        'include_filters[geo][points][2][lon]': '-102.0',
        'include_filters[geo][points][3][lat]': '37.0',
        'include_filters[geo][points][3][lon]': '-109.0',
        'page': 1,
        'per_page': 10
    }

    print(f"Requesting: {BASE_URL}/search with params: {params}")
    response = requests.get(f"{BASE_URL}/search", params=params)
    data = response.json()

    print(f"Total Found: {data.get('meta', {}).get('totalCount')}")

    print("\nList of titles:")
    for item in data.get('data', []):
        print(f"  - {item['attributes'].get('dct_title_s', 'N/A')}")

def example_11():
    """11. Advanced Search (adv_q)"""
    print("\n--- Example 11: Advanced Search (Maps + 'Island' - 'antarctica') ---\n")
    # Step 11: Advanced Search with adv_q
    # Logic: (ResourceClass=Maps AND Title=Island) NOT Title=Antarctica
    adv_query = [
        {"op": "AND", "f": "gbl_resourceClass_sm", "q": "Maps"},
        {"op": "AND", "f": "dct_title_s", "q": "Island"},
        {"op": "NOT", "f": "dct_title_s", "q": "antarctica"}
    ]

    params = {
        'q': '',
        'adv_q': json.dumps(adv_query),
        'page': 1,
        'per_page': 10
    }

    print(f"Requesting: {BASE_URL}/search with params: {params}")
    response = requests.get(f"{BASE_URL}/search", params=params)
    data = response.json()

    print(f"Total Found: {data.get('meta', {}).get('totalCount')}")

    print("\nList of titles:")
    for item in data.get('data', []):
        print(f"  - {item['attributes'].get('ogm', {}).get('dct_title_s', 'N/A')}")

def main():
    parser = argparse.ArgumentParser(description="Run BTAA Geoportal API Examples")
    parser.add_argument(
        "example", 
        nargs="?", 
        default="all", 
        help="The example number to run (1-11) or 'all' to run all examples."
    )
    args = parser.parse_args()

    examples = {
        "1": example_1,
        "2": example_2,
        "3": example_3,
        "4": example_4,
        "5": example_5,
        "6": example_6,
        "7": example_7,
        "8": example_8,
        "9": example_9,
        "10": example_10,
        "11": example_11
    }

    print("Starting BTAA Geoportal API Examples...")

    if args.example.lower() == "all":
        for key in sorted(examples.keys(), key=int):
            examples[key]()
    elif args.example in examples:
        examples[args.example]()
    else:
        print(f"Invalid example number: {args.example}")
        print("Please choose a number between 1 and 11, or 'all'.")
        sys.exit(1)

    print("\nCompleted.")

if __name__ == "__main__":
    main()

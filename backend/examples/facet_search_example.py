"""
Facet Search Endpoint Example

This example demonstrates the /search/facets/{facet_name} endpoint features:
- Basic facet retrieval with sorting
- Pagination
- Filtering facet values (q_facet)
- Search context (facet counts reflect filtered resultsets)
- Multiple facet fields

HOW TO RUN LOCALLY:
==================

1. Make sure your local API server is running:
   $ uvicorn main:app --reload
   (Server should be running on http://localhost:8000)

2. Install required dependencies:
   $ pip install requests
   (For Jupyter notebook support: pip install ipython)

3. Run as a Python script:
   $ python examples/facet_search_example.py

4. Or run in a Jupyter notebook:
   $ jupyter notebook
   (Then open and run this file)

5. To use a different server, change the base_url variable below.
"""

import requests
import json

# Try to import IPython display for Jupyter notebooks, fallback for regular Python
try:
    from IPython.display import HTML, display
    HAS_IPYTHON = True
except ImportError:
    HAS_IPYTHON = False
    # Fallback display function for regular Python
    def display(html):
        print(html)

def display_table(headers, rows):
    """Display a table, using HTML in Jupyter or plain text in regular Python."""
    if HAS_IPYTHON:
        html_table = "<table border='1' style='border-collapse: collapse;'>\n"
        html_table += "  <tr>" + "".join(f"<th>{h}</th>" for h in headers) + "</tr>\n"
        for row in rows:
            html_table += "  <tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>\n"
        html_table += "</table>"
        display(HTML(html_table))
    else:
        # Calculate column widths
        col_widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                col_widths[i] = max(col_widths[i], len(str(cell)))
        
        # Print header
        header_row = " | ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers))
        print(header_row)
        print("-" * len(header_row))
        
        # Print rows
        for row in rows:
            print(" | ".join(str(cell).ljust(col_widths[i]) for i, cell in enumerate(row)))

# Configure base URL - change this to your local server if running locally
# Local: 'http://localhost:8000/api/v1'
# Dev: 'https://lib-btaageoapi-dev-app-01.oit.umn.edu/api/v1'
base_url = 'http://localhost:8000/api/v1'  # Change this to match your setup
headers = {'accept': 'application/json'}

# ============================================================================
# Step 1: Basic facet retrieval - Get provider facets
# ============================================================================
print("=" * 70)
print("STEP 1: Basic facet retrieval - Get provider facets (default: count_desc)")
print("=" * 70)

facet_url = f'{base_url}/search/facets/schema_provider_s'

params_step1 = {
    'page': 1,
    'per_page': 10
}

response_step1 = requests.get(facet_url, params=params_step1, headers=headers)

if response_step1.status_code == 200:
    data_step1 = response_step1.json()
    meta_step1 = data_step1.get('meta', {})
    total_count_step1 = meta_step1.get('totalCount', 'N/A')
    total_pages_step1 = meta_step1.get('totalPages', 'N/A')
    current_page_step1 = meta_step1.get('currentPage', 'N/A')
    sort_step1 = meta_step1.get('sort', 'N/A')
    
    print(f"\nFacet: schema_provider_s")
    print(f"Sort: {sort_step1} (default)")
    print(f"Page: {current_page_step1} of {total_pages_step1}")
    print(f"\nTotal number of facet values: {total_count_step1}")
    
    facet_values_step1 = []
    for item in data_step1.get('data', []):
        attrs = item.get('attributes', {})
        facet_values_step1.append({
            'label': attrs.get('label', 'N/A'),
            'hits': attrs.get('hits', 'N/A')
        })
    
    print("\nTop 10 providers (sorted by count, descending):")
    display_table(
        ['Provider', 'Count'],
        [[fv['label'], fv['hits']] for fv in facet_values_step1]
    )
else:
    print(f"Error: {response_step1.status_code}")
    print(response_step1.text)

# ============================================================================
# Step 2: Sort alphabetically (ascending)
# ============================================================================
print("\n\n" + "=" * 70)
print("STEP 2: Sort alphabetically (ascending)")
print("=" * 70)

params_step2 = {
    'page': 1,
    'per_page': 10,
    'sort': 'alpha_asc'
}

response_step2 = requests.get(facet_url, params=params_step2, headers=headers)

if response_step2.status_code == 200:
    data_step2 = response_step2.json()
    meta_step2 = data_step2.get('meta', {})
    sort_step2 = meta_step2.get('sort', 'N/A')
    
    print(f"\nFacet: schema_provider_s")
    print(f"Sort: {sort_step2}")
    
    facet_values_step2 = []
    for item in data_step2.get('data', []):
        attrs = item.get('attributes', {})
        facet_values_step2.append({
            'label': attrs.get('label', 'N/A'),
            'hits': attrs.get('hits', 'N/A')
        })
    
    print("\nTop 10 providers (sorted alphabetically, ascending):")
    display_table(
        ['Provider', 'Count'],
        [[fv['label'], fv['hits']] for fv in facet_values_step2]
    )
else:
    print(f"Error: {response_step2.status_code}")
    print(response_step2.text)

# ============================================================================
# Step 3: Filter facet values with q_facet (search within facets)
# ============================================================================
print("\n\n" + "=" * 70)
print("STEP 3: Filter facet values - Search for providers containing 'University'")
print("=" * 70)

params_step3 = {
    'page': 1,
    'per_page': 10,
    'sort': 'count_desc',
    'q_facet': 'University'  # Filter facet values to only those containing "University"
}

response_step3 = requests.get(facet_url, params=params_step3, headers=headers)

if response_step3.status_code == 200:
    data_step3 = response_step3.json()
    meta_step3 = data_step3.get('meta', {})
    total_count_step3 = meta_step3.get('totalCount', 'N/A')
    
    print(f"\nFacet: schema_provider_s")
    print(f"Filter: q_facet='University'")
    print(f"Sort: count_desc")
    print(f"\nTotal matching facet values: {total_count_step3}")
    
    facet_values_step3 = []
    for item in data_step3.get('data', []):
        attrs = item.get('attributes', {})
        facet_values_step3.append({
            'label': attrs.get('label', 'N/A'),
            'hits': attrs.get('hits', 'N/A')
        })
    
    print("\nProviders containing 'University' (sorted by count):")
    display_table(
        ['Provider', 'Count'],
        [[fv['label'], fv['hits']] for fv in facet_values_step3]
    )
else:
    print(f"Error: {response_step3.status_code}")
    print(response_step3.text)

# ============================================================================
# Step 4: Pagination - Get second page
# ============================================================================
print("\n\n" + "=" * 70)
print("STEP 4: Pagination - Get second page of providers")
print("=" * 70)

params_step4 = {
    'page': 2,
    'per_page': 10,
    'sort': 'count_desc'
}

response_step4 = requests.get(facet_url, params=params_step4, headers=headers)

if response_step4.status_code == 200:
    data_step4 = response_step4.json()
    meta_step4 = data_step4.get('meta', {})
    current_page_step4 = meta_step4.get('currentPage', 'N/A')
    total_pages_step4 = meta_step4.get('totalPages', 'N/A')
    links_step4 = data_step4.get('links', {})
    
    print(f"\nFacet: schema_provider_s")
    print(f"Page: {current_page_step4} of {total_pages_step4}")
    print(f"Per page: 10")
    print(f"\nPagination links:")
    print(f"  Self: {links_step4.get('self', 'N/A')}")
    print(f"  First: {links_step4.get('first', 'N/A')}")
    print(f"  Last: {links_step4.get('last', 'N/A')}")
    print(f"  Prev: {links_step4.get('prev', 'N/A')}")
    print(f"  Next: {links_step4.get('next', 'N/A')}")
    
    facet_values_step4 = []
    for item in data_step4.get('data', []):
        attrs = item.get('attributes', {})
        facet_values_step4.append({
            'label': attrs.get('label', 'N/A'),
            'hits': attrs.get('hits', 'N/A')
        })
    
    print("\nProviders on page 2 (sorted by count):")
    display_table(
        ['Provider', 'Count'],
        [[fv['label'], fv['hits']] for fv in facet_values_step4]
    )
else:
    print(f"Error: {response_step4.status_code}")
    print(response_step4.text)

# ============================================================================
# Step 5: Facet values within a search context - Filter by search query
# ============================================================================
print("\n\n" + "=" * 70)
print("STEP 5: Facet values within search context - Providers for 'water' search")
print("=" * 70)

params_step5 = {
    'q': 'water',  # Search query to filter the resultset
    'page': 1,
    'per_page': 10,
    'sort': 'count_desc'
}

response_step5 = requests.get(facet_url, params=params_step5, headers=headers)

if response_step5.status_code == 200:
    data_step5 = response_step5.json()
    meta_step5 = data_step5.get('meta', {})
    total_count_step5 = meta_step5.get('totalCount', 'N/A')
    
    print(f"\nFacet: schema_provider_s")
    print(f"Search context: q='water'")
    print(f"Sort: count_desc")
    print(f"\nTotal providers in 'water' search resultset: {total_count_step5}")
    
    # Compare with step 1 (no search context)
    if isinstance(total_count_step1, int) and isinstance(total_count_step5, int):
        difference = total_count_step1 - total_count_step5
        print(f"\nComparison:")
        print(f"  Without search filter: {total_count_step1} providers")
        print(f"  With 'water' filter:   {total_count_step5} providers")
        print(f"  Difference: {difference} providers")
    
    facet_values_step5 = []
    for item in data_step5.get('data', []):
        attrs = item.get('attributes', {})
        facet_values_step5.append({
            'label': attrs.get('label', 'N/A'),
            'hits': attrs.get('hits', 'N/A')
        })
    
    print("\nTop providers for 'water' search (sorted by count):")
    display_table(
        ['Provider', "Count (in 'water' results)"],
        [[fv['label'], fv['hits']] for fv in facet_values_step5]
    )
else:
    print(f"Error: {response_step5.status_code}")
    print(response_step5.text)

# ============================================================================
# Step 6: Facet values with include_filters - Show providers for specific spatial coverage
# ============================================================================
print("\n\n" + "=" * 70)
print("STEP 6: Facet values with include_filters - Providers for 'Minnesota' resources")
print("=" * 70)

params_step6 = {
    'include_filters[dct_spatial_sm][]': 'Minnesota',  # Filter by spatial coverage
    'page': 1,
    'per_page': 10,
    'sort': 'count_desc'
}

response_step6 = requests.get(facet_url, params=params_step6, headers=headers)

if response_step6.status_code == 200:
    data_step6 = response_step6.json()
    meta_step6 = data_step6.get('meta', {})
    total_count_step6 = meta_step6.get('totalCount', 'N/A')
    
    print(f"\nFacet: schema_provider_s")
    print(f"Filter: include_filters[dct_spatial_sm][]='Minnesota'")
    print(f"Sort: count_desc")
    print(f"\nTotal providers for Minnesota resources: {total_count_step6}")
    
    # Compare with step 1 (no filters)
    if isinstance(total_count_step1, int) and isinstance(total_count_step6, int):
        difference = total_count_step1 - total_count_step6
        print(f"\nComparison:")
        print(f"  Without filters:        {total_count_step1} providers")
        print(f"  With Minnesota filter:   {total_count_step6} providers")
        print(f"  Difference: {difference} providers")
    
    facet_values_step6 = []
    for item in data_step6.get('data', []):
        attrs = item.get('attributes', {})
        facet_values_step6.append({
            'label': attrs.get('label', 'N/A'),
            'hits': attrs.get('hits', 'N/A')
        })
    
    print("\nTop providers for Minnesota resources (sorted by count):")
    display_table(
        ['Provider', 'Count (Minnesota resources)'],
        [[fv['label'], fv['hits']] for fv in facet_values_step6]
    )
else:
    print(f"Error: {response_step6.status_code}")
    print(response_step6.text)

# ============================================================================
# Step 7: Different facet field - Get spatial coverage facets
# ============================================================================
print("\n\n" + "=" * 70)
print("STEP 7: Different facet field - Get spatial coverage facets")
print("=" * 70)

spatial_facet_url = f'{base_url}/search/facets/dct_spatial_sm'

params_step7 = {
    'page': 1,
    'per_page': 15,
    'sort': 'count_desc'
}

response_step7 = requests.get(spatial_facet_url, params=params_step7, headers=headers)

if response_step7.status_code == 200:
    data_step7 = response_step7.json()
    meta_step7 = data_step7.get('meta', {})
    total_count_step7 = meta_step7.get('totalCount', 'N/A')
    facet_name_step7 = meta_step7.get('facetName', 'N/A')
    
    print(f"\nFacet: {facet_name_step7}")
    print(f"Sort: count_desc")
    print(f"Per page: 15")
    print(f"\nTotal spatial coverage values: {total_count_step7}")
    
    facet_values_step7 = []
    for item in data_step7.get('data', []):
        attrs = item.get('attributes', {})
        facet_values_step7.append({
            'label': attrs.get('label', 'N/A'),
            'hits': attrs.get('hits', 'N/A')
        })
    
    print("\nTop 15 spatial coverage values (sorted by count):")
    display_table(
        ['Spatial Coverage', 'Count'],
        [[fv['label'], fv['hits']] for fv in facet_values_step7]
    )
else:
    print(f"Error: {response_step7.status_code}")
    print(response_step7.text)

# ============================================================================
# Step 8: Sort options comparison - Show all sort options
# ============================================================================
print("\n\n" + "=" * 70)
print("STEP 8: Sort options comparison - Show all available sort options")
print("=" * 70)

sort_options = ['count_desc', 'count_asc', 'alpha_asc', 'alpha_desc']
sort_results = {}

for sort_option in sort_options:
    params = {
        'page': 1,
        'per_page': 5,  # Just show top 5 for comparison
        'sort': sort_option
    }
    
    response = requests.get(facet_url, params=params, headers=headers)
    if response.status_code == 200:
        data = response.json()
        values = []
        for item in data.get('data', []):
            attrs = item.get('attributes', {})
            values.append({
                'label': attrs.get('label', 'N/A'),
                'hits': attrs.get('hits', 'N/A')
            })
        sort_results[sort_option] = values

print("\nComparison of sort options (top 5 providers):")
print("\n" + "-" * 70)

for sort_option, values in sort_results.items():
    print(f"\nSort: {sort_option}")
    display_table(
        ['Provider', 'Count'],
        [[v['label'], v['hits']] for v in values]
    )

# ============================================================================
# Summary
# ============================================================================
print("\n\n" + "=" * 70)
print("SUMMARY: Facet Endpoint Features")
print("=" * 70)
print("\nThe /search/facets/{facet_name} endpoint provides:")
print("  1. Basic facet retrieval with default sorting (count_desc)")
print("  2. Multiple sort options: count_desc, count_asc, alpha_asc, alpha_desc")
print("  3. Pagination support with page and per_page parameters")
print("  4. Filtering facet values with q_facet parameter")
print("  5. Search context support - facet counts reflect filtered resultsets")
print("  6. Filter context support - use include_filters/exclude_filters")
print("  7. Works with any facet field (schema_provider_s, dct_spatial_sm, etc.)")
print("\nThis enables building Zappos-style facet interfaces where users can:")
print("  - View top N facet values")
print("  - Click 'View more' to paginate through all values")
print("  - Sort by count or alphabetically")
print("  - Search/filter the facet list to narrow down options")
print("  - See how facet counts change based on current search/filter context")


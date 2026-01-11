import requests
import json
from IPython.display import HTML, display

url = 'https://lib-btaageoapi-dev-app-01.oit.umn.edu/api/v1/search'
headers = {'accept': 'application/json'}

# ============================================================================
# Step 1: Start with a single clause query
# ============================================================================
print("=" * 70)
print("STEP 1: Single clause - Find resources with 'Iowa' in the title")
print("=" * 70)

adv_q_step1 = [
    {"op": "AND", "f": "dct_title_s", "q": "Iowa"}
]

params_step1 = {
    'adv_q': json.dumps(adv_q_step1),
    'page': 1,
    'per_page': 10
}

response_step1 = requests.get(url, params=params_step1, headers=headers)

if response_step1.status_code == 200:
    data_step1 = response_step1.json()
    total_count_step1 = data_step1.get('meta', {}).get('totalCount', 'N/A')
    
    print(f"\nQuery clauses: {json.dumps(adv_q_step1, indent=2)}")
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
# Step 2: Add a NOT clause to exclude certain results
# ============================================================================
print("\n\n" + "=" * 70)
print("STEP 2: Add NOT clause - Exclude resources with 'Wisconsin' in the title")
print("=" * 70)

adv_q_step2 = [
    {"op": "AND", "f": "dct_title_s", "q": "Iowa"},
    {"op": "NOT", "f": "dct_title_s", "q": "Wisconsin"}
]

params_step2 = {
    'adv_q': json.dumps(adv_q_step2),
    'page': 1,
    'per_page': 10
}

response_step2 = requests.get(url, params=params_step2, headers=headers)

if response_step2.status_code == 200:
    data_step2 = response_step2.json()
    total_count_step2 = data_step2.get('meta', {}).get('totalCount', 'N/A')
    
    print(f"\nQuery clauses: {json.dumps(adv_q_step2, indent=2)}")
    print(f"\nTotal number of resources found: {total_count_step2}")
    
    # Show comparison with previous step
    if isinstance(total_count_step1, int) and isinstance(total_count_step2, int):
        difference = total_count_step1 - total_count_step2
        print(f"Results narrowed by: {difference} resources (from {total_count_step1} to {total_count_step2})")
    
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
# Step 3: Add another AND clause to further narrow results
# ============================================================================
print("\n\n" + "=" * 70)
print("STEP 3: Add another AND clause - Require 'Water' in the description")
print("=" * 70)

adv_q_step3 = [
    {"op": "AND", "f": "dct_title_s", "q": "Iowa"},
    {"op": "NOT", "f": "dct_title_s", "q": "Wisconsin"},
    {"op": "AND", "f": "dct_description_sm", "q": "Water"}
]

params_step3 = {
    'adv_q': json.dumps(adv_q_step3),
    'page': 1,
    'per_page': 10
}

response_step3 = requests.get(url, params=params_step3, headers=headers)

if response_step3.status_code == 200:
    data_step3 = response_step3.json()
    total_count_step3 = data_step3.get('meta', {}).get('totalCount', 'N/A')
    
    print(f"\nQuery clauses: {json.dumps(adv_q_step3, indent=2)}")
    print(f"\nTotal number of resources found: {total_count_step3}")
    
    # Show comparison with previous steps
    if isinstance(total_count_step2, int) and isinstance(total_count_step3, int):
        difference = total_count_step2 - total_count_step3
        print(f"Results narrowed by: {difference} resources (from {total_count_step2} to {total_count_step3})")
    
    if isinstance(total_count_step1, int) and isinstance(total_count_step3, int):
        total_difference = total_count_step1 - total_count_step3
        print(f"Total refinement: {total_difference} resources removed from initial query (from {total_count_step1} to {total_count_step3})")
    
    titles_step3 = [item['attributes'].get('dct_title_s', 'N/A') for item in data_step3.get('data', [])]
    
    html_list_step3 = "<ol>\n"
    for title in titles_step3:
        html_list_step3 += f"  <li>{title}</li>\n"
    html_list_step3 += "</ol>"
    
    print("\nList of titles:")
    display(HTML(html_list_step3))
else:
    print(f"Error: {response_step3.status_code}")
    print(response_step3.text)

# ============================================================================
# Summary
# ============================================================================
print("\n\n" + "=" * 70)
print("SUMMARY: Progressive Query Refinement")
print("=" * 70)
print(f"Step 1 (single clause):     {total_count_step1} results")
print(f"Step 2 (add NOT clause):    {total_count_step2} results")
print(f"Step 3 (add AND clause):    {total_count_step3} results")
print("\nEach additional clause in adv_q further refines the search results!")


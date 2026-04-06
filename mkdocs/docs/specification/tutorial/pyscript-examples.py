import json
from pyscript import Element
import pyodide_http
pyodide_http.patch_all()
import requests

BASE_URL = "https://lib-btaageoapi-dev-app-01.oit.umn.edu/api/v1"

def print_to_output(output_id, text):
    """Helper to append text to output area"""
    output = Element(output_id)
    current = output.element.innerText
    output.element.innerText = current + text + "\n"

def clear_output(output_id):
    """Clear output area"""
    Element(output_id).element.innerText = ""

def show_output(output_id):
    """Show output area"""
    Element(output_id).element.classList.add("visible")

def disable_button(btn_id):
    """Disable a button"""
    Element(btn_id).element.disabled = True

def enable_button(btn_id):
    """Enable a button"""
    Element(btn_id).element.disabled = False

def example_1(event):
    """Example 1: Basic Keyword Search"""
    output_id = "output-1"
    btn_id = "run-btn-1"
    
    try:
        disable_button(btn_id)
        clear_output(output_id)
        show_output(output_id)
        print_to_output(output_id, "🔄 Running Example 1: Basic Keyword Search for 'Seattle'...")
        
        response = requests.get(f"{BASE_URL}/search", params={"q": "seattle"})
        data = response.json()
        
        print_to_output(output_id, f"✅ Status: {response.status_code}")
        print_to_output(output_id, f"📊 Total Hits: {data.get('meta', {}).get('totalCount')}")
        print_to_output(output_id, f"🔗 URL: {response.url}")
        
        if data.get('data'):
            print_to_output(output_id, f"\n📍 First 3 results:")
            for i, item in enumerate(data['data'][:3], 1):
                title = item['attributes'].get('dct_title_s', 'No title')
                print_to_output(output_id, f"  {i}. {title}")
    except Exception as e:
        print_to_output(output_id, f"❌ Error: {str(e)}")
    finally:
        enable_button(btn_id)

def example_2(event):
    """Example 2: Filtering by Resource Class"""
    output_id = "output-2"
    btn_id = "run-btn-2"
    
    try:
        disable_button(btn_id)
        clear_output(output_id)
        show_output(output_id)
        print_to_output(output_id, "🔄 Running Example 2: Filtering for 'Maps'...")
        
        params = {
            "q": "seattle",
            "include_filters[gbl_resourceClass_sm][]": "Maps"
        }
        response = requests.get(f"{BASE_URL}/search", params=params)
        data = response.json()
        
        print_to_output(output_id, f"✅ Status: {response.status_code}")
        print_to_output(output_id, f"📊 Total Maps Found: {data.get('meta', {}).get('totalCount')}")
        
        if data.get('data'):
            print_to_output(output_id, f"\n🗺️ First 3 maps:")
            for i, item in enumerate(data['data'][:3], 1):
                title = item['attributes'].get('dct_title_s', 'No title')
                print_to_output(output_id, f"  {i}. {title}")
    except Exception as e:
        print_to_output(output_id, f"❌ Error: {str(e)}")
    finally:
        enable_button(btn_id)

def example_3(event):
    """Example 3: Pagination"""
    output_id = "output-3"
    btn_id = "run-btn-3"
    
    try:
        disable_button(btn_id)
        clear_output(output_id)
        show_output(output_id)
        print_to_output(output_id, "🔄 Running Example 3: Pagination (Page 2)...")
        
        params = {
            "q": "seattle",
            "page": 2,
            "per_page": 10
        }
        response = requests.get(f"{BASE_URL}/search", params=params)
        data = response.json()
        
        print_to_output(output_id, f"✅ Status: {response.status_code}")
        print_to_output(output_id, f"📄 Page: 2")
        print_to_output(output_id, f"📊 Items on this page: {len(data.get('data', []))}")
        
        if data.get('data'):
            print_to_output(output_id, f"\n📍 Results 11-13:")
            for i, item in enumerate(data['data'][:3], 11):
                title = item['attributes'].get('dct_title_s', 'No title')
                print_to_output(output_id, f"  {i}. {title}")
    except Exception as e:
        print_to_output(output_id, f"❌ Error: {str(e)}")
    finally:
        enable_button(btn_id)

def example_4(event):
    """Example 4: Sorting Results"""
    output_id = "output-4"
    btn_id = "run-btn-4"
    
    try:
        disable_button(btn_id)
        clear_output(output_id)
        show_output(output_id)
        print_to_output(output_id, "🔄 Running Example 4: Sorting by Year (Ascending)...")
        
        params = {
            "q": "seattle",
            "sort": "year_asc"
        }
        response = requests.get(f"{BASE_URL}/search", params=params)
        data = response.json()
        
        print_to_output(output_id, f"✅ Status: {response.status_code}")
        print_to_output(output_id, f"📊 Total Results: {data.get('meta', {}).get('totalCount')}")
        
        if data.get('data'):
            print_to_output(output_id, f"\n📅 First 3 results (oldest first):")
            for i, item in enumerate(data['data'][:3], 1):
                title = item['attributes'].get('dct_title_s', 'No title')
                year = item['attributes'].get('gbl_indexYear_im', ['Unknown'])[0] if item['attributes'].get('gbl_indexYear_im') else 'Unknown'
                print_to_output(output_id, f"  {i}. ({year}) {title}")
    except Exception as e:
        print_to_output(output_id, f"❌ Error: {str(e)}")
    finally:
        enable_button(btn_id)

def example_5(event):
    """Example 5: Fetching a Single Resource"""
    output_id = "output-5"
    btn_id = "run-btn-5"
    
    try:
        disable_button(btn_id)
        clear_output(output_id)
        show_output(output_id)
        resource_id = "p16022coll205:660"
        print_to_output(output_id, f"🔄 Running Example 5: Fetching Resource {resource_id}...")
        
        response = requests.get(f"{BASE_URL}/resources/{resource_id}")
        data = response.json()
        
        print_to_output(output_id, f"✅ Status: {response.status_code}")
        
        if data.get('data'):
            attrs = data['data']['attributes']
            print_to_output(output_id, f"\n📋 Resource Details:")
            print_to_output(output_id, f"  ID: {data['data']['id']}")
            print_to_output(output_id, f"  Title: {attrs.get('dct_title_s', 'N/A')}")
            print_to_output(output_id, f"  Issued: {attrs.get('dct_issued_s', 'N/A')}")
            print_to_output(output_id, f"  Publisher: {attrs.get('dct_publisher_sm', ['N/A'])[0] if attrs.get('dct_publisher_sm') else 'N/A'}")
    except Exception as e:
        print_to_output(output_id, f"❌ Error: {str(e)}")
    finally:
        enable_button(btn_id)

def example_6(event):
    """Example 6: Extracting the IIIF Manifest"""
    output_id = "output-6"
    btn_id = "run-btn-6"
    
    try:
        disable_button(btn_id)
        clear_output(output_id)
        show_output(output_id)
        resource_id = "p16022coll205:660"
        print_to_output(output_id, f"🔄 Running Example 6: Extracting IIIF Manifest for {resource_id}...")
        
        response = requests.get(f"{BASE_URL}/resources/{resource_id}")
        data = response.json()
        
        refs = json.loads(data['data']['attributes']['dct_references_s'])
        manifest = refs.get("http://iiif.io/api/presentation#manifest")
        
        print_to_output(output_id, f"✅ Status: {response.status_code}")
        print_to_output(output_id, f"\n🖼️ IIIF Manifest URL:")
        print_to_output(output_id, f"  {manifest if manifest else 'Not found'}")
    except Exception as e:
        print_to_output(output_id, f"❌ Error: {str(e)}")
    finally:
        enable_button(btn_id)

def example_7(event):
    """Example 7: Filtering by Year"""
    output_id = "output-7"
    btn_id = "run-btn-7"
    
    try:
        disable_button(btn_id)
        clear_output(output_id)
        show_output(output_id)
        print_to_output(output_id, "🔄 Running Example 7: Filtering by Year 1922...")
        
        params = {
            "include_filters[gbl_indexYear_im][]": 1922
        }
        response = requests.get(f"{BASE_URL}/search", params=params)
        data = response.json()
        
        print_to_output(output_id, f"✅ Status: {response.status_code}")
        print_to_output(output_id, f"📊 Maps from 1922: {data.get('meta', {}).get('totalCount')}")
        
        if data.get('data'):
            print_to_output(output_id, f"\n📅 First 3 maps from 1922:")
            for i, item in enumerate(data['data'][:3], 1):
                title = item['attributes'].get('dct_title_s', 'No title')
                print_to_output(output_id, f"  {i}. {title}")
    except Exception as e:
        print_to_output(output_id, f"❌ Error: {str(e)}")
    finally:
        enable_button(btn_id)

def example_8(event):
    """Example 8: Inspecting Bounding Boxes"""
    output_id = "output-8"
    btn_id = "run-btn-8"
    
    try:
        disable_button(btn_id)
        clear_output(output_id)
        show_output(output_id)
        print_to_output(output_id, "🔄 Running Example 8: Inspecting Bounding Boxes...")
        
        response = requests.get(f"{BASE_URL}/search", params={"q": "seattle"})
        data = response.json()
        
        print_to_output(output_id, f"✅ Status: {response.status_code}")
        
        if data.get('data'):
            print_to_output(output_id, f"\n🌍 Bounding boxes for first 3 results:")
            for i, item in enumerate(data['data'][:3], 1):
                title = item['attributes'].get('dct_title_s', 'No title')[:50]
                bbox = item['attributes'].get('dcat_bbox', 'N/A')
                print_to_output(output_id, f"  {i}. {title}...")
                print_to_output(output_id, f"     BBox: {bbox}")
    except Exception as e:
        print_to_output(output_id, f"❌ Error: {str(e)}")
    finally:
        enable_button(btn_id)

def example_9(event):
    """Example 9: Discovering Facets"""
    output_id = "output-9"
    btn_id = "run-btn-9"
    
    try:
        disable_button(btn_id)
        clear_output(output_id)
        show_output(output_id)
        print_to_output(output_id, "🔄 Running Example 9: Discovering Facets (Providers)...")
        
        response = requests.get(f"{BASE_URL}/search", params={"q": "minnesota"})
        data = response.json()
        
        print_to_output(output_id, f"✅ Status: {response.status_code}")
        print_to_output(output_id, f"\n🏛️ Providers found:")
        
        for item in data.get('included', []):
            if item['type'] == 'facet' and item['id'] == 'schema_provider_s':
                for facet_item in item['attributes']['items'][:5]:
                    label = facet_item['attributes']['label']
                    hits = facet_item['attributes']['hits']
                    print_to_output(output_id, f"  • {label} ({hits} items)")
                break
    except Exception as e:
        print_to_output(output_id, f"❌ Error: {str(e)}")
    finally:
        enable_button(btn_id)

def example_10(event):
    """Example 10: Finding Downloadable Content"""
    output_id = "output-10"
    btn_id = "run-btn-10"
    
    try:
        disable_button(btn_id)
        clear_output(output_id)
        show_output(output_id)
        print_to_output(output_id, "🔄 Running Example 10: Finding Downloadable Content...")
        
        params = {
            "q": "seattle",
            "include_filters[dct_accessRights_s][]": "Public"
        }
        response = requests.get(f"{BASE_URL}/search", params=params)
        data = response.json()
        
        print_to_output(output_id, f"✅ Status: {response.status_code}")
        print_to_output(output_id, f"📊 Public items found: {data.get('meta', {}).get('totalCount')}")
        print_to_output(output_id, f"\n💾 Downloadable items (first 3):")
        
        count = 0
        for item in data.get('data', []):
            if count >= 3:
                break
            try:
                refs = json.loads(item['attributes']['dct_references_s'])
                download_url = refs.get("http://schema.org/downloadUrl")
                if download_url:
                    title = item['attributes']['dct_title_s'][:50]
                    print_to_output(output_id, f"  {count + 1}. {title}...")
                    print_to_output(output_id, f"     URL: {download_url[:70]}...")
                    count += 1
            except:
                continue
                
        if count == 0:
            print_to_output(output_id, "  No downloadable items in first page of results")
    except Exception as e:
        print_to_output(output_id, f"❌ Error: {str(e)}")
    finally:
        enable_button(btn_id)

# Bind event handlers to buttons
Element("run-btn-1").element.onclick = example_1
Element("run-btn-2").element.onclick = example_2
Element("run-btn-3").element.onclick = example_3
Element("run-btn-4").element.onclick = example_4
Element("run-btn-5").element.onclick = example_5
Element("run-btn-6").element.onclick = example_6
Element("run-btn-7").element.onclick = example_7
Element("run-btn-8").element.onclick = example_8
Element("run-btn-9").element.onclick = example_9
Element("run-btn-10").element.onclick = example_10

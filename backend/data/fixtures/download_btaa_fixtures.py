#!/usr/bin/env python3
"""
Download BTAA fixture files from the links in btaa_fixtures_list.csv
Appends /raw to each link and downloads the files.
"""

import csv
import os
import sys
from pathlib import Path
from urllib.parse import urlparse
import requests
from urllib.parse import quote


def sanitize_filename(url, index):
    """Create a safe filename from URL or use index."""
    # Remove /raw from the end if present
    url_clean = url.replace('/raw', '').rstrip('/')
    
    # Extract the last part of the URL path (the record ID)
    parsed = urlparse(url_clean)
    path_parts = [p for p in parsed.path.split('/') if p]
    if path_parts:
        # Use the last part (record ID), but sanitize it
        name = path_parts[-1]
        # Replace problematic characters for filesystem
        name = name.replace(':', '_').replace('/', '_').replace('\\', '_')
        name = name.replace('?', '_').replace('*', '_').replace('|', '_')
        name = name.replace('<', '_').replace('>', '_').replace('"', '_')
        # Remove any query parameters or fragments
        name = name.split('?')[0].split('#')[0]
        # Limit length
        if len(name) > 150:
            name = name[:150]
        # Ensure it's not empty
        if name:
            return name
    return f"fixture_{index}"


def download_file(url, output_dir, index):
    """Download a file from URL and save it to output_dir."""
    try:
        print(f"Downloading {index}: {url}")
        response = requests.get(url, timeout=30, allow_redirects=True)
        response.raise_for_status()
        
        # Determine filename
        filename = sanitize_filename(url, index)
        
        # Try to get extension from Content-Type header
        content_type = response.headers.get('Content-Type', '')
        if 'json' in content_type:
            filename = f"{filename}.json"
        elif 'xml' in content_type:
            filename = f"{filename}.xml"
        elif 'html' in content_type:
            filename = f"{filename}.html"
        elif 'text' in content_type:
            filename = f"{filename}.txt"
        
        # If filename doesn't have extension, try to infer from URL
        if '.' not in filename:
            parsed = urlparse(url)
            if parsed.path.endswith('.json'):
                filename = f"{filename}.json"
            elif parsed.path.endswith('.xml'):
                filename = f"{filename}.xml"
        
        output_path = output_dir / filename
        
        # Handle duplicate filenames
        counter = 1
        original_path = output_path
        while output_path.exists():
            stem = original_path.stem
            suffix = original_path.suffix
            output_path = output_dir / f"{stem}_{counter}{suffix}"
            counter += 1
        
        # Save file
        with open(output_path, 'wb') as f:
            f.write(response.content)
        
        print(f"  Saved to: {output_path}")
        return True, output_path
        
    except requests.exceptions.RequestException as e:
        print(f"  Error downloading {url}: {e}")
        return False, None
    except Exception as e:
        print(f"  Unexpected error with {url}: {e}")
        return False, None


def main():
    # Get the directory where this script is located
    script_dir = Path(__file__).parent
    csv_file = script_dir / "btaa_fixtures_list.csv"
    output_dir = script_dir / "btaa_fixtures_data"
    
    # Create output directory
    output_dir.mkdir(exist_ok=True)
    print(f"Output directory: {output_dir}")
    
    # Read CSV and extract links
    links = []
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            link = row.get('Link to example', '').strip()
            if link:  # Only process non-empty links
                # Append /raw to the link
                raw_link = f"{link}/raw"
                links.append((raw_link, row.get('Title of Record', '')))
    
    print(f"\nFound {len(links)} links to download\n")
    
    # Download each file
    successful = 0
    failed = 0
    
    for index, (link, title) in enumerate(links, 1):
        success, path = download_file(link, output_dir, index)
        if success:
            successful += 1
        else:
            failed += 1
    
    print(f"\n{'='*60}")
    print(f"Download complete!")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Total: {len(links)}")


if __name__ == "__main__":
    main()

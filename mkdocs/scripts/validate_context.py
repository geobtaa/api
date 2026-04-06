#!/usr/bin/env python3
"""
Validation script for JSON-LD contexts.
"""

import json
import sys
import argparse
from pathlib import Path


def validate_context(context_file):
    """Validate JSON-LD context structure."""
    try:
        with open(context_file, 'r') as f:
            context = json.load(f)
        
        # Basic validation
        if "@context" not in context:
            print(f"ERROR: {context_file} - Missing @context key")
            return False
        
        context_obj = context["@context"]
        
        # Check for required namespaces
        required_namespaces = ["@vocab", "dc", "geo", "prov"]
        for ns in required_namespaces:
            if ns not in context_obj:
                print(f"WARNING: {context_file} - Missing namespace: {ns}")
        
        # Validate term definitions
        for term, definition in context_obj.items():
            if isinstance(definition, dict):
                if "@id" not in definition:
                    print(f"WARNING: {context_file} - Term '{term}' missing @id")
                if "@type" in definition and definition["@type"] not in ["@id", "@vocab"]:
                    print(f"WARNING: {context_file} - Term '{term}' has invalid @type: {definition['@type']}")
        
        print(f"✓ {context_file} - Context validation passed")
        return True
        
    except json.JSONDecodeError as e:
        print(f"ERROR: {context_file} - Invalid JSON: {e}")
        return False
    except Exception as e:
        print(f"ERROR: {context_file} - {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Validate JSON-LD contexts")
    parser.add_argument("input", help="Context file or directory to validate")
    parser.add_argument("--recursive", "-r", action="store_true", help="Recursively validate directories")
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    
    if input_path.is_file():
        success = validate_context(input_path)
        sys.exit(0 if success else 1)
    
    elif input_path.is_dir():
        if args.recursive:
            context_files = list(input_path.rglob("*.jsonld"))
        else:
            context_files = list(input_path.glob("*.jsonld"))
        
        if not context_files:
            print(f"No .jsonld files found in {input_path}")
            sys.exit(1)
        
        success_count = 0
        for context_file in context_files:
            if validate_context(context_file):
                success_count += 1
        
        print(f"\nValidation complete: {success_count}/{len(context_files)} contexts passed")
        sys.exit(0 if success_count == len(context_files) else 1)
    
    else:
        print(f"ERROR: {input_path} does not exist")
        sys.exit(1)


if __name__ == "__main__":
    main() 
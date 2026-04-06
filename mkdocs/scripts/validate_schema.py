#!/usr/bin/env python3
"""
Validation script for JSON data against JSON schemas.
"""

import json
import sys
import argparse
from pathlib import Path
from jsonschema import validate, ValidationError, SchemaError


def validate_data(schema_file, data_file):
    """Validate JSON data against a JSON schema."""
    try:
        # Load schema
        with open(schema_file, 'r') as f:
            schema = json.load(f)
        
        # Load data
        with open(data_file, 'r') as f:
            data = json.load(f)
        
        # Validate
        validate(instance=data, schema=schema)
        print(f"✓ {data_file} - Validation passed against {schema_file}")
        return True
        
    except json.JSONDecodeError as e:
        print(f"ERROR: {data_file} - Invalid JSON: {e}")
        return False
    except SchemaError as e:
        print(f"ERROR: {schema_file} - Invalid schema: {e}")
        return False
    except ValidationError as e:
        print(f"ERROR: {data_file} - Validation failed: {e.message}")
        print(f"  Path: {' -> '.join(str(p) for p in e.path)}")
        return False
    except Exception as e:
        print(f"ERROR: {data_file} - {e}")
        return False


def validate_schema_file(schema_file):
    """Validate that a JSON schema file is well-formed."""
    try:
        with open(schema_file, 'r') as f:
            schema = json.load(f)
        
        # Basic schema validation
        if "$schema" not in schema:
            print(f"WARNING: {schema_file} - Missing $schema field")
        
        if "$id" not in schema:
            print(f"WARNING: {schema_file} - Missing $id field")
        
        if "title" not in schema:
            print(f"WARNING: {schema_file} - Missing title field")
        
        if "description" not in schema:
            print(f"WARNING: {schema_file} - Missing description field")
        
        print(f"✓ {schema_file} - Schema validation passed")
        return True
        
    except json.JSONDecodeError as e:
        print(f"ERROR: {schema_file} - Invalid JSON: {e}")
        return False
    except Exception as e:
        print(f"ERROR: {schema_file} - {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Validate JSON data against JSON schemas")
    parser.add_argument("--schema", "-s", help="Schema file to use for validation")
    parser.add_argument("--data", "-d", help="Data file to validate")
    parser.add_argument("--validate-schemas", action="store_true", help="Validate schema files themselves")
    parser.add_argument("--recursive", "-r", action="store_true", help="Recursively process directories")
    
    args = parser.parse_args()
    
    if args.validate_schemas:
        # Validate schema files
        schema_dir = Path("schemas")
        if not schema_dir.exists():
            print("ERROR: schemas directory not found")
            sys.exit(1)
        
        if args.recursive:
            schema_files = list(schema_dir.rglob("*.json"))
        else:
            schema_files = list(schema_dir.glob("*.json"))
        
        if not schema_files:
            print("No .json schema files found")
            sys.exit(1)
        
        success_count = 0
        for schema_file in schema_files:
            if validate_schema_file(schema_file):
                success_count += 1
        
        print(f"\nSchema validation complete: {success_count}/{len(schema_files)} schemas passed")
        sys.exit(0 if success_count == len(schema_files) else 1)
    
    elif args.schema and args.data:
        # Validate specific data against specific schema
        success = validate_data(args.schema, args.data)
        sys.exit(0 if success else 1)
    
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main() 
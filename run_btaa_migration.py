#!/usr/bin/env python3
"""
Script to run the BTAA OGM Aardvark migration.

This script adds the BTAA-specific fields to the resources table
to support BTAA flavored OGM Aardvark records.
"""

import sys
import os
from pathlib import Path

# Add the project root directory to Python path
sys.path.append(str(Path(__file__).parent))

from db.migrations.add_btaa_ogm_fields import add_btaa_ogm_fields


def main():
    """Run the BTAA migration."""
    print("Starting BTAA OGM Aardvark migration...")
    
    try:
        add_btaa_ogm_fields()
        print("✅ BTAA migration completed successfully!")
    except Exception as e:
        print(f"❌ BTAA migration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

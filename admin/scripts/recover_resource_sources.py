"""Retired: Resource Source identity now comes from the managing Set."""

import sys


def main():
    print(
        "This command is retired. A Resource inherits its Source from its managing Set. "
        "Use link_resource_sets.py with a reviewed Set mapping; no changes were made.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())

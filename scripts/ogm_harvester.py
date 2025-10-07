#!/usr/bin/env python3
"""
OpenGeoMetadata Harvester

A Python implementation that mimics the GeoCombine::Harvester class for harvesting
Geoblacklight documents from OpenGeoMetadata repositories for indexing.
"""

import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, Generator, List, Optional, Tuple
from urllib.error import URLError
from urllib.request import urlopen


class OGMHarvester:
    """Harvests Geoblacklight documents from OpenGeoMetadata for indexing."""

    # Non-metadata repositories that shouldn't be harvested
    DENYLIST = [
        "GeoCombine",
        "aardvark",
        "metadata-issues",
        "ogm_utils-python",
        "opengeometadata.github.io",
        "opengeometadata-rails",
        "gbl-1_to_aardvark",
    ]

    # GitHub API endpoint for OpenGeoMetadata repositories
    OGM_API_URI = "https://api.github.com/orgs/opengeometadata/repos?per_page=1000"

    def __init__(
        self,
        ogm_path: Optional[str] = None,
        schema_version: str = "Aardvark",
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the harvester.

        Args:
            ogm_path: Path to store OpenGeoMetadata repositories (defaults to data/opengeometadata)
            schema_version: Schema version to filter for (defaults to "Aardvark")
            logger: Logger instance (defaults to basic logger)
        """
        self.ogm_path = ogm_path or os.path.join("data", "opengeometadata")
        self.schema_version = schema_version
        self.logger = logger or self._setup_logger()

        # Ensure the OGM path exists
        os.makedirs(self.ogm_path, exist_ok=True)

    def _setup_logger(self) -> logging.Logger:
        """Set up a basic logger if none provided."""
        logger = logging.getLogger("ogm_harvester")
        logger.setLevel(logging.INFO)

        if not logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        return logger

    def docs_to_index(self) -> Generator[Tuple[Dict, str], None, None]:
        """
        Enumerable of docs to index, for passing to an indexer.

        Yields:
            Tuple of (record, path) for each valid document found
        """
        self.logger.info(f"loading documents from {self.ogm_path}")

        ogm_path = Path(self.ogm_path)
        if not ogm_path.exists():
            self.logger.warning(f"OGM path does not exist: {self.ogm_path}")
            return

        for json_file in ogm_path.rglob("*.json"):
            # Skip layers.json files
            if json_file.name == "layers.json":
                self.logger.debug(f"skipping {json_file}; not a geoblacklight JSON document")
                continue

            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    doc = json.load(f)

                # Handle both single records and arrays of records
                records = [doc] if isinstance(doc, dict) else doc

                for record in records:
                    if not isinstance(record, dict):
                        continue

                    # Skip indexing if this record has a different schema version than what we want
                    record_schema = record.get("gbl_mdVersion_s") or record.get(
                        "geoblacklight_version"
                    )
                    record_id = record.get("layer_slug_s") or record.get("dc_identifier_s")

                    if record_schema != self.schema_version:
                        self.logger.debug(
                            f"skipping {record_id}; schema version {record_schema} "
                            f"doesn't match {self.schema_version}"
                        )
                        continue

                    self.logger.debug(f"found record {record_id} at {json_file}")
                    yield record, str(json_file)

            except (json.JSONDecodeError, IOError) as e:
                self.logger.error(f"Error reading {json_file}: {e}")
                continue

    def pull(self, repo: str) -> Optional[str]:
        """
        Update a repository via git.
        If the repository doesn't exist, clone it.

        Args:
            repo: Repository name

        Returns:
            Repository name if successful, None otherwise
        """
        repo_path = os.path.join(self.ogm_path, repo)

        if not os.path.isdir(repo_path):
            return self.clone(repo)

        try:
            # Change to repo directory and pull
            original_cwd = os.getcwd()
            os.chdir(repo_path)

            subprocess.run(["git", "pull"], capture_output=True, text=True, check=True)

            self.logger.info(f"updated {repo}")
            return repo

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error pulling {repo}: {e}")
            return None
        finally:
            os.chdir(original_cwd)

    def pull_all(self) -> List[str]:
        """
        Update all repositories.

        Returns:
            List of repository names that were updated
        """
        updated = []
        for repo in self.repositories():
            result = self.pull(repo)
            if result:
                updated.append(result)

        self.logger.info(f"updated {len(updated)} repositories")
        return updated

    def clone(self, repo: str) -> Optional[str]:
        """
        Clone a repository via git.
        If the repository already exists, skip it.

        Args:
            repo: Repository name

        Returns:
            Repository name if successful, None otherwise
        """
        repo_path = os.path.join(self.ogm_path, repo)
        repo_url = f"https://github.com/OpenGeoMetadata/{repo}.git"

        # Skip if exists
        if os.path.isdir(repo_path):
            self.logger.warning(f"skipping clone to {repo_path}; directory exists")
            return None

        try:
            # Get repository info
            repo_info = self._repository_info(repo)

            # Warn if archived or empty
            if repo_info.get("archived"):
                self.logger.warning(f"repository is archived: {repo_url}")
            if repo_info.get("size", 0) == 0:
                self.logger.warning(f"repository is empty: {repo_url}")

            # Clone the repository
            subprocess.run(
                ["git", "clone", "--depth", "1", repo_url, repo_path],
                capture_output=True,
                text=True,
                check=True,
            )

            self.logger.info(f"cloned {repo_url} to {repo_path}")
            return repo

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error cloning {repo}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error getting info for {repo}: {e}")
            return None

    def clone_all(self) -> List[str]:
        """
        Clone all repositories via git.

        Returns:
            List of repository names that were cloned
        """
        cloned = []
        for repo in self.repositories():
            result = self.clone(repo)
            if result:
                cloned.append(result)

        self.logger.info(f"cloned {len(cloned)} repositories")
        return cloned

    def repositories(self) -> List[str]:
        """
        List of repository names to harvest.

        Returns:
            List of repository names
        """
        try:
            with urlopen(self.OGM_API_URI) as response:
                repos_data = json.loads(response.read().decode("utf-8"))

            # Filter repositories
            valid_repos = []
            for repo in repos_data:
                if repo["size"] > 0 and not repo["archived"] and repo["name"] not in self.DENYLIST:
                    valid_repos.append(repo["name"])

            return valid_repos

        except (URLError, json.JSONDecodeError) as e:
            self.logger.error(f"Error fetching repositories: {e}")
            return []

    def _repository_info(self, repo_name: str) -> Dict:
        """
        Get repository information from GitHub API.

        Args:
            repo_name: Repository name

        Returns:
            Repository information dictionary
        """
        url = f"https://api.github.com/repos/opengeometadata/{repo_name}"
        with urlopen(url) as response:
            return json.loads(response.read().decode("utf-8"))


def main():
    """Main function for command-line usage."""
    import argparse

    parser = argparse.ArgumentParser(description="OpenGeoMetadata Harvester")
    parser.add_argument(
        "--ogm-path",
        default=os.path.join("data", "opengeometadata"),
        help="Path to store OpenGeoMetadata repositories",
    )
    parser.add_argument("--schema-version", default="Aardvark", help="Schema version to filter for")
    parser.add_argument(
        "--action",
        choices=["clone", "pull", "list", "harvest"],
        default="harvest",
        help="Action to perform",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    # Set up logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    harvester = OGMHarvester(ogm_path=args.ogm_path, schema_version=args.schema_version)

    if args.action == "clone":
        harvester.clone_all()
    elif args.action == "pull":
        harvester.pull_all()
    elif args.action == "list":
        repos = harvester.repositories()
        print(f"Found {len(repos)} repositories:")
        for repo in repos:
            print(f"  - {repo}")
    elif args.action == "harvest":
        # Clone/pull repositories first
        harvester.pull_all()

        # Then harvest documents
        count = 0
        for record, path in harvester.docs_to_index():
            count += 1
            record_id = record.get("layer_slug_s") or record.get("dc_identifier_s")
            print(f"Harvested: {record_id} from {path}")

        print(f"Total documents harvested: {count}")


if __name__ == "__main__":
    main()

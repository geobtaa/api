"""BTAA Geo API CLI."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("btaa-geo-api-cli")
except PackageNotFoundError:
    __version__ = "0.1.0"

from collections.abc import Iterator
from typing import Any


def route_paths(route_owner: Any) -> list[str]:
    """Return registered route paths, including routes nested by include_router."""
    return [path for path, _route in routes_with_paths(route_owner)]


def route_by_path(route_owner: Any, path: str) -> Any | None:
    """Find a registered route by path, including nested include_router routes."""
    for route_path, route in routes_with_paths(route_owner):
        if route_path == path:
            return route
    return None


def routes_with_paths(route_owner: Any, prefix: str = "") -> Iterator[tuple[str, Any]]:
    for route in getattr(route_owner, "routes", []):
        route_prefix = getattr(route, "prefix", "") or ""
        nested_prefix = _join_route_path(prefix, route_prefix)

        path = getattr(route, "path", None)
        if isinstance(path, str):
            yield _join_route_path(prefix, path), route

        if getattr(route, "routes", None):
            yield from routes_with_paths(route, nested_prefix)


def _join_route_path(prefix: str, path: str) -> str:
    if not prefix:
        return path
    if not path:
        return prefix
    if path == prefix or path.startswith(f"{prefix.rstrip('/')}/"):
        return path
    return f"{prefix.rstrip('/')}/{path.lstrip('/')}"

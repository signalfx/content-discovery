"""Navigator API service for fetching and updating navigators."""

import sys
from typing import Dict, Any
from .base_service import do_get, do_put, do_post, RemoteNotFound
from .crosslink_service import update_crosslinks

# Server-managed fields that must be dropped before POSTing a fresh
# create — sending them either errors or seeds the new resource with
# the source env's metadata, both of which we want to avoid.
_CREATE_STRIP_FIELDS = ("id", "created", "creator", "lastUpdated", "lastUpdatedBy")


def fetch_navigator_export_by_id(navigator_id: str, base_url: str, token: str, format: str = "json") -> Any:
    """
    Fetch a navigator export by ID.
    
    Args:
        navigator_id: The navigator ID
        base_url: The base API URL
        token: The SignalFx access token
        format: Return format, either "json" or "text"
        
    Returns:
        The exported navigator data
        
    Raises:
        RemoteNotFound: If the navigator does not exist (HTTP 404)
        RuntimeError: For any other non-200 response
    """
    resp = do_get(f"{base_url}/v2/navigator/{navigator_id}/export", token)
    if resp.status_code == 404:
        raise RemoteNotFound(f"navigator {navigator_id} not found")
    if resp.status_code != 200:
        raise RuntimeError(f"Failed to fetch navigator {navigator_id}: {resp.text}")
    if format == "json":
        return resp.json()
    return resp.text


def create_navigator(
    navigator_export: Dict[str, Any], base_url: str, token: str
) -> Dict[str, Any]:
    """Create a navigator in the target env from a navigator export blob.

    Strips server-managed fields from the inner ``navigator`` object so
    the backend assigns a fresh id and timestamps rather than echoing
    the source env's. Returns the parsed response so callers can pick
    up the new id for an optional local write-back.
    """
    navigator = dict(navigator_export["navigatorExport"]["navigator"])
    for field in _CREATE_STRIP_FIELDS:
        navigator.pop(field, None)

    resp = do_post(f"{base_url}/v2/navigator", token, navigator)
    if resp.status_code not in (200, 201):
        raise RuntimeError(
            f"Failed to create navigator: {resp.status_code} {resp.text}"
        )
    return resp.json()


def update_navigator(navigator_export: Dict[str, Any], base_url: str, token: str) -> bool:
    """
    Update a navigator using the navigatorExport object.
    
    Args:
        navigator_export: The navigator export data
        base_url: The base API URL
        token: The SignalFx access token
        
    Returns:
        True if successful, False otherwise
    """
    navigator = navigator_export["navigatorExport"]["navigator"]
    navigator_id = navigator["id"]

    # Strict update: never silently auto-create on 404. A stale or
    # deleted navigator id must surface as a failure so the caller can
    # decide whether to invoke ``create`` explicitly.
    resp = do_put(f"{base_url}/v2/navigator/{navigator_id}", token, navigator)
    if resp.status_code in [200, 201]:
        print(f"  ✏️  Updated navigator: {navigator.get('name', navigator_id)}")
    elif resp.status_code == 404:
        print(
            f"  ❌ Navigator {navigator_id} not found in master; "
            f"use 'create' instead of 'update' / 'apply'",
            file=sys.stderr,
        )
        return False
    else:
        print(f"  ❌ Failed to update navigator {navigator_id}: {resp.text}", file=sys.stderr)
        return False
    
    # Update crosslinks if present (at root level, not under navigatorExport)
    crosslinks = navigator_export.get("crossLinkExports", [])
    if crosslinks:
        _, _, failed = update_crosslinks(crosslinks, base_url, token)
        if failed:
            print(f"  ❌ Failed to write {failed} crosslink(s) for navigator {navigator_id}", file=sys.stderr)
            return False
    
    return True

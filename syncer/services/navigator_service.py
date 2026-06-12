"""Navigator API service for fetching and updating navigators."""

import sys
from typing import Dict, Any
from .base_service import do_get, do_put, do_post, RemoteNotFound
from .crosslink_service import update_crosslinks

# Server-managed fields that must be dropped before POSTing a fresh
# create — sending them either errors or seeds the new resource with
# the source env's metadata, both of which we want to avoid.
_CREATE_STRIP_FIELDS = ("id", "created", "creator", "lastUpdated", "lastUpdatedBy")

# API quirk: the navigator export endpoint always returns these list
# fields as ``[]`` when empty, but PUT / POST reject ``[]`` with a
# server-side validation error of the form
# ``"metricClasses size must be between 1 and 10"`` or
# ``"metricColumns size must be between 1 and 50"``. The accepted way
# to represent "no entries" on write is ``null``. We coerce the empty
# lists to ``None`` immediately before sending, without mutating the
# in-memory export blob (so the local file we write back stays a
# faithful mirror of what the server returns on the next GET).
_EMPTY_LIST_TO_NULL_FIELDS = ("metricClasses", "metricColumns")


def _normalize_empty_lists_for_write(navigator: Dict[str, Any]) -> Dict[str, Any]:
    """Return a shallow copy of ``navigator`` with empty ``metricClasses``
    and ``metricColumns`` lists replaced by ``None``.

    See ``_EMPTY_LIST_TO_NULL_FIELDS`` for the why. Callers should always
    pass the normalized dict to PUT / POST and keep the original blob
    for any post-write local-file refresh.
    """
    normalized = dict(navigator)
    for field in _EMPTY_LIST_TO_NULL_FIELDS:
        value = normalized.get(field)
        if isinstance(value, list) and len(value) == 0:
            normalized[field] = None
    return normalized


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
    navigator = _normalize_empty_lists_for_write(navigator)

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
    payload = _normalize_empty_lists_for_write(navigator)

    # Strict update: never silently auto-create on 404. A stale or
    # deleted navigator id must surface as a failure so the caller can
    # decide whether to invoke ``create`` explicitly.
    resp = do_put(f"{base_url}/v2/navigator/{navigator_id}", token, payload)
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

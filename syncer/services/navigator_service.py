"""Navigator API service for fetching and updating navigators."""

from __future__ import annotations

import copy
import sys
from typing import Any, Dict, List
from .base_service import do_get, do_put, do_post, RemoteNotFound
from .crosslink_service import update_crosslinks

# Server-managed fields that must be dropped before POSTing a fresh
# create — sending them either errors or seeds the new resource with
# the source env's metadata, both of which we want to avoid.
_CREATE_STRIP_FIELDS = ("id", "created", "creator", "lastUpdated", "lastUpdatedBy")

# Crosslink-specific server-managed fields. ``id`` is included so the
# create path forces a fresh POST rather than a PUT against a source-env
# crosslink id that may not exist in the target.
_CROSSLINK_STRIP_FIELDS = ("id", "created", "creator", "lastUpdated", "lastUpdatedBy")


def _crosslinks_for_create(
    crosslink_exports: List[Dict[str, Any]],
    original_navigator_id: str | None,
    new_navigator_id: str,
) -> List[Dict[str, Any]]:
    """Rewrite ``crossLinkExports`` for the create flow.

    Deep-copies each entry, strips server-managed fields from the inner
    crosslink, and rewrites any ``targets[*].navigatorId`` that matches
    the source-env navigator id to the freshly-assigned target id. We
    only rewrite self-references — targets pointing at OTHER navigators
    must remain unchanged.

    Returns a new list suitable for :func:`update_crosslinks`.
    """
    rewritten: List[Dict[str, Any]] = []
    for entry in crosslink_exports or ():
        if not isinstance(entry, dict):
            continue
        entry = copy.deepcopy(entry)
        # Payload keys vary between snake_case and camelCase between exports.
        cl_key = "crosslink" if "crosslink" in entry else (
            "crossLink" if "crossLink" in entry else None
        )
        if not cl_key:
            continue
        crosslink = entry[cl_key]
        if not isinstance(crosslink, dict):
            continue
        for field in _CROSSLINK_STRIP_FIELDS:
            crosslink.pop(field, None)
        targets = crosslink.get("targets")
        if isinstance(targets, list) and original_navigator_id:
            for target in targets:
                if (
                    isinstance(target, dict)
                    and target.get("navigatorId") == original_navigator_id
                ):
                    target["navigatorId"] = new_navigator_id
        rewritten.append(entry)
    return rewritten


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
    the source env's, then writes any ``crossLinkExports`` from the
    same payload so the new navigator keeps its drilldowns and links.
    Self-referencing ``targets[*].navigatorId`` are rewritten to the
    new server-assigned id; targets pointing at other navigators are
    left untouched.

    Returns the parsed POST response so callers can pick up the new id
    for an optional local write-back.

    Raises:
        RuntimeError: If the navigator POST fails, or if any of the
            companion crosslink writes fail. The error message names
            the freshly-created navigator id so the caller can clean
            up or finish the sync manually.
    """
    original_navigator = navigator_export["navigatorExport"]["navigator"]
    original_navigator_id = original_navigator.get("id")

    navigator = dict(original_navigator)
    for field in _CREATE_STRIP_FIELDS:
        navigator.pop(field, None)

    resp = do_post(f"{base_url}/v2/navigator", token, navigator)
    if resp.status_code not in (200, 201):
        raise RuntimeError(
            f"Failed to create navigator: {resp.status_code} {resp.text}"
        )
    response = resp.json()
    new_navigator_id = response.get("id") if isinstance(response, dict) else None

    # Push the navigator's companion crosslinks. Mirrors
    # ``update_navigator`` so the create path doesn't silently leave
    # the new navigator without its drilldowns / links.
    crosslink_exports = navigator_export.get("crossLinkExports") or []
    if crosslink_exports and new_navigator_id:
        rewritten = _crosslinks_for_create(
            crosslink_exports, original_navigator_id, new_navigator_id
        )
        if rewritten:
            _, _, failed = update_crosslinks(rewritten, base_url, token)
            if failed:
                raise RuntimeError(
                    f"navigator {new_navigator_id} was created but "
                    f"{failed} crosslink(s) failed to write; "
                    "the new navigator may be missing drilldowns / links."
                )
    elif crosslink_exports and not new_navigator_id:
        # Defensive: shouldn't happen against a healthy API, but if
        # the POST succeeded without echoing an id we can't rewrite
        # the self-target references safely.
        print(
            "  ⚠️  Navigator create response did not include an id; "
            "skipping crosslink push to avoid pointing them at the "
            "wrong navigator. Run `update <path>` once the local file "
            "is refreshed to backfill the crosslinks.",
            file=sys.stderr,
        )

    return response


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

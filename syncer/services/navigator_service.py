"""Navigator API service for fetching and updating navigators."""

import sys
from typing import Dict, Any
from .base_service import do_get, do_put, do_post
from .crosslink_service import update_crosslinks


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
        RuntimeError: If the fetch fails
    """
    resp = do_get(f"{base_url}/v2/navigator/{navigator_id}/export", token)
    if resp.status_code != 200:
        raise RuntimeError(f"Failed to fetch navigator {navigator_id}: {resp.text}")
    if format == "json":
        return resp.json()
    return resp.text


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
    
    # Update the navigator itself
    resp = do_put(f"{base_url}/v2/navigator/{navigator_id}", token, navigator)
    if resp.status_code in [200, 201]:
        print(f"  ✏️  Updated navigator: {navigator.get('name', navigator_id)}")
    elif resp.status_code == 404:
        # Navigator doesn't exist, create it
        resp = do_post(f"{base_url}/v2/navigator", token, navigator)
        if resp.status_code in [200, 201]:
            print(f"  ➕ Created navigator: {navigator.get('name', navigator_id)}")
        else:
            print(f"  ❌ Failed to create navigator {navigator_id}: {resp.text}", file=sys.stderr)
            return False
    else:
        print(f"  ❌ Failed to update navigator {navigator_id}: {resp.text}", file=sys.stderr)
        return False
    
    # Update crosslinks if present (at root level, not under navigatorExport)
    crosslinks = navigator_export.get("crossLinkExports", [])
    if crosslinks:
        updated, created = update_crosslinks(crosslinks, base_url, token)
        # Silently handle crosslinks (counts included in update message)
    
    return True


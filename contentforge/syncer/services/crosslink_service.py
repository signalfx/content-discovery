"""Crosslink API service for fetching and updating crosslinks."""

import sys
from typing import Dict, Any, List
from .base_service import do_get, do_put, do_post


def fetch_crosslink_by_id(crosslink_id: str, base_url: str, token: str) -> Dict[str, Any]:
    """
    Fetch a crosslink by ID.
    
    Args:
        crosslink_id: The crosslink ID
        base_url: The base API URL
        token: The SignalFx access token
        
    Returns:
        The crosslink data
        
    Raises:
        RuntimeError: If the fetch fails
    """
    resp = do_get(f"{base_url}/v2/crosslink/{crosslink_id}", token)
    if resp.status_code != 200:
        raise RuntimeError(f"Failed to fetch crosslink {crosslink_id}: {resp.text}")
    return resp.json()


def update_crosslink(crosslink: Dict[str, Any], base_url: str, token: str) -> bool:
    """
    Update a crosslink.
    
    Args:
        crosslink: The crosslink data
        base_url: The base API URL
        token: The SignalFx access token
        
    Returns:
        True if successful, False otherwise
    """
    crosslink_id = crosslink.get("id")
    identifier = crosslink_id or crosslink.get("propertyName", "<unknown crosslink>")
    
    if not crosslink_id:
        resp = do_post(f"{base_url}/v2/crosslink", token, crosslink)
        if resp.status_code in [200, 201]:
            return True
        print(f"  ❌ Failed to create crosslink {identifier}: {resp.text}", file=sys.stderr)
        return False
    
    resp = do_put(f"{base_url}/v2/crosslink/{crosslink_id}", token, crosslink)
    if resp.status_code in [200, 201]:
        return True
    if resp.status_code == 404:
        # Crosslink doesn't exist, create it
        resp = do_post(f"{base_url}/v2/crosslink", token, crosslink)
        if resp.status_code in [200, 201]:
            return True
        print(f"  ❌ Failed to create crosslink {identifier}: {resp.text}", file=sys.stderr)
        return False
    
    print(f"  ❌ Failed to update crosslink {identifier}: {resp.text}", file=sys.stderr)
    return False


def update_crosslinks(
    crosslink_exports: List[Dict[str, Any]], base_url: str, token: str
) -> tuple[int, int, int]:
    """
    Update multiple crosslinks by comparing with remote state.
    
    Args:
        crosslink_exports: List of crosslink export objects
        base_url: The base API URL
        token: The SignalFx access token
        
    Returns:
        Tuple of (updated_count, created_count, failed_count)
    """
    updated_count = 0
    created_count = 0
    failed_count = 0
    
    for crosslink_export in crosslink_exports:
        # Exports vary between snake_case and camelCase payload keys, normalize here
        crosslink = crosslink_export.get("crosslink") or crosslink_export.get("crossLink")
        if not crosslink:
            continue
        
        crosslink_id = crosslink.get("id")
        if not crosslink_id:
            if update_crosslink(crosslink, base_url, token):
                print(f"  ➕ Created crosslink: {crosslink.get('propertyName', '<unnamed crosslink>')}")
                created_count += 1
            else:
                failed_count += 1
            continue
        
        # Fetch remote state to check if it changed
        try:
            remote_crosslink = fetch_crosslink_by_id(crosslink_id, base_url, token)
            
            # Compare local and remote
            if remote_crosslink != crosslink:
                # Crosslink has changed, update it
                if update_crosslink(crosslink, base_url, token):
                    print(f"  ✏️  Updated crosslink: {crosslink.get('propertyName', crosslink_id)}")
                    updated_count += 1
                else:
                    failed_count += 1
            # else: crosslink unchanged, skip
            
        except RuntimeError:
            # Crosslink doesn't exist, create it
            if update_crosslink(crosslink, base_url, token):
                print(f"  ➕ Created crosslink: {crosslink.get('propertyName', crosslink_id)}")
                created_count += 1
            else:
                failed_count += 1
    
    return updated_count, created_count, failed_count

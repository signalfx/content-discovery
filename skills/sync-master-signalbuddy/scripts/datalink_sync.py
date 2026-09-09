"""Crosslink API service for fetching and updating crosslinks."""

import sys
from pathlib import Path
from typing import Dict, Any, List

SFX_SCRIPT_DIR = Path(__file__).resolve().parents[2] / "sfx-api" / "scripts"
if str(SFX_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SFX_SCRIPT_DIR))

from sfx_http import RemoteNotFound
from sfx_client import create_object, get_object, prepare_payload, update_object


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
    return get_object("datalink", crosslink_id, base_url, token)


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
        try:
            create_object("datalink", crosslink, base_url, token)
            return True
        except RuntimeError as exc:
            print(f"  ❌ Failed to create crosslink {identifier}: {exc}", file=sys.stderr)
            return False

    payload = prepare_payload(crosslink)
    try:
        update_object("datalink", crosslink_id, payload, base_url, token)
        return True
    except RemoteNotFound:
        try:
            create_object("datalink", payload, base_url, token)
            return True
        except RuntimeError as exc:
            print(f"  ❌ Failed to create crosslink {identifier}: {exc}", file=sys.stderr)
            return False
    except RuntimeError as exc:
        print(f"  ❌ Failed to update crosslink {identifier}: {exc}", file=sys.stderr)
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
                print(
                    f"  ➕ Created crosslink: {crosslink.get('propertyName', '<unnamed crosslink>')}",
                    file=sys.stderr,
                )
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
                    print(
                        f"  ✏️  Updated crosslink: {crosslink.get('propertyName', crosslink_id)}",
                        file=sys.stderr,
                    )
                    updated_count += 1
                else:
                    failed_count += 1
            # else: crosslink unchanged, skip
            
        except RuntimeError:
            # Crosslink doesn't exist, create it
            if update_crosslink(crosslink, base_url, token):
                print(
                    f"  ➕ Created crosslink: {crosslink.get('propertyName', crosslink_id)}",
                    file=sys.stderr,
                )
                created_count += 1
            else:
                failed_count += 1
    
    return updated_count, created_count, failed_count

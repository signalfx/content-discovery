"""Shared utilities for syncer tools"""

import json
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

from services.base_service import do_get

SCRIPT_DIR = Path(__file__).parent


def get_realm_config() -> Optional[List[Dict[str, Any]]]:
    """Read realm configuration from .token file"""
    try:
        token_file = SCRIPT_DIR.parent / "syncer" / ".token"
        with open(token_file, 'r') as f:
            config = json.load(f)
        
        if isinstance(config, list):
            return config
        else:
            return None
    except (OSError, json.JSONDecodeError, KeyError):
        return None


def get_config_for_env(env_name: str) -> Optional[Dict[str, Any]]:
    """Get the configuration for a specific environment"""
    config = get_realm_config()
    if not config:
        return None
    
    for item in config:
        if item.get("env") == env_name:
            return item
    
    return None


def get_token_for_env(env_name: str) -> Optional[str]:
    """Get the access token for a specific environment"""
    env_config = get_config_for_env(env_name)
    if env_config and "token" in env_config:
        return env_config["token"]
    
    return None


def get_realm_for_env(env_name: str) -> Optional[str]:
    """Get the realm for a specific environment"""
    env_config = get_config_for_env(env_name)
    if env_config and "realm" in env_config:
        return env_config["realm"]
    
    return None


def fetch_organization_info(base_url: str, token: str) -> Optional[Dict[str, Any]]:
    """Fetch organization information from the API"""
    try:
        resp = do_get(f"{base_url}/v2/organization", token)
        if resp.status_code == 200:
            return resp.json()
        else:
            return None
    except Exception:
        return None


def get_changed_files() -> List[Tuple[str, Path]]:
    """Get list of modified JSON files using git status"""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=SCRIPT_DIR.parent,
            capture_output=True,
            text=True,
            check=True
        )
        
        changed_files = []
        for line in result.stdout.strip().split('\n'):
            if not line or not line.endswith('.json'):
                continue
                
            file_path = SCRIPT_DIR.parent / line
            if not file_path.exists():
                continue
            
            try:
                rel_path = file_path.relative_to(SCRIPT_DIR.parent)
                if 'navigators' in rel_path.parts:
                    changed_files.append(("navigator", file_path))
                elif 'group' in rel_path.parts:
                    changed_files.append(("group", file_path))
                elif 'detector' in rel_path.parts:
                    changed_files.append(("detector", file_path))
            except ValueError:
                continue
        
        return changed_files
    except subprocess.CalledProcessError:
        return []


def extract_resource_info(file_type: str, file_path: Path) -> Optional[Tuple[str, str]]:
    """Extract resource ID and name from a JSON file"""
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        if file_type == "navigator":
            nav = data.get("navigatorExport", {}).get("navigator", {})
            return (nav.get("id"), nav.get("name"))
        elif file_type == "group":
            group = data.get("groupExport", {}).get("group", {})
            return (group.get("id"), group.get("name"))
        elif file_type == "detector":
            detector = data.get("detectorExport", {}).get("detector", {})
            return (detector.get("id"), detector.get("name"))
    except (json.JSONDecodeError, KeyError):
        return None
    
    return None


def compare_json_objects(old_obj: Dict[str, Any], new_obj: Dict[str, Any], path: str = "") -> List[str]:
    """Compare two JSON objects and return a list of changes"""
    changes = []
    all_keys = set(old_obj.keys()) | set(new_obj.keys())
    
    for key in sorted(all_keys):
        current_path = f"{path}.{key}" if path else key
        
        if key not in old_obj:
            changes.append(f"  ➕ Added: {current_path}")
        elif key not in new_obj:
            changes.append(f"  ❌ Removed: {current_path}")
        elif old_obj[key] != new_obj[key]:
            if not isinstance(old_obj[key], (dict, list)):
                old_val = str(old_obj[key])[:50]
                new_val = str(new_obj[key])[:50]
                changes.append(f"  ✏️  {current_path}: {old_val} → {new_val}")
            elif isinstance(old_obj[key], list) and isinstance(new_obj[key], list):
                if len(old_obj[key]) != len(new_obj[key]):
                    changes.append(f"  ✏️  {current_path}: {len(old_obj[key])} items → {len(new_obj[key])} items")
            else:
                changes.append(f"  ✏️  {current_path}: modified")
    
    return changes


def summarize_group_changes(old_data: Dict[str, Any], new_data: Dict[str, Any]) -> Dict[str, Any]:
    """Summarize changes in a dashboard group export"""
    summary = {
        "group_modified": False,
        "charts_added": 0,
        "charts_modified": 0,
        "charts_removed": 0,
        "dashboards_added": 0,
        "dashboards_modified": 0,
        "dashboards_removed": 0,
        "crosslinks_added": 0,
        "crosslinks_modified": 0,
        "crosslinks_removed": 0,
    }
    
    old_export = old_data.get("groupExport", old_data)
    new_export = new_data.get("groupExport", new_data)
    
    old_group = old_export.get("group", {})
    new_group = new_export.get("group", {})
    
    group_keys_to_compare = ["name", "description", "teams"]
    for key in group_keys_to_compare:
        if old_group.get(key) != new_group.get(key):
            summary["group_modified"] = True
            break
    
    # Extract charts from chartExports (with nested structure)
    old_charts = {c["chart"]["id"]: c["chart"] for c in old_data.get("chartExports", [])}
    new_charts = {c["chart"]["id"]: c["chart"] for c in new_data.get("chartExports", [])}
    
    summary["charts_added"] = len(set(new_charts.keys()) - set(old_charts.keys()))
    summary["charts_removed"] = len(set(old_charts.keys()) - set(new_charts.keys()))
    
    # Compare charts ignoring metadata fields
    for chart_id in set(old_charts.keys()) & set(new_charts.keys()):
        if _has_chart_changed(old_charts[chart_id], new_charts[chart_id]):
            summary["charts_modified"] += 1
    
    # Extract dashboards from dashboardExports (with nested structure)
    old_dashboards = {d["dashboard"]["id"]: d["dashboard"] for d in old_data.get("dashboardExports", [])}
    new_dashboards = {d["dashboard"]["id"]: d["dashboard"] for d in new_data.get("dashboardExports", [])}
    
    summary["dashboards_added"] = len(set(new_dashboards.keys()) - set(old_dashboards.keys()))
    summary["dashboards_removed"] = len(set(old_dashboards.keys()) - set(new_dashboards.keys()))
    
    # Compare dashboards ignoring metadata fields
    for dash_id in set(old_dashboards.keys()) & set(new_dashboards.keys()):
        if _has_dashboard_changed(old_dashboards[dash_id], new_dashboards[dash_id]):
            summary["dashboards_modified"] += 1
    
    # Extract crosslinks
    old_crosslinks = {cl.get("crosslink", {}).get("id"): cl.get("crosslink") 
                      for cl in old_data.get("crossLinkExports", [])}
    new_crosslinks = {cl.get("crosslink", {}).get("id"): cl.get("crosslink") 
                      for cl in new_data.get("crossLinkExports", [])}
    
    summary["crosslinks_added"] = len(set(new_crosslinks.keys()) - set(old_crosslinks.keys()))
    summary["crosslinks_removed"] = len(set(old_crosslinks.keys()) - set(new_crosslinks.keys()))
    
    for cl_id in set(old_crosslinks.keys()) & set(new_crosslinks.keys()):
        if cl_id and old_crosslinks[cl_id] != new_crosslinks[cl_id]:
            summary["crosslinks_modified"] += 1
    
    return summary


def _has_chart_changed(local_chart: Dict[str, Any], remote_chart: Dict[str, Any]) -> bool:
    """Check if chart has meaningful changes, ignoring metadata fields."""
    # Fields to ignore (auto-generated or metadata)
    ignore_fields = {"created", "lastUpdated", "lastUpdatedBy", "creator"}
    
    # Get all keys from both charts
    all_keys = set(local_chart.keys()) | set(remote_chart.keys())
    keys_to_compare = all_keys - ignore_fields
    
    for key in keys_to_compare:
        if local_chart.get(key) != remote_chart.get(key):
            return True
    return False


def _has_dashboard_changed(local_dashboard: Dict[str, Any], remote_dashboard: Dict[str, Any]) -> bool:
    """Check if dashboard has meaningful changes, ignoring metadata fields."""
    # Fields to ignore (auto-generated or metadata)
    ignore_fields = {"created", "lastUpdated", "lastUpdatedBy", "creator"}
    
    # Get all keys from both dashboards
    all_keys = set(local_dashboard.keys()) | set(remote_dashboard.keys())
    keys_to_compare = all_keys - ignore_fields
    
    for key in keys_to_compare:
        if local_dashboard.get(key) != remote_dashboard.get(key):
            return True
    return False


def base_api_url_from_realm(realm: str) -> str:
    """Get base API URL from realm"""
    return f"https://api.{realm}.signalfx.com"

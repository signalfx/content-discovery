"""Dashboard Group API service for fetching and updating dashboard groups."""

import sys
from typing import Dict, Any
from .base_service import do_get, do_put, do_post, RemoteNotFound
from .crosslink_service import update_crosslinks


def fetch_group_export_by_id(group_id: str, base_url: str, token: str, format: str = "json") -> Any:
    """
    Fetch a dashboard group export by ID.
    
    Args:
        group_id: The dashboard group ID
        base_url: The base API URL
        token: The SignalFx access token
        format: Return format, either "json" or "text"
        
    Returns:
        The exported dashboard group data
        
    Raises:
        RemoteNotFound: If the group does not exist (HTTP 404)
        RuntimeError: For any other non-200 response
    """
    resp = do_get(f"{base_url}/v2/dashboardgroup/{group_id}/export", token)
    if resp.status_code == 404:
        raise RemoteNotFound(f"dashboard group {group_id} not found")
    if resp.status_code != 200:
        raise RuntimeError(f"Failed to fetch dashboard group {group_id}: {resp.text}")
    if format == "json":
        return resp.json()
    return resp.text


def create_dashboard_group_via_import(
    group_export: Dict[str, Any], base_url: str, token: str
) -> Dict[str, Any]:
    """Create a dashboard group in a fresh env via the import endpoint.

    POSTs the full export payload to ``/v2/dashboardgroup/import``. The
    backend assigns new ids to the group and every child chart,
    dashboard, and crosslink, and rewires all cross-references
    server-side. This is the only safe way to create a group in an env
    where the source ids do not exist — POSTing the children one by one
    (as the older code did) leaves dashboards pointing at dead chart
    ids.

    Returns the JSON response, which contains the new ids the caller
    can use for a follow-up fetch and local write-back.
    """
    resp = do_post(f"{base_url}/v2/dashboardgroup/import", token, group_export)
    if resp.status_code not in (200, 201):
        raise RuntimeError(
            f"Failed to import dashboard group: {resp.status_code} {resp.text}"
        )
    return resp.json()


def update_dashboard_group(group_export: Dict[str, Any], base_url: str, token: str) -> bool:
    """
    Update a dashboard group by intelligently updating only changed charts and dashboards.
    
    Args:
        group_export: The dashboard group export data
        base_url: The base API URL
        token: The SignalFx access token
        
    Returns:
        True if successful, False otherwise
    """
    group_id = group_export["groupExport"]["group"]["id"]

    # Fetch current remote state. update_dashboard_group is strictly an
    # update: a missing group is surfaced as a failure with a pointer
    # to the ``create <path> --yes`` CLI verb. Auto-creating here via
    # ``/v2/dashboardgroup/import`` would succeed at the API but leave
    # the local JSON pinned to the now-stale source id, and the next
    # ``apply`` would import a duplicate group. Capturing the new id
    # requires the local-file write-back plumbing that lives in
    # ``cli._refresh_local``, which only the ``create`` verb runs.
    try:
        remote_export = fetch_group_export_by_id(group_id, base_url, token, format="json")
    except RemoteNotFound:
        print(
            f"  ❌ Dashboard group {group_id} not found in master; "
            f"use 'create <path> --yes' so the local file is rewritten "
            f"with the server-assigned ids",
            file=sys.stderr,
        )
        return False
    except RuntimeError as e:
        print(f"  ❌ Failed to fetch dashboard group {group_id}: {e}", file=sys.stderr)
        return False
    
    # Compare and update group properties
    local_group = group_export["groupExport"]["group"]
    remote_group = remote_export["groupExport"]["group"]
    overall_success = True
    
    if _has_group_changed(local_group, remote_group):
        resp = do_put(f"{base_url}/v2/dashboardgroup/{group_id}", token, local_group)
        if resp.status_code in [200, 201]:
            print(f"  ✏️  Updated dashboard group: {local_group.get('name', group_id)}")
        else:
            print(f"  ❌ Failed to update group {group_id}: {resp.text}", file=sys.stderr)
            return False
    else:
        print(f"  ℹ️  Dashboard group unchanged")
    
    # Compare and update charts
    local_charts = {c["chart"]["id"]: c["chart"] for c in group_export.get("chartExports", [])}
    remote_charts = {c["chart"]["id"]: c["chart"] for c in remote_export.get("chartExports", [])}
    
    charts_added = set(local_charts.keys()) - set(remote_charts.keys())
    charts_removed = set(remote_charts.keys()) - set(local_charts.keys())
    charts_maybe_modified = set(local_charts.keys()) & set(remote_charts.keys())
    
    for chart_id in charts_added:
        chart = local_charts[chart_id]
        resp = do_post(f"{base_url}/v2/chart", token, chart)
        if resp.status_code in [200, 201]:
            print(f"  ➕ Created chart: {chart.get('name', chart_id)}")
        else:
            print(f"  ❌ Failed to create chart {chart_id}: {resp.text}", file=sys.stderr)
            overall_success = False
    
    for chart_id in charts_maybe_modified:
        if _has_chart_changed(local_charts[chart_id], remote_charts[chart_id]):
            chart = local_charts[chart_id]
            resp = do_put(f"{base_url}/v2/chart/{chart_id}", token, chart)
            if resp.status_code in [200, 201]:
                print(f"  ✏️  Updated chart: {chart.get('name', chart_id)}")
            else:
                print(f"  ❌ Failed to update chart {chart_id}: {resp.text}", file=sys.stderr)
                overall_success = False
    
    if charts_removed:
        print(f"  ℹ️  {len(charts_removed)} chart(s) exist remotely but not locally (not deleted)")
    
    # Compare and update dashboards
    local_dashboards = {d["dashboard"]["id"]: d["dashboard"] for d in group_export.get("dashboardExports", [])}
    remote_dashboards = {d["dashboard"]["id"]: d["dashboard"] for d in remote_export.get("dashboardExports", [])}
    
    dashboards_added = set(local_dashboards.keys()) - set(remote_dashboards.keys())
    dashboards_removed = set(remote_dashboards.keys()) - set(local_dashboards.keys())
    dashboards_maybe_modified = set(local_dashboards.keys()) & set(remote_dashboards.keys())
    
    for dashboard_id in dashboards_added:
        dashboard = local_dashboards[dashboard_id]
        resp = do_post(f"{base_url}/v2/dashboard", token, dashboard)
        if resp.status_code in [200, 201]:
            print(f"  ➕ Created dashboard: {dashboard.get('name', dashboard_id)}")
        else:
            print(f"  ❌ Failed to create dashboard {dashboard_id}: {resp.text}", file=sys.stderr)
            overall_success = False
    
    for dashboard_id in dashboards_maybe_modified:
        if _has_dashboard_changed(local_dashboards[dashboard_id], remote_dashboards[dashboard_id]):
            dashboard = local_dashboards[dashboard_id]
            resp = do_put(f"{base_url}/v2/dashboard/{dashboard_id}", token, dashboard)
            if resp.status_code in [200, 201]:
                print(f"  ✏️  Updated dashboard: {dashboard.get('name', dashboard_id)}")
            else:
                print(f"  ❌ Failed to update dashboard {dashboard_id}: {resp.text}", file=sys.stderr)
                overall_success = False
    
    if dashboards_removed:
        print(f"  ℹ️  {len(dashboards_removed)} dashboard(s) exist remotely but not locally (not deleted)")
    
    # Compare and update crosslinks
    local_crosslinks = group_export.get("crossLinkExports", [])
    remote_crosslinks = remote_export.get("crossLinkExports", [])
    
    if local_crosslinks or remote_crosslinks:
        updated, created, failed = update_crosslinks(local_crosslinks, base_url, token)
        if failed:
            print(f"  ❌ Failed to write {failed} crosslink(s) for group {group_id}", file=sys.stderr)
            overall_success = False
    
    return overall_success


def _has_group_changed(local_group: Dict[str, Any], remote_group: Dict[str, Any]) -> bool:
    """Check if group properties have changed (excluding children)."""
    keys_to_compare = ["name", "description", "teams"]
    for key in keys_to_compare:
        if local_group.get(key) != remote_group.get(key):
            return True
    return False


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

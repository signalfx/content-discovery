"""Dashboard-group export, import, and dependency-ordered update service."""

from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any, Dict

SFX_SCRIPT_DIR = Path(__file__).resolve().parents[2] / "sfx-api" / "scripts"
if str(SFX_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SFX_SCRIPT_DIR))

from sfx_http import RemoteNotFound, do_post
from datalink_sync import update_crosslinks
from sfx_client import (
    create_object,
    export_object,
    prepare_payload,
    update_object,
)


def fetch_group_export_by_id(
    group_id: str, base_url: str, token: str, format: str = "json"
) -> Any:
    """Fetch a complete dashboard-group export by ID."""
    exported = export_object("dashboard-group", group_id, base_url, token)
    if format == "json":
        return exported
    return exported if isinstance(exported, str) else str(exported)


def create_dashboard_group_via_import(
    group_export: Dict[str, Any], base_url: str, token: str
) -> Dict[str, Any]:
    """Import a complete group so the API rewires all child IDs."""
    response = do_post(f"{base_url}/v2/dashboardgroup/import", token, group_export)
    if response.status_code not in (200, 201):
        raise RuntimeError(
            f"Failed to import dashboard group: {response.status_code} {response.text}"
        )
    return response.json()


def _replace_ids(value: Any, replacements: Dict[str, str]) -> Any:
    """Recursively replace newly-created child IDs in dependent payloads."""
    if isinstance(value, str):
        return replacements.get(value, value)
    if isinstance(value, list):
        return [_replace_ids(item, replacements) for item in value]
    if isinstance(value, dict):
        return {key: _replace_ids(item, replacements) for key, item in value.items()}
    return value


def _objects(exports: list[Dict[str, Any]], key: str) -> Dict[str, Dict[str, Any]]:
    objects: Dict[str, Dict[str, Any]] = {}
    for item in exports:
        obj = item.get(key, {})
        object_id = obj.get("id")
        if object_id:
            objects[object_id] = obj
    return objects


def _sync_children(
    resource: str,
    local_objects: Dict[str, Dict[str, Any]],
    remote_objects: Dict[str, Dict[str, Any]],
    replacements: Dict[str, str],
    base_url: str,
    token: str,
) -> Dict[str, str]:
    """Create or update one child type and return old-to-new IDs."""
    created_ids: Dict[str, str] = {}
    added = set(local_objects) - set(remote_objects)
    shared = set(local_objects) & set(remote_objects)

    for object_id in sorted(added):
        local = _replace_ids(local_objects[object_id], replacements)
        response = create_object(resource, prepare_payload(local), base_url, token)
        new_id = response.get("id") if isinstance(response, dict) else None
        if not new_id:
            raise RuntimeError(
                f"created {resource} {object_id} but the API response contained no id"
            )
        created_ids[object_id] = new_id
        print(
            f"  ➕ Created {resource}: {local.get('name', object_id)}",
            file=sys.stderr,
        )

    all_replacements = {**replacements, **created_ids}
    for object_id in sorted(shared):
        local = _replace_ids(local_objects[object_id], all_replacements)
        remote = remote_objects[object_id]
        changed = (
            _has_chart_changed(local, remote)
            if resource == "chart"
            else _has_dashboard_changed(local, remote)
        )
        if changed:
            update_object(
                resource,
                object_id,
                prepare_payload(local),
                base_url,
                token,
            )
            print(
                f"  ✏️  Updated {resource}: {local.get('name', object_id)}",
                file=sys.stderr,
            )

    removed = set(remote_objects) - set(local_objects)
    if removed:
        print(
            f"  ℹ️  {len(removed)} {resource}(s) exist remotely but not locally "
            "(not deleted)",
            file=sys.stderr,
        )
    return created_ids


def update_dashboard_group(
    group_export: Dict[str, Any], base_url: str, token: str
) -> bool:
    """Apply a group export in chart → dashboard → group → data-link order."""
    local_export = copy.deepcopy(group_export)
    local_group = local_export["groupExport"]["group"]
    group_id = local_group["id"]

    try:
        remote_export = fetch_group_export_by_id(group_id, base_url, token)

        local_charts = _objects(local_export.get("chartExports", []), "chart")
        remote_charts = _objects(remote_export.get("chartExports", []), "chart")
        chart_ids = _sync_children(
            "chart", local_charts, remote_charts, {}, base_url, token
        )

        local_dashboards = _objects(
            local_export.get("dashboardExports", []), "dashboard"
        )
        remote_dashboards = _objects(
            remote_export.get("dashboardExports", []), "dashboard"
        )
        dashboard_ids = _sync_children(
            "dashboard",
            local_dashboards,
            remote_dashboards,
            chart_ids,
            base_url,
            token,
        )

        replacements = {**chart_ids, **dashboard_ids}
        prepared_group = prepare_payload(_replace_ids(local_group, replacements))
        remote_group = remote_export["groupExport"]["group"]
        if _has_group_changed(prepared_group, remote_group):
            update_object(
                "dashboard-group", group_id, prepared_group, base_url, token
            )
            print(
                f"  ✏️  Updated dashboard group: {local_group.get('name', group_id)}",
                file=sys.stderr,
            )
        else:
            print("  ℹ️  Dashboard group unchanged", file=sys.stderr)

        local_crosslinks = _replace_ids(
            local_export.get("crossLinkExports", []), replacements
        )
        if local_crosslinks:
            _, _, failed = update_crosslinks(local_crosslinks, base_url, token)
            if failed:
                raise RuntimeError(
                    f"failed to write {failed} data link(s) for group {group_id}"
                )
        return True
    except RemoteNotFound:
        print(
            f"  ❌ Dashboard group {group_id} not found in master; "
            "use 'create <path> --yes'",
            file=sys.stderr,
        )
    except RuntimeError as exc:
        print(f"  ❌ Failed to update dashboard group {group_id}: {exc}", file=sys.stderr)
    return False


def _has_group_changed(local_group: Dict[str, Any], remote_group: Dict[str, Any]) -> bool:
    keys_to_compare = ("name", "description", "teams", "dashboards", "dashboardConfigs")
    return any(local_group.get(key) != remote_group.get(key) for key in keys_to_compare)


def _has_chart_changed(local_chart: Dict[str, Any], remote_chart: Dict[str, Any]) -> bool:
    ignored = {"created", "lastUpdated", "lastUpdatedBy", "creator"}
    keys = (set(local_chart) | set(remote_chart)) - ignored
    return any(local_chart.get(key) != remote_chart.get(key) for key in keys)


def _has_dashboard_changed(
    local_dashboard: Dict[str, Any], remote_dashboard: Dict[str, Any]
) -> bool:
    ignored = {"created", "lastUpdated", "lastUpdatedBy", "creator"}
    keys = (set(local_dashboard) | set(remote_dashboard)) - ignored
    return any(local_dashboard.get(key) != remote_dashboard.get(key) for key in keys)

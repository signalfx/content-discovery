"""Shared utilities for syncer tools"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

SFX_SCRIPT_DIR = Path(__file__).resolve().parents[2] / "sfx-api" / "scripts"
if str(SFX_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SFX_SCRIPT_DIR))

from sfx_http import do_get  # noqa: E402

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[3]

# Root-level credential file. By design this CLI talks to one and only
# one SignalBuddy org — Master SignalBuddy — and the file holds nothing
# but the API token (single line). The file is gitignored.
TOKEN_FILE = REPO_ROOT / ".token"

# Master SignalBuddy lives on the us0 realm. There is no other realm
# this CLI talks to, so the value is a constant rather than a config
# field. If MSB ever moves realms, change this in one place.
MASTER_REALM = "us0"

# Canonical on-disk directories per resource type. Used both for discovery
# (scanning for the local file that matches a given id) and for write-back
# path inference when no existing local file matches.
RESOURCE_DIRS: Dict[str, str] = {
    "navigator": "navigators",
    "group": "group",
    "detector": "detector",
}


def load_token_file() -> str:
    """Return the token string stored in the root ``.token`` file.

    The file holds exactly one thing: the API token as a single line.
    Surrounding whitespace and trailing newlines are stripped. Returns
    an empty string if the file is absent — callers fall back to the
    ``SIGNALBUDDY_TOKEN`` environment variable in that case.
    """
    if not TOKEN_FILE.exists():
        return ""
    try:
        return TOKEN_FILE.read_text(encoding="utf-8").strip()
    except OSError as e:
        raise RuntimeError(f"failed to read {TOKEN_FILE}: {e}") from e


def get_master_credentials() -> Optional[Tuple[str, str]]:
    """Return ``(realm, token)`` for Master SignalBuddy, or ``None``.

    Resolution order for the token: root ``.token`` file first, then
    the ``SIGNALBUDDY_TOKEN`` process environment variable. The realm
    is always :data:`MASTER_REALM` — it's a property of the CLI, not
    of the user's config. Returns ``None`` when neither source
    supplies a token so the caller can produce one clear error.
    """
    token = load_token_file() or os.environ.get("SIGNALBUDDY_TOKEN", "").strip()
    if not token:
        return None
    return MASTER_REALM, token


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


def _git_lines(args: List[str]) -> List[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def _ref_exists(ref: str) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", ref],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def _default_change_base() -> str:
    """Choose HEAD locally or the mainline merge-base on a feature branch."""
    target = os.environ.get("CI_MERGE_REQUEST_TARGET_BRANCH_NAME", "").strip()
    if target:
        for candidate in (f"origin/{target}", target):
            if _ref_exists(candidate):
                return candidate

    try:
        branch = _git_lines(["branch", "--show-current"])[0]
    except (subprocess.CalledProcessError, IndexError):
        return "HEAD"
    if branch in ("main", "master"):
        return "HEAD"
    for candidate in ("origin/master", "master", "origin/main", "main"):
        if _ref_exists(candidate):
            return candidate
    return "HEAD"


def get_changed_files(base_ref: Optional[str] = None) -> List[Tuple[str, Path]]:
    """Return changed content files from branch, index, worktree, and untracked state."""
    try:
        selected_base = base_ref or _default_change_base()
        anchor = selected_base
        if selected_base != "HEAD":
            anchor = _git_lines(["merge-base", selected_base, "HEAD"])[0]

        names = set(_git_lines(["diff", "--name-only", anchor, "--"]))
        names.update(_git_lines(["ls-files", "--others", "--exclude-standard"]))

        changed_files = []
        for line in sorted(names):
            if not line or not line.endswith('.json'):
                continue

            file_path = REPO_ROOT / line
            if not file_path.exists():
                continue

            try:
                rel_path = file_path.relative_to(REPO_ROOT)
                if rel_path.parts[0] == 'navigators':
                    changed_files.append(("navigator", file_path))
                elif rel_path.parts[0] == 'group':
                    changed_files.append(("group", file_path))
                elif rel_path.parts[0] == 'detector':
                    changed_files.append(("detector", file_path))
            except ValueError:
                continue

        return changed_files
    except (subprocess.CalledProcessError, IndexError):
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
    
    group_keys_to_compare = [
        "name",
        "description",
        "teams",
        "dashboards",
        "dashboardConfigs",
    ]
    for key in group_keys_to_compare:
        if not export_values_equal(old_group.get(key), new_group.get(key)):
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
                      for cl in old_data.get("crossLinkExports") or []}
    new_crosslinks = {cl.get("crosslink", {}).get("id"): cl.get("crosslink") 
                      for cl in new_data.get("crossLinkExports") or []}
    
    summary["crosslinks_added"] = len(set(new_crosslinks.keys()) - set(old_crosslinks.keys()))
    summary["crosslinks_removed"] = len(set(old_crosslinks.keys()) - set(new_crosslinks.keys()))
    
    for cl_id in set(old_crosslinks.keys()) & set(new_crosslinks.keys()):
        if cl_id and not export_values_equal(
            old_crosslinks[cl_id], new_crosslinks[cl_id]
        ):
            summary["crosslinks_modified"] += 1
    
    return summary


def export_values_equal(local_value: Any, remote_value: Any) -> bool:
    """Compare exported values while ignoring harmless API normalization.

    SignalBuddy commonly turns nullable collection fields such as ``tags``,
    ``filters.sources``, and ``chartLinks`` into empty lists or objects on
    export. Those representations are operationally equivalent and must not
    cause every child object in a dashboard group to be updated.
    """
    if local_value == remote_value:
        return True
    if local_value is None and remote_value in ([], {}):
        return True
    if remote_value is None and local_value in ([], {}):
        return True
    if isinstance(local_value, dict) and isinstance(remote_value, dict):
        keys = set(local_value) | set(remote_value)
        return all(
            export_values_equal(local_value.get(key), remote_value.get(key))
            for key in keys
        )
    if isinstance(local_value, list) and isinstance(remote_value, list):
        return len(local_value) == len(remote_value) and all(
            export_values_equal(local_item, remote_item)
            for local_item, remote_item in zip(local_value, remote_value)
        )
    return False


def _has_chart_changed(local_chart: Dict[str, Any], remote_chart: Dict[str, Any]) -> bool:
    """Check if chart has meaningful changes, ignoring metadata fields."""
    # Fields to ignore (auto-generated or metadata)
    ignore_fields = {"created", "lastUpdated", "lastUpdatedBy", "creator"}
    
    # Get all keys from both charts
    all_keys = set(local_chart.keys()) | set(remote_chart.keys())
    keys_to_compare = all_keys - ignore_fields
    
    for key in keys_to_compare:
        if not export_values_equal(local_chart.get(key), remote_chart.get(key)):
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
        if not export_values_equal(local_dashboard.get(key), remote_dashboard.get(key)):
            return True
    return False


def base_api_url_from_realm(realm: str) -> str:
    """Get base API URL from realm"""
    return f"https://api.{realm}.signalfx.com"


# --- local file discovery / write-back -----------------------------------


def _iter_resource_files(resource_type: str) -> List[Path]:
    """All ``*.json`` files under the canonical directory for ``resource_type``."""
    directory = RESOURCE_DIRS.get(resource_type)
    if not directory:
        return []
    root = REPO_ROOT / directory
    if not root.exists():
        return []
    return sorted(root.rglob("*.json"))


def find_local_file_for_id(resource_type: str, resource_id: str) -> Optional[Path]:
    """Scan canonical dirs for the local file whose JSON id matches.

    Returns the first match (ids are globally unique within an org), or
    ``None`` if no file contains the id. Silently skips unreadable /
    malformed files so a single bad file can't break discovery.
    """
    if not resource_id:
        return None
    for candidate in _iter_resource_files(resource_type):
        info = extract_resource_info(resource_type, candidate)
        if info and info[0] == resource_id:
            return candidate
    return None


def _safe_filename(name: str) -> str:
    """Strip filesystem-hostile characters from a resource name.

    SignalBuddy names allow slashes, colons, etc. that map to subpaths or
    are invalid on Windows. Replace runs of unsafe characters with a
    single space and collapse whitespace so we never silently create a
    nested directory from a name like ``"AWS / Lambda"``.
    """
    cleaned = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', " ", name).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned or "unnamed"


def canonical_path_for(
    resource_type: str, name: str, category: Optional[str] = None
) -> Optional[Path]:
    """Compute the on-disk path the repo would use for a fresh write.

    ``group`` and ``detector`` are flat directories so the path is
    unambiguous. ``navigator`` is grouped by category subdirectory and
    nothing in the navigator export tells us the category — callers must
    supply one, or fall back to requiring an explicit ``--out``. Returns
    ``None`` when a path cannot be safely determined.
    """
    directory = RESOURCE_DIRS.get(resource_type)
    if not directory:
        return None
    filename = f"{_safe_filename(name)}.json"
    if resource_type == "navigator":
        if not category:
            return None
        return REPO_ROOT / directory / _safe_filename(category) / filename
    return REPO_ROOT / directory / filename


class _JsonSpanParser:
    """Locate JSON value spans without changing the source representation."""

    def __init__(self, source: str) -> None:
        self.source = source
        self.decoder = json.JSONDecoder()

    def parse(self) -> Tuple[Any, int, int, Any]:
        node = self._value(self._skip(0))
        if self._skip(node[2]) != len(self.source):
            raise ValueError("unexpected content after JSON document")
        return node

    def _skip(self, offset: int) -> int:
        while offset < len(self.source) and self.source[offset].isspace():
            offset += 1
        return offset

    def _value(self, start: int) -> Tuple[Any, int, int, Any]:
        if start >= len(self.source):
            raise ValueError("unexpected end of JSON document")
        token = self.source[start]
        if token == "{":
            return self._object(start)
        if token == "[":
            return self._array(start)
        value, length = self.decoder.raw_decode(self.source[start:])
        return value, start, start + length, None

    def _object(self, start: int) -> Tuple[Any, int, int, Any]:
        offset = self._skip(start + 1)
        values: Dict[str, Any] = {}
        children: Dict[str, Any] = {}
        if self.source[offset] == "}":
            return values, start, offset + 1, children
        while True:
            key, length = self.decoder.raw_decode(self.source[offset:])
            if not isinstance(key, str):
                raise ValueError("JSON object key must be a string")
            offset = self._skip(offset + length)
            if self.source[offset] != ":":
                raise ValueError("expected ':' after JSON object key")
            child = self._value(self._skip(offset + 1))
            values[key] = child[0]
            children[key] = child
            offset = self._skip(child[2])
            if self.source[offset] == "}":
                return values, start, offset + 1, children
            if self.source[offset] != ",":
                raise ValueError("expected ',' between JSON object values")
            offset = self._skip(offset + 1)

    def _array(self, start: int) -> Tuple[Any, int, int, Any]:
        offset = self._skip(start + 1)
        values: List[Any] = []
        children: List[Any] = []
        if self.source[offset] == "]":
            return values, start, offset + 1, children
        while True:
            child = self._value(offset)
            values.append(child[0])
            children.append(child)
            offset = self._skip(child[2])
            if self.source[offset] == "]":
                return values, start, offset + 1, children
            if self.source[offset] != ",":
                raise ValueError("expected ',' between JSON array values")
            offset = self._skip(offset + 1)


def _format_preserving_replacements(
    node: Tuple[Any, int, int, Any], fresh: Any, *, root: bool = False
) -> List[Tuple[int, int, str]]:
    current, start, end, children = node
    if export_values_equal(current, fresh):
        return []
    if isinstance(current, dict) and isinstance(fresh, dict):
        if set(current) == set(fresh):
            replacements: List[Tuple[int, int, str]] = []
            for key in current:
                replacements.extend(
                    _format_preserving_replacements(children[key], fresh[key])
                )
            return replacements
    elif isinstance(current, list) and isinstance(fresh, list):
        if len(current) == len(fresh):
            replacements = []
            for child, fresh_item in zip(children, fresh):
                replacements.extend(
                    _format_preserving_replacements(child, fresh_item)
                )
            return replacements
    if root:
        return [
            (
                start,
                end,
                json.dumps(fresh, indent=2, sort_keys=True, ensure_ascii=False),
            )
        ]
    return [(start, end, json.dumps(fresh, ensure_ascii=False, separators=(",", ":")))]


def _write_preserving_json_format(path: Path, payload: Dict[str, Any]) -> None:
    source = path.read_text(encoding="utf-8")
    root = _JsonSpanParser(source).parse()
    replacements = _format_preserving_replacements(root, payload, root=True)
    for start, end, rendered in sorted(replacements, reverse=True):
        source = source[:start] + rendered + source[end:]
    with path.open("w", encoding="utf-8") as f:
        f.write(source)


def write_local_resource(
    path: Path, payload: Dict[str, Any], *, preserve_format: bool = False
) -> None:
    """Write an export, optionally retaining an existing file's JSON layout."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if preserve_format and path.exists():
        try:
            _write_preserving_json_format(path, payload)
        except (IndexError, OSError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                f"cannot safely preserve dashboard-group formatting in {path}: {exc}"
            ) from exc
        return
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True, ensure_ascii=False)
        f.write("\n")

#!/usr/bin/env python3
"""Deterministically update and validate content-discovery release notes."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

try:
    import yaml
except ImportError as exc:  # pragma: no cover - exercised by the real hook environment
    raise SystemExit(
        "content changelog requires PyYAML; install repository requirements first"
    ) from exc


REPO_ROOT = Path(__file__).resolve().parents[3]
CHANGELOG_PATH = REPO_ROOT / "content_release_notes.yaml"
CHANGELOG_RELATIVE_PATH = "content_release_notes.yaml"
GENERATED_BY = "content-changelog/pre-commit"
CONTENT_ROOTS = ("detector", "navigators", "group")
SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
IGNORED_DESCRIPTION_FIELDS = {
    "created",
    "creator",
    "hashCode",
    "lastUpdated",
    "lastUpdatedBy",
}
MISSING = object()


@dataclass(frozen=True)
class ContentChange:
    status: str
    path: str
    previous_path: str | None = None

    @property
    def paths(self) -> list[str]:
        if self.previous_path and self.previous_path != self.path:
            return [self.previous_path, self.path]
        return [self.path]


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=check,
    )


def is_content_path(path: str) -> bool:
    return path.endswith(".json") and path.split("/", 1)[0] in CONTENT_ROOTS


def staged_changes() -> list[ContentChange]:
    result = git(
        "diff",
        "--cached",
        "--name-status",
        "-M",
        "--diff-filter=ACMDR",
        "--",
        *CONTENT_ROOTS,
    )
    changes: list[ContentChange] = []
    for raw_line in result.stdout.splitlines():
        parts = raw_line.split("\t")
        if len(parts) < 2:
            continue
        status = parts[0][0]
        if status == "R" and len(parts) == 3:
            old_path, new_path = parts[1], parts[2]
            if is_content_path(old_path) or is_content_path(new_path):
                changes.append(ContentChange(status, new_path, old_path))
        elif is_content_path(parts[1]):
            changes.append(ContentChange(status, parts[1]))
    return sorted(changes, key=lambda item: (item.path, item.previous_path or ""))


def changed_paths(changes: Iterable[ContentChange]) -> set[str]:
    return {path for change in changes for path in change.paths if is_content_path(path)}


def read_git_text(spec: str) -> str | None:
    result = git("show", spec, check=False)
    return result.stdout if result.returncode == 0 else None


def read_change_document(change: ContentChange) -> dict[str, Any]:
    if change.status == "D":
        raw = read_git_text(f"HEAD:{change.path}")
    else:
        raw = read_git_text(f":{change.path}")
    if not raw and change.previous_path:
        raw = read_git_text(f"HEAD:{change.previous_path}")
    if not raw:
        return {}
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid staged JSON for {change.path}: {exc}") from exc


def content_metadata(change: ContentChange) -> tuple[str, str]:
    document = read_change_document(change)
    root = change.path.split("/", 1)[0]
    if root == "detector":
        payload = document.get("detectorExport", {}).get("detector", {})
        category = "detector"
    elif root == "navigators":
        payload = document.get("navigatorExport", {}).get("navigator", {})
        category = "navigator"
    else:
        payload = document.get("groupExport", {}).get("group", {})
        category = "dashboard_group"
    name = payload.get("name") if isinstance(payload, dict) else None
    fallback_path = change.previous_path if change.status == "D" else change.path
    return str(name or Path(fallback_path or change.path).stem), category


def previous_change_document(change: ContentChange) -> dict[str, Any]:
    path = change.previous_path or change.path
    raw = read_git_text(f"HEAD:{path}")
    if not raw:
        return {}
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid previous JSON for {path}: {exc}") from exc


def content_payload(document: dict[str, Any], category: str) -> Any:
    if category == "detector":
        return document.get("detectorExport", {}).get("detector", {})
    if category == "navigator":
        return document.get("navigatorExport", {}).get("navigator", {})
    return document


def semantic_changes(
    old: Any, new: Any, path: tuple[str | int, ...] = ()
) -> list[tuple[tuple[str | int, ...], Any, Any]]:
    """Return meaningful leaf changes while ignoring export metadata churn."""
    if old == new or (old is MISSING and new is None) or (new is MISSING and old is None):
        return []
    if isinstance(old, dict) and isinstance(new, dict):
        changes = []
        for key in sorted(set(old) | set(new)):
            if key in IGNORED_DESCRIPTION_FIELDS:
                continue
            changes.extend(
                semantic_changes(
                    old.get(key, MISSING), new.get(key, MISSING), (*path, key)
                )
            )
        return changes
    if isinstance(old, list) and isinstance(new, list) and len(old) == len(new):
        changes = []
        for index, (old_item, new_item) in enumerate(zip(old, new)):
            changes.extend(semantic_changes(old_item, new_item, (*path, index)))
        return changes
    return [(path, old, new)]


def humanize_field(field: str) -> str:
    words = re.sub(r"(?<!^)(?=[A-Z])", " ", field).replace("_", " ")
    return words.lower()


def render_value(value: Any) -> str:
    if value is MISSING:
        return "unset"
    rendered = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return rendered if len(rendered) <= 70 else rendered[:67] + "..."


def describe_modified_content(
    change: ContentChange, name: str, category: str
) -> str:
    old = content_payload(previous_change_document(change), category)
    new = content_payload(read_change_document(change), category)
    changes = semantic_changes(old, new)
    if not changes:
        return f"Refreshed exported metadata for {name}."

    program_paths = [path for path, _, _ in changes if path and path[-1] == "programText"]
    if category == "dashboard_group" and program_paths:
        chart_indexes = {
            path[path.index("chartExports") + 1]
            for path in program_paths
            if "chartExports" in path and path.index("chartExports") + 1 < len(path)
        }
        if chart_indexes and len(program_paths) == len(changes):
            noun = "chart" if len(chart_indexes) == 1 else "charts"
            return f"Updated program text in {len(chart_indexes)} {noun}."

    if len(changes) == 1:
        path, old_value, new_value = changes[0]
        field = humanize_field(str(path[-1])) if path else "content"
        return (
            f"Changed {field} from {render_value(old_value)} "
            f"to {render_value(new_value)}."
        )

    details: list[str] = []
    for path, _, _ in changes:
        string_path = [str(part) for part in path]
        if "rules" in string_path:
            label = "detector rules"
        elif "visualizations" in string_path:
            label = "visualizations"
        elif path and path[-1] == "programText":
            label = "program text"
        else:
            label = humanize_field(str(path[-1])) if path else "content"
        if label not in details:
            details.append(label)

    shown = details[:3]
    if len(details) > 3:
        shown.append("other content fields")
    if len(shown) == 1:
        detail_text = shown[0]
    else:
        detail_text = ", ".join(shown[:-1]) + f", and {shown[-1]}"
    return f"Updated {detail_text} in {name}."


def blob_identity(change: ContentChange) -> str:
    specs: list[str] = []
    if change.previous_path:
        specs.append(f"HEAD:{change.previous_path}")
    specs.append(f"HEAD:{change.path}" if change.status == "D" else f":{change.path}")
    identities: list[str] = []
    for spec in specs:
        result = git("rev-parse", spec, check=False)
        identities.append(result.stdout.strip() if result.returncode == 0 else "missing")
    return ":".join(identities)


def change_id(changes: Iterable[ContentChange]) -> str:
    digest = hashlib.sha256()
    for change in changes:
        digest.update(
            f"{change.status}\0{change.previous_path or ''}\0{change.path}\0{blob_identity(change)}\n".encode()
        )
    return digest.hexdigest()[:20]


def default_changelog() -> dict[str, Any]:
    return {
        "metadata": {
            "version": "2.0.0",
            "last_updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "description": "Version-based changelog tracking system for all content pieces",
            "structure": "Grouped by version number with files changed in each version",
        },
        "versions": {},
        "change_types": {
            "created": "Initial creation of content piece",
            "updated": "General update to existing content",
            "metric_changed": "Changes to metric queries or calculations",
            "visualization_changed": "Changes to charts, dashboards, or display",
            "metadata_changed": "Changes to metadata",
            "detector_rule_changed": "Changes to detector rules or conditions",
            "deprecated": "Content marked as deprecated",
            "deleted": "Content removed from the repository",
            "migrated": "Content migrated to another source",
            "bug_fix": "Bug fix or correction",
            "performance_improvement": "Performance optimization",
        },
        "categories": {
            "detector": "Detector/Alert configuration",
            "navigator": "Navigator configuration",
            "dashboard_group": "Dashboard group configuration",
        },
    }


def parse_yaml(raw: str, source: str) -> dict[str, Any]:
    try:
        value = yaml.safe_load(raw) or {}
    except yaml.YAMLError as exc:
        raise RuntimeError(f"could not parse {source}: {exc}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"{source} must contain a YAML mapping")
    value.setdefault("metadata", {})
    value.setdefault("versions", {})
    if not isinstance(value["versions"], dict):
        raise RuntimeError(f"{source} versions must be a mapping")
    return value


def load_worktree_changelog() -> dict[str, Any]:
    if not CHANGELOG_PATH.exists():
        return default_changelog()
    return parse_yaml(CHANGELOG_PATH.read_text(encoding="utf-8"), str(CHANGELOG_PATH))


def load_git_changelog(spec: str) -> dict[str, Any]:
    raw = read_git_text(spec)
    return parse_yaml(raw, spec) if raw is not None else default_changelog()


def semantic_versions(versions: Iterable[Any]) -> list[tuple[int, int, int]]:
    parsed = []
    for value in versions:
        match = SEMVER_RE.match(str(value))
        if match:
            parsed.append(tuple(int(part) for part in match.groups()))
    return parsed


def next_patch_version(versions: Iterable[Any], baseline: Any = None) -> str:
    candidates = list(versions)
    if baseline is not None:
        candidates.append(baseline)
    parsed = semantic_versions(candidates)
    major, minor, patch = max(parsed) if parsed else (0, 0, 0)
    return f"{major}.{minor}.{patch + 1}"


def generated_entry_for(changes: list[ContentChange], identifier: str) -> dict[str, Any]:
    entries = []
    for change in changes:
        name, category = content_metadata(change)
        if change.status == "A":
            change_type, description = "created", f"Added {name}."
        elif change.status == "D":
            change_type, description = "deleted", f"Removed {name}."
        elif change.status == "R":
            change_type = "updated"
            description = f"Renamed {Path(change.previous_path or '').stem} to {name}."
        else:
            change_type = "updated"
            description = describe_modified_content(change, name, category)
        entries.append(
            {
                "name": name,
                "category": category,
                "description": description,
                "change_type": change_type,
                "breaking_change": False,
                "files_modified": change.paths,
            }
        )
    return {
        "date": datetime.now(timezone.utc).date().isoformat(),
        "change_id": identifier,
        "generated_by": GENERATED_BY,
        "files": entries,
    }


def ensure_changelog_not_partially_staged() -> None:
    staged = git("diff", "--cached", "--name-only", "--", CHANGELOG_RELATIVE_PATH).stdout.strip()
    unstaged = git("diff", "--name-only", "--", CHANGELOG_RELATIVE_PATH).stdout.strip()
    if unstaged:
        state = "staged and unstaged" if staged else "unstaged"
        raise RuntimeError(
            f"{CHANGELOG_RELATIVE_PATH} has {state} edits; stage or discard them before retrying"
        )


def update_staged(stage_output: bool) -> bool:
    changes = staged_changes()
    if not changes:
        print("content changelog: no staged content files changed")
        return False

    ensure_changelog_not_partially_staged()
    identifier = change_id(changes)
    changelog = load_worktree_changelog()
    versions = changelog["versions"]

    for entry in versions.values():
        if isinstance(entry, dict) and entry.get("change_id") == identifier:
            print(f"content changelog: staged change {identifier} is already documented")
            if stage_output:
                git("add", "--", CHANGELOG_RELATIVE_PATH)
            return False

    head_versions = load_git_changelog(f"HEAD:{CHANGELOG_RELATIVE_PATH}")["versions"]
    for version in list(versions):
        entry = versions[version]
        if (
            isinstance(entry, dict)
            and entry.get("generated_by") == GENERATED_BY
            and str(version) not in {str(item) for item in head_versions}
        ):
            del versions[version]

    version = next_patch_version(versions, changelog.get("metadata", {}).get("version"))
    versions[version] = generated_entry_for(changes, identifier)
    changelog["versions"] = dict(
        sorted(
            versions.items(),
            key=lambda item: tuple(int(part) for part in str(item[0]).split("."))
            if SEMVER_RE.match(str(item[0]))
            else (-1, -1, -1),
            reverse=True,
        )
    )
    changelog["metadata"]["last_updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    CHANGELOG_PATH.write_text(
        yaml.safe_dump(changelog, sort_keys=False, allow_unicode=True, width=120),
        encoding="utf-8",
    )
    if stage_output:
        git("add", "--", CHANGELOG_RELATIVE_PATH)
    print(f"content changelog: added version {version} for {len(changes)} staged file(s)")
    return True


def entry_paths(entry: Any) -> set[str]:
    paths: set[str] = set()
    if not isinstance(entry, dict):
        return paths
    for file_entry in entry.get("files", []):
        if isinstance(file_entry, dict):
            paths.update(str(path) for path in file_entry.get("files_modified", []))
    return paths


def staged_changelog() -> dict[str, Any]:
    raw = read_git_text(f":{CHANGELOG_RELATIVE_PATH}")
    if raw is None:
        raise RuntimeError(f"{CHANGELOG_RELATIVE_PATH} is not staged")
    return parse_yaml(raw, f"staged {CHANGELOG_RELATIVE_PATH}")


def validate_staged() -> bool:
    changes = staged_changes()
    if not changes:
        raw = read_git_text(f":{CHANGELOG_RELATIVE_PATH}")
        if raw is not None:
            parse_yaml(raw, f"staged {CHANGELOG_RELATIVE_PATH}")
        print("content changelog validation: no staged content files changed")
        return True
    identifier = change_id(changes)
    changelog = staged_changelog()
    matches = [
        entry
        for entry in changelog["versions"].values()
        if isinstance(entry, dict) and entry.get("change_id") == identifier
    ]
    documented = set().union(*(entry_paths(entry) for entry in matches)) if matches else set()
    missing = changed_paths(changes) - documented
    if not matches or missing:
        print("content changelog validation failed", file=sys.stderr)
        if not matches:
            print(f"  missing staged change_id: {identifier}", file=sys.stderr)
        for path in sorted(missing):
            print(f"  undocumented: {path}", file=sys.stderr)
        return False
    print(f"content changelog validation: {len(documented)} staged path(s) documented")
    return True


def base_changed_paths(base_ref: str) -> set[str]:
    merge_base = git("merge-base", base_ref, "HEAD").stdout.strip()
    if not merge_base:
        raise RuntimeError(f"could not resolve merge base for {base_ref}")
    result = git(
        "diff",
        "--name-only",
        "--diff-filter=ACMDR",
        merge_base,
        "HEAD",
        "--",
        *CONTENT_ROOTS,
    )
    return {line for line in result.stdout.splitlines() if is_content_path(line)}


def validate_base(base_ref: str) -> bool:
    current_changelog = load_worktree_changelog()
    paths = base_changed_paths(base_ref)
    if not paths:
        print("content changelog validation: no content files changed")
        return True
    merge_base = git("merge-base", base_ref, "HEAD").stdout.strip()
    current = current_changelog["versions"]
    base = load_git_changelog(f"{merge_base}:{CHANGELOG_RELATIVE_PATH}")["versions"]
    new_entries = [entry for version, entry in current.items() if version not in base]
    documented = set().union(*(entry_paths(entry) for entry in new_entries)) if new_entries else set()
    missing = paths - documented
    if missing:
        print("content changelog validation failed", file=sys.stderr)
        for path in sorted(missing):
            print(f"  undocumented since {base_ref}: {path}", file=sys.stderr)
        return False
    print(f"content changelog validation: {len(paths)} changed path(s) documented since {base_ref}")
    return True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    update = subparsers.add_parser("update", help="update release notes")
    update.add_argument("--staged", action="store_true", required=True)
    update.add_argument("--stage", action="store_true", help="stage the updated changelog")
    validate = subparsers.add_parser("validate", help="validate release-note coverage")
    mode = validate.add_mutually_exclusive_group(required=True)
    mode.add_argument("--staged", action="store_true")
    mode.add_argument("--base")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "update":
            update_staged(args.stage)
            return 0
        return 0 if (validate_staged() if args.staged else validate_base(args.base)) else 1
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"content changelog failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

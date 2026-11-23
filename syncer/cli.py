"""Command-line front end for the content syncer.

A small, scriptable surface over ``syncer/services/`` for pushing local
JSON edits to Master SignalBuddy and pulling the current state back.
By design every operation runs against exactly one org — Master
SignalBuddy — and credentials live in the root ``.token`` file. There
is no ``--env`` flag and no multi-env machinery.

Subcommands (run any with ``-h`` for help):
  plan    Show what would be synced from the local repo to master.
  apply   Push all locally changed files to master. Requires --yes.
  update  Strict update of one resource in master. Auto-refreshes local file.
  create  Strict create of one resource in master. Auto-writes local file with new id.
  pull    Fetch one resource from master and overwrite the local file.
  fetch   Print the current master-side state of a resource to stdout.
  diff    Diff a local JSON file against the current master state.

Credentials: a single Master SignalBuddy API token. Put it in the root
``.token`` file (gitignored) as a single line — nothing else. Or, for
CI / agent runs, set ``SIGNALBUDDY_TOKEN`` as a process environment
variable. The realm is hard-wired to Master SignalBuddy's realm in
``syncer/utils.MASTER_REALM`` (currently ``us0``).

Output:
  - All commands print a single structured JSON object on stdout.
  - Human-friendly progress / warnings go to stderr only.
  - Exit code 0 on success, non-zero on any failure.

Run from the repo root:
  python -m syncer.cli plan
  python -m syncer.cli apply --yes
  python -m syncer.cli update path/to/file.json --yes
  python -m syncer.cli create path/to/file.json --yes
  python -m syncer.cli pull --type group --id <ID> --yes
  python -m syncer.cli fetch navigator <ID>
  python -m syncer.cli diff path/to/file.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
SYNCER_DIR = Path(__file__).resolve().parent

# ``services/`` and ``utils`` use plain (non-package-relative) imports of
# each other (``from services.base_service import ...``, ``from utils import
# ...``). Ensure ``syncer/`` itself is on sys.path so both
# ``python -m syncer.cli`` and ``python syncer/cli.py`` resolve them.
if str(SYNCER_DIR) not in sys.path:
    sys.path.insert(0, str(SYNCER_DIR))

from services.base_service import RemoteNotFound  # noqa: E402
from services.detector_service import (  # noqa: E402
    create_detector,
    fetch_detector_export_by_id,
    update_detector,
)
from services.group_service import (  # noqa: E402
    create_dashboard_group_via_import,
    fetch_group_export_by_id,
    update_dashboard_group,
)
from services.navigator_service import (  # noqa: E402
    create_navigator,
    fetch_navigator_export_by_id,
    update_navigator,
)
from utils import (  # noqa: E402
    base_api_url_from_realm,
    canonical_path_for,
    compare_json_objects,
    extract_resource_info,
    find_local_file_for_id,
    get_changed_files,
    get_master_credentials,
    summarize_group_changes,
    write_local_resource,
)

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_NOT_FOUND = 3
EXIT_API_FAILURE = 4
EXIT_PARTIAL = 5
EXIT_REFUSED = 6

VALID_TYPES = ("navigator", "group", "detector")

# Directory-to-type mapping used to infer the resource type from a local
# path. Inverse of utils.RESOURCE_DIRS but kept inline in the CLI so the
# CLI's path-handling stays self-contained and easy to reason about.
_DIR_TO_TYPE = {"navigators": "navigator", "group": "group", "detector": "detector"}


# --- credential helpers --------------------------------------------------


class CliError(RuntimeError):
    """Raised on user-visible CLI errors that should not produce a traceback."""

    def __init__(self, message: str, exit_code: int = EXIT_USAGE) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def resolve_credentials() -> tuple[str, str]:
    """Return ``(realm, token)`` for Master SignalBuddy.

    There is only one set of credentials: the master token. We look for
    it in the root ``.token`` file first, then in process env vars of
    the same name. Raises :class:`CliError` (never a raw exception)
    with an actionable message on any failure mode.
    """
    try:
        creds = get_master_credentials()
    except RuntimeError as e:
        raise CliError(str(e), exit_code=EXIT_USAGE) from e
    if creds is not None:
        return creds
    raise CliError(
        "No credentials available for Master SignalBuddy. Put your API "
        "token in the root .token file (a single line, nothing else), or "
        "export it as the SIGNALBUDDY_TOKEN environment variable.",
    )


def maybe_resolve_credentials() -> tuple[str, str] | None:
    """Like :func:`resolve_credentials` but returns ``None`` instead of raising.

    Used by read-only paths (``plan``) where the user may want a
    local-only summary without contacting SignalBuddy at all. A
    malformed ``.token`` is still surfaced loudly — silently swallowing
    it would mask a config bug.
    """
    try:
        return get_master_credentials()
    except RuntimeError as e:
        raise CliError(str(e), exit_code=EXIT_USAGE) from e


# --- output helpers ------------------------------------------------------


def emit(result: dict[str, Any]) -> None:
    """Print a single structured JSON object to stdout."""
    json.dump(result, sys.stdout, indent=2, sort_keys=False, default=str)
    sys.stdout.write("\n")


def stderr(msg: str) -> None:
    print(msg, file=sys.stderr)


# --- fetch / update routing ---------------------------------------------


def _fetch_resource(rtype: str, rid: str, base_url: str, token: str) -> dict[str, Any]:
    if rtype == "navigator":
        return fetch_navigator_export_by_id(rid, base_url, token)
    if rtype == "group":
        return fetch_group_export_by_id(rid, base_url, token)
    if rtype == "detector":
        return fetch_detector_export_by_id(rid, base_url, token)
    raise CliError(f"Unknown resource type {rtype!r}; expected one of {VALID_TYPES}")


def _apply_resource(rtype: str, local: dict[str, Any], base_url: str, token: str) -> bool:
    if rtype == "navigator":
        return update_navigator(local, base_url, token)
    if rtype == "group":
        return update_dashboard_group(local, base_url, token)
    if rtype == "detector":
        return update_detector(local, base_url, token)
    raise CliError(f"Unknown resource type {rtype!r}; expected one of {VALID_TYPES}")


def _create_resource(rtype: str, payload: dict[str, Any], base_url: str, token: str) -> dict[str, Any]:
    """Dispatch to the right ``create_*`` service function for ``rtype``.

    Returns the API response JSON so the caller can extract the
    server-assigned id for write-back.
    """
    if rtype == "navigator":
        return create_navigator(payload, base_url, token)
    if rtype == "group":
        return create_dashboard_group_via_import(payload, base_url, token)
    if rtype == "detector":
        return create_detector(payload, base_url, token)
    raise CliError(f"Unknown resource type {rtype!r}; expected one of {VALID_TYPES}")


# --- targeting / path helpers -------------------------------------------


def _resource_type_from_path(path: Path) -> str | None:
    """Infer ``navigator|group|detector`` from a file path's parent dir.

    Walks parents because navigators are nested one extra level deep
    (``navigators/<category>/<name>.json``); groups and detectors are flat.
    """
    for part in path.parts:
        rtype = _DIR_TO_TYPE.get(part)
        if rtype:
            return rtype
    return None


def _new_id_from_create_response(rtype: str, response: dict[str, Any]) -> str | None:
    """Pull the server-assigned id out of a ``create_*`` response.

    Each resource type's create endpoint returns a slightly different
    shape. ``None`` if the response doesn't carry an id in the expected
    place — the caller decides whether that's fatal.
    """
    if not isinstance(response, dict):
        return None
    if rtype == "group":
        # POST /v2/dashboardgroup/import returns the full export payload
        # with new ids; the new group id lives at groupExport.group.id.
        return response.get("groupExport", {}).get("group", {}).get("id")
    if rtype == "navigator":
        # POST /v2/navigator returns the created navigator object.
        return response.get("id")
    if rtype == "detector":
        return response.get("id")
    return None


def _resolve_writeback_path(
    rtype: str, rid: str, fresh: dict[str, Any], explicit_out: Path | None
) -> Path:
    """Decide where to write a master-side export on disk.

    Resolution order: (1) explicit ``--out``, (2) existing local file
    matched by id, (3) canonical path computed from the resource name.
    Navigators have a category subdirectory that we can't infer from
    the export — for those we require an existing match or explicit
    ``--out`` and surface a clear error otherwise.

    ``--out`` is sandboxed: relative paths resolve against ``REPO_ROOT``
    and any path that escapes the repo (symlinks included) is rejected.
    ``write_local_resource`` would otherwise happily ``mkdir -p`` and
    overwrite arbitrary files when invoked by automation.
    """
    if explicit_out is not None:
        target = explicit_out if explicit_out.is_absolute() else REPO_ROOT / explicit_out
        target = target.resolve()
        if not target.is_relative_to(REPO_ROOT):
            raise CliError(
                f"--out {explicit_out} resolves outside the repository root "
                f"({REPO_ROOT}); refusing to write",
                exit_code=EXIT_USAGE,
            )
        return target
    existing = find_local_file_for_id(rtype, rid)
    if existing:
        return existing
    info = extract_resource_info_from_payload(rtype, fresh)
    name = (info or (None, None))[1]
    if not name:
        raise CliError(
            f"could not infer output path for {rtype} {rid}: missing name in export; "
            "pass --out <path>",
            exit_code=EXIT_USAGE,
        )
    canonical = canonical_path_for(rtype, name)
    if canonical is None:
        raise CliError(
            f"could not infer output path for {rtype} {name!r}: "
            "navigators require either an existing local file with this id "
            "or an explicit --out <path>",
            exit_code=EXIT_USAGE,
        )
    return canonical


def extract_resource_info_from_payload(
    rtype: str, payload: dict[str, Any]
) -> tuple[str | None, str | None] | None:
    """In-memory variant of utils.extract_resource_info.

    Pulls (id, name) from an already-loaded export dict so we don't have
    to round-trip through a temp file just to inspect a fetched payload.
    """
    if rtype == "navigator":
        nav = payload.get("navigatorExport", {}).get("navigator", {})
        return (nav.get("id"), nav.get("name"))
    if rtype == "group":
        grp = payload.get("groupExport", {}).get("group", {})
        return (grp.get("id"), grp.get("name"))
    if rtype == "detector":
        det = payload.get("detectorExport", {}).get("detector", {})
        return (det.get("id"), det.get("name"))
    return None




# --- subcommand implementations -----------------------------------------


def _load_local_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise CliError(f"File not found: {path}", exit_code=EXIT_NOT_FOUND)
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise CliError(f"Failed to parse JSON {path}: {e}", exit_code=EXIT_USAGE) from e


def _filter_changed_by_paths(
    changed: list[tuple[str, Path]], wanted: list[str] | None
) -> list[tuple[str, Path]]:
    if not wanted:
        return changed
    wanted_resolved = {str(Path(p).resolve()) for p in wanted}
    return [(t, p) for (t, p) in changed if str(p.resolve()) in wanted_resolved]


def cmd_plan(args: argparse.Namespace) -> int:
    """Compute and emit the list of resources that would be synced.

    If credentials are available we fetch each changed resource from
    master and produce a per-file change summary. If not (no ``.token``,
    no env vars) we still emit a local-only plan with
    ``remote_state="unknown"`` for every entry — useful for an offline
    "what would I sync" sanity check.
    """
    creds = maybe_resolve_credentials()
    changed = _filter_changed_by_paths(get_changed_files(), args.paths)

    resources: list[dict[str, Any]] = []
    fetch_errors = 0
    for rtype, path in changed:
        info = extract_resource_info(rtype, path)
        rid, rname = (info or (None, None))
        rel_path = str(path.relative_to(REPO_ROOT)) if REPO_ROOT in path.parents else str(path)
        entry: dict[str, Any] = {
            "type": rtype,
            "path": rel_path,
            "id": rid,
            "name": rname,
            "remote_state": "unknown",
        }
        if creds and rid:
            realm, token = creds
            base_url = base_api_url_from_realm(realm)
            try:
                remote = _fetch_resource(rtype, rid, base_url, token)
                local = _load_local_json(path)
                if rtype == "group":
                    entry["change_summary"] = summarize_group_changes(remote, local)
                else:
                    entry["changes"] = compare_json_objects(remote, local)
                entry["remote_state"] = "exists"
            except RuntimeError as e:
                entry["remote_state"] = "missing_or_unreadable"
                entry["fetch_error"] = str(e)
                fetch_errors += 1
        resources.append(entry)

    emit(
        {
            "command": "plan",
            "realm": creds[0] if creds else None,
            "would_sync_count": len(resources),
            "resources": resources,
            "fetch_errors": fetch_errors,
        }
    )
    return EXIT_OK


def cmd_apply(args: argparse.Namespace) -> int:
    """Push all locally changed files to Master SignalBuddy. Requires --yes."""
    if not args.yes:
        raise CliError("apply is destructive; re-run with --yes to confirm")
    realm, token = resolve_credentials()
    base_url = base_api_url_from_realm(realm)

    changed = _filter_changed_by_paths(get_changed_files(), args.paths)
    if not changed:
        emit({"command": "apply", "applied_count": 0, "results": [], "realm": realm})
        return EXIT_OK

    results: list[dict[str, Any]] = []
    failures = 0
    for rtype, path in changed:
        info = extract_resource_info(rtype, path)
        rid, rname = (info or (None, None))
        rel_path = str(path.relative_to(REPO_ROOT)) if REPO_ROOT in path.parents else str(path)
        entry: dict[str, Any] = {"type": rtype, "path": rel_path, "id": rid, "name": rname}
        if not rid:
            entry["status"] = "skipped"
            entry["reason"] = "could not extract resource id"
            failures += 1
            results.append(entry)
            continue
        try:
            local = _load_local_json(path)
            ok = _apply_resource(rtype, local, base_url, token)
            entry["status"] = "applied" if ok else "failed"
            if not ok:
                failures += 1
        except (RuntimeError, CliError) as e:
            entry["status"] = "failed"
            entry["error"] = str(e)
            failures += 1
        results.append(entry)

    emit(
        {
            "command": "apply",
            "realm": realm,
            "applied_count": sum(1 for r in results if r.get("status") == "applied"),
            "failed_count": failures,
            "results": results,
        }
    )
    return EXIT_OK if failures == 0 else EXIT_PARTIAL


def cmd_fetch(args: argparse.Namespace) -> int:
    """Fetch the current master state of a single resource as JSON."""
    if args.type not in VALID_TYPES:
        raise CliError(f"type must be one of {VALID_TYPES}, got {args.type!r}")
    realm, token = resolve_credentials()
    base_url = base_api_url_from_realm(realm)
    try:
        data = _fetch_resource(args.type, args.id, base_url, token)
    except RuntimeError as e:
        raise CliError(str(e), exit_code=EXIT_API_FAILURE) from e
    emit(
        {
            "command": "fetch",
            "realm": realm,
            "type": args.type,
            "id": args.id,
            "resource": data,
        }
    )
    return EXIT_OK


def cmd_diff(args: argparse.Namespace) -> int:
    """Diff a single local JSON file against the current master state."""
    path = Path(args.path)
    local = _load_local_json(path)

    rtype: str | None = None
    for candidate in VALID_TYPES:
        if candidate in path.parts or candidate + "s" in path.parts:
            rtype = candidate
            break
    if rtype is None:
        # Look at the JSON structure as a fallback
        if "navigatorExport" in local:
            rtype = "navigator"
        elif "groupExport" in local:
            rtype = "group"
        elif "detectorExport" in local:
            rtype = "detector"
    if rtype is None:
        raise CliError(
            f"Cannot infer resource type from path or content: {path}. "
            "Move the file under navigators/, group/, or detector/."
        )
    info = extract_resource_info(rtype, path)
    rid, rname = (info or (None, None))
    if not rid:
        raise CliError(f"Could not extract resource id from {path}")

    realm, token = resolve_credentials()
    base_url = base_api_url_from_realm(realm)
    try:
        remote = _fetch_resource(rtype, rid, base_url, token)
    except RuntimeError as e:
        raise CliError(str(e), exit_code=EXIT_API_FAILURE) from e

    result: dict[str, Any] = {
        "command": "diff",
        "realm": realm,
        "type": rtype,
        "id": rid,
        "name": rname,
        "path": str(path),
    }
    if rtype == "group":
        result["change_summary"] = summarize_group_changes(remote, local)
    else:
        result["changes"] = compare_json_objects(remote, local)
    emit(result)
    return EXIT_OK


# --- new single-resource verbs ------------------------------------------


def _load_payload_from_path(path: Path) -> tuple[str, str, dict[str, Any]]:
    """Resolve (rtype, rid, payload) from a local file path.

    Validates that the file lives under a known canonical directory and
    that the JSON carries an id — keeps the caller's logic free of
    type-dispatch on local files.
    """
    rtype = _resource_type_from_path(path)
    if not rtype:
        raise CliError(
            f"cannot infer resource type from path {path}: "
            "expected a file under navigators/, group/, or detector/",
        )
    if not path.exists():
        raise CliError(f"File not found: {path}", exit_code=EXIT_NOT_FOUND)
    payload = _load_local_json(path)
    info = extract_resource_info_from_payload(rtype, payload)
    rid = (info or (None, None))[0]
    if not rid:
        raise CliError(
            f"local file {path} has no id; use 'create {path}' instead of 'update'",
        )
    return rtype, rid, payload


def _fetch_or_remote_not_found(
    rtype: str, rid: str, base_url: str, token: str
) -> tuple[bool, dict[str, Any] | None, str | None]:
    """Wrap ``_fetch_resource`` returning (exists, payload, error_text).

    Used by the pre-checks on ``update`` (must exist) and ``create``
    (must NOT exist). Returns a tri-state instead of raising so each
    caller can produce a verb-appropriate message.
    """
    try:
        payload = _fetch_resource(rtype, rid, base_url, token)
        return True, payload, None
    except RemoteNotFound:
        return False, None, None
    except RuntimeError as e:
        return False, None, str(e)


def _refresh_local(
    rtype: str,
    rid: str,
    base_url: str,
    token: str,
    explicit_out: Path | None = None,
) -> Path:
    """Re-fetch ``rid`` from master and write the export to disk.

    Shared by ``update`` (post-write refresh), ``create`` (capture the
    new server-assigned id), and ``pull`` (the whole purpose).
    Raises ``CliError`` on any failure so callers never see a
    half-finished write.
    """
    try:
        fresh = _fetch_resource(rtype, rid, base_url, token)
    except RuntimeError as e:
        raise CliError(
            f"write succeeded but post-write fetch from master failed: {e}",
            exit_code=EXIT_API_FAILURE,
        ) from e
    target = _resolve_writeback_path(rtype, rid, fresh, explicit_out)
    write_local_resource(target, fresh)
    return target


def cmd_update(args: argparse.Namespace) -> int:
    """Strict update: PUT the local file to master; fail on 404.

    Pre-checks that the resource exists in master with a GET so the
    error message points the user at ``create`` instead of falling
    through silently. On success, re-fetches from master and overwrites
    the local file so server-normalized fields (``lastUpdated``, etc.)
    end up on disk.
    """
    if not args.yes:
        raise CliError("update is destructive; re-run with --yes to confirm")
    realm, token = resolve_credentials()
    base_url = base_api_url_from_realm(realm)

    local_path = Path(args.path)
    rtype, rid, payload = _load_payload_from_path(local_path)

    exists, _, fetch_err = _fetch_or_remote_not_found(rtype, rid, base_url, token)
    if not exists and fetch_err:
        raise CliError(
            f"failed to check {rtype} {rid} in master: {fetch_err}",
            exit_code=EXIT_API_FAILURE,
        )
    if not exists:
        raise CliError(
            f"{rtype} {rid} not found in master; "
            f"use 'create {args.path}' instead",
            exit_code=EXIT_NOT_FOUND,
        )

    try:
        ok = _apply_resource(rtype, payload, base_url, token)
    except RuntimeError as e:
        raise CliError(str(e), exit_code=EXIT_API_FAILURE) from e
    if not ok:
        raise CliError(
            f"update of {rtype} {rid} failed (see stderr above)",
            exit_code=EXIT_API_FAILURE,
        )

    target = _refresh_local(rtype, rid, base_url, token, local_path)
    rel = str(target.relative_to(REPO_ROOT)) if REPO_ROOT in target.parents else str(target)

    emit(
        {
            "command": "update",
            "realm": realm,
            "type": rtype,
            "id": rid,
            "status": "applied",
            "local_file_written": rel,
        }
    )
    return EXIT_OK


def cmd_create(args: argparse.Namespace) -> int:
    """Strict create: POST a new resource to master; fail if id exists.

    For groups the create uses ``POST /v2/dashboardgroup/import`` so the
    backend rewires all child ids server-side; for navigator/detector
    the inner object is POSTed with server-managed metadata fields
    stripped. After a successful create the local file is overwritten
    with the fresh export so it carries the new server-assigned id.
    """
    if not args.yes:
        raise CliError("create is destructive; re-run with --yes to confirm")
    realm, token = resolve_credentials()
    base_url = base_api_url_from_realm(realm)

    local_path = Path(args.path)
    rtype = _resource_type_from_path(local_path)
    if not rtype:
        raise CliError(
            f"cannot infer resource type from path {local_path}: "
            "expected a file under navigators/, group/, or detector/",
        )
    if not local_path.exists():
        raise CliError(f"File not found: {local_path}", exit_code=EXIT_NOT_FOUND)
    payload = _load_local_json(local_path)
    info = extract_resource_info_from_payload(rtype, payload)
    rid = (info or (None, None))[0]

    # Refuse to duplicate an existing resource. ``rid`` may be empty for
    # a brand-new local file, in which case there is nothing to check.
    if rid:
        exists, _, fetch_err = _fetch_or_remote_not_found(rtype, rid, base_url, token)
        if exists:
            raise CliError(
                f"{rtype} {rid} already exists in master; "
                f"use 'update {local_path}' instead",
                exit_code=EXIT_REFUSED,
            )
        if not exists and fetch_err:
            raise CliError(
                f"failed to check {rtype} {rid} in master: {fetch_err}",
                exit_code=EXIT_API_FAILURE,
            )

    try:
        response = _create_resource(rtype, payload, base_url, token)
    except RuntimeError as e:
        raise CliError(str(e), exit_code=EXIT_API_FAILURE) from e

    new_id = _new_id_from_create_response(rtype, response)
    if not new_id:
        raise CliError(
            "create succeeded but could not extract new id from response; "
            "skipping local refresh. Use `pull` once you know the new id.",
            exit_code=EXIT_API_FAILURE,
        )

    target = _refresh_local(rtype, new_id, base_url, token, local_path)
    rel = str(target.relative_to(REPO_ROOT)) if REPO_ROOT in target.parents else str(target)

    emit(
        {
            "command": "create",
            "realm": realm,
            "type": rtype,
            "source_id": rid,
            "new_id": new_id,
            "status": "created",
            "local_file_written": rel,
        }
    )
    return EXIT_OK


def cmd_pull(args: argparse.Namespace) -> int:
    """Fetch a single resource from master and write it to a local file.

    Resolution order for the output path: explicit ``--out`` first,
    then any existing local file whose id matches, then the canonical
    path computed from the resource name. Navigators without an
    existing local match require ``--out`` because the category
    subdirectory can't be inferred from the export payload.
    """
    if not args.yes:
        raise CliError("pull overwrites local files; re-run with --yes to confirm")
    if args.type not in VALID_TYPES:
        raise CliError(f"--type must be one of {VALID_TYPES}, got {args.type!r}")
    realm, token = resolve_credentials()
    base_url = base_api_url_from_realm(realm)

    try:
        fresh = _fetch_resource(args.type, args.id, base_url, token)
    except RemoteNotFound as e:
        raise CliError(
            f"{args.type} {args.id} not found in master",
            exit_code=EXIT_NOT_FOUND,
        ) from e
    except RuntimeError as e:
        raise CliError(str(e), exit_code=EXIT_API_FAILURE) from e

    explicit_out = Path(args.out) if args.out else None
    target = _resolve_writeback_path(args.type, args.id, fresh, explicit_out)
    write_local_resource(target, fresh)
    rel = str(target.relative_to(REPO_ROOT)) if REPO_ROOT in target.parents else str(target)
    emit(
        {
            "command": "pull",
            "realm": realm,
            "type": args.type,
            "id": args.id,
            "local_file_written": rel,
        }
    )
    return EXIT_OK


# --- argument parsing ----------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="syncer.cli",
        description="Content syncer between this repo and Master SignalBuddy.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    plan = sub.add_parser("plan", help="Show what would be synced (dry-run).")
    plan.add_argument(
        "--paths",
        nargs="*",
        help="Optional list of files to include; defaults to all changed JSON files.",
    )
    plan.set_defaults(func=cmd_plan)

    apply_p = sub.add_parser("apply", help="Push all locally changed files to Master SignalBuddy.")
    apply_p.add_argument(
        "--paths",
        nargs="*",
        help="Optional list of files to include; defaults to all changed JSON files.",
    )
    apply_p.add_argument("--yes", action="store_true", help="Required to confirm destructive write.")
    apply_p.set_defaults(func=cmd_apply)

    update_p = sub.add_parser(
        "update",
        help="Strict update of one resource from a local file (no fallback to create).",
    )
    update_p.add_argument("path", help="Local JSON file to push to master.")
    update_p.add_argument("--yes", action="store_true", help="Required to confirm destructive write.")
    update_p.set_defaults(func=cmd_update)

    create_p = sub.add_parser(
        "create",
        help="Strict create of one resource from a local file (no overwrite of existing).",
    )
    create_p.add_argument("path", help="Local JSON file to POST to master.")
    create_p.add_argument("--yes", action="store_true", help="Required to confirm destructive write.")
    create_p.set_defaults(func=cmd_create)

    pull_p = sub.add_parser(
        "pull",
        help="Fetch one resource from master and overwrite the matching local file.",
    )
    pull_p.add_argument("--type", choices=VALID_TYPES, required=True)
    pull_p.add_argument("--id", required=True)
    pull_p.add_argument(
        "--out",
        help="Optional output path; defaults to the existing local file or the canonical path.",
    )
    pull_p.add_argument("--yes", action="store_true", help="Required to confirm destructive write.")
    pull_p.set_defaults(func=cmd_pull)

    fetch_p = sub.add_parser("fetch", help="Fetch current state of a single resource (stdout).")
    fetch_p.add_argument("type", choices=VALID_TYPES)
    fetch_p.add_argument("id")
    fetch_p.set_defaults(func=cmd_fetch)

    diff_p = sub.add_parser("diff", help="Diff a local file vs master state.")
    diff_p.add_argument("path")
    diff_p.set_defaults(func=cmd_diff)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except CliError as e:
        stderr(f"error: {e}")
        return e.exit_code


if __name__ == "__main__":
    raise SystemExit(main())

"""Push changed JSON content to Master SignalBuddy and refresh local hashCodes."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def sync_changed_json(
    paths: list[str] | None = None,
    *,
    refresh_local: bool = True,
) -> dict[str, Any]:
    """Run syncer plan + apply for changed content JSON files.

    When ``refresh_local`` is True (default), each applied file is
    re-fetched from Master SignalBuddy so the local copy carries the
    updated ``hashCode`` required by CI validation.
    """
    cmd = [
        sys.executable,
        "-m",
        "contentforge.syncer.cli",
        "apply",
        "--yes",
    ]
    if refresh_local:
        cmd.append("--refresh-local")
    if paths:
        cmd.extend(["--paths", *paths])

    result = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    if not result.stdout.strip():
        return {
            "ok": result.returncode == 0,
            "exit_code": result.returncode,
            "error": result.stderr or "syncer produced no output",
        }

    payload = json.loads(result.stdout)
    payload["ok"] = result.returncode in (0, 5)
    payload["exit_code"] = result.returncode
    return payload


def plan_changed_json(paths: list[str] | None = None) -> dict[str, Any]:
    """Dry-run: show what would be synced without writing."""
    cmd = [sys.executable, "-m", "contentforge.syncer.cli", "plan"]
    if paths:
        cmd.extend(["--paths", *paths])

    result = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    if not result.stdout.strip():
        return {"ok": False, "error": result.stderr or "syncer produced no output"}

    payload = json.loads(result.stdout)
    payload["ok"] = result.returncode == 0
    return payload

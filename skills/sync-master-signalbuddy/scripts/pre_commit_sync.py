"""Synchronize staged content with Master SignalBuddy before a Git commit."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence


REPO_ROOT = Path(__file__).resolve().parents[3]
SYNC_SCRIPT = REPO_ROOT / "skills/sync-master-signalbuddy/scripts/sync_changed.py"
VALIDATION_SCRIPT = REPO_ROOT / "tools/scripts/validate_content.sh"
CONTENT_DIRECTORIES = ("navigators/", "detector/", "group/")


class HookError(RuntimeError):
    """A pre-commit condition that must block the commit."""


def _run(
    command: Sequence[str],
    *,
    capture_output: bool = False,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=capture_output,
        check=False,
    )


def _git_paths(*args: str) -> list[str]:
    result = _run(("git", *args), capture_output=True)
    if result.returncode != 0:
        raise HookError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return [line for line in result.stdout.splitlines() if line]


def _is_sync_content(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return normalized.endswith(".json") and normalized.startswith(CONTENT_DIRECTORIES)


def staged_content_paths() -> list[str]:
    """Return staged navigator, detector, and group JSON paths."""
    staged = _git_paths(
        "diff", "--cached", "--name-only", "--diff-filter=ACMR", "--"
    )
    return sorted(path for path in staged if _is_sync_content(path))


def unstaged_versions(paths: Sequence[str]) -> list[str]:
    """Return selected paths that also contain unstaged changes."""
    if not paths:
        return []
    changed = set(_git_paths("diff", "--name-only", "--", *paths))
    return [path for path in paths if path in changed]


def validate_content() -> None:
    env = os.environ.copy()
    env.pop("CI_MR_TARGET_BRANCH", None)
    result = _run(("/bin/bash", str(VALIDATION_SCRIPT)), env=env)
    if result.returncode != 0:
        raise HookError("content validation failed")


def run_sync_command(command: str, paths: Sequence[str]) -> dict[str, Any]:
    args = [sys.executable, str(SYNC_SCRIPT), command, "--paths", *paths]
    if command == "apply":
        args.append("--yes")

    result = _run(args, capture_output=True)
    if result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    if result.stderr:
        print(result.stderr, end="" if result.stderr.endswith("\n") else "\n", file=sys.stderr)
    if result.returncode != 0:
        raise HookError(f"Master SignalBuddy {command} failed (exit {result.returncode})")

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise HookError(f"Master SignalBuddy {command} returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise HookError(f"Master SignalBuddy {command} returned an invalid result")
    return payload


def require_exact_results(
    payload: dict[str, Any], paths: Sequence[str], *, phase: str
) -> None:
    """Fail closed unless the sync result accounts for every selected path."""
    entries_key = "resources" if phase == "plan" else "results"
    entries = payload.get(entries_key)
    if not isinstance(entries, list):
        raise HookError(f"Master SignalBuddy {phase} omitted {entries_key}")

    returned_paths = {
        entry.get("path") for entry in entries if isinstance(entry, dict)
    }
    missing = [path for path in paths if path not in returned_paths]
    unexpected = sorted(
        path for path in returned_paths if isinstance(path, str) and path not in paths
    )
    if missing or unexpected:
        details = []
        if missing:
            details.append("missing:\n" + "\n".join(f"  - {path}" for path in missing))
        if unexpected:
            details.append(
                "unexpected:\n" + "\n".join(f"  - {path}" for path in unexpected)
            )
        raise HookError(
            f"Master SignalBuddy {phase} did not exactly match the staged files:\n"
            + "\n".join(details)
        )

    if phase == "apply":
        incomplete = []
        for entry in entries:
            if not isinstance(entry, dict):
                incomplete.append("<unknown>")
            elif entry.get("status") != "applied":
                incomplete.append(entry.get("path", "<unknown>"))
        if incomplete:
            formatted = "\n".join(f"  - {path}" for path in incomplete)
            raise HookError(
                "Master SignalBuddy did not apply every staged file:\n"
                f"{formatted}"
            )


def main() -> int:
    try:
        paths = staged_content_paths()
        if not paths:
            validate_content()
            return 0

        mixed = unstaged_versions(paths)
        if mixed:
            formatted = "\n".join(f"  - {path}" for path in mixed)
            raise HookError(
                "these staged content files also have unstaged edits; stage or "
                f"discard those edits before committing:\n{formatted}"
            )

        print("Synchronizing staged content with Master SignalBuddy:")
        for path in paths:
            print(f"  - {path}")

        plan = run_sync_command("plan", paths)
        if int(plan.get("fetch_errors", 0)) > 0:
            raise HookError("the sync plan contains remote fetch errors")
        require_exact_results(plan, paths, phase="plan")

        applied = run_sync_command("apply", paths)
        if int(applied.get("failed_count", 0)) > 0:
            raise HookError("one or more Master SignalBuddy updates failed")
        require_exact_results(applied, paths, phase="apply")

        restage = _run(("git", "add", "--", *paths), capture_output=True)
        if restage.returncode != 0:
            raise HookError(restage.stderr.strip() or "failed to stage canonical exports")

        # The API export can normalize the JSON, so validate the exact files that
        # will now be committed after refreshing the index.
        validate_content()
        print("Master SignalBuddy sync complete; canonical exports are staged.")
        return 0
    except HookError as exc:
        print(f"pre-commit blocked: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

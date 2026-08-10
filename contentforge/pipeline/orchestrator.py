#!/usr/bin/env python3
"""Orchestrate bug-report workflow: JIRA ticket, GitLab triage issue, SignalBuddy sync.

The pipeline no longer opens a merge request directly. Instead, it creates
a GitLab **issue** with the Jira context and heuristic search hints, and
assigns it to a GitLab Duo Agent Platform service account. The Duo Flow
(bound to an "Assign" trigger in AI → Triggers) fires from that assignment
and produces the actual fix MR autonomously.

Usage:
  python -m contentforge.pipeline.orchestrator triage \\
    --title "Fix K8s Node CPU detector threshold" \\
    --description "Reported in #o11y-ootb-content ..." \\
    --slack-permalink "https://..."

  python -m contentforge.pipeline.orchestrator sync-json --paths "detector/K8s Node CPU.json"

Environment variables (never commit these):
  CONTENT_FORGE_JIRA_EMAIL, CONTENT_FORGE_JIRA_TOKEN — Atlassian API auth
  CONTENT_FORGE_GIT_TOKEN                            — GitLab PAT
  (legacy aliases: JIRA_EMAIL, JIRA_API_TOKEN, GITLAB_TOKEN)
  DUO_FLOW_ASSIGNEE_ID                               — GitLab user id of the
                                                       Duo service account
                                                       (overrides settings.yaml)
  SIGNALBUDDY_TOKEN                                  — Master SignalBuddy API token
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import requests
import yaml

CONTENTFORGE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = CONTENTFORGE_DIR.parent
SETTINGS_PATH = CONTENTFORGE_DIR / "settings.yaml"
CONFIG_PATH = CONTENTFORGE_DIR / "config.yaml"


def env_var(*names: str) -> str:
    """Return the first set environment variable among ``names``."""
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config() -> dict[str, Any]:
    cfg: dict[str, Any] = {}
    if SETTINGS_PATH.exists():
        with SETTINGS_PATH.open(encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    if CONFIG_PATH.exists():
        with CONFIG_PATH.open(encoding="utf-8") as f:
            cfg = _deep_merge(cfg, yaml.safe_load(f) or {})

    reviewer_env = os.environ.get("GITLAB_REVIEWER_IDS", "").strip()
    if reviewer_env:
        ids = [int(x.strip()) for x in reviewer_env.split(",") if x.strip().isdigit()]
        cfg.setdefault("gitlab", {})["default_reviewer_ids"] = ids

    mentions_env = os.environ.get("SLACK_OWNER_MENTIONS", "").strip()
    if mentions_env:
        cfg.setdefault("slack", {})["owner_mentions"] = [
            x.strip() for x in mentions_env.split(",") if x.strip()
        ]

    if not cfg:
        example = CONTENTFORGE_DIR / "config.yaml.example"
        raise SystemExit(
            f"No contentforge config found. Add {SETTINGS_PATH.name} or copy {example} "
            f"to config.yaml under contentforge/."
        )
    return cfg


def slugify(text: str, max_len: int = 48) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:max_len].rstrip("-") or "bugfix"


def jira_rest_base(cfg: dict[str, Any], token: str) -> tuple[str, str]:
    """Return (api_base, browse_base) for Jira REST calls.

    Scoped API tokens (ATATT3…) must use the platform gateway:
      https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3
    Classic tokens use the site URL:
      https://splunk.atlassian.net/rest/api/3

    See: https://support.atlassian.com/atlassian-account/docs/manage-api-tokens-for-your-atlassian-account/
    """
    jira = cfg.get("jira", {})
    browse_base = jira.get("base_url", "https://splunk.atlassian.net").rstrip("/")
    cloud_id = env_var("CONTENT_FORGE_JIRA_CLOUD_ID") or jira.get("cloud_id", "")
    use_gateway = env_var("CONTENT_FORGE_JIRA_USE_GATEWAY").lower() in ("1", "true", "yes")
    if not use_gateway and token.startswith("ATATT3"):
        use_gateway = True

    if use_gateway and cloud_id:
        api_base = f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3"
        return api_base, browse_base

    if use_gateway and not cloud_id:
        raise SystemExit(
            "Scoped Jira API token detected. Set jira.cloud_id in contentforge/settings.yaml "
            "or CONTENT_FORGE_JIRA_CLOUD_ID (see https://splunk.atlassian.net/_edge/tenant_info)."
        )

    return f"{browse_base}/rest/api/3", browse_base


def _extract_adf_text(node: Any) -> str:
    """Best-effort extraction of plain text from an Atlassian Document Format node.

    Jira returns descriptions and comments as nested ADF JSON. We only need a
    text summary for downstream heuristic search, so we walk the tree and
    concatenate every ``text`` leaf we find.
    """
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return "\n".join(x for x in (_extract_adf_text(n) for n in node) if x)
    if isinstance(node, dict):
        parts: list[str] = []
        if node.get("type") == "text" and isinstance(node.get("text"), str):
            parts.append(node["text"])
        content = node.get("content")
        if content:
            parts.append(_extract_adf_text(content))
        return " ".join(p for p in parts if p)
    return ""


def get_jira_issue(cfg: dict[str, Any], key: str) -> dict[str, Any]:
    """Fetch an existing Jira issue by key.

    Returns the same shape as :func:`create_jira_issue` plus ``summary`` and
    ``description_text`` fields, so callers can drop-in either result.
    Used when the pipeline is triggered against an already-created ticket
    (Forge → Jira → automation flow).
    """
    email = env_var("CONTENT_FORGE_JIRA_EMAIL", "JIRA_EMAIL")
    token = env_var("CONTENT_FORGE_JIRA_TOKEN", "JIRA_API_TOKEN")
    if not email or not token:
        raise SystemExit(
            "Set CONTENT_FORGE_JIRA_EMAIL and CONTENT_FORGE_JIRA_TOKEN "
            "(or JIRA_EMAIL and JIRA_API_TOKEN)."
        )

    api_base, browse_base = jira_rest_base(cfg, token)
    resp = requests.get(
        f"{api_base}/issue/{key}",
        auth=(email, token),
        headers={"Accept": "application/json"},
        params={"fields": "summary,description,status,assignee,reporter"},
        timeout=60,
    )
    if resp.status_code >= 400:
        raise SystemExit(f"JIRA fetch failed ({resp.status_code}): {resp.text}")

    data = resp.json()
    fields = data.get("fields", {}) or {}
    return {
        "key": data.get("key") or key,
        "url": f"{browse_base}/browse/{key}",
        "id": data.get("id"),
        "summary": fields.get("summary") or "",
        "description_text": _extract_adf_text(fields.get("description")),
        "status": (fields.get("status") or {}).get("name"),
        "reused": True,
    }


def comment_on_jira_issue(
    cfg: dict[str, Any], key: str, comment_text: str
) -> dict[str, Any]:
    """Append a plain-text comment to an existing Jira issue.

    Comment failures are treated as non-fatal (logged, returned as
    ``{"ok": False, ...}``) so a Jira permissions issue never blocks an
    otherwise-successful MR + Slack notification.
    """
    email = env_var("CONTENT_FORGE_JIRA_EMAIL", "JIRA_EMAIL")
    token = env_var("CONTENT_FORGE_JIRA_TOKEN", "JIRA_API_TOKEN")
    if not email or not token:
        print(
            "[orchestrator] JIRA comment skipped: credentials not set",
            file=sys.stderr,
        )
        return {"ok": False, "error": "missing_credentials"}

    api_base, _ = jira_rest_base(cfg, token)
    payload = {
        "body": {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": comment_text}],
                }
            ],
        }
    }
    resp = requests.post(
        f"{api_base}/issue/{key}/comment",
        auth=(email, token),
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        json=payload,
        timeout=60,
    )
    if resp.status_code >= 400:
        print(
            f"[orchestrator] JIRA comment failed ({resp.status_code}): {resp.text}",
            file=sys.stderr,
        )
        return {"ok": False, "status_code": resp.status_code}
    return {"ok": True, "comment_id": resp.json().get("id")}


def create_jira_issue(
    cfg: dict[str, Any],
    *,
    title: str,
    description: str,
    slack_permalink: str | None = None,
) -> dict[str, Any]:
    email = env_var("CONTENT_FORGE_JIRA_EMAIL", "JIRA_EMAIL")
    token = env_var("CONTENT_FORGE_JIRA_TOKEN", "JIRA_API_TOKEN")
    if not email or not token:
        raise SystemExit(
            "Set CONTENT_FORGE_JIRA_EMAIL and CONTENT_FORGE_JIRA_TOKEN "
            "(or JIRA_EMAIL and JIRA_API_TOKEN)."
        )

    jira = cfg.get("jira", {})
    api_base, browse_base = jira_rest_base(cfg, token)
    project_key = env_var("CONTENT_FORGE_JIRA_PROJECT_KEY") or jira.get("project_key", "BITS")
    issue_type = jira.get("issue_type", "Bug")
    labels = jira.get("default_labels") or []

    body_parts = [description]
    if slack_permalink:
        body_parts.append(f"\n\nSlack thread: {slack_permalink}")

    payload = {
        "fields": {
            "project": {"key": project_key},
            "summary": title,
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": "\n".join(body_parts)}],
                    }
                ],
            },
            "issuetype": {"name": issue_type},
            "labels": labels,
        }
    }

    resp = requests.post(
        f"{api_base}/issue",
        auth=(email, token),
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        json=payload,
        timeout=60,
    )
    if resp.status_code >= 400:
        raise SystemExit(f"JIRA create failed ({resp.status_code}): {resp.text}")

    data = resp.json()
    key = data.get("key")
    return {
        "key": key,
        "url": f"{browse_base}/browse/{key}",
        "id": data.get("id"),
    }


def _duo_flow_assignee_id(cfg: dict[str, Any]) -> int | None:
    """Return the GitLab user id of the Duo Flow service account, if configured.

    Precedence: ``DUO_FLOW_ASSIGNEE_ID`` env var (CI) > ``gitlab.duo_flow_assignee_id``
    in ``settings.yaml`` / ``config.yaml``. Missing config is not fatal — the
    issue is still created (unassigned), a loud warning is logged, and the
    caller can manually assign to trigger the Flow.
    """
    raw = (env_var("DUO_FLOW_ASSIGNEE_ID") or "").strip()
    if not raw:
        raw = str((cfg.get("gitlab") or {}).get("duo_flow_assignee_id") or "").strip()
    if not raw or raw.lower() in ("none", "null"):
        return None
    try:
        return int(raw)
    except ValueError:
        print(
            f"[orchestrator] WARNING: duo_flow_assignee_id={raw!r} is not an integer; "
            "issue will be created unassigned.",
            file=sys.stderr,
        )
        return None


def create_gitlab_issue(
    cfg: dict[str, Any],
    *,
    title: str,
    description: str,
    jira_key: str | None = None,
) -> dict[str, Any]:
    """Create a GitLab issue and assign to the Duo Flow service account.

    We create an **issue**, not a merge request. The Duo Agent Platform Flow
    (configured with an "Assign" trigger against ``duo_flow_assignee_id``)
    picks up the assignment event, reads the issue body as its task context,
    and produces the fix MR autonomously.

    The issue title includes the Jira key so any MR the Flow opens can
    reference it (``Fixes #<iid>`` or ``Related: BITS-XXXX``) for Jira/GitLab
    auto-linking.

    Idempotency is intentionally NOT enforced here — the poller (see
    ``poll_forge_tickets.py``) applies a permanent ``ootb-auto-triaged``
    label on Jira before triggering us, so this function only runs once per
    ticket. If it runs twice (e.g. manual re-trigger), we create a second
    issue on purpose — cheaper than teaching the pipeline about "which of
    the two open issues counts".
    """
    gitlab_token = env_var("CONTENT_FORGE_GIT_TOKEN", "GITLAB_TOKEN")
    if not gitlab_token:
        raise SystemExit("Set CONTENT_FORGE_GIT_TOKEN (or GITLAB_TOKEN).")

    gl = cfg.get("gitlab", {})
    base_url = gl.get("base_url", "https://cd.splunkdev.com").rstrip("/")
    project_id = gl.get("project_id", 9336)
    labels = ",".join(gl.get("default_labels") or [])
    assignee_id = _duo_flow_assignee_id(cfg)

    issue_title = title if jira_key is None else f"[{jira_key}] {title}"
    issue_description = description
    if jira_key:
        jira_url = (
            f"{cfg.get('jira', {}).get('base_url', 'https://splunk.atlassian.net')}"
            f"/browse/{jira_key}"
        )
        issue_description = (
            f"{description}\n\n---\n\nJira: {jira_url}\nJira key: `{jira_key}`"
        )

    issue_payload: dict[str, Any] = {
        "title": issue_title,
        "description": issue_description,
    }
    if labels:
        issue_payload["labels"] = labels
    if assignee_id is not None:
        # GitLab accepts either assignee_id (single) or assignee_ids (array);
        # both fields fire an "Assign" webhook. We use the array form so the
        # same code path can be extended to co-assign a human reviewer later.
        issue_payload["assignee_ids"] = [assignee_id]
    else:
        print(
            "[orchestrator] WARNING: no duo_flow_assignee_id resolved. "
            "Issue will be created UNASSIGNED and Duo Flow will NOT fire. "
            "Set DUO_FLOW_ASSIGNEE_ID as a CI variable, or "
            "gitlab.duo_flow_assignee_id in contentforge/settings.yaml, "
            "then re-run.",
            file=sys.stderr,
        )

    resp = requests.post(
        f"{base_url}/api/v4/projects/{project_id}/issues",
        headers={
            "PRIVATE-TOKEN": gitlab_token,
            "Content-Type": "application/json",
        },
        json=issue_payload,
        timeout=60,
    )
    if resp.status_code >= 400:
        raise SystemExit(
            f"GitLab issue create failed ({resp.status_code}): {resp.text}"
        )

    issue = resp.json()
    return {
        "iid": issue.get("iid"),
        "web_url": issue.get("web_url"),
        "assignee_id": assignee_id,
        "assigned": assignee_id is not None,
    }


def commit_and_push_json_changes(branch: str, message: str) -> dict[str, Any]:
    status = subprocess.run(
        ["git", "status", "--porcelain", "--", "navigators/", "group/", "detector/"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    changed = [line[3:] for line in status.stdout.splitlines() if line.strip()]
    if not changed:
        return {"committed": False, "changed_files": []}

    subprocess.run(["git", "add", *changed], cwd=REPO_ROOT, check=True)
    subprocess.run(["git", "commit", "-m", message], cwd=REPO_ROOT, check=True)
    subprocess.run(["git", "push", "origin", branch], cwd=REPO_ROOT, check=True)
    return {"committed": True, "changed_files": changed}


def cmd_triage(args: argparse.Namespace) -> int:
    cfg = load_config()
    jira = create_jira_issue(
        cfg,
        title=args.title,
        description=args.description,
        slack_permalink=args.slack_permalink,
    )
    issue = create_gitlab_issue(
        cfg,
        title=args.title,
        description=args.description,
        jira_key=jira.get("key"),
    )

    result = {
        "command": "triage",
        "jira": jira,
        "gitlab_issue": issue,
    }
    print(json.dumps(result, indent=2))
    return 0


def cmd_sync_json(args: argparse.Namespace) -> int:
    from contentforge.pipeline.signalbuddy_sync import sync_changed_json

    paths = args.paths or None
    result = sync_changed_json(paths, refresh_local=not args.no_refresh)
    print(json.dumps(result, indent=2))

    if args.commit and result.get("ok"):
        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        commit_msg = args.commit_message or "chore: refresh hashCode after SignalBuddy sync"
        commit_result = commit_and_push_json_changes(branch, commit_msg)
        result["git"] = commit_result
        print(json.dumps(result, indent=2))

    return 0 if result.get("ok") else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="OOTB bug-report workflow orchestrator")
    sub = p.add_subparsers(dest="command", required=True)

    triage = sub.add_parser(
        "triage",
        help="Create JIRA ticket and GitLab issue assigned to Duo Flow service account",
    )
    triage.add_argument("--title", required=True)
    triage.add_argument("--description", required=True)
    triage.add_argument("--slack-permalink", default=None)
    triage.set_defaults(func=cmd_triage)

    sync = sub.add_parser(
        "sync-json",
        help="Push changed JSON to Master SignalBuddy and refresh hashCodes",
    )
    sync.add_argument("--paths", nargs="*", help="Specific JSON files to sync")
    sync.add_argument(
        "--no-refresh",
        action="store_true",
        help="Skip local hashCode refresh (not recommended for MRs)",
    )
    sync.add_argument(
        "--commit",
        action="store_true",
        help="Commit and push refreshed JSON files to the current branch",
    )
    sync.add_argument("--commit-message", default=None)
    sync.set_defaults(func=cmd_sync_json)

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

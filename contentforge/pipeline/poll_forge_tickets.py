#!/usr/bin/env python3
"""Poll Jira for Forge-created OOTB tickets and trigger the fix pipeline.

Runs from a GitLab scheduled pipeline (``$CI_PIPELINE_SOURCE == "schedule"``).
For each newly-created ticket that Forge posted (reporter =
``srv-jira-hermesalert``) in the configured project, we:

  1. Label the ticket ``ootb-auto-triaged`` — idempotency lock. The JQL
     filter excludes anything already carrying this label, so a mid-poll
     crash can only ever *skip* a ticket, never re-fire.
  2. POST to GitLab's pipeline trigger endpoint with
     ``variables[OOTB_JIRA_KEY]=<key>`` and ``variables[OOTB_BUG_INPUT]=<summary>``.
     That kicks off a fresh pipeline which runs ``ootb-bug-fix`` +
     ``ootb-propose-fix`` for the single ticket.

Auth model:
  The downstream pipeline is triggered with GitLab's built-in ``CI_JOB_TOKEN``
  (auto-injected into every CI job). No dedicated pipeline trigger token
  needed — CI_JOB_TOKEN can create pipelines in the same project since
  GitLab 16.7 via ``POST /api/v4/projects/:id/pipeline`` with the
  ``JOB-TOKEN`` header.

Environment variables:
  CONTENT_FORGE_JIRA_EMAIL / JIRA_EMAIL     — Jira Basic auth email
  CONTENT_FORGE_JIRA_TOKEN / JIRA_API_TOKEN — Jira API token
  CI_JOB_TOKEN                              — auto-injected by GitLab CI
  GITLAB_TRIGGER_REF                        — target branch for the triggered
                                              pipeline (default: current
                                              CI_COMMIT_REF_NAME, i.e. the
                                              same branch the poller runs on)
  GITLAB_TRIGGER_PROJECT_ID                 — GitLab project id (default: CI_PROJECT_ID)
  GITLAB_BASE_URL                           — GitLab base URL (default: CI_SERVER_URL)
  POLL_PROJECT                              — Jira project key (default: BITS)
  POLL_WINDOW_MINUTES                       — JQL 'created >= -Nm' window (default: 30)
  POLL_DRY_RUN=1                            — skip labeling + trigger, just print
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

import requests

from contentforge.pipeline.orchestrator import env_var, jira_rest_base, load_config

AUTO_TRIAGED_LABEL = "ootb-auto-triaged"
FORGE_REPORTER_EMAIL = "srv-jira-hermesalert@splunk.com"


class PollError(Exception):
    """Non-fatal error while processing a single ticket."""


def build_jql(project: str, window_minutes: int) -> str:
    return (
        f'project = {project} '
        f'AND reporter = "{FORGE_REPORTER_EMAIL}" '
        f'AND created >= -{window_minutes}m '
        f'AND (labels IS EMPTY OR labels NOT IN ({AUTO_TRIAGED_LABEL})) '
        "ORDER BY created ASC"
    )


def _jira_auth() -> tuple[str, str]:
    email = env_var("CONTENT_FORGE_JIRA_EMAIL", "JIRA_EMAIL")
    token = env_var("CONTENT_FORGE_JIRA_TOKEN", "JIRA_API_TOKEN")
    if not email or not token:
        raise SystemExit(
            "JIRA credentials not set (need JIRA_EMAIL + JIRA_API_TOKEN "
            "or CONTENT_FORGE_JIRA_* equivalents)."
        )
    return email, token


def query_forge_tickets(cfg: dict[str, Any], jql: str) -> list[dict[str, Any]]:
    """Search Jira via the modern ``POST /rest/api/3/search/jql`` endpoint.

    Atlassian removed the legacy ``/search`` endpoint in 2026 (returns 410
    Gone). The replacement takes a JSON body and returns ``{issues,
    nextPageToken}`` — we don't paginate because a 30-minute window on one
    project can't realistically exceed maxResults=50.

    See: https://developer.atlassian.com/changelog/#CHANGE-2046
    """
    email, token = _jira_auth()
    api_base, _ = jira_rest_base(cfg, token)
    resp = requests.post(
        f"{api_base}/search/jql",
        auth=(email, token),
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        json={
            "jql": jql,
            "fields": [
                "summary",
                "labels",
                "created",
                "reporter",
                "issuetype",
                "status",
            ],
            "maxResults": 50,
        },
        timeout=60,
    )
    if resp.status_code >= 400:
        raise SystemExit(f"JIRA search failed ({resp.status_code}): {resp.text}")
    return resp.json().get("issues", []) or []


def add_label_to_ticket(cfg: dict[str, Any], key: str, label: str) -> None:
    email, token = _jira_auth()
    api_base, _ = jira_rest_base(cfg, token)
    payload = {"update": {"labels": [{"add": label}]}}
    resp = requests.put(
        f"{api_base}/issue/{key}",
        auth=(email, token),
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        json=payload,
        timeout=60,
    )
    if resp.status_code >= 400:
        raise PollError(
            f"label add on {key} failed ({resp.status_code}): {resp.text}"
        )


def remove_label_from_ticket(cfg: dict[str, Any], key: str, label: str) -> None:
    """Best-effort rollback used only when trigger fails after labeling."""
    email, token = _jira_auth()
    api_base, _ = jira_rest_base(cfg, token)
    payload = {"update": {"labels": [{"remove": label}]}}
    try:
        requests.put(
            f"{api_base}/issue/{key}",
            auth=(email, token),
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
    except requests.RequestException as exc:
        print(f"[poll] {key}: label rollback failed: {exc}", file=sys.stderr)


def trigger_pipeline(key: str, summary: str) -> dict[str, Any]:
    """Kick off a downstream pipeline for one Jira ticket using CI_JOB_TOKEN.

    GitLab's ``POST /api/v4/projects/:id/pipeline`` endpoint (not the older
    ``/trigger/pipeline``) accepts the auto-injected ``CI_JOB_TOKEN`` when
    creating pipelines in the same project. That means no additional CI
    variable is required — the job's own identity is enough.
    """
    job_token = env_var("CI_JOB_TOKEN")
    if not job_token:
        raise SystemExit(
            "CI_JOB_TOKEN not available. poll_forge_tickets is designed to run "
            "inside a GitLab CI job; outside of CI you need a pipeline trigger "
            "token or a personal access token instead."
        )

    ref = (
        env_var("GITLAB_TRIGGER_REF")
        or env_var("CI_COMMIT_REF_NAME")
        or "rajthakk/ootb-e2e-test"
    )
    project_id = env_var("GITLAB_TRIGGER_PROJECT_ID") or env_var("CI_PROJECT_ID") or "9336"
    base_url = (
        env_var("GITLAB_BASE_URL")
        or env_var("CI_SERVER_URL")
        or "https://cd.splunkdev.com"
    ).rstrip("/")

    resp = requests.post(
        f"{base_url}/api/v4/projects/{project_id}/pipeline",
        headers={"JOB-TOKEN": job_token, "Content-Type": "application/json"},
        json={
            "ref": ref,
            "variables": [
                {"key": "OOTB_JIRA_KEY", "value": key},
                {"key": "OOTB_BUG_INPUT", "value": summary},
            ],
        },
        timeout=60,
    )
    if resp.status_code >= 400:
        raise PollError(
            f"GitLab pipeline create for {key} failed ({resp.status_code}): {resp.text}"
        )
    return resp.json()


def process_ticket(cfg: dict[str, Any], ticket: dict[str, Any]) -> dict[str, Any]:
    key = ticket.get("key") or ""
    summary = (ticket.get("fields") or {}).get("summary") or ""
    add_label_to_ticket(cfg, key, AUTO_TRIAGED_LABEL)
    try:
        pipeline = trigger_pipeline(key, summary)
    except PollError:
        remove_label_from_ticket(cfg, key, AUTO_TRIAGED_LABEL)
        raise
    return {
        "key": key,
        "summary": summary,
        "pipeline_id": pipeline.get("id"),
        "pipeline_url": pipeline.get("web_url"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Poll Jira for Forge OOTB tickets")
    parser.add_argument(
        "--project", default=env_var("POLL_PROJECT") or "BITS",
        help="Jira project key to poll (default: BITS)",
    )
    parser.add_argument(
        "--window-minutes",
        type=int,
        default=int(env_var("POLL_WINDOW_MINUTES") or "30"),
        help="Match tickets created within this many minutes (default: 30)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=env_var("POLL_DRY_RUN").lower() in ("1", "true", "yes"),
        help="List matches without labeling or triggering.",
    )
    args = parser.parse_args()

    cfg = load_config()
    jql = build_jql(args.project, args.window_minutes)
    print(f"[poll] JQL: {jql}")

    tickets = query_forge_tickets(cfg, jql)
    print(f"[poll] {len(tickets)} matching ticket(s)")

    triggered: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for ticket in tickets:
        key = ticket.get("key") or "?"
        summary = (ticket.get("fields") or {}).get("summary") or ""
        if args.dry_run:
            print(f"[poll] DRY-RUN would trigger {key}: {summary}")
            continue
        try:
            result = process_ticket(cfg, ticket)
            triggered.append(result)
            print(
                f"[poll] {key}: triggered pipeline {result['pipeline_id']} "
                f"→ {result['pipeline_url']}"
            )
        except PollError as exc:
            print(f"[poll] {key}: {exc}", file=sys.stderr)
            errors.append({"key": key, "error": str(exc)})

    summary_out = {
        "jql": jql,
        "found": len(tickets),
        "triggered": triggered,
        "errors": errors,
        "dry_run": args.dry_run,
    }
    print(json.dumps(summary_out, indent=2))

    if os.environ.get("CI"):
        try:
            with open("poll_summary.json", "w", encoding="utf-8") as fh:
                json.dump(summary_out, fh, indent=2)
        except OSError as exc:
            print(f"[poll] failed to write poll_summary.json: {exc}", file=sys.stderr)

    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())

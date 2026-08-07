#!/usr/bin/env python3
"""End-to-end OOTB bug pipeline: analyze repo → JIRA → draft MR → notify Slack.

Triggered from GitLab ChatOps:
  /gitlab run ootb-bug-fix K8s Node CPU detector fires at 70% instead of 90%

Or via pipeline trigger variable OOTB_BUG_INPUT.

Environment variables:
  JIRA_EMAIL, JIRA_API_TOKEN, GITLAB_TOKEN — required for triage
  SLACK_WEBHOOK_URL and/or SLACK_BOT_TOKEN + SLACK_CHANNEL_ID — Slack notify
  SLACK_THREAD_TS — reply in thread (bot API)
  SIGNALBUDDY_TOKEN — optional; with OOTB_SYNC_MSB=true after JSON changes exist
  CHAT_INPUT — set automatically by GitLab ChatOps
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any

from automation.repo_search import build_rca, search_repo, summarize_for_jira


def _emit_chatops_reply(text: str) -> None:
    from automation.slack_notify import emit_chatops_reply

    emit_chatops_reply(text)


def _notify_slack(*args, **kwargs):
    from automation.slack_notify import notify_slack

    return notify_slack(*args, **kwargs)


def _load_config():
    from automation.orchestrator import load_config

    return load_config()


def _create_jira_issue(cfg, **kwargs):
    from automation.orchestrator import create_jira_issue

    return create_jira_issue(cfg, **kwargs)


def _create_gitlab_draft_mr(cfg, **kwargs):
    from automation.orchestrator import create_gitlab_draft_mr

    return create_gitlab_draft_mr(cfg, **kwargs)


def normalize_bug_input(bug_text: str) -> str:
    text = bug_text.strip()
    text = re.sub(r"^ootb-bug:\s*", "", text, flags=re.I)
    return text.strip()


def derive_title(bug_text: str, *, max_len: int = 120) -> str:
    first_line = normalize_bug_input(bug_text).splitlines()[0] if bug_text.strip() else "OOTB content bug"
    if len(first_line) > max_len:
        return first_line[: max_len - 3] + "..."
    return first_line or "OOTB content bug"


def _post_working_ack(title: str) -> dict[str, Any] | None:
    from automation.slack_notify import bot_api_configured, post_working_ack

    channel = os.environ.get("SLACK_CHANNEL_ID")
    if not bot_api_configured(channel=channel):
        return None
    return post_working_ack(title, channel=channel)


def run_pipeline(
    bug_text: str,
    *,
    slack_permalink: str | None = None,
    chatops_reply: bool = False,
    sync_msb: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    bug_text = normalize_bug_input(bug_text)
    title = derive_title(bug_text)
    ack: dict[str, Any] | None = None

    if chatops_reply or os.environ.get("CI_PIPELINE_SOURCE") == "chat":
        from automation.slack_notify import format_working_ack

        _emit_chatops_reply(format_working_ack(title))
    elif os.environ.get("OOTB_BUG_INPUT"):
        ack = _post_working_ack(title)

    matches = search_repo(bug_text)
    match_dicts = [
        {"path": m.path, "score": m.score, "reasons": m.reasons} for m in matches
    ]
    rca = build_rca(bug_text, matches)

    if dry_run:
        return {
            "command": "ootb-bug-fix",
            "dry_run": True,
            "title": title,
            "input": bug_text,
            "rca": rca,
            "matches": match_dicts,
            "slack_ack": ack,
        }

    cfg = _load_config()
    full_description = summarize_for_jira(bug_text, matches, rca)
    jira = _create_jira_issue(
        cfg,
        title=title,
        description=full_description,
        slack_permalink=slack_permalink,
    )

    mr_description = f"{full_description}\n\n---\n\n{rca}"
    mr = _create_gitlab_draft_mr(
        cfg,
        title=title,
        description=mr_description,
        jira_key=jira.get("key"),
    )

    sync_result: dict[str, Any] | None = None
    if sync_msb or os.environ.get("OOTB_SYNC_MSB", "").lower() in ("1", "true", "yes"):
        from automation.signalbuddy_sync import sync_changed_json

        paths = [m.path for m in matches[:3]] if matches else None
        sync_result = sync_changed_json(paths, refresh_local=True)

    slack_cfg = cfg.get("slack") or {}
    owner_mentions = slack_cfg.get("owner_mentions") or []

    result: dict[str, Any] = {
        "command": "ootb-bug-fix",
        "title": title,
        "input": bug_text,
        "rca": rca,
        "matches": match_dicts,
        "jira": jira,
        "merge_request": mr,
        "reviewers": {
            "gitlab_reviewer_ids": (cfg.get("gitlab") or {}).get("default_reviewer_ids") or [],
        },
        "signalbuddy_sync": sync_result,
        "slack_ack": ack,
    }

    result["slack"] = _notify_slack(
        result,
        owner_mentions=owner_mentions,
        chatops_reply=chatops_reply,
        thread_ts=os.environ.get("SLACK_THREAD_TS"),
        channel=os.environ.get("SLACK_CHANNEL_ID"),
    )
    return result


def cmd_run(args: argparse.Namespace) -> int:
    bug_text = normalize_bug_input(
        args.input or os.environ.get("CHAT_INPUT") or os.environ.get("OOTB_BUG_INPUT") or ""
    )
    if not bug_text:
        raise SystemExit(
            "No bug text. Pass --input, set CHAT_INPUT (ChatOps), or OOTB_BUG_INPUT (trigger)."
        )

    result = run_pipeline(
        bug_text,
        slack_permalink=args.slack_permalink,
        chatops_reply=args.chatops_reply,
        sync_msb=args.sync_msb,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="OOTB end-to-end bug pipeline")
    sub = p.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Analyze, triage, notify")
    run.add_argument("--input", default=None, help="Bug report text")
    run.add_argument("--slack-permalink", default=os.environ.get("SLACK_MESSAGE_PERMALINK"))
    run.add_argument(
        "--chatops-reply",
        action="store_true",
        help="Emit GitLab ChatOps chat_reply block for Slack",
    )
    run.add_argument(
        "--sync-msb",
        action="store_true",
        help="Push changed JSON to Master SignalBuddy (requires local changes + token)",
    )
    run.add_argument(
        "--dry-run",
        action="store_true",
        help="Search + RCA only; skip JIRA/MR/Slack (no credentials needed)",
    )
    run.set_defaults(func=cmd_run)

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

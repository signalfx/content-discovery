#!/usr/bin/env python3
"""End-to-end OOTB bug pipeline: fetch existing Jira ticket → analyze repo → draft MR → comment on Jira → notify Slack.

Forge creates the Jira ticket upstream from a Slack bug report; this pipeline
only reacts to an already-existing ticket. It never creates Jira tickets.

Triggered by pipeline trigger variable OOTB_JIRA_KEY (e.g. BITS-1583), typically
via a Jira Automation rule ("Send Web Request" on Issue Created).

Environment variables:
  OOTB_JIRA_KEY                                  — required, existing Jira issue key
  OOTB_BUG_INPUT                                 — optional bug-text override
                                                   (defaults to ticket summary/description)
  JIRA_EMAIL, JIRA_API_TOKEN, GITLAB_TOKEN       — required for Jira read/comment + MR
  SLACK_WEBHOOK_URL / SLACK_BOT_TOKEN + SLACK_CHANNEL_ID — Slack notify
  SLACK_THREAD_TS                                — reply in thread (bot API)
  SIGNALBUDDY_TOKEN                              — optional; with OOTB_SYNC_MSB=true
  CHAT_INPUT                                     — set automatically by GitLab ChatOps
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any

from contentforge.pipeline.repo_search import build_rca, search_repo, summarize_for_jira


def _emit_chatops_reply(text: str) -> None:
    from contentforge.pipeline.slack_notify import emit_chatops_reply

    emit_chatops_reply(text)


def _notify_slack(*args, **kwargs):
    from contentforge.pipeline.slack_notify import notify_slack

    return notify_slack(*args, **kwargs)


def _load_config():
    from contentforge.pipeline.orchestrator import load_config

    return load_config()


def _get_jira_issue(cfg, key):
    from contentforge.pipeline.orchestrator import get_jira_issue

    return get_jira_issue(cfg, key)


def _comment_on_jira_issue(cfg, key, comment_text):
    from contentforge.pipeline.orchestrator import comment_on_jira_issue

    return comment_on_jira_issue(cfg, key, comment_text)


def _create_gitlab_draft_mr(cfg, **kwargs):
    from contentforge.pipeline.orchestrator import create_gitlab_draft_mr

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
    from contentforge.pipeline.slack_notify import bot_api_configured, post_working_ack

    channel = os.environ.get("SLACK_CHANNEL_ID")
    if not bot_api_configured(channel=channel):
        return None
    return post_working_ack(title, channel=channel)


def run_pipeline(
    jira_key: str,
    *,
    bug_text: str = "",
    slack_permalink: str | None = None,
    chatops_reply: bool = False,
    sync_msb: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Analyze an existing Jira ticket, create a draft MR, notify Slack.

    The Jira ticket is expected to already exist (created upstream by Forge
    from a Slack bug report). We fetch its summary/description, run repo
    search, open the draft MR, and post a comment linking the MR back on the
    ticket. No Jira ticket is created here.
    """
    if not jira_key:
        raise SystemExit(
            "OOTB_JIRA_KEY (or --jira-key) is required. The pipeline no "
            "longer creates Jira tickets — Forge creates them upstream."
        )

    cfg = _load_config()
    ticket = _get_jira_issue(cfg, jira_key)

    bug_text = normalize_bug_input(
        bug_text or ticket.get("description_text") or ticket.get("summary") or ""
    )
    title = derive_title(bug_text or ticket.get("summary") or jira_key)
    ack: dict[str, Any] | None = None

    if chatops_reply or os.environ.get("CI_PIPELINE_SOURCE") == "chat":
        from contentforge.pipeline.slack_notify import format_working_ack

        _emit_chatops_reply(format_working_ack(title))
    elif os.environ.get("OOTB_BUG_INPUT") or jira_key:
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
            "jira": ticket,
            "rca": rca,
            "matches": match_dicts,
            "slack_ack": ack,
        }

    full_description = summarize_for_jira(bug_text, matches, rca)
    mr_description = f"{full_description}\n\n---\n\n{rca}"
    mr = _create_gitlab_draft_mr(
        cfg,
        title=title,
        description=mr_description,
        jira_key=jira_key,
    )

    comment_result = _comment_on_jira_issue(
        cfg,
        jira_key,
        (
            f"Automated triage: draft MR opened at {mr.get('web_url')} "
            f"(branch {mr.get('branch')}).\n"
            f"Likely affected: "
            f"{', '.join(m.path for m in matches[:3]) if matches else 'no clear match'}"
        ),
    )

    sync_result: dict[str, Any] | None = None
    if sync_msb or os.environ.get("OOTB_SYNC_MSB", "").lower() in ("1", "true", "yes"):
        from contentforge.pipeline.signalbuddy_sync import sync_changed_json

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
        "jira": ticket,
        "jira_comment": comment_result,
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

    _write_triage_artifact(bug_text, title, matches, ticket, mr)
    return result


def _write_triage_artifact(
    bug_text: str,
    title: str,
    matches: list[Any],
    jira: dict[str, Any],
    mr: dict[str, Any],
) -> None:
    """Emit a triage.json artifact for the downstream ootb-propose-fix CI job.

    The auto-fix job consumes this via `needs:` + `artifacts:` and refuses to
    touch any file that isn't in `allowed_files`, so this artifact is the trust
    boundary between the heuristic search and the LLM.
    """
    if not os.environ.get("CI"):
        return

    artifact_path = os.environ.get("OOTB_TRIAGE_ARTIFACT", "triage.json")
    primary = matches[0].path if matches else None
    payload = {
        "bug_text": bug_text,
        "title": title,
        "jira_key": jira.get("key"),
        "jira_url": jira.get("url"),
        "mr_iid": mr.get("iid"),
        "mr_url": mr.get("web_url"),
        "branch": mr.get("branch"),
        "primary_file": primary,
        "allowed_files": [m.path for m in matches[:1]],
        "matches": [
            {"path": m.path, "score": m.score, "reasons": m.reasons}
            for m in matches
        ],
    }
    try:
        with open(artifact_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        print(f"[bug_pipeline] wrote triage artifact -> {artifact_path}")
    except OSError as exc:
        print(f"[bug_pipeline] failed to write triage artifact: {exc}", file=sys.stderr)


def cmd_run(args: argparse.Namespace) -> int:
    jira_key = (args.jira_key or os.environ.get("OOTB_JIRA_KEY") or "").strip()
    if not jira_key:
        raise SystemExit(
            "OOTB_JIRA_KEY (or --jira-key) is required. Forge creates the "
            "ticket upstream; this pipeline only reacts to existing tickets."
        )

    bug_text = normalize_bug_input(
        args.input or os.environ.get("CHAT_INPUT") or os.environ.get("OOTB_BUG_INPUT") or ""
    )

    result = run_pipeline(
        jira_key,
        bug_text=bug_text,
        slack_permalink=args.slack_permalink,
        chatops_reply=args.chatops_reply,
        sync_msb=args.sync_msb,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, indent=2, default=str))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="OOTB end-to-end bug pipeline")
    sub = p.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Analyze, triage, notify")
    run.add_argument(
        "--jira-key",
        default=None,
        help="Existing Jira issue key (e.g. BITS-1583). Falls back to OOTB_JIRA_KEY env.",
    )
    run.add_argument(
        "--input",
        default=None,
        help="Optional bug text override. Defaults to the Jira ticket's summary/description.",
    )
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
        help="Search + RCA only; skip MR/Slack (no GitLab credentials needed)",
    )
    run.set_defaults(func=cmd_run)

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

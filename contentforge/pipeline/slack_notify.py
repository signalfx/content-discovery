"""Post pipeline results to Slack (webhook or Bot API)."""

from __future__ import annotations

import json
import os
import sys
from typing import Any

import requests


def env_var(*names: str) -> str:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


def bot_api_configured(*, channel: str | None = None) -> bool:
    return bool(
        env_var("CONTENT_FORGE_SLACK_BOT_TOKEN", "SLACK_BOT_TOKEN")
        and (channel or os.environ.get("SLACK_CHANNEL_ID", "")).strip()
    )


def format_working_ack(title: str) -> str:
    # Plain text (no mrkdwn) + Unicode emoji, so the same message renders
    # correctly through Slack Bot API, Incoming Webhooks, Workflow Builder
    # webhook triggers, and GitLab ChatOps chat_reply blocks.
    return (
        f"⏳ Working on OOTB bug: {title}\n"
        "Searching content repo, creating GitLab triage issue for Duo Flow…"
    )


def post_working_ack(
    title: str,
    *,
    channel: str | None = None,
    thread_ts: str | None = None,
) -> dict[str, Any]:
    return post_via_bot_api(
        format_working_ack(title),
        channel=channel,
        thread_ts=thread_ts or os.environ.get("SLACK_THREAD_TS"),
    )


def format_slack_message(result: dict[str, Any], *, owner_mentions: list[str] | None = None) -> str:
    """Plain-text message that renders identically across all Slack channels.

    Uses Unicode emoji and full URLs on their own lines so Slack's auto-linkify
    handles them without needing mrkdwn — which is not parsed by Workflow
    Builder webhook triggers, only by Bot API and Incoming Webhooks.

    The pipeline's terminal state is now "GitLab triage issue opened,
    assigned to Duo Flow". The actual fix MR is produced asynchronously by
    Duo; we don't wait for it here.
    """
    jira = result.get("jira") or {}
    issue = result.get("gitlab_issue") or {}
    rca = result.get("rca") or ""
    matches = result.get("matches") or []
    pipeline_url = os.environ.get("CI_PIPELINE_URL", "").strip()

    jira_key = jira.get("key") or "n/a"
    jira_url = jira.get("url")
    issue_iid = issue.get("iid") or "?"
    issue_url = issue.get("web_url")
    assigned = issue.get("assigned", False)

    lines = [f"✅ OOTB triage complete — {jira_key} · GitLab issue #{issue_iid}"]
    if jira_url:
        lines.append(f"JIRA:  {jira_url}")
    if issue_url:
        lines.append(f"Issue: {issue_url}")
    if assigned:
        lines.append("Assigned to Duo Flow service account — auto-fix MR will follow.")
    else:
        lines.append(
            "⚠️ Issue is UNASSIGNED — set DUO_FLOW_ASSIGNEE_ID to activate Duo Flow."
        )
    lines.append("")

    if pipeline_url:
        lines.append(f"Pipeline: {pipeline_url}")
        lines.append("")

    if matches:
        lines.append("Likely affected files:")
        for m in matches[:5]:
            lines.append(f"  • {m.get('path', m)}")
        lines.append("")

    if rca:
        summary = rca.split("**Primary suspect:**")
        excerpt = summary[1].strip() if len(summary) > 1 else rca
        excerpt = excerpt[:400] + ("…" if len(excerpt) > 400 else "")
        excerpt = excerpt.replace("**", "").replace("`", "")
        lines.append(f"RCA: {excerpt}")
        lines.append("")

    mentions = owner_mentions or []
    if mentions:
        # <@UID> mentions only render as pings in Bot API messages, but they
        # degrade gracefully to plain text elsewhere.
        lines.append("Watching: " + " ".join(f"<@{uid}>" for uid in mentions))

    return "\n".join(lines)


def post_via_webhook(text: str, *, webhook_url: str | None = None) -> dict[str, Any]:
    url = (webhook_url or os.environ.get("SLACK_WEBHOOK_URL", "")).strip()
    if not url:
        return {"ok": False, "skipped": True, "reason": "SLACK_WEBHOOK_URL not set"}

    resp = requests.post(url, json={"text": text}, timeout=30)
    return {"ok": resp.status_code == 200, "status_code": resp.status_code, "body": resp.text[:500]}


def post_via_bot_api(
    text: str,
    *,
    channel: str | None = None,
    thread_ts: str | None = None,
    token: str | None = None,
) -> dict[str, Any]:
    bot_token = token or env_var("CONTENT_FORGE_SLACK_BOT_TOKEN", "SLACK_BOT_TOKEN")
    channel_id = (channel or os.environ.get("SLACK_CHANNEL_ID", "")).strip()
    if not bot_token or not channel_id:
        return {
            "ok": False,
            "skipped": True,
            "reason": "CONTENT_FORGE_SLACK_BOT_TOKEN (or SLACK_BOT_TOKEN) or SLACK_CHANNEL_ID not set",
        }

    payload: dict[str, Any] = {"channel": channel_id, "text": text, "mrkdwn": True}
    if thread_ts:
        payload["thread_ts"] = thread_ts

    resp = requests.post(
        "https://slack.com/api/chat.postMessage",
        headers={"Authorization": f"Bearer {bot_token}", "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    data = resp.json()
    return {"ok": bool(data.get("ok")), "response": data}


def emit_chatops_reply(text: str) -> None:
    """Print GitLab ChatOps chat_reply section (job output → Slack)."""
    import time

    ts = int(time.time())
    block = f"section_start:{ts}:chat_reply\r\033[0K\n{text}\nsection_end:{ts}:chat_reply\r\033[0K"
    print(block)


def notify_slack(
    result: dict[str, Any],
    *,
    owner_mentions: list[str] | None = None,
    chatops_reply: bool = False,
    thread_ts: str | None = None,
    channel: str | None = None,
) -> dict[str, Any]:
    text = format_slack_message(result, owner_mentions=owner_mentions)
    outcomes: dict[str, Any] = {"message": text}

    if chatops_reply or os.environ.get("CI_PIPELINE_SOURCE") == "chat":
        emit_chatops_reply(text)
        outcomes["chatops"] = True

    webhook = post_via_webhook(text)
    if not webhook.get("skipped"):
        outcomes["webhook"] = webhook

    bot = post_via_bot_api(text, channel=channel, thread_ts=thread_ts or os.environ.get("SLACK_THREAD_TS"))
    if not bot.get("skipped"):
        outcomes["bot_api"] = bot

    return outcomes


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python -m contentforge.pipeline.slack_notify '<json result>'", file=sys.stderr)
        return 2
    result = json.loads(sys.argv[1])
    notify_slack(result, chatops_reply="--chatops" in sys.argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

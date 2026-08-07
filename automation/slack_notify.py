"""Post pipeline results to Slack (webhook or Bot API)."""

from __future__ import annotations

import json
import os
import sys
from typing import Any

import requests


def bot_api_configured(*, channel: str | None = None) -> bool:
    return bool(
        os.environ.get("SLACK_BOT_TOKEN", "").strip()
        and (channel or os.environ.get("SLACK_CHANNEL_ID", "")).strip()
    )


def format_working_ack(title: str) -> str:
    return (
        f":hourglass_flowing_sand: Working on OOTB bug: *{title}*\n"
        "Searching content repo, creating JIRA + draft MR…"
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
    jira = result.get("jira") or {}
    mr = result.get("merge_request") or {}
    rca = result.get("rca") or ""
    matches = result.get("matches") or []
    pipeline_url = os.environ.get("CI_PIPELINE_URL", "").strip()

    lines = [
        "*OOTB bug automation complete*",
        "",
        f"*JIRA:* <{jira.get('url', 'n/a')}|{jira.get('key', 'n/a')}>",
        f"*Draft MR:* <{mr.get('web_url', 'n/a')}|!{mr.get('iid', '?')}>",
        f"*Branch:* `{mr.get('branch', 'n/a')}`",
        "",
    ]

    if pipeline_url:
        lines.append(f"*Pipeline:* <{pipeline_url}|view run>")
        lines.append("")

    if matches:
        lines.append("*Likely affected files:*")
        for m in matches[:5]:
            lines.append(f"• `{m.get('path', m)}`")
        lines.append("")

    if rca:
        # Slack mrkdwn: shorten for chat; full RCA stays in JIRA/MR
        summary = rca.split("**Primary suspect:**")
        if len(summary) > 1:
            lines.append(f"*RCA:* {summary[1].strip()[:400]}")
        else:
            lines.append(f"*RCA:* {rca[:400]}...")
        lines.append("")

    reviewers = result.get("reviewers") or {}
    if reviewers.get("gitlab_reviewer_ids"):
        lines.append(f"*GitLab reviewers assigned:* {reviewers['gitlab_reviewer_ids']}")

    mentions = owner_mentions or []
    if mentions:
        lines.append("")
        lines.append("Review requested: " + " ".join(f"<@{uid}>" for uid in mentions))

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
    bot_token = (token or os.environ.get("SLACK_BOT_TOKEN", "")).strip()
    channel_id = (channel or os.environ.get("SLACK_CHANNEL_ID", "")).strip()
    if not bot_token or not channel_id:
        return {
            "ok": False,
            "skipped": True,
            "reason": "SLACK_BOT_TOKEN or SLACK_CHANNEL_ID not set",
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
        print("Usage: python -m automation.slack_notify '<json result>'", file=sys.stderr)
        return 2
    result = json.loads(sys.argv[1])
    notify_slack(result, chatops_reply="--chatops" in sys.argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

/**
 * Post an in-thread Slack update after ootb-propose-fix runs.
 *
 * Reads:
 *   propose_fix_summary.json — produced by bridge_it_propose_fix.mjs
 *   triage.json              — produced by ootb-bug-fix (contains MR/Jira context)
 *
 * Posts via:
 *   1. Slack Bot API (chat.postMessage) — threaded reply (preferred)
 *   2. Slack Incoming Webhook — channel post (fallback)
 *   3. GitLab ChatOps chat_reply block on stdout — inline reply for /gitlab run
 *
 * At least one path posts based on which env vars are set. If nothing is
 * configured, the script exits cleanly with a stdout log; it never fails the
 * ootb-propose-fix job.
 *
 * Env (same names the Python notify_slack() uses):
 *   CONTENT_FORGE_SLACK_BOT_TOKEN or SLACK_BOT_TOKEN
 *   SLACK_CHANNEL_ID
 *   SLACK_THREAD_TS               (optional — reply in-thread if set)
 *   SLACK_WEBHOOK_URL             (optional — used as fallback)
 *   CI_PIPELINE_SOURCE            (optional — "chat" enables ChatOps reply)
 *   CI_PIPELINE_URL, CI_JOB_URL   (optional — linked in the message)
 *   OOTB_PROPOSE_FIX_SUMMARY      (optional — override summary path)
 *   OOTB_TRIAGE_ARTIFACT          (optional — override triage path)
 *   OOTB_PROPOSE_FIX_PUSHED       (optional — "true" if git push succeeded)
 */

import fs from "fs";
import https from "https";

const SUMMARY_PATH =
  process.env.OOTB_PROPOSE_FIX_SUMMARY || "propose_fix_summary.json";
const TRIAGE_PATH = process.env.OOTB_TRIAGE_ARTIFACT || "triage.json";

function log(msg) {
  console.log(`[slack-update] ${msg}`);
}

function readJsonIfExists(path) {
  if (!fs.existsSync(path)) return null;
  try {
    return JSON.parse(fs.readFileSync(path, "utf8"));
  } catch (err) {
    log(`WARN: failed to parse ${path}: ${err.message}`);
    return null;
  }
}

function httpsJson(hostname, path, method, headers, body) {
  return new Promise((resolve, reject) => {
    const req = https.request(
      { hostname, path, method, headers },
      (res) => {
        const chunks = [];
        res.on("data", (c) => chunks.push(c));
        res.on("end", () => {
          const raw = Buffer.concat(chunks).toString();
          let parsed = null;
          try {
            parsed = JSON.parse(raw);
          } catch (_) {}
          resolve({ status: res.statusCode, body: raw, json: parsed });
        });
      }
    );
    req.on("error", reject);
    if (body) req.write(body);
    req.end();
  });
}

function formatMessage(summary, triage, opts) {
  const { pushed } = opts;
  const mrIid = triage?.mr_iid ?? "?";
  const mrUrl = triage?.mr_url ?? "";
  const jiraKey = triage?.jira_key ?? "n/a";
  const jiraUrl = triage?.jira_url ?? "";
  const primary = triage?.primary_file ?? summary?.file ?? "unknown";
  const pipelineUrl = (process.env.CI_PIPELINE_URL || "").trim();
  const jobUrl = (process.env.CI_JOB_URL || "").trim();

  const jiraLink = jiraUrl ? `<${jiraUrl}|${jiraKey}>` : `\`${jiraKey}\``;
  const mrLink = mrUrl ? `<${mrUrl}|!${mrIid}>` : `!${mrIid}`;

  const status = summary?.status || "unknown";
  const confidence =
    typeof summary?.confidence === "number"
      ? summary.confidence.toFixed(2)
      : "n/a";

  const lines = [];

  if (status === "applied" && pushed) {
    const ops = Array.isArray(summary.applied) ? summary.applied.length : 0;
    lines.push(
      `:robot_face: *CircuIT auto-fix applied* to MR ${mrLink} (JIRA ${jiraLink})`
    );
    lines.push(`*File:* \`${primary}\``);
    lines.push(`*Operations:* ${ops} \`replace\` op(s)   *Confidence:* ${confidence}`);
    if (summary.explanation) {
      lines.push(`*Why:* ${truncate(summary.explanation, 400)}`);
    }
    if (summary.risk_notes) {
      lines.push(`:warning: *Reviewer must double-check:* ${truncate(summary.risk_notes, 300)}`);
    }
    lines.push("");
    lines.push(
      "The MR pipeline will now re-run the validators against the AI-generated diff. Please review before merging."
    );
  } else if (status === "applied" && !pushed) {
    lines.push(
      `:warning: *CircuIT auto-fix produced a patch but git push failed* for MR ${mrLink}. Check the CI job.`
    );
    if (jobUrl) lines.push(`*Job:* <${jobUrl}|view logs>`);
  } else if (status === "low_confidence") {
    lines.push(
      `:mag: *CircuIT auto-fix declined* (confidence ${confidence} < threshold ${summary?.threshold ?? "0.70"}) for MR ${mrLink} (JIRA ${jiraLink}).`
    );
    if (summary.explanation) {
      lines.push(`*Model note:* ${truncate(summary.explanation, 400)}`);
    }
    lines.push("");
    lines.push("The MR is still open with the RCA — please review and fix manually.");
  } else if (status === "no_applied_ops") {
    const rejected = Array.isArray(summary.rejected) ? summary.rejected.length : 0;
    lines.push(
      `:no_entry_sign: *CircuIT auto-fix proposed ${rejected} op(s), all rejected by guardrails* for MR ${mrLink} (JIRA ${jiraLink}).`
    );
    lines.push(
      "This is expected when the model wants to touch immutable fields (hashCode/id/version) or a file outside the primary suspect. MR left as triage-only."
    );
  } else if (status === "no_primary_file") {
    lines.push(
      `:mag: *CircuIT auto-fix skipped* — no primary suspect file identified during triage for MR ${mrLink}.`
    );
  } else {
    lines.push(
      `:grey_question: *CircuIT auto-fix finished with status:* \`${status}\` for MR ${mrLink} (JIRA ${jiraLink}).`
    );
    if (jobUrl) lines.push(`*Job:* <${jobUrl}|view logs>`);
  }

  if (pipelineUrl) {
    lines.push(`*Pipeline:* <${pipelineUrl}|view run>`);
  }

  return lines.join("\n");
}

function truncate(text, max) {
  const s = String(text);
  return s.length > max ? s.slice(0, max - 1) + "…" : s;
}

function emitChatopsReply(text) {
  const ts = Math.floor(Date.now() / 1000);
  process.stdout.write(
    `section_start:${ts}:chat_reply\r\x1b[0K\n${text}\nsection_end:${ts}:chat_reply\r\x1b[0K\n`
  );
}

async function postBotApi(text) {
  const token = (
    process.env.CONTENT_FORGE_SLACK_BOT_TOKEN ||
    process.env.SLACK_BOT_TOKEN ||
    ""
  ).trim();
  const channel = (process.env.SLACK_CHANNEL_ID || "").trim();
  if (!token || !channel) return { skipped: true, reason: "no bot token or channel" };

  const threadTs = (process.env.SLACK_THREAD_TS || "").trim() || undefined;

  const payload = { channel, text, mrkdwn: true };
  if (threadTs) payload.thread_ts = threadTs;
  const body = JSON.stringify(payload);

  const resp = await httpsJson("slack.com", "/api/chat.postMessage", "POST", {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
    "Content-Length": Buffer.byteLength(body, "utf8"),
  }, body);

  const ok = !!(resp.json && resp.json.ok);
  return {
    ok,
    status: resp.status,
    error: resp.json ? resp.json.error : undefined,
  };
}

async function postWebhook(text) {
  const url = (process.env.SLACK_WEBHOOK_URL || "").trim();
  if (!url) return { skipped: true, reason: "no webhook url" };

  try {
    const parsed = new URL(url);
    const body = JSON.stringify({ text });
    const resp = await httpsJson(parsed.hostname, parsed.pathname + parsed.search, "POST", {
      "Content-Type": "application/json",
      "Content-Length": Buffer.byteLength(body, "utf8"),
    }, body);
    return { ok: resp.status >= 200 && resp.status < 300, status: resp.status };
  } catch (err) {
    return { ok: false, error: err.message };
  }
}

async function main() {
  const summary = readJsonIfExists(SUMMARY_PATH);
  const triage = readJsonIfExists(TRIAGE_PATH);

  if (!summary) {
    log(`no summary at ${SUMMARY_PATH}; nothing to post`);
    return;
  }
  if (!triage) {
    log(`no triage at ${TRIAGE_PATH}; posting best-effort message without MR/Jira links`);
  }

  const pushed = String(process.env.OOTB_PROPOSE_FIX_PUSHED || "").toLowerCase() === "true";
  const text = formatMessage(summary, triage || {}, { pushed });

  log(`message:\n${text}\n---`);

  if (String(process.env.CI_PIPELINE_SOURCE || "").toLowerCase() === "chat") {
    emitChatopsReply(text);
    log("emitted ChatOps chat_reply block");
  }

  const bot = await postBotApi(text);
  if (bot.skipped) {
    log(`bot API skipped: ${bot.reason}`);
  } else if (bot.ok) {
    log("posted via Slack Bot API");
  } else {
    log(`WARN: Slack Bot API returned status=${bot.status} error=${bot.error}`);
  }

  if (!bot.ok) {
    const wh = await postWebhook(text);
    if (wh.skipped) log(`webhook skipped: ${wh.reason}`);
    else if (wh.ok) log("posted via Slack webhook (fallback)");
    else log(`WARN: webhook failed status=${wh.status} error=${wh.error}`);
  }
}

main().catch((err) => {
  console.error(`[slack-update] unhandled error: ${err?.stack || err}`);
  process.exit(0);
});

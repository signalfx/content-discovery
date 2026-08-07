# Slack Workflow — test from `#test_ai_ootb` without merging to `master`

This is the **recommended way to test from Slack** while automation lives on the `lab` branch.

## Flow

```
You:  ootb-bug: K8s Node CPU detector fires at 70% instead of 90%
  ↓
Slack Workflow (instant reply in thread)
  ↓
GitLab pipeline trigger (ref=lab, OOTB_BUG_INPUT + SLACK_THREAD_TS)
  ↓
CI job ootb-bug-fix → JIRA + draft MR → bot posts completion in thread
```

---

## Prerequisites checklist

- [ ] Automation pushed to **`lab`** on GitLab (includes `contentforge/` + `.gitlab-ci.yml`)
- [ ] **Pipeline trigger token** created (Settings → CI/CD → Pipeline triggers)
- [ ] **GitLab CI variables** set on project 9336 (see below)
- [ ] **Slack bot** invited to `#test_ai_ootb` (`/invite @YourBot`)
- [ ] **Slack Workflow** created (steps below)

---

## Step 1 — GitLab CI variables

Project: `observability/shared/content-discovery` (9336)  
**Settings → CI/CD → Variables**

| Variable | Required | Notes |
|----------|----------|-------|
| `JIRA_EMAIL` | Yes | Your `@splunk.com` email |
| `JIRA_API_TOKEN` | Yes | [Atlassian API token](https://id.atlassian.com/manage-profile/security/api-tokens) |
| `GITLAB_TOKEN` | Yes | PAT with `api` scope on `cd.splunkdev.com` |
| `SLACK_BOT_TOKEN` | Yes | Bot token (`xoxb-…`) with `chat:write` |
| `GITLAB_REVIEWER_IDS` | No | Comma-separated GitLab user IDs |
| `SLACK_OWNER_MENTIONS` | No | Comma-separated Slack user IDs to @mention |

`SLACK_CHANNEL_ID` and `SLACK_THREAD_TS` are passed **per run** by the workflow (not stored in CI).

---

## Step 2 — Pipeline trigger token

1. **Settings → CI/CD → Pipeline triggers → Add trigger**
2. Copy the token (keep it secret — use only in Slack Workflow)

Test manually (replace values):

```bash
export CI_TRIGGER_TOKEN="your-trigger-token"
export SLACK_CHANNEL_ID="C0XXXXXXXX"   # #test_ai_ootb channel ID
export SLACK_THREAD_TS="1234567890.123456"

curl --request POST \
  --form "token=${CI_TRIGGER_TOKEN}" \
  --form "ref=lab" \
  --form "variables[OOTB_BUG_INPUT]=K8s Node CPU detector fires at 70% instead of 90%" \
  --form "variables[SLACK_CHANNEL_ID]=${SLACK_CHANNEL_ID}" \
  --form "variables[SLACK_THREAD_TS]=${SLACK_THREAD_TS}" \
  "https://cd.splunkdev.com/api/v4/projects/9336/trigger/pipeline"
```

Confirm a pipeline starts on branch **`lab`** with job **`ootb-bug-fix`**.

---

## Step 3 — Get `#test_ai_ootb` channel ID

In Slack: open channel → **View channel details** → copy **Channel ID** (starts with `C`).

You will paste this into the workflow webhook as a fixed value for `variables[SLACK_CHANNEL_ID]`.

---

## Step 4 — Create the Slack Workflow

Open **Workflow Builder** (Slack menu → Tools → Workflow Builder → Create).

### Trigger

| Setting | Value |
|---------|--------|
| Type | **From a webhook** OR **When a message is posted** in `#test_ai_ootb` |
| Filter | Message text **contains** `ootb-bug:` |

> Use **message posted** if you want keyword trigger. Use **webhook** only if you prefer an external caller.

### Step A — Reply in thread (optional but recommended)

Slack can send the instant ack; CI also posts one if the bot token is set.

| Setting | Value |
|---------|--------|
| Action | **Send a message to a channel** |
| Channel | `#test_ai_ootb` |
| Message | `:hourglass_flowing_sand: Working on it — creating JIRA + draft MR…` |
| Reply in thread | **Yes** (use the triggering message’s thread) |

### Step B — Trigger GitLab pipeline

| Setting | Value |
|---------|--------|
| Action | **Send a web request** |
| Method | `POST` |
| URL | `https://cd.splunkdev.com/api/v4/projects/9336/trigger/pipeline` |
| Body type | `application/x-www-form-urlencoded` |

**Form fields:**

| Key | Value |
|-----|--------|
| `token` | Your pipeline trigger token |
| `ref` | `lab` |
| `variables[OOTB_BUG_INPUT]` | `{{Message text}}` (Workflow variable for message body) |
| `variables[SLACK_CHANNEL_ID]` | `C0XXXXXXXX` (fixed — your channel ID) |
| `variables[SLACK_THREAD_TS]` | `{{Message timestamp}}` or `{{Thread timestamp}}` if replying in thread |

Workflow variable names differ slightly by Slack version. Use:

- **Message text** → full text including `ootb-bug:`
- **Message ts** → for top-level posts
- **Thread ts** → if the bug is posted inside an existing thread (prefer thread parent ts)

Publish the workflow and ensure it is **available in `#test_ai_ootb`**.

---

## Step 5 — Test

Post in `#test_ai_ootb`:

```
ootb-bug: K8s Node CPU detector fires at 70% instead of 90%
```

**Expected:**

1. Workflow ack in the thread (within seconds)
2. GitLab pipeline on **`lab`** ([pipelines page](https://cd.splunkdev.com/observability/shared/content-discovery/-/pipelines?ref=lab))
3. Bot message in thread with **BITS ticket**, **draft MR**, and **suspect file** (`detector/K8s Node CPU.json`)

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Workflow runs, no pipeline | Bad trigger token or wrong `ref` | Re-check token; use `ref=lab` |
| Pipeline fails immediately | Missing `JIRA_*` or `GITLAB_TOKEN` | Set CI variables |
| Pipeline succeeds, no Slack reply | Bot not in channel / bad token | `/invite` bot; verify `SLACK_BOT_TOKEN` |
| Reply in channel, not thread | Wrong `SLACK_THREAD_TS` | Use message ts or parent thread ts |
| `not_in_channel` from Slack API | Bot not invited | `/invite @BotName` in `#test_ai_ootb` |
| Job not found | `.gitlab-ci.yml` not on `lab` | Push automation branch |

---

## After testing works

When ready for production:

1. Merge automation to **`master`**
2. Switch workflow `ref` from `lab` → `master` (or use `/gitlab run ootb-bug-fix …` and remove the workflow)
3. Point channel from `#test_ai_ootb` → `#o11y-ootb-content`

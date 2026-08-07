---
name: bug-report-workflow
description: End-to-end workflow for bugs reported in #o11y-ootb-content — create a JIRA BITS ticket, open a draft GitLab MR with reviewers, fix OOTB JSON content, sync to Master SignalBuddy with hashCode refresh, and validate before merge. Use when a bug is reported in Slack #o11y-ootb-content, when triaging OOTB content issues, or when the user asks to start a bug fix for navigators/dashboards/detectors.
---

# OOTB Bug-Report Workflow

Automates the path from Slack bug report → JIRA ticket → GitLab draft MR → JSON fix → Master SignalBuddy sync → CI validation.

## When to use

- A bug is reported in **#o11y-ootb-content**
- User asks to triage, fix, or create a ticket/MR for OOTB content
- User needs to sync JSON changes to Master SignalBuddy and refresh `hashCode`

## Prerequisites

- `contentforge/config.yaml` exists (copy from `contentforge/config.yaml.example`)
- Env vars: `JIRA_EMAIL`, `JIRA_API_TOKEN`, `GITLAB_TOKEN`
- SignalBuddy: root `.token` file or `SIGNALBUDDY_TOKEN`
- `jq` installed for local validation

## Workflow

```
Task progress:
- [ ] Step 1: Parse bug report (title, affected content, Slack permalink)
- [ ] Step 2: Triage — JIRA ticket + draft MR
- [ ] Step 3: Fix JSON content on MR branch
- [ ] Step 4: Sync to Master SignalBuddy with hashCode refresh
- [ ] Step 5: Commit, push, validate, notify Slack
```

### Step 1 — Parse the bug report

Extract from the Slack message:

- **Title** — concise summary for JIRA/MR
- **Description** — steps to reproduce, expected vs actual, affected navigator/group/detector names
- **Slack permalink** — link to the triggering message

If the affected content file is unclear, search the repo:

```bash
rg -l "keyword" group/ navigators/ detector/
```

### Step 2 — Triage (JIRA + draft MR)

```bash
python -m contentforge.pipeline.orchestrator triage \
  --title "<title>" \
  --description "<description>" \
  --slack-permalink "<slack-url>" \
  --checkout
```

This creates:

- A **BITS** JIRA ticket with `o11y-ootb` label
- A **draft** GitLab MR on branch `fix/bits-<JIRA-KEY>-<date>` with configured reviewers

Post the JIRA and MR links back in the Slack thread.

### Step 3 — Fix JSON content

Edit the relevant files under `navigators/`, `group/`, or `detector/`.

Rules (enforced by CI):

- **Never change resource IDs** (`navigatorExport.navigator.id`, `groupExport.group.id`, etc.)
- **hashCode must change** after content edits — this happens automatically after SignalBuddy sync

### Step 4 — Sync to Master SignalBuddy

Always plan first, then apply with local refresh:

```bash
python -m contentforge.syncer.cli plan
python -m contentforge.syncer.cli apply --yes --refresh-local
```

Or for specific files:

```bash
python -m contentforge.syncer.cli apply --yes --refresh-local --paths "detector/K8s Node CPU.json"
```

The `--refresh-local` flag re-fetches each resource from master, writing the updated `hashCode` to disk.

**Never apply without showing the plan to the user first** unless they explicitly approved in the same session.

### Step 5 — Commit, push, validate

```bash
git add navigators/ group/ detector/
git commit -m "fix(<JIRA-KEY>): <summary>"
git push origin HEAD
```

Optionally run local validation:

```bash
CI_MR_TARGET_BRANCH=master /bin/bash scripts/validate_content.sh
```

Notify Slack with MR link and summary of changes.

## Safety rails

- Never print or log API tokens
- Never change resource IDs in JSON exports
- Always run `plan` before `apply` and get user approval
- Draft MRs stay draft until the fix is validated and ready for review
- SignalBuddy sync targets **Master SignalBuddy only** (realm `us0`)

## Configuration

Reviewer IDs and labels live in `contentforge/config.yaml`:

```yaml
gitlab:
  default_reviewer_ids: [12345, 67890]  # GitLab user IDs
```

## Exit codes (syncer)

| Code | Meaning |
|------|---------|
| 0 | Success |
| 5 | Partial failure (some resources failed) |

Report failures verbatim from the `error` fields in syncer JSON output.

## Related skills

- `sync-master-signalbuddy` — detailed SignalBuddy sync reference
- `contentforge/README.md` — setup and architecture

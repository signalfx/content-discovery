# Scripts


### Apply Navigator Categories & Navigator Category Groups to Navigator (apply_navigator_categories.py)

Although the JSON files stored in `navigatorCategories` and `navigatorCategoryGroups` should be considered as the single source of truth, there will be no actual effect until the data is disseminated to individual navigators through this script.

This script shortcuts the process described in [this wiki page](https://signalfuse.atlassian.net/wiki/spaces/APPS/pages/669220923/Updating+built-in+content+managed+by+Signalbuddy). As a result, you only need to follow these steps to update `navigatorCategory` or `navigatorCategoryGroup`.

1. Make changes in JSON files under `navigatorCategory` or `navigatorCategoryGroup` directory.
2. Run this script.
```
./apply_navigator_categories.py [Signalbuddy Master Org USER_TOKEN]
```
3. Test it in lab (Step 7~8 in the [wiki](https://signalfuse.atlassian.net/wiki/spaces/APPS/pages/669220923/Updating+built-in+content+managed+by+Signalbuddy))
4. Create PR to master (Step 9)

### BridgeIT content validation (validate_bridgeit_content.mjs)

This script validates any added/changed content (specifically, navigators and dashboard groups) using BridgeIT. It will send an API request to the BridgeIT API to search for typographical/semantic issues in the changed content, and will exit with a non-zero status code if any such potential issues are found. Files that are unchanged are not analyzed.

This script runs automatically as part of the Gitlab pipeline when an MR is created/updated. It is non-blocking, meaning it will not prevent the MR from being merged in case potential issues are found (to avoid blocking in case of hallucinations).

Variables that must be set in Gitlab CI/CD settings for the repo for this to work:

- ```BRIDGE_API_CLIENT_ID```: The client ID for the BridgeIT API.
- ```BRIDGE_API_CLIENT_SECRET```: The client secret for the BridgeIT API.
- ```BRIDGE_API_APP_KEY```: The app key for the BridgeIT API.
- (optional) ```BRIDGE_API_MODEL_NAME```: The AI model to use for validation. Defaults to "gpt-4.1". For list of available models, see: https://cisco.sharepoint.com/:w:/r/sites/BridgeIT/Shared%20Documents/API%20Docs%20-%20GPT.docx?d=w0b9f9bbd876b4c70a1897954d24f57bd&csf=1&web=1&e=AczLhG
- (optional) ```BRIDGE_API_TEMPERATURE```: The temperature for the AI model. Defaults to 1.
- (optional) ```BRIDGE_API_TOP_P```: The top_p for the AI model. Defaults to 0.25.

When running locally, you can set these variables in your environment or pass them as command line arguments. For example:

```EXPORT BRIDGE_API_CLIENT_ID=client_id```

### BridgeIT/CircuIT auto-fix proposer (bridge_it_propose_fix.mjs)

This script is the auto-fix companion to the validator. Instead of pointing out
issues, it asks the same BridgeIT/CircuIT model to *propose a minimal
RFC-6902 JSON patch* that fixes a triaged OOTB bug, and applies that patch on
disk so a downstream CI step can commit and push it to the MR branch.

It runs in the `propose-fix` stage of `.gitlab-ci.yml` as the `ootb-propose-fix`
job, and consumes the `triage.json` artifact emitted by `ootb-bug-fix`
(populated by `contentforge/pipeline/bug_pipeline.py`).

Conservative defaults (v1):

- Only the top-1 "primary suspect" file may be modified.
- Only `replace` operations are accepted (no `add`/`remove`/`move`/`copy`).
- Paths pointing at `hashCode`, `id`, `version`, `importQualifier`, or any
  `*_id` field are hard-blocked (these are managed by Master SignalBuddy).
- Applied only if the model reports `confidence >= 0.7`
  (override with `PROPOSE_FIX_MIN_CONFIDENCE`).
- `allow_failure: true` — the human still has a Jira + placeholder MR even if
  the LLM proposes nothing usable.

Reuses the same GitLab CI/CD variables as the validator
(`BRIDGE_API_CLIENT_ID`, `_SECRET`, `_APP_KEY`, and optional
`BRIDGE_API_MODEL_NAME`). Adds one optional knob:

- `PROPOSE_FIX_MIN_CONFIDENCE`: minimum LLM self-reported confidence to apply
  the patch. Defaults to `0.7`.

A summary of what was applied/rejected is written to `propose_fix_summary.json`
and kept as a CI artifact for 30 days for debugging.

### OOTB auto-fix Slack update (slack_post_propose_fix_update.mjs)

Reads `propose_fix_summary.json` + `triage.json` and posts a status update to
Slack. Runs as the final step of the `ootb-propose-fix` CI job, so the same
Slack thread that got the initial "Working on OOTB bug…" ack also gets a
follow-up message telling reviewers whether the AI:

- pushed a patch (with confidence, op count, and reviewer risk notes), or
- declined for low confidence, or
- proposed ops that were all blocked by the guardrails.

Posting is best-effort and uses whichever mechanism is configured (Bot API
threaded reply preferred, webhook fallback, plus a GitLab ChatOps
`chat_reply` block when the pipeline was triggered by `/gitlab run`). If no
Slack config is present in the environment the script exits cleanly. It never
fails the CI job — the propose-fix job is already `allow_failure: true`, and
this notifier catches all exceptions to `exit 0`.

Env (same names the Python notifier already uses; all optional):

- `CONTENT_FORGE_SLACK_BOT_TOKEN` or `SLACK_BOT_TOKEN`
- `SLACK_CHANNEL_ID`
- `SLACK_THREAD_TS` — reply in-thread when set (propagated from the trigger)
- `SLACK_WEBHOOK_URL` — fallback if the Bot API path is not configured
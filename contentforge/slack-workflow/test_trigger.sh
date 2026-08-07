#!/usr/bin/env bash
# Test GitLab pipeline trigger for Slack Workflow path (no merge to master required).
#
# Usage:
#   export CI_TRIGGER_TOKEN="..."
#   export SLACK_CHANNEL_ID="C0XXXXXXXX"   # #test_ai_ootb
#   export SLACK_THREAD_TS="1234567890.123456"  # optional; omit to post to channel root
#   ./contentforge/slack-workflow/test_trigger.sh "ootb-bug: K8s Node CPU detector fires at 70% instead of 90%"

set -euo pipefail

BUG_TEXT="${1:-K8s Node CPU detector fires at 70% instead of 90%}"
REF="${OOTB_PIPELINE_BRANCH:-lab}"
PROJECT_ID="${GITLAB_PROJECT_ID:-9336}"
GITLAB_HOST="${GITLAB_HOST:-cd.splunkdev.com}"

: "${CI_TRIGGER_TOKEN:?Set CI_TRIGGER_TOKEN (Settings → CI/CD → Pipeline triggers)}"

ARGS=(
  --form "token=${CI_TRIGGER_TOKEN}"
  --form "ref=${REF}"
  --form "variables[OOTB_BUG_INPUT]=${BUG_TEXT}"
)

if [[ -n "${SLACK_CHANNEL_ID:-}" ]]; then
  ARGS+=(--form "variables[SLACK_CHANNEL_ID]=${SLACK_CHANNEL_ID}")
fi

if [[ -n "${SLACK_THREAD_TS:-}" ]]; then
  ARGS+=(--form "variables[SLACK_THREAD_TS]=${SLACK_THREAD_TS}")
fi

echo "Triggering pipeline on ref=${REF} ..."
curl --silent --show-error --request POST \
  "${ARGS[@]}" \
  "https://${GITLAB_HOST}/api/v4/projects/${PROJECT_ID}/trigger/pipeline" | jq .

echo ""
echo "Check: https://${GITLAB_HOST}/observability/shared/content-discovery/-/pipelines?ref=${REF}"

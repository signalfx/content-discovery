#!/usr/bin/env bash
# Verify that every path in every commit of the public mirror is allowlisted.
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
target_repo="${MIRROR_TARGET_REPO:-splunk/content-discovery}"
branches="master"

log() { printf '%s\n' "$*" >&2; }
"${script_dir}/validate-public-catalog.sh" --config-only

scratch="$(mktemp -d)"
cleanup() {
  rm -rf "${scratch}"
}
trap cleanup EXIT

rc=0
for branch in ${branches}; do
  log ""
  log "=== verify ${branch} ==="
  work="${scratch}/${branch//\//_}"
  git clone --quiet --single-branch --branch "${branch}" \
    "https://github.com/${target_repo}.git" "${work}"

  unexpected="$(git -C "${work}" log --all --pretty=format: --name-only | sort -u | awk '
    NF && $0 != "PUBLIC_CATALOG.md" && $0 != "catalog-realms.json" &&
    $0 !~ /^group\/.*\.json$/ && $0 !~ /^navigators\/.*\.json$/ &&
    $0 !~ /^detector\/.*\.json$/ { print; exit }
  ')"
  if [ -n "${unexpected}" ]; then
    log "  ERROR: non-catalog path exists in public history: ${unexpected}"
    rc=1
    continue
  fi

  invalid_json=''
  while IFS= read -r -d '' file; do
    if ! jq empty "${file}" >/dev/null 2>&1; then
      invalid_json="${file#${work}/}"
      break
    fi
  done < <(find "${work}/group" "${work}/navigators" "${work}/detector" -type f -name '*.json' -print0)
  if [ -n "${invalid_json}" ]; then
    log "  ERROR: invalid public catalog JSON: ${invalid_json}"
    rc=1
    continue
  fi

  commits="$(git -C "${work}" rev-list --count HEAD)"
  files="$(find "${work}/group" "${work}/navigators" "${work}/detector" -type f -name '*.json' | wc -l | tr -d ' ')"
  log "  OK: ${files} catalog files across ${commits} reachable commits; no internal paths"
done

exit "${rc}"

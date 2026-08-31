#!/usr/bin/env bash
# Publish a one-way, allowlist-only GitLab -> GitHub catalog mirror.
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/.." && pwd)"
config_file="${script_dir}/public-catalog-paths.conf"
target_repo="${MIRROR_TARGET_REPO:-splunk/content-discovery}"
branches="master"
source_url="${MIRROR_SOURCE_URL:-$(git -C "${repo_root}" remote get-url origin)}"

log() { printf '%s\n' "$*" >&2; }
redact_url() { printf '%s' "$1" | sed -E 's|(://)[^/@]*@|\1<redacted>@|'; }
strip_userinfo() { printf '%s' "$1" | sed -E 's|(://)[^/@]*@|\1|'; }
url_userinfo() { printf '%s' "$1" | sed -nE 's|^[a-zA-Z][a-zA-Z0-9+.-]*://([^/@]+)@.*$|\1|p'; }
url_prefix() { printf '%s' "$1" | sed -nE 's#^([a-zA-Z][a-zA-Z0-9+.-]*://)([^/@]+@)?([^/]+).*#\1\3#p'; }

command -v git-filter-repo >/dev/null 2>&1 || { log 'ERROR: git-filter-repo is required'; exit 1; }
"${script_dir}/validate-public-catalog.sh" --config-only

public_paths=()
while IFS= read -r line || [ -n "${line}" ]; do
  line="${line%%#*}"
  line="${line#"${line%%[![:space:]]*}"}"
  line="${line%"${line##*[![:space:]]}"}"
  [ -z "${line}" ] && continue
  public_paths+=("${line%/}")
done < "${config_file}"

token="$("${script_dir}/github-app-token.sh")"
scratch="$(mktemp -d)"
cleanup() {
  rm -rf "${scratch}"
  unset token auth_header source_auth_header GIT_CONFIG_COUNT \
    GIT_CONFIG_KEY_0 GIT_CONFIG_VALUE_0 GIT_CONFIG_KEY_1 GIT_CONFIG_VALUE_1
}
trap cleanup EXIT

# Inject credentials through environment-based Git config. Tokens are never
# written to .git/config and never appear in argv/process listings.
auth_header="AUTHORIZATION: basic $(printf 'x-access-token:%s' "${token}" | base64 | tr -d '\n')"
export GIT_CONFIG_COUNT=1
export GIT_CONFIG_KEY_0='http.https://github.com/.extraheader'
export GIT_CONFIG_VALUE_0="${auth_header}"

source_userinfo="$(url_userinfo "${source_url}")"
if [ -n "${source_userinfo}" ]; then
  source_prefix="$(url_prefix "${source_url}")"
  source_auth_header="AUTHORIZATION: basic $(printf '%s' "${source_userinfo}" | base64 | tr -d '\n')"
  export GIT_CONFIG_COUNT=2
  export GIT_CONFIG_KEY_1="http.${source_prefix}/.extraheader"
  export GIT_CONFIG_VALUE_1="${source_auth_header}"
  source_url="$(strip_userinfo "${source_url}")"
fi

filter_args=()
for path in "${public_paths[@]}"; do
  filter_args+=(--path "${path}")
done

log "Source: $(redact_url "${source_url}")"
log "Target: ${target_repo}; branches: ${branches}"
log "Public allowlist: ${public_paths[*]}"

rc=0
for branch in ${branches}; do
  log ""
  log "=== ${branch} ==="
  work="${scratch}/${branch//\//_}"
  git clone --quiet --single-branch --branch "${branch}" "${source_url}" "${work}"
  before="$(git -C "${work}" rev-parse HEAD)"

  # Rebuild the complete branch history using only public catalog paths. An
  # allowlist makes unknown future internal files private by default.
  git -C "${work}" filter-repo --force "${filter_args[@]}" >/dev/null
  after="$(git -C "${work}" rev-parse HEAD)"
  log "  sanitized ${before:0:8} -> ${after:0:8}"

  # Defense in depth: independently reject any path that escaped filtering.
  unexpected="$(git -C "${work}" log --all --pretty=format: --name-only | sort -u | awk '
    NF && $0 != "PUBLIC_CATALOG.md" && $0 != "catalog-realms.json" &&
    $0 !~ /^group\/.*\.json$/ && $0 !~ /^navigators\/.*\.json$/ &&
    $0 !~ /^detector\/.*\.json$/ { print; exit }
  ')"
  if [ -n "${unexpected}" ]; then
    log "  ERROR: unexpected public-history path: ${unexpected}"
    rc=1
    continue
  fi

  github_url="https://github.com/${target_repo}.git"
  if git -C "${work}" fetch --quiet "${github_url}" \
      "refs/heads/${branch}:refs/remotes/public/${branch}" 2>/dev/null; then
    public_tip="$(git -C "${work}" rev-parse "refs/remotes/public/${branch}")"
    if git -C "${work}" merge-base --is-ancestor "${public_tip}" HEAD; then
      push_flags=()
      log "  public branch is a fast-forward"
    elif [ "${MIRROR_ALLOW_NON_FF:-0}" = "1" ]; then
      push_flags=(--force)
      log "  manual cutover permits non-fast-forward publication"
    else
      log "  REFUSED: publication would be non-fast-forward; use the manual cutover job"
      rc=1
      continue
    fi
  else
    push_flags=()
    log "  public branch does not exist yet; first publication"
  fi

  if git -C "${work}" push "${push_flags[@]}" "${github_url}" "HEAD:refs/heads/${branch}"; then
    log "  PUSH OK"
  else
    log "  PUSH FAILED"
    rc=1
  fi
done

exit "${rc}"

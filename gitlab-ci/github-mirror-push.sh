#!/usr/bin/env bash
# Publish a one-way, allowlist-only GitLab -> GitHub catalog snapshot.
#
# Public history is generated rather than copied: every commit has a controlled
# author, committer, message, and timestamp. No internal author identity, email,
# commit message, merge-request link, or source SHA enters GitHub history.
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/.." && pwd)"
config_file="${script_dir}/public-catalog-paths.conf"
target_repo="${MIRROR_TARGET_REPO:-splunk/content-discovery}"
branch="master"
source_url="${MIRROR_SOURCE_URL:-$(git -C "${repo_root}" remote get-url origin)}"

publisher_name="Splunk OOTB Catalog Publisher"
publisher_email="content-discovery-mirror@users.noreply.github.com"
publisher_message="Publish OOTB catalog snapshot"
# A fixed timestamp makes a generated commit deterministic for a given tree and
# parent while disclosing no internal commit or pipeline timing metadata.
publisher_date="2000-01-01T00:00:00Z"

log() { printf '%s\n' "$*" >&2; }
redact_url() { printf '%s' "$1" | sed -E 's|(://)[^/@]*@|\1<redacted>@|'; }
strip_userinfo() { printf '%s' "$1" | sed -E 's|(://)[^/@]*@|\1|'; }
url_userinfo() { printf '%s' "$1" | sed -nE 's|^[a-zA-Z][a-zA-Z0-9+.-]*://([^/@]+)@.*$|\1|p'; }
url_prefix() { printf '%s' "$1" | sed -nE 's#^([a-zA-Z][a-zA-Z0-9+.-]*://)([^/@]+@)?([^/]+).*#\1\3#p'; }

for required_tool in git curl openssl tar python3; do
  command -v "${required_tool}" >/dev/null 2>&1 || {
    log "ERROR: vetted mirror image is missing required tool: ${required_tool}"
    exit 1
  }
done
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
auth_header="AUTHORIZATION: basic $(printf 'x-access-token:%s' "${token}" | openssl base64 -A)"
export GIT_CONFIG_COUNT=1
export GIT_CONFIG_KEY_0='http.https://github.com/.extraheader'
export GIT_CONFIG_VALUE_0="${auth_header}"

source_userinfo="$(url_userinfo "${source_url}")"
if [ -n "${source_userinfo}" ]; then
  source_prefix="$(url_prefix "${source_url}")"
  source_auth_header="AUTHORIZATION: basic $(printf '%s' "${source_userinfo}" | openssl base64 -A)"
  export GIT_CONFIG_COUNT=2
  export GIT_CONFIG_KEY_1="http.${source_prefix}/.extraheader"
  export GIT_CONFIG_VALUE_1="${source_auth_header}"
  source_url="$(strip_userinfo "${source_url}")"
fi

source_work="${scratch}/source"
publish_work="${scratch}/publish"
github_url="https://github.com/${target_repo}.git"

log "Source: $(redact_url "${source_url}") (branch ${branch})"
log "Target: ${target_repo} (branch ${branch})"
log "Public allowlist: ${public_paths[*]}"

git clone --quiet --single-branch --branch "${branch}" "${source_url}" "${source_work}"
"${source_work}/gitlab-ci/validate-public-catalog.sh"

# Export only the approved current tree into a brand-new repository. Unlike a
# path-filtered clone, this carries no internal Git objects or metadata.
mkdir -p "${publish_work}"
git -C "${source_work}" archive --format=tar HEAD -- "${public_paths[@]}" \
  | tar -xf - -C "${publish_work}"
git -C "${publish_work}" init --quiet --initial-branch="${branch}"
git -C "${publish_work}" add --all
catalog_tree="$(git -C "${publish_work}" write-tree)"

public_ref="refs/remotes/public/${branch}"
public_tip=''
public_history_safe=false
if git -C "${publish_work}" fetch --quiet "${github_url}" \
    "refs/heads/${branch}:${public_ref}" 2>/dev/null; then
  public_tip="$(git -C "${publish_work}" rev-parse "${public_ref}")"
  public_history_safe=true

  unexpected="$(git -C "${publish_work}" log "${public_ref}" --pretty=format: --name-only | sort -u | awk '
    NF && $0 != "PUBLIC_CATALOG.md" && $0 != "catalog-realms.json" &&
    $0 !~ /^group\/.*\.json$/ && $0 !~ /^navigators\/.*\.json$/ &&
    $0 !~ /^detector\/.*\.json$/ { print; exit }
  ')"
  if [ -n "${unexpected}" ]; then
    log "Existing public history contains unexpected path: ${unexpected}"
    public_history_safe=false
  fi

  while IFS= read -r commit; do
    [ -n "${commit}" ] || continue
    author_name="$(git -C "${publish_work}" show -s --format='%an' "${commit}")"
    author_email="$(git -C "${publish_work}" show -s --format='%ae' "${commit}")"
    committer_name="$(git -C "${publish_work}" show -s --format='%cn' "${commit}")"
    committer_email="$(git -C "${publish_work}" show -s --format='%ce' "${commit}")"
    subject="$(git -C "${publish_work}" show -s --format='%s' "${commit}")"
    body="$(git -C "${publish_work}" show -s --format='%b' "${commit}")"
    author_date="$(git -C "${publish_work}" show -s --format='%aI' "${commit}")"
    committer_date="$(git -C "${publish_work}" show -s --format='%cI' "${commit}")"
    parent_count="$(git -C "${publish_work}" show -s --format='%P' "${commit}" | awk '{print NF}')"

    if [ "${author_name}" != "${publisher_name}" ] ||
       [ "${author_email}" != "${publisher_email}" ] ||
       [ "${committer_name}" != "${publisher_name}" ] ||
       [ "${committer_email}" != "${publisher_email}" ] ||
       [ "${subject}" != "${publisher_message}" ] ||
       [ -n "${body}" ] ||
       [ "${author_date}" != "2000-01-01T00:00:00+00:00" ] ||
       [ "${committer_date}" != "2000-01-01T00:00:00+00:00" ] ||
       [ "${parent_count}" -gt 1 ]; then
      log "Existing public commit ${commit:0:8} violates generated-metadata policy"
      public_history_safe=false
      break
    fi
  done < <(git -C "${publish_work}" rev-list "${public_ref}")
fi

parent_args=()
push_flags=()
if [ -z "${public_tip}" ]; then
  log "Public master does not exist yet; creating a generated root snapshot"
elif [ "${public_history_safe}" = true ]; then
  public_tree="$(git -C "${publish_work}" rev-parse "${public_ref}^{tree}")"
  if [ "${public_tree}" = "${catalog_tree}" ]; then
    log "Public catalog already matches the generated snapshot; nothing to push"
    exit 0
  fi
  parent_args=(-p "${public_tip}")
  log "Existing public history satisfies metadata policy; creating a fast-forward snapshot"
else
  if [ "${MIRROR_ALLOW_NON_FF:-0}" != "1" ]; then
    log "REFUSED: existing public history contains unsanitized metadata or paths"
    log "Run the reviewed manual cutover job to replace it with a generated root snapshot"
    exit 1
  fi
  push_flags=(--force)
  log "Manual cutover will replace unsanitized public history with a generated root snapshot"
fi

generated_commit="$(printf '%s\n' "${publisher_message}" | \
  GIT_AUTHOR_NAME="${publisher_name}" \
  GIT_AUTHOR_EMAIL="${publisher_email}" \
  GIT_COMMITTER_NAME="${publisher_name}" \
  GIT_COMMITTER_EMAIL="${publisher_email}" \
  GIT_AUTHOR_DATE="${publisher_date}" \
  GIT_COMMITTER_DATE="${publisher_date}" \
  git -C "${publish_work}" commit-tree "${catalog_tree}" "${parent_args[@]}")"
git -C "${publish_work}" update-ref "refs/heads/${branch}" "${generated_commit}"

if git -C "${publish_work}" push "${push_flags[@]}" "${github_url}" \
    "refs/heads/${branch}:refs/heads/${branch}"; then
  log "PUSH OK: generated snapshot ${generated_commit:0:8}"
else
  log "PUSH FAILED"
  exit 1
fi

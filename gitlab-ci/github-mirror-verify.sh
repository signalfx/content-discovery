#!/usr/bin/env bash
# Verify that every path in every commit of the public mirror is allowlisted.
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
target_repo="${MIRROR_TARGET_REPO:-splunk/content-discovery}"
branches="master"
publisher_name="Splunk OOTB Catalog Publisher"
publisher_email="content-discovery-mirror@users.noreply.github.com"
publisher_message="Publish OOTB catalog snapshot"

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

  metadata_error=''
  while IFS= read -r commit; do
    [ -n "${commit}" ] || continue
    author_name="$(git -C "${work}" show -s --format='%an' "${commit}")"
    author_email="$(git -C "${work}" show -s --format='%ae' "${commit}")"
    committer_name="$(git -C "${work}" show -s --format='%cn' "${commit}")"
    committer_email="$(git -C "${work}" show -s --format='%ce' "${commit}")"
    subject="$(git -C "${work}" show -s --format='%s' "${commit}")"
    body="$(git -C "${work}" show -s --format='%b' "${commit}")"
    author_date="$(git -C "${work}" show -s --format='%aI' "${commit}")"
    committer_date="$(git -C "${work}" show -s --format='%cI' "${commit}")"
    parent_count="$(git -C "${work}" show -s --format='%P' "${commit}" | awk '{print NF}')"
    if [ "${author_name}" != "${publisher_name}" ] ||
       [ "${author_email}" != "${publisher_email}" ] ||
       [ "${committer_name}" != "${publisher_name}" ] ||
       [ "${committer_email}" != "${publisher_email}" ] ||
       [ "${subject}" != "${publisher_message}" ] ||
       [ -n "${body}" ] ||
       [ "${author_date}" != "2000-01-01T00:00:00+00:00" ] ||
       [ "${committer_date}" != "2000-01-01T00:00:00+00:00" ] ||
       [ "${parent_count}" -gt 1 ]; then
      metadata_error="${commit}"
      break
    fi
  done < <(git -C "${work}" rev-list HEAD)
  if [ -n "${metadata_error}" ]; then
    log "  ERROR: public commit violates generated-metadata policy: ${metadata_error:0:8}"
    rc=1
    continue
  fi

  invalid_json=''
  while IFS= read -r -d '' file; do
    if ! python3 -m json.tool "${file}" >/dev/null 2>&1; then
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
  log "  OK: ${files} catalog files across ${commits} generated commits; no internal paths or metadata"
done

exit "${rc}"

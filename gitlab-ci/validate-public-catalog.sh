#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/.." && pwd)"
config_file="${script_dir}/public-catalog-paths.conf"

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

[ -f "${config_file}" ] || die "missing ${config_file}"

paths=()
seen_public_readme=0
seen_realm_manifest=0
seen_groups=0
seen_navigators=0
seen_detectors=0
while IFS= read -r line || [ -n "${line}" ]; do
  line="${line%%#*}"
  line="${line#"${line%%[![:space:]]*}"}"
  line="${line%"${line##*[![:space:]]}"}"
  [ -z "${line}" ] && continue

  # Keep this hard-coded guard independent from the config. A config-only
  # change must never be enough to publish internal files accidentally.
  case "${line}" in
    PUBLIC_CATALOG.md) seen_public_readme=$((seen_public_readme + 1)) ;;
    catalog-realms.json) seen_realm_manifest=$((seen_realm_manifest + 1)) ;;
    group/) seen_groups=$((seen_groups + 1)) ;;
    navigators/) seen_navigators=$((seen_navigators + 1)) ;;
    detector/) seen_detectors=$((seen_detectors + 1)) ;;
    *) die "path is not approved for public mirroring: ${line}" ;;
  esac
  paths+=("${line}")
done < "${config_file}"

[ "${#paths[@]}" -eq 5 ] &&
  [ "${seen_public_readme}" -eq 1 ] &&
  [ "${seen_realm_manifest}" -eq 1 ] &&
  [ "${seen_groups}" -eq 1 ] &&
  [ "${seen_navigators}" -eq 1 ] &&
  [ "${seen_detectors}" -eq 1 ] || die "public allowlist must contain each approved path exactly once"

if [ "${1:-}" = "--config-only" ]; then
  exit 0
fi

for path in "${paths[@]}"; do
  [ -e "${repo_root}/${path%/}" ] || die "allowlisted path does not exist: ${path}"
done

non_json="$(find "${repo_root}/group" "${repo_root}/navigators" "${repo_root}/detector" -type f ! -name '*.json' -print -quit)"
[ -z "${non_json}" ] || die "non-JSON file exists in a public catalog directory: ${non_json#${repo_root}/}"

python3 -m json.tool "${repo_root}/catalog-realms.json" >/dev/null

json_count=0
while IFS= read -r -d '' file; do
  python3 -m json.tool "${file}" >/dev/null || die "invalid JSON: ${file#${repo_root}/}"
  json_count=$((json_count + 1))
done < <(find "${repo_root}/group" "${repo_root}/navigators" "${repo_root}/detector" -type f -name '*.json' -print0)

[ "${json_count}" -gt 0 ] || die "public catalog contains no JSON definitions"
printf 'Validated %s public catalog JSON files and the strict path allowlist.\n' "${json_count}"

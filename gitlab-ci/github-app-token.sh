#!/usr/bin/env bash
# Mint a short-lived GitHub App installation token without putting either the
# private key or JWT on the process command line.
set -euo pipefail

: "${GITHUB_APP_ID:?GITHUB_APP_ID must be set}"
: "${GITHUB_APP_PRIVATE_KEY_FILE:?GITHUB_APP_PRIVATE_KEY_FILE must be set}"

api="${GITHUB_API:-https://api.github.com}"
target_repo="${MIRROR_TARGET_REPO:-splunk/content-discovery}"

case "${target_repo}" in
  */*)
    owner="${target_repo%%/*}"
    repository="${target_repo#*/}"
    ;;
  *)
    printf 'ERROR: MIRROR_TARGET_REPO must be in owner/repository form\n' >&2
    exit 1
    ;;
esac
case "${owner}/${repository}" in
  /*|*/|*/*/*)
    printf 'ERROR: MIRROR_TARGET_REPO must be in owner/repository form\n' >&2
    exit 1
    ;;
esac
case "${repository}" in
  ''|*/*)
    printf 'ERROR: MIRROR_TARGET_REPO must be in owner/repository form\n' >&2
    exit 1
    ;;
esac

command -v curl >/dev/null 2>&1 || { printf 'ERROR: curl is required\n' >&2; exit 1; }
command -v openssl >/dev/null 2>&1 || { printf 'ERROR: openssl is required\n' >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { printf 'ERROR: python3 is required\n' >&2; exit 1; }
[ -r "${GITHUB_APP_PRIVATE_KEY_FILE}" ] || { printf 'ERROR: GitHub App key is unreadable\n' >&2; exit 1; }

b64url() {
  openssl base64 -A | tr '+/' '-_' | tr -d '='
}

now="$(date +%s)"
iat="$((now - 60))"
exp="$((now + 540))"
header='{"alg":"RS256","typ":"JWT"}'
payload="$(printf '{\"iat\":%s,\"exp\":%s,\"iss\":\"%s\"}' "${iat}" "${exp}" "${GITHUB_APP_ID}")"
signing_input="$(printf '%s' "${header}" | b64url).$(printf '%s' "${payload}" | b64url)"
signature="$(printf '%s' "${signing_input}" | openssl dgst -sha256 -sign "${GITHUB_APP_PRIVATE_KEY_FILE}" | b64url)"
jwt="${signing_input}.${signature}"

jwt_cfg="$(mktemp)"
token_request="$(mktemp)"
chmod 0600 "${jwt_cfg}"
chmod 0600 "${token_request}"
cleanup() { rm -f "${jwt_cfg}" "${token_request}"; unset jwt response token; }
trap cleanup EXIT
printf 'header = "Authorization: Bearer %s"\n' "${jwt}" > "${jwt_cfg}"

# GitHub otherwise grants the token every repository and permission available
# to the installation. Limit it to the mirror destination and its sole needed
# permission. Generate JSON rather than interpolating a repository name into it.
python3 -c \
  'import json, sys; json.dump({"repositories": [sys.argv[1]], "permissions": {"contents": "write"}}, sys.stdout)' \
  "${repository}" > "${token_request}"

installation_id="${GITHUB_APP_INSTALLATION_ID:-}"
if [ -z "${installation_id}" ]; then
  installation_id="$(curl -fsS -K "${jwt_cfg}" \
    -H 'Accept: application/vnd.github+json' \
    -H 'X-GitHub-Api-Version: 2022-11-28' \
    "${api}/app/installations" | python3 -c \
      'import json, sys; data = json.load(sys.stdin); print(data[0]["id"] if data else "")')"
fi
[ -n "${installation_id}" ] && [ "${installation_id}" != "null" ] || {
  printf 'ERROR: could not resolve the GitHub App installation id\n' >&2
  exit 1
}

response="$(curl -fsS -X POST -K "${jwt_cfg}" \
  -H 'Accept: application/vnd.github+json' \
  -H 'Content-Type: application/json' \
  -H 'X-GitHub-Api-Version: 2022-11-28' \
  --data-binary "@${token_request}" \
  "${api}/app/installations/${installation_id}/access_tokens")"
token="$(printf '%s' "${response}" | python3 -c \
  'import json, sys; print(json.load(sys.stdin).get("token", ""))')"
[ -n "${token}" ] && [ "${token}" != "null" ] || {
  printf 'ERROR: GitHub returned no installation token\n' >&2
  exit 1
}

# The caller captures stdout; never log this value.
printf '%s\n' "${token}"

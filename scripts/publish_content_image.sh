#!/usr/bin/env bash
# publish_content_image.sh
#
# Packages the content-discovery repo (navigators/, group/, detector/) as an OCI image
# and pushes it to a Docker registry using only curl — no Docker daemon or skopeo needed.
#
# The image uses the OCI Distribution Spec: one tar.gz layer + a config blob with the
# "created" timestamp. Signalbuddy lists tags by branch prefix and picks the newest one
# by parsing the "created" field, so each commit gets its own immutable tag.
#
# Tag format: <branch-sanitized>-<short-sha>
# e.g. feature-my-branch-abc12345
#
# Usage:
#   REGISTRY=docker-test.repo.splunkdev.net \
#   AUTH_TOKEN=<base64-user:pass> \
#   CI_COMMIT_REF_NAME=feature/my-branch \
#   CI_COMMIT_SHORT_SHA=abc12345 \
#   CI_COMMIT_SHA=abc12345... \
#   ./scripts/publish_content_image.sh

set -euo pipefail

# ── Credentials ─────────────────────────────────────────────────────────────
# CI_COMMIT_BRANCH is only set on branch pipelines, not MR pipelines.
# Use CI_PIPELINE_SOURCE to select the right role and registry.
creds-helper init

if [[ "${CI_PIPELINE_SOURCE:-}" == "merge_request_event" ]]; then
  # MR build: push to docker-test for validation before merge
  DOCKER_ROLE="docker-test-deployer-role"
  REGISTRY="docker-test.repo.splunkdev.net"
else
  # Master merge: push to production registry
  DOCKER_ROLE="docker-deployer-role"
  REGISTRY="docker.repo.splunkdev.net"
fi

# creds-helper writes credentials to ~/.docker/config.json
eval $(creds-helper docker --eval "artifactory:v2/cloud/role/${DOCKER_ROLE}")

# Extract the Basic auth token for the target registry — used by curl below
AUTH_TOKEN=$(python3 - <<PYEOF
import json
with open("${HOME}/.docker/config.json") as f:
    c = json.load(f)
print(c.get("auths", {}).get("${REGISTRY}", {}).get("auth", ""))
PYEOF
)

# ── Inputs ──────────────────────────────────────────────────────────────────
BRANCH="${CI_COMMIT_REF_NAME:?CI_COMMIT_REF_NAME must be set}"
SHORT_SHA="${CI_COMMIT_SHORT_SHA:?CI_COMMIT_SHORT_SHA must be set}"
FULL_SHA="${CI_COMMIT_SHA:?CI_COMMIT_SHA must be set}"

REPO_PATH="observability/shared/content-discovery"
IMAGE="${REGISTRY}/${REPO_PATH}"
BRANCH_SANITIZED=$(echo "${BRANCH}" | sed 's/[^a-zA-Z0-9._-]/-/g')
TAG="${BRANCH_SANITIZED}-${SHORT_SHA}"
API="https://${REGISTRY}/v2/${REPO_PATH}"
CURL_AUTH=(-H "Authorization: Basic ${AUTH_TOKEN}")

echo "============================================="
echo " Publishing content image"
echo "  Registry : ${REGISTRY}"
echo "  Image    : ${IMAGE}:${TAG}"
echo "  Branch   : ${BRANCH}"
echo "  Commit   : ${FULL_SHA}"
echo "============================================="

# ── Step 1: Package content directories as a single tar.gz ──────────────────
echo "[1/4] Packaging navigators/, group/, detector/ into content.tar.gz..."
# --exclude must precede directory arguments in GNU tar
tar --exclude="*.DS_Store" --exclude="*._*" -czf content.tar.gz \
    navigators/ group/ detector/

TAR_DIGEST="sha256:$(sha256sum content.tar.gz | awk '{print $1}')"
TAR_SIZE=$(wc -c < content.tar.gz)
echo "      Layer digest : ${TAR_DIGEST}"
echo "      Layer size   : ${TAR_SIZE} bytes"

# ── Step 2: Build OCI image config blob ─────────────────────────────────────
# The "created" timestamp is stored in the config so signalbuddy can sort
# tags by push time using Instant.parse() — lexicographic sort is unreliable
# when timestamps have different formats (fractional seconds, offsets, etc.)
echo "[2/4] Building OCI image config..."
CREATED="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
CONFIG=$(printf \
    '{"architecture":"amd64","os":"linux","created":"%s","config":{"Labels":{"branch":"%s","commit":"%s"}},"rootfs":{"type":"layers","diff_ids":["%s"]}}' \
    "${CREATED}" "${BRANCH}" "${FULL_SHA}" "${TAR_DIGEST}")
CONFIG_DIGEST="sha256:$(echo -n "${CONFIG}" | sha256sum | awk '{print $1}')"
CONFIG_SIZE=${#CONFIG}

mkdir -p oci/blobs/sha256
echo '{"imageLayoutVersion":"1.0.0"}' > oci/oci-layout
cp content.tar.gz "oci/blobs/sha256/${TAR_DIGEST#sha256:}"
echo -n "${CONFIG}"   > "oci/blobs/sha256/${CONFIG_DIGEST#sha256:}"

# ── Step 3: Build OCI manifest ───────────────────────────────────────────────
MANIFEST=$(printf \
    '{"schemaVersion":2,"mediaType":"application/vnd.oci.image.manifest.v1+json","config":{"mediaType":"application/vnd.oci.image.config.v1+json","digest":"%s","size":%d},"layers":[{"mediaType":"application/vnd.oci.image.layer.v1.tar+gzip","digest":"%s","size":%d}]}' \
    "${CONFIG_DIGEST}" "${CONFIG_SIZE}" "${TAR_DIGEST}" "${TAR_SIZE}")
MANIFEST_DIGEST="sha256:$(echo -n "${MANIFEST}" | sha256sum | awk '{print $1}')"
echo -n "${MANIFEST}" > "oci/blobs/sha256/${MANIFEST_DIGEST#sha256:}"

# ── Step 4: Push to registry via OCI Distribution Spec ──────────────────────
echo "[3/4] Pushing blobs to ${REGISTRY}..."

# Push config blob (small, always upload)
echo "      Pushing config blob ${CONFIG_DIGEST}..."
curl -fsSL -X POST "${CURL_AUTH[@]}" \
    -H "Content-Type: application/octet-stream" \
    --data-binary "@oci/blobs/sha256/${CONFIG_DIGEST#sha256:}" \
    "${API}/blobs/uploads/?digest=${CONFIG_DIGEST}" \
    -o /dev/null

# Check if layer blob already exists (avoids re-uploading 25 MB on every push)
LAYER_STATUS=$(curl -sS -o /dev/null -w "%{http_code}" "${CURL_AUTH[@]}" \
    -I "${API}/blobs/${TAR_DIGEST}")
if [[ "${LAYER_STATUS}" == "200" ]]; then
    echo "      Layer blob already exists, skipping upload."
else
    echo "      Pushing layer blob ${TAR_DIGEST} (${TAR_SIZE} bytes)..."
    curl -fsSL -X POST "${CURL_AUTH[@]}" \
        -H "Content-Type: application/octet-stream" \
        --data-binary "@content.tar.gz" \
        "${API}/blobs/uploads/?digest=${TAR_DIGEST}" \
        -o /dev/null
fi

echo "[4/4] Pushing manifest as ${IMAGE}:${TAG}..."
curl -fsSL -X PUT "${CURL_AUTH[@]}" \
    -H "Content-Type: application/vnd.oci.image.manifest.v1+json" \
    --data-binary "@oci/blobs/sha256/${MANIFEST_DIGEST#sha256:}" \
    "${API}/manifests/${TAG}" \
    -o /dev/null

echo "============================================="
echo " Successfully published:"
echo "  ${IMAGE}:${TAG}"
echo "============================================="

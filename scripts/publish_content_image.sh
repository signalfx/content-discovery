#!/usr/bin/env bash
# publish_content_image.sh
#
# Packages the content-discovery repo (navigators/, group/, detector/) as an OCI image
# and pushes it to a Docker registry using only curl — no Docker daemon or skopeo needed.
#
# The image follows the OCI Distribution Spec:
#   - One tar.gz layer containing all content files
#   - A config blob with the "created" timestamp so signalbuddy can sort tags
#     by push time using Instant.parse() (lexicographic sort is unreliable across
#     RFC3339 variants with different UTC offsets or fractional-second widths)
#
# Tag format: <branch-sanitized>-<short-sha>  e.g. feature-my-branch-abc12345
# Signalbuddy lists all tags, filters by branch prefix, and picks the newest one.
# Tags are immutable — each push creates a new tag, never overwrites.

set -euo pipefail

# ── Credentials ──────────────────────────────────────────────────────────────
# CI_COMMIT_BRANCH is only set on branch pipelines, not MR pipelines.
# Use CI_PIPELINE_SOURCE to select the right deployer role and registry.
creds-helper init

if [[ "${CI_PIPELINE_SOURCE:-}" == "merge_request_event" ]]; then
  # MR build: push to docker-test, tag = <source-branch-sanitized>-<sha>
  # Used by developers to test content changes before merging
  DOCKER_ROLE="docker-test-deployer-role"
  REGISTRY="docker-test.repo.splunkdev.net"
elif [[ "${CI_COMMIT_BRANCH:-}" == "master" ]]; then
  # Merged to master: push to production registry, tag = master-<sha>
  # signalbuddy production uses branchPrefix=master
  DOCKER_ROLE="docker-deployer-role"
  REGISTRY="docker.repo.splunkdev.net"
else
  # Merged to lab (or any other protected branch): push to docker-test, tag = lab-<sha>
  # signalbuddy lab0 uses branchPrefix=lab pointing at docker-test registry
  DOCKER_ROLE="docker-test-deployer-role"
  REGISTRY="docker-test.repo.splunkdev.net"
fi

# creds-helper docker --eval writes credentials to a temp dir and exports
# DOCKER_CONFIG pointing to that directory. Read the auth token from there.
eval $(creds-helper docker --eval "artifactory:v2/cloud/role/${DOCKER_ROLE}")

AUTH_TOKEN=$(python3 -c "
import json, os, sys
docker_cfg = os.environ.get('DOCKER_CONFIG', '')
if not docker_cfg:
    sys.exit('ERROR: DOCKER_CONFIG not set after creds-helper docker --eval')
cfg_path = os.path.join(docker_cfg, 'config.json')
with open(cfg_path) as f:
    cfg = json.load(f)
token = cfg.get('auths', {}).get('${REGISTRY}', {}).get('auth', '')
if not token:
    sys.exit('ERROR: no auth token for ${REGISTRY} in ' + cfg_path)
print(token)
")

# ── Inputs ────────────────────────────────────────────────────────────────────
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

# ── Step 1: Package content directories as a single tar.gz ───────────────────
echo "[1/4] Packaging navigators/, group/, detector/ into content.tar.gz..."
# --exclude must precede directory arguments in GNU tar
tar --exclude="*.DS_Store" --exclude="*._*" -czf content.tar.gz \
    navigators/ group/ detector/

# TAR_DIGEST: digest of the compressed blob (used in manifest layers[].digest)
TAR_DIGEST="sha256:$(sha256sum content.tar.gz | awk '{print $1}')"
TAR_SIZE=$(wc -c < content.tar.gz)

# UNCOMPRESSED_DIGEST: digest of the raw tar stream (required by OCI spec for
# rootfs.diff_ids — must match the uncompressed layer, not the gzip wrapper)
UNCOMPRESSED_DIGEST="sha256:$(gunzip -c content.tar.gz | sha256sum | awk '{print $1}')"

echo "      Layer digest (compressed)   : ${TAR_DIGEST}"
echo "      Layer digest (uncompressed) : ${UNCOMPRESSED_DIGEST}"
echo "      Layer size                  : ${TAR_SIZE} bytes"

# ── Step 2: Build OCI image config blob ──────────────────────────────────────
# Branch and commit are JSON-encoded via python to handle special characters
# (e.g. quotes in branch names would break the JSON if interpolated directly).
echo "[2/4] Building OCI image config..."
CREATED="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
CONFIG=$(python3 - <<PYEOF
import json
print(json.dumps({
    "architecture": "amd64",
    "os": "linux",
    "created": "${CREATED}",
    "config": {
        "Labels": {
            "branch": "${BRANCH}",
            "commit": "${FULL_SHA}"
        }
    },
    "rootfs": {
        "type": "layers",
        "diff_ids": ["${UNCOMPRESSED_DIGEST}"]
    }
}, separators=(',', ':')))
PYEOF
)
CONFIG_DIGEST="sha256:$(echo -n "${CONFIG}" | sha256sum | awk '{print $1}')"
CONFIG_SIZE=${#CONFIG}

mkdir -p oci/blobs/sha256
echo '{"imageLayoutVersion":"1.0.0"}' > oci/oci-layout
cp content.tar.gz "oci/blobs/sha256/${TAR_DIGEST#sha256:}"
echo -n "${CONFIG}" > "oci/blobs/sha256/${CONFIG_DIGEST#sha256:}"

# ── Step 3: Build OCI manifest ───────────────────────────────────────────────
MANIFEST=$(printf \
    '{"schemaVersion":2,"mediaType":"application/vnd.oci.image.manifest.v1+json","config":{"mediaType":"application/vnd.oci.image.config.v1+json","digest":"%s","size":%d},"layers":[{"mediaType":"application/vnd.oci.image.layer.v1.tar+gzip","digest":"%s","size":%d}]}' \
    "${CONFIG_DIGEST}" "${CONFIG_SIZE}" "${TAR_DIGEST}" "${TAR_SIZE}")
MANIFEST_DIGEST="sha256:$(echo -n "${MANIFEST}" | sha256sum | awk '{print $1}')"
echo -n "${MANIFEST}" > "oci/blobs/sha256/${MANIFEST_DIGEST#sha256:}"

# ── Step 4: Push to registry via OCI Distribution Spec ───────────────────────
echo "[3/4] Pushing blobs to ${REGISTRY}..."

# Push config blob (always upload — it is small and changes every push)
echo "      Pushing config blob ${CONFIG_DIGEST}..."
curl -fsSL -X POST "${CURL_AUTH[@]}" \
    -H "Content-Type: application/octet-stream" \
    --data-binary "@oci/blobs/sha256/${CONFIG_DIGEST#sha256:}" \
    "${API}/blobs/uploads/?digest=${CONFIG_DIGEST}" \
    -o /dev/null

# Check if the layer blob already exists — skip upload if so (saves 25 MB bandwidth)
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

# Public catalog mirror runbook

GitLab is authoritative. GitHub `splunk/content-discovery` is a read-only,
allowlist-only mirror containing the OOTB catalog and public realm metadata.

## Required setup

1. Create `splunk/content-discovery` on GitHub as a public repository with
   direct user pushes disabled and the mirroring GitHub App allowed to bypass
   the branch ruleset.
2. Install the organization-owned GitHub App with contents write permission.
3. Configure protected, masked GitLab variables:
   - `PIPELINE_GITHUB_APP_ID`
   - `PIPELINE_GITHUB_APP_PRIVATE_KEY` (base64-encoded PEM or file variable)
   - `PIPELINE_GITHUB_APP_INSTALLATION_ID` (optional)
4. Protect the GitLab `master` branch.

## First cutover

Run `public-catalog-mirror-cutover` manually from a protected `master` push
pipeline. Confirm that the verify step reports only allowlisted paths in the
complete public `master` history. Set the GitHub repository's default branch
to `master`, then set
`PIPELINE_GITHUB_MIRROR_PUSH_ENABLED=true` to arm steady-state publication.

## Steady state

Each protected `master` push mirrors only `master`; scheduled `master`
pipelines do the same. The automatic job permits only fast-forward updates. It
fails closed if the sanitized history diverges, if an unexpected path appears,
or if post-push verification fails. Verification clones GitHub without
credentials, so it also proves the catalog is genuinely public.

## Allowlist changes

Changes to `gitlab-ci/public-catalog-paths.conf` can rewrite public history.
The independent hard-coded guard in `validate-public-catalog.sh` must also be
updated, reviewed, and validated. Drain or notify consumers, then use the
manual cutover job. Never add CI, credentials, scripts, service manifests,
internal documentation, or developer tooling to the public allowlist.

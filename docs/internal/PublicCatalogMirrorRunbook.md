# Public catalog mirror runbook

GitLab is authoritative. GitHub `splunk/content-discovery` is a read-only,
allowlist-only mirror containing the OOTB catalog and public realm metadata.

The mirror publishes generated snapshot commits, not filtered internal
commits. Each public commit has the fixed author
`Splunk OOTB Catalog Publisher`, the non-personal address
`content-discovery-mirror@users.noreply.github.com`, the message
`Publish OOTB catalog snapshot`, and a fixed timestamp. This prevents internal
authors, email addresses, commit messages, merge-request links, source commit
identifiers, and timing metadata from entering public history.

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
5. Use the vetted, versioned internal CI image configured in `.gitlab-ci.yml`.
   Publishing tools must be provided by that image; do not add runtime package
   installation to the mirror job.

## First cutover

Run `public-catalog-mirror-cutover` manually from a protected `master` push
pipeline. Confirm that the verify step reports only allowlisted paths in the
complete public `master` history and that every commit satisfies the generated
metadata policy. This first cutover replaces any earlier path-filtered history
that may contain internal Git metadata. Set the GitHub repository's default
branch to `master`, then set
`PIPELINE_GITHUB_MIRROR_PUSH_ENABLED=true` to arm steady-state publication.

## Steady state

Each protected `master` push mirrors only `master`; scheduled `master`
pipelines do the same. The automatic job permits only fast-forward updates. It
fails closed if the generated history diverges, if an unexpected path or
commit metadata appears, or if post-push verification fails. Verification
clones GitHub without credentials, so it also proves the catalog is genuinely
public. If catalog content has not changed, no new snapshot commit is created.

## Allowlist changes

Changes to `gitlab-ci/public-catalog-paths.conf` can require replacing public
snapshot history.
The independent hard-coded guard in `validate-public-catalog.sh` must also be
updated, reviewed, and validated. Drain or notify consumers, then use the
manual cutover job when existing snapshots no longer satisfy the new policy.
Never add CI, credentials, scripts, service manifests, internal documentation,
or developer tooling to the public allowlist.

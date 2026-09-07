---
name: content-mr
description: Create, verify, and monitor GitLab merge requests for content-discovery ticket fixes, including template-aware descriptions and reviewer assignment. Use after a ticket change is committed or when reconciling an existing content-maintainer MR.
---

# Manage a content-discovery merge request

Use this skill only for GitLab delivery. It does not decide ticket requirements, edit content files, merge an MR, or transition Jira.

Read [references/mr-contract.md](references/mr-contract.md) before creating an MR or assigning reviewers.

## Repository target

The GitLab project is `https://cd.splunkdev.com/observability/shared/content-discovery`. Resolve the default branch from the remote; do not guess it. Use the full internal host for CLI and API operations.

## Required inputs

Require a Jira key and URL, source branch, exact commit SHA, implementation summary, and validation evidence. Every MR must request review from these baseline GitLab usernames:

- `ashokshah`
- `hisingh`
- `punitu`
- `svashisth`

Ticket-specific reviewers may be added but must not replace the baseline reviewers. The working tree must be clean and the branch must contain only the intended ticket change.

## Create idempotently

1. Fetch the target branch and verify branch divergence.
2. Find a repository MR template and preserve it when one exists.
3. Search for an existing open MR with the same project and source branch.
4. If one exists, update and verify it instead of creating another.
5. Push the exact source branch and create the MR against the verified default branch.
6. Include the Jira link, scope, exclusions, validation, SignalBuddy sync outcome, and AI-assistance disclosure.
7. Resolve all baseline and additional reviewer usernames through the GitLab API, remove duplicates and the MR author, and assign the resulting user IDs.
8. Fetch the MR again and verify its IID, URL, source branch, target branch, head SHA, title, description, and reviewers.

A pushed branch is not an MR. A CLI command that prints an MR URL and then errors must be verified through the API before it is reported as created.

## Monitor an MR

Fetch the MR, pipelines, jobs, approvals, and unresolved discussions. Classify it as:

- `merged`;
- `open_actionable` for branch-caused failures, conflicts, or actionable review comments;
- `open_waiting_review` when healthy and awaiting people;
- `open_external_failure` for runner, registry, credential, or unrelated infrastructure failures;
- `closed_unmerged`;
- `unverifiable`.

Do not treat an allowed-to-fail job as a failed pipeline. Do not rewrite repository code to hide an external infrastructure failure. Never merge automatically.

## Completion output

Return the verified project ID, MR IID and URL, source and target branches, head SHA, state classification, pipeline summary, unresolved-discussion count, approval summary, and reviewer usernames. Redact credentials and tokens.

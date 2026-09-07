# Daily run contract

## Required configuration

- complete Jira JQL;
- Jira site/project and automation identity;
- exact `Ready for verification` transition name or ID;
- Jira owner account IDs for mentions;
- internal GitLab project URL;
- optional additional GitLab reviewer usernames or an approved reference MR; the `$content-mr` baseline reviewers remain mandatory;
- maximum new tickets, changed files, and diff size per run;
- reminder interval;
- allowed repository paths and remote-write policy.

When content JSON is in scope, `content_release_notes.yaml` is an allowed required generated file and must be included in changed-file and diff-size accounting.

Refuse apply mode when a required write setting is absent. Read-only inventory and planning may still run.

## Run phases

1. `preflight`: credentials, tools, repository, lock, configuration, and state readability.
2. `reconcile`: inspect every ticket with an unfinished lifecycle state.
3. `discover`: query Jira and normalize eligible tickets.
4. `process`: investigate and optionally execute bounded new work.
5. `persist`: atomically record each completed external operation before moving on.
6. `summarize`: report outcomes and release the lock.

## Durable state

Store state under the repository-ignored `tools/content-maintainer/.state/` directory unless configuration selects another safe local path. Keep coordinator state in the checkout that owns the scheduled run, never in a ticket worktree. Record:

- schema version and configuration fingerprint;
- run history and lock owner;
- per-ticket lifecycle and Jira cursor;
- question fingerprints and reminder dates;
- worktree, branch, and base SHA;
- verified MR identity, SHA, pipeline, discussions, and reviewers;
- external operation keys and returned IDs.

Write state atomically. Remote Jira and GitLab reads remain authoritative after interruption.

## Modes

- `inventory`: read-only discovery and state comparison.
- `plan`: gather context and produce ticket plans without external writes.
- `run --dry-run`: simulate lifecycle choices and rendered comments/MRs.
- `run --ticket <key>`: bounded pilot for one eligible ticket.
- `run`: configured daily apply mode.

## Failure policy

Continue after a ticket-scoped failure. Stop the run for invalid configuration, unavailable state storage, lock contention, corrupted repository state, or shared authentication failure. Apply bounded retries only to demonstrably transient reads; do not blindly repeat writes.

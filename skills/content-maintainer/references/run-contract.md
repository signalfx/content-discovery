# Scheduled run contract

## Required configuration

- Jira site and complete JQL, including its project scope;
- an authenticated Jira identity that preflight can discover and persist;
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

1. `initialize`: assign a run ID and create its unique local log.
2. `preflight`: credentials, tools, repository, lock, configuration, and state readability.
3. `reconcile`: inspect every ticket with an unfinished lifecycle state.
4. `discover`: query Jira and normalize eligible tickets.
5. `process`: investigate and optionally execute bounded new work.
6. `persist`: atomically record each completed external operation before moving on.
7. `summarize`: report outcomes and release the lock.

## Per-run local logs

Every invocation, including inventory, planning, dry-run, ticket-scoped, and scheduled apply runs, must create a new log before service preflight or any external write. Store it under the repository-ignored directory:

```text
tools/content-maintainer/.state/runs/<UTC timestamp>-<run ID>.log
```

Use a UTC timestamp with second precision and a random UUID run ID so concurrent starts never share a filename. Create a new file exclusively; never append a new run to, reuse, or overwrite an earlier run log. If the directory or log cannot be created, make no external changes and report the logging failure in the Codex run output.

Append a timestamped record for run mode, configuration fingerprint, each phase start and result, tickets inspected, lifecycle decisions, intended and verified external operations, relevant returned IDs or URLs, validation outcomes, retryable failures, blockers, and final status. Record failures before stopping whenever the log remains writable. Full dry runs must record rendered comments, transitions, repository changes, SignalBuddy calls, and MR actions that would have occurred.

Logs must be useful without exposing credentials. Never record tokens, cookies, authorization headers, raw credential-bearing environment values, or unsanitized command/API output. Do not stage run logs, include them in ticket file/diff limits, or delete old logs automatically.

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
- `run`: configured scheduled apply mode.

## Failure policy

Continue after a ticket-scoped failure. Stop the run for invalid configuration, unavailable state storage, lock contention, corrupted repository state, or shared authentication failure. Apply bounded retries only to demonstrably transient reads; do not blindly repeat writes.

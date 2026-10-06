# Scheduled run contract

## Required configuration

- Jira site and complete JQL, including its project scope;
- an authenticated Codex Atlassian connection with Jira and Confluence access, from which preflight can discover the logged-in Jira identity for the current run;
- exact transition name or ID and exact resulting Jira status name for `In Progress`;
- exact transition name or ID and exact resulting Jira status name for `In Review`;
- exact transition name or ID and exact resulting Jira status name for `Ready For Verification`;
- Jira owner email addresses that preflight can resolve uniquely to active account IDs for mentions;
- internal GitLab project URL;
- optional additional GitLab reviewer usernames or an approved reference MR; the `$content-mr` baseline reviewers remain mandatory;
- maximum Todo tickets selected for new processing per run, changed files, and diff size per ticket;
- reminder interval;
- allowed repository paths and remote-write policy.

When content JSON is in scope, `content_release_notes.yaml` is an allowed required generated file and must be included in changed-file and diff-size accounting.

The complete configured JQL is the operation boundary. Fully paginate it each run, then assess every returned ticket using its current Jira status and linked Jira, GitLab, and repository evidence. Jira is the source of truth; no per-ticket coordinator state file or prior-run registry is required. Apply `limits.max_todo_tickets_per_run` only to tickets in the configured Todo status. Continue all eligible active/In Progress tickets regardless of that cap; tickets in other statuses are assessed and acted on when their current evidence requires it.

Refuse apply mode when a required write setting is absent. Read-only inventory and planning may still run.

For a selected Todo ticket in apply mode, the work-start boundary is: compare the current Jira status with `jira.in_progress_status`; when they differ, discover and execute the selector in `jira.in_progress_transition`; re-read Jira and require the exact configured target status; then create or verify the idempotent work-started comment. Never compare a transition ID or transition name with the current status. Complete this boundary before creating a worktree or editing repository files. If it fails, record any verified partial Jira operation in the run log and do not begin implementation. A dry run renders these operations without performing them.

After an MR is remotely verified and its Jira comment is created or verified, compare the current Jira status with `jira.in_review_status`. When they differ, discover and execute `jira.in_review_transition`, re-read Jira, and require the exact configured target status. A retry must perform only the missing comment or transition operation.

After an MR is independently verified as merged and merge evidence is created or verified in Jira, compare the current Jira status with `jira.ready_for_verification_status`. When they differ, discover and execute `jira.ready_for_verification_transition`, re-read Jira, and require the exact configured target status.

Apply mode requires `remote_writes.jira_comments`, `remote_writes.jira_in_progress_transition`, `remote_writes.jira_in_review_transition`, and `remote_writes.jira_ready_for_verification_transition` to be `true` before starting new ticket work. A false value is an intentional policy restriction, not permission to skip a lifecycle boundary.

Preflight must perform a real Jira read through the Codex Atlassian connection and verify Confluence access before a run that may need linked documentation. Configuration metadata or a successful process exit alone is not proof of access. If the connection is absent, disconnected, or requires reauthentication, stop before external writes and prompt the user to set up or reconnect Atlassian in Codex. Never ask for an Atlassian token or make scheduled runs depend on `dev-login`. Ghost may be used only as an explicitly chosen manual diagnostic fallback, not as the scheduled authentication path.

## Run phases

1. `initialize`: assign a run ID and create its unique local log.
2. `preflight`: verify credentials, tools, repository, lock, and configuration.
3. `query`: fully paginate the complete configured Jira JQL.
4. `assess`: inspect every returned ticket and determine its next action from current Jira status, comments, linked MR, and repository state.
5. `select`: choose up to the configured Todo-ticket limit for new processing; do not apply that limit to active/In Progress follow-up.
6. `process`: handle active tickets and selected Todo tickets one at a time, skipping tickets whose current evidence shows no action is needed.
7. `summarize`: report ticket decisions and verified operations, then release the lock.

## Evidence resolution before questions

The maintainer owns ordinary engineering judgment. It must not stop at the first inconsistency or missing detail. Before classifying a ticket as `needs_information`:

1. Compare the complete ticket, acceptance criteria, comments, attachments, and linked specifications. Prefer specific object IDs, examples, and documented behavior over stale or generalized summaries.
2. Inspect the current repository objects, surrounding implementation, history, and analogous accepted fixes.
3. Check authoritative API, vendor, or product documentation when behavior or metric semantics can be established externally.
4. Reconcile apparent conflicts by testing which interpretation matches the stated outcome, object names and descriptions, established repository conventions, and technically correct behavior.
5. Record the selected interpretation, evidence, and any non-blocking assumption in the run log, implementation plan, and MR description.

Proceed when this evidence supports one defensible outcome with reasonable confidence, even if every source is not worded identically. Do not ask for information that is discoverable, for confirmation of a supported conclusion, or for choices that are normal implementation details.

A question may block work only when the evidence has been exhausted and at least two materially different, technically valid outcomes remain, with no safe precedence. The unresolved choice must affect user-visible behavior, acceptance criteria, data correctness, permissions, destructive scope, or another decision the maintainer is not authorized to make. Log the competing outcomes and exhausted sources before asking.

## Per-run local logs

Every invocation, including inventory, planning, dry-run, ticket-scoped, and scheduled apply runs, must create a new log before service preflight or any external write. Store it under the repository-ignored directory:

```text
tools/content-maintainer/.state/runs/<UTC timestamp>-<run ID>.log
```

Use a UTC timestamp with second precision and a random UUID run ID so concurrent starts never share a filename. Create a new file exclusively; never append a new run to, reuse, or overwrite an earlier run log. If the directory or log cannot be created, make no external changes and report the logging failure in the Codex run output.

Append a timestamped record for run mode, configuration fingerprint, each phase start and result, tickets inspected, lifecycle decisions, evidence used to resolve ambiguities, non-blocking assumptions, intended and verified external operations, relevant returned IDs or URLs, validation outcomes, retryable failures, blockers, and final status. Record failures before stopping whenever the log remains writable. Full dry runs must record rendered comments, transitions, repository changes, SignalBuddy calls, and MR actions that would have occurred.

Logs must be useful without exposing credentials. Never record tokens, cookies, authorization headers, raw credential-bearing environment values, or unsanitized command/API output. Do not stage run logs, include them in ticket file/diff limits, or delete old logs automatically.

## Local run data

Store only unique run logs and the non-overlapping run lock under `tools/content-maintainer/.state/`. Do not maintain a durable per-ticket state file, processed-ticket list, comment cursor, or out-of-scope registry. Each run rebuilds its ticket set from the complete configured JQL and reads current Jira/GitLab/repository state before deciding whether work is needed. Use current comments and remote operation evidence to make writes idempotent. The log is for audit and troubleshooting only; later runs must not depend on it to find or resume tickets.

## Modes

- `inventory`: read-only query and per-ticket next-action assessment.
- `plan`: gather context and produce ticket plans without external writes.
- `run --dry-run`: simulate lifecycle choices and rendered comments/MRs.
- `run --ticket <key>`: bounded pilot for one eligible ticket.
- `run`: configured scheduled apply mode.

## Failure policy

Continue after a ticket-scoped failure. Stop the run for invalid configuration, unavailable run-log storage, lock contention, corrupted repository state, or shared authentication failure. Apply bounded retries only to demonstrably transient reads; do not blindly repeat writes.

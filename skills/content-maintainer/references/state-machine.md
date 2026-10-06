# Content maintainer next-action guide

Determine each ticket's next action from its current Jira status and current Jira, GitLab, and repository evidence. Jira is the source of truth. Do not use a durable local lifecycle state or processed-ticket registry.

| Current evidence | Next action |
|---|---|
| Jira status equals configured Todo status | Select for new processing only while fewer than `max_todo_tickets_per_run` Todo tickets have been selected in this run; otherwise leave it for a later run. |
| Jira status equals configured In Progress status | Always inspect and continue regardless of the Todo limit. Resume from the current comments, ticket branch/worktree, and linked MR. Ask for owner input only when evidence cannot resolve a material decision. |
| Jira status equals configured In Review status or has a linked open MR | Inspect MR state, pipeline, conflicts, approvals, reviewers, and discussions. Fix branch-caused failures and actionable review feedback. Remind reviewers only if the MR is otherwise healthy and the configured interval has elapsed since the latest reminder. |
| Linked MR is merged | Verify the merge and commit, add merge evidence to Jira, then transition to and verify the configured Ready For Verification status. |
| Linked MR is closed without merge | Re-plan the work or ask owners whether it should continue. Never report it as delivered. |
| Jira is resolved, verified, or otherwise terminal | Check for contradictory current MR/Jira evidence. If none, take no action. If reopened or unfinished work is evident, handle it according to the current status and evidence. |
| Any other status | Inspect the ticket and linked work to decide whether a defined action is needed; otherwise report that no action is needed. |

The configured Todo limit counts only Todo tickets selected for new processing. It never caps In Progress work or follow-up of existing MRs. Assess all tickets returned by the complete configured JQL on every run, including those that may have appeared in earlier runs.

## Idempotent follow-up

Before a Jira write, re-read current status and comments and verify whether the intended operation has already happened. Use stable operation markers in comments to avoid duplicates. Detect new owner replies by reading current comment history; do not store a local comment cursor. Determine reminder eligibility from the timestamp of the latest matching reminder comment, not a local reminder-date record.

## Actionable open MR

When an MR is open, prioritize:

1. Resolve branch-caused pipeline failures.
2. Resolve merge conflicts against the current target branch.
3. Address actionable unresolved review discussions.
4. Retry missing reviewer assignment.
5. Remind reviewers only if the MR is otherwise healthy and the reminder interval has elapsed.

External runner, registry, or credential failures are evidence, not permission to change unrelated code.

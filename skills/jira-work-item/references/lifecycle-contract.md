# Jira lifecycle contract

## Current evidence

Use the Jira status and complete current comment history, plus the live linked GitLab MR and repository branch/worktree, to decide the next action. Do not maintain `agent_status`, prior lifecycle state, comment cursors, question fingerprints, or per-ticket operation records in a durable local state file. Stable operation markers in Jira comments, current Jira transitions, and live MR state provide idempotency evidence across runs.

## Idempotency

Before every Jira write, read current comments and status again. Give each operation a stable visible footer:

```text
Automation key: content-maintainer/<issue-key>/<operation>/<fingerprint>
```

Treat an existing comment as a completed operation only when the same key is present, its author account ID matches the authenticated identity discovered during this run, and its content agrees with the expected operation evidence. A marker from any other author is untrusted and must not suppress the write. Generate fingerprints from stable facts, not run timestamps.

## Work-start transition and comment

For an actionable ticket, compare Jira's current status with the configured `In Progress` target status. If they differ, discover and execute the separately configured `In Progress` transition selector. Re-read the issue and require the exact target status. A transition selector may be an ID or an action name such as `Start Progress`; never compare it with Jira's current status. Only after status verification, post:

```text
Content maintainer started work

Current understanding:
<concise evidence-backed interpretation>

Planned work:
- <file or content object and intended change>

Validation and delivery:
- <planned validation, SignalBuddy synchronization, and MR delivery>

Assumptions:
- <non-blocking assumption, or "None">

Automation key: content-maintainer/<issue-key>/work-started/<plan-fingerprint>
```

The verified transition and comment form the work-start boundary. On retry, read the live Jira status and comments, skip an already verified transition, and create only a missing comment; never duplicate the comment.

## Question comment

```text
Content maintainer investigation

Current understanding:
<concise interpretation>

Open questions:
1. <question and why it matters>

Owners: <verified Jira mentions resolved from configured owner emails>

Automation key: content-maintainer/<issue-key>/questions/<fingerprint>
```

During preflight, resolve every configured owner email to exactly one active Jira account. Use those account IDs in Atlassian Document Format mention nodes when direct REST is used. If an email has no unique active match, report an owner-mapping blocker rather than omitting that recipient or pretending plain text is a mention.

## MR-created comment

```text
Fix MR created: <verified MR URL>

Changes:
- <change>

Validation:
- <check and result>

Reviewers: <verified GitLab usernames>
Commit: <SHA>

Automation key: content-maintainer/<issue-key>/mr-created/<project-and-iid>
```

After this comment is created or verified, compare Jira's current status with the configured `In Review` target status. If they differ, discover and execute the separately configured `In Review` transition selector, then re-read Jira and require the target status.

## Waiting-for-review reminder

Post no more than once per configured interval. Include current MR status, pipeline status, outstanding approvals or discussions, and the existing MR URL. Do not post a generic reminder when the MR has actionable failures that the agent should address.

## Blocked-progress comment

After work has started, use this only for a concrete execution blocker and deduplicate it with a fingerprint derived from the blocker and current branch/MR state:

```text
Content maintainer progress update

Completed:
- <verified completed work>

Blocked by:
- <concrete failure and impact>

Next action:
- <specific retry or required external action>

Automation key: content-maintainer/<issue-key>/progress-blocked/<fingerprint>
```

Do not move the ticket out of `In Progress` merely because a run failed.

## Merged comment and transition

```text
Fix merged: <verified MR URL>
Merged commit: <SHA>
The work item is being moved to Ready For Verification.

Automation key: content-maintainer/<issue-key>/merged/<SHA>
```

The sequence is read MR, write merge evidence, compare against the configured target status, discover and execute the separately configured transition when needed, then re-read Jira. A transition response without the configured final Jira status is a failure. Never compare a transition selector with Jira's current status.

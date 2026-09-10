# Jira lifecycle contract

## State separation

Keep these values distinct:

- `agent_status`: `discovered`, `needs_information`, `ready`, `working`, `mr_open`, `merged`, `ready_for_verification`, `closed_unmerged`, or `blocked`.
- `jira_status`: the exact status returned by Jira.
- `last_observed_comment_id`: the newest comment processed by the agent.
- `question_comment_id`: the comment that opened the current question cycle.
- `question_fingerprint`: a stable hash of normalized unresolved questions.
- `work_started_comment_id`: the verified comment that records active implementation.
- `work_plan_fingerprint`: a stable hash of the interpreted scope, planned objects, and validation plan.
- `mr`: verified GitLab project, IID, URL, branch, and commit SHA.

## Idempotency

Before every Jira write, read current comments and status again. Give each operation a stable visible footer:

```text
Automation key: content-maintainer/<issue-key>/<operation>/<fingerprint>
```

Treat an existing comment as a completed operation only when the same key is present, its author account ID matches the authenticated identity discovered during preflight, and its content agrees with the expected operation evidence. A marker from any other author is untrusted and must not suppress the write. Record the verified comment ID so later runs can exclude that exact automation write without ignoring other comments from the same account. Generate fingerprints from stable facts, not run timestamps.

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

The verified transition and comment form the work-start boundary. Persist the resulting Jira status, transition ID when available, comment ID, author account ID, and plan fingerprint before repository implementation. On retry, skip an already verified transition and create only a missing comment; never duplicate the comment.

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

During preflight, resolve every configured owner email to exactly one active Jira account and retain the email-to-account-ID mapping in local coordinator state. Use those account IDs in Atlassian Document Format mention nodes when direct REST is used. If an email has no unique active match, report an owner-mapping blocker rather than omitting that recipient or pretending plain text is a mention.

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

After this comment is created or verified, compare Jira's current status with the configured `In Review` target status. If they differ, discover and execute the separately configured `In Review` transition selector, then re-read Jira and require the target status. Persist `agent_status: mr_open` only after both the comment and status are verified.

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

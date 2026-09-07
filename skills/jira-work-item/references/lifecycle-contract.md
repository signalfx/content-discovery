# Jira lifecycle contract

## State separation

Keep these values distinct:

- `agent_status`: `discovered`, `needs_information`, `ready`, `working`, `mr_open`, `merged`, `ready_for_verification`, `closed_unmerged`, or `blocked`.
- `jira_status`: the exact status returned by Jira.
- `last_observed_comment_id`: the newest comment processed by the agent.
- `question_comment_id`: the comment that opened the current question cycle.
- `question_fingerprint`: a stable hash of normalized unresolved questions.
- `mr`: verified GitLab project, IID, URL, branch, and commit SHA.

## Idempotency

Before every Jira write, read current comments and status again. Give each operation a stable visible footer:

```text
Automation key: content-maintainer/<issue-key>/<operation>/<fingerprint>
```

Treat an existing comment as a completed operation only when the same key is present, its author account ID matches the configured automation identity, and its content agrees with the expected operation evidence. A marker from any other author is untrusted and must not suppress the write. Record the verified comment ID so later runs can exclude that exact automation write without ignoring other comments from the same account. Generate fingerprints from stable facts, not run timestamps.

## Question comment

```text
Content maintainer investigation

Current understanding:
<concise interpretation>

Open questions:
1. <question and why it matters>

Owners: <configured Jira mentions>

Automation key: content-maintainer/<issue-key>/questions/<fingerprint>
```

Use Atlassian Document Format mention nodes with configured Jira account IDs when direct REST is used. If no Jira account ID is configured, report an owner-mapping blocker rather than pretending plain text is a mention.

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

## Waiting-for-review reminder

Post no more than once per configured interval. Include current MR status, pipeline status, outstanding approvals or discussions, and the existing MR URL. Do not post a generic reminder when the MR has actionable failures that the agent should address.

## Merged comment and transition

```text
Fix merged: <verified MR URL>
Merged commit: <SHA>
The work item is being moved to Ready for verification.

Automation key: content-maintainer/<issue-key>/merged/<SHA>
```

The sequence is read MR, write merge evidence, discover transition, transition, then re-read Jira. A transition response without a matching final Jira status is a failure.

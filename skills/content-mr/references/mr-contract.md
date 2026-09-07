# Content MR contract

## Branch contract

- Start from refreshed `origin/<default-branch>` in an isolated worktree.
- Use `codex/<jira-key-lowercase>-<short-slug>` unless configuration provides another approved prefix.
- One Jira ticket maps to one branch and one open MR.
- Refuse unrelated staged or committed changes.
- Record the exact commit SHA before pushing and verify the MR head SHA matches it afterward.

## Description contract

Preserve the repository template when present and ensure the final description includes:

```text
## Jira
<key and link>

## Summary
<what changed and why>

## Scope
- <files or content objects>

## Not changed
- <important exclusions>

## Validation
- <command or check>: <result>

## SignalBuddy synchronization
<not applicable, verified update/export, or failure>

## AI assistance
This merge request was created with assistance from OpenAI Codex.
```

## Reviewer contract

The mandatory baseline reviewer usernames for every content-discovery MR are:

```text
ashokshah
hisingh
punitu
svashisth
```

Additional reviewer input may be a list of exact GitLab usernames or an explicitly approved reference MR. Additional reviewers are combined with, and never replace, the baseline list. `CODEOWNERS` groups are useful ownership evidence but are not automatically individual reviewers.

For each configured username:

1. Resolve it on the internal GitLab host.
2. Require exactly one active user.
3. Exclude the MR author.
4. Assign reviewer IDs in one update.
5. Re-fetch and compare the resulting reviewer username set.

An unresolved baseline or additional reviewer is a partial delivery: keep the verified MR, return the missing username, and allow the coordinator to retry assignment without creating another MR.

## Verification contract

MR creation is complete only when a GitLab API read confirms:

- project and IID;
- `state=opened`;
- expected source and target branches;
- expected head SHA;
- description includes the Jira URL and AI disclosure;
- all baseline reviewers other than the MR author are assigned;
- requested additional resolvable reviewers are assigned.

Persist project ID and IID as the stable identity. URLs and titles are presentation fields.

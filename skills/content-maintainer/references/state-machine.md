# Content maintainer state machine

| State | Entry evidence | Next daily action | Valid exits |
|---|---|---|---|
| `discovered` | Ticket matched configured JQL | Hydrate and investigate | `needs_information`, `ready`, `blocked` |
| `needs_information` | Verified Jira question comment | Read comments after cursor | `ready`, `needs_information`, `blocked` |
| `ready` | Complete acceptance criteria and plan | Create isolated worktree | `working`, `blocked` |
| `working` | Worktree, branch, and plan recorded | Implement and validate | `mr_open`, `needs_information`, `blocked` |
| `mr_open` | Verified GitLab project and IID | Reconcile MR and feedback | `mr_open`, `merged`, `closed_unmerged`, `blocked` |
| `merged` | GitLab reports merged with commit | Comment and transition Jira | `ready_for_verification`, `blocked` |
| `ready_for_verification` | Jira re-read confirms target status | No action unless reopened | `discovered` if Jira reopens |
| `closed_unmerged` | GitLab reports closed without merge | Re-plan or ask owner | `ready`, `needs_information`, `blocked` |
| `blocked` | Concrete terminal or run-policy blocker | Retry only when relevant state changes | Any justified state |

Persist both `agent_status` and `jira_status`; never store Jira's status in the agent lifecycle field.

## Actionable open MR

When an MR is open, prioritize actions in this order:

1. Resolve branch-caused pipeline failures.
2. Resolve merge conflicts against the current target branch.
3. Address actionable unresolved review discussions.
4. Retry missing reviewer assignment.
5. Remind reviewers only if the MR is otherwise healthy.

External runner, registry, or credential failures are evidence, not permission to change unrelated code.

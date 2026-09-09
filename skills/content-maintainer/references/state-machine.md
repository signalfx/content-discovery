# Content maintainer state machine

| State | Entry evidence | Next scheduled action | Valid exits |
|---|---|---|---|
| `discovered` | Ticket matched configured JQL | Hydrate, exhaust evidence resolution, and investigate | `needs_information`, `ready`, `blocked` |
| `needs_information` | Verified Jira question comment | Read comments after cursor | `ready`, `needs_information`, `blocked` |
| `ready` | Complete acceptance criteria and plan | Verify Jira `In Progress` and work-started comment, then create isolated worktree | `working`, `blocked` |
| `working` | Verified Jira work-start boundary plus worktree, branch, and plan | Implement, validate, and post an idempotent blocker update if execution stops | `mr_open`, `needs_information`, `blocked` |
| `mr_open` | Verified GitLab project and IID | Reconcile MR and feedback | `mr_open`, `merged`, `closed_unmerged`, `blocked` |
| `merged` | GitLab reports merged with commit | Comment and transition Jira | `ready_for_verification`, `blocked` |
| `ready_for_verification` | Jira re-read confirms target status | No action unless reopened | `discovered` if Jira reopens |
| `closed_unmerged` | GitLab reports closed without merge | Re-plan or ask owner | `ready`, `needs_information`, `blocked` |
| `blocked` | Concrete terminal or run-policy blocker | Retry only when relevant state changes | Any justified state |

Persist both `agent_status` and `jira_status`; never store Jira's status in the agent lifecycle field.

`needs_information` is valid only after the run contract's evidence-resolution process leaves multiple materially different, technically valid outcomes that require owner judgment. A documented, evidence-backed assumption exits to `ready`; residual uncertainty by itself does not.

Enter `working` only after Jira has been re-read in the configured `In Progress` status and the authenticated maintainer's work-started comment has been created or verified under the idempotency contract. Never use a local branch or worktree alone as evidence that Jira progress tracking succeeded.

## Actionable open MR

When an MR is open, prioritize actions in this order:

1. Resolve branch-caused pipeline failures.
2. Resolve merge conflicts against the current target branch.
3. Address actionable unresolved review discussions.
4. Retry missing reviewer assignment.
5. Remind reviewers only if the MR is otherwise healthy.

External runner, registry, or credential failures are evidence, not permission to change unrelated code.

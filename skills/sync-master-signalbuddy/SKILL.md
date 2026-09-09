---
name: sync-master-signalbuddy
description: Detect changed content-discovery navigator, detector, and dashboard-group exports in local work, staged commits, or a feature branch; update those objects in the Master SignalBuddy org through the SFX API skill; and export the server-canonical objects back into the same files. Use for pre-commit synchronization, planning, publishing, or refreshing repository content against Master SignalBuddy.
---

# Sync content to Master SignalBuddy

This skill orchestrates repository changes. Use `$sfx-api` as its API execution layer; do not duplicate endpoints or issue ad hoc HTTP calls.

The required lifecycle is:

1. Detect changed content files.
2. Export the current objects from Master SignalBuddy and build a plan.
3. Show the plan and obtain explicit approval, or use the commit action as approval in the installed pre-commit workflow.
4. Apply updates in dependency order.
5. Export every successfully updated top-level object back into its original file.

## Target and credentials

This workflow targets only the Master SignalBuddy org in realm `us0`. The repository `.token` file contains its API token; `SIGNALBUDDY_TOKEN` is the fallback. Never display the token or place it on a command line.

Run the sync engine from the repository root:

```bash
.venv/bin/python skills/sync-master-signalbuddy/scripts/sync_changed.py <command>
```

## Detect local and branch changes

The engine considers JSON files under `navigators/`, `detector/`, and `group/` from:

- commits on the current feature branch since its merge-base with the mainline;
- staged and unstaged working-tree changes;
- untracked content files.

On `main` or `master`, it compares the working tree with `HEAD`. On a feature branch, it automatically selects the available mainline ref. Pass `--base <ref>` when the target branch must be explicit.

## Automatic pre-commit synchronization

The repository hook at `tools/scripts/pre-commit` runs `scripts/pre_commit_sync.py`. For commits containing staged JSON files under `navigators/`, `detector/`, or `group/`, it automatically:

1. Validates repository content.
2. Refuses partially staged content files that also have unstaged edits.
3. Plans only the staged content paths and stops on remote fetch errors.
4. Applies those paths to Master SignalBuddy without another prompt; invoking `git commit` is the approval for this hook-managed sync.
5. Exports the canonical server objects, stages those refreshed files, and validates again.

After this sync step succeeds, the repository hook invokes `$content-changelog` to generate, stage, and validate release-note entries from the final staged exports. The changelog step is deterministic and does not make additional SignalBuddy calls.

Unrelated commits run validation but do not contact Master SignalBuddy. Any validation, credential, network, planning, update, export, or staging failure blocks the commit. `git commit --no-verify` remains Git's explicit emergency bypass.

## Plan, approve, apply

Always plan first:

```bash
.venv/bin/python skills/sync-master-signalbuddy/scripts/sync_changed.py plan
.venv/bin/python skills/sync-master-signalbuddy/scripts/sync_changed.py plan --base origin/master
.venv/bin/python skills/sync-master-signalbuddy/scripts/sync_changed.py plan --paths "group/Kubernetes.json"
```

Summarize each file, object ID, and meaningful difference from Master SignalBuddy. Do not apply when the plan has authentication or fetch errors. Obtain explicit user approval before running this command manually:

```bash
.venv/bin/python skills/sync-master-signalbuddy/scripts/sync_changed.py apply --yes
```

Use the same `--base` and `--paths` values from the approved plan. Approval for one subset does not authorize other changed files.

## Apply and export behavior

For a navigator:

1. Update the navigator through `$sfx-api` using its existing ID.
2. Update associated data links when present.
3. Export the navigator from Master SignalBuddy into the same local file.

For a detector:

1. Update the detector through `$sfx-api` using its existing ID.
2. Export the detector from Master SignalBuddy into the same local file.

For a dashboard group:

1. Compare the local export with its repository base and select only charts,
   dashboards, group fields, and data links changed by the branch or working tree.
2. Export the current complete group from Master SignalBuddy.
3. Create or update only the selected charts first.
4. Remap IDs for newly created charts in dependent dashboards.
5. Create or update only selected dashboards.
6. Remap IDs for newly created dashboards in the dashboard group.
7. Update the dashboard-group object only when selected group fields changed.
8. Create or update only selected associated data links.
9. Export the complete group from Master SignalBuddy into the same local file,
   updating changed JSON values without reordering keys or reformatting untouched
   content. Treat API-normalized null and empty collection values as equivalent.

Do not delete remote charts, dashboards, or data links merely because they are absent locally. Deletion requires a separate explicit request and plan.

If any API operation for a file fails, mark that file failed and do not overwrite it with a partial export. Successful files are refreshed independently. Report partial failures and their API errors.

## Single-file operations

Use these when the user names one file:

```bash
.venv/bin/python skills/sync-master-signalbuddy/scripts/sync_changed.py diff "detector/example.json"
.venv/bin/python skills/sync-master-signalbuddy/scripts/sync_changed.py update "detector/example.json" --yes
.venv/bin/python skills/sync-master-signalbuddy/scripts/sync_changed.py fetch detector <id>
.venv/bin/python skills/sync-master-signalbuddy/scripts/sync_changed.py pull --type detector --id <id> --yes
```

`update` must verify that the ID exists, apply the same API flow, and export the result back into the named file. Use `create` only for an explicitly requested new object; dashboard-group creation uses the complete import endpoint so chart and dashboard IDs are rewired atomically.

## Completion criteria

A sync is complete only when:

- every approved changed file has status `applied`;
- each successful file was exported from Master SignalBuddy after its update;
- the local file contains that fresh export;
- failures and intentionally skipped deletions are reported clearly.

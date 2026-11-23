---
name: sync-master-signalbuddy
description: Pushes content-discovery JSON changes (navigators, dashboard groups, detectors) from this repo to the Master SignalBuddy org, fetches the current state of a resource from SignalBuddy, or previews the diff without writing. Use when the user asks to sync, publish, push, deploy, or apply changed content to SignalBuddy / SignalFx / Master SignalBuddy, or when they want to see what would change before pushing, or when they want to inspect the live state of a navigator / group / detector by id.
---

# Sync content to Master SignalBuddy

This repo is the source-of-truth mirror of the Master SignalBuddy org.
The `syncer/cli.py` tool talks to exactly one place — Master SignalBuddy
— via the SignalFx REST API. There is no multi-env support and there
are no env flags. The credentials in the root `.token` file are always
the master token.

The bulk flow is always: **plan → review → apply**. Never apply without
showing the user the plan first.

## When to use

- The user asks to "sync", "push", "publish", "deploy", "release", or
  "apply" content to Master SignalBuddy / SignalFx / SignalBuddy.
- The user asks "what would change?" before a sync.
- The user asks for the current state of a navigator / group / detector
  by id.
- The user asks to **update one specific resource** in master by file
  path (e.g. "just push this one dashboard").
- The user asks to **create a brand-new resource** in master from a
  local file.
- The user asks to **pull / export** a resource from master back into
  the local repo (refresh a file, or bootstrap a new local file from an
  existing master id).

## Credentials

One file, one org, one line. Root `.token` (gitignored) holds only the
API token — no keys, no quotes, just the token string:

```
<your-master-signalbuddy-api-token>
```

Fallback: `SIGNALBUDDY_TOKEN` as a process environment variable (used
in CI / agent runs).

The realm is hardcoded to Master SignalBuddy's realm in
`syncer/utils.MASTER_REALM` (currently `us0`); it is not a config field.

If neither the file nor the env var is set, every command other than
`plan` errors out with a single clear message.

## Prerequisites (verify before any command)

For the bulk repo-driven workflow, local changes must exist:

```bash
git diff --name-only HEAD -- 'navigators/*' 'group/*' 'detector/*'
```

If empty, tell the user there is nothing to bulk-sync and stop. (The
single-resource `update` / `create` / `pull` verbs do not require a
git change.)

## Standard workflow (bulk push of locally changed files)

```
Task progress:
- [ ] Step 1: List changed files
- [ ] Step 2: Run plan
- [ ] Step 3: Show plan summary to the user and get explicit approval
- [ ] Step 4: Run apply with --yes
- [ ] Step 5: Report results
```

### Step 1 — list changed files

```bash
git diff --name-only HEAD -- 'navigators/*' 'group/*' 'detector/*'
```

### Step 2 — run plan

```bash
python -m syncer.cli plan
```

Output is JSON with a `resources` array. Each entry has `type`, `path`,
`id`, `name`, `remote_state`, and either `change_summary` (groups) or
`changes` (navigators / detectors). Parse it and summarise for the user.

To restrict to specific files:

```bash
python -m syncer.cli plan --paths "navigators/AWS/AWS Instances - unified.json"
```

### Step 3 — show the plan summary and get approval

Format the summary like this:

```
Master SignalBuddy sync plan (realm: us0)
3 resources would be updated:
  * navigator "AWS Instances"     navigators/AWS/AWS Instances - unified.json   3 field changes
  * group     "K8s health"        group/K8s health.json                          1 chart modified, 0 dashboards
  * detector  "K8s Node CPU"      detector/K8s Node CPU.json                     2 field changes

Proceed with apply?
```

Wait for explicit user confirmation. Never auto-apply.

### Step 4 — apply

```bash
python -m syncer.cli apply --yes
```

`--yes` is required; without it the command aborts.

Restrict to a subset with `--paths` (same syntax as `plan`). Useful
when the user approved only some of the planned changes.

### Step 5 — report results

Output JSON has a `results` array. Each entry has `status` of
`applied`, `failed`, or `skipped`. Exit code is 0 on full success, 5
on partial failure. Report the counts and list any failures verbatim
from the `error` fields.

## Read-only operations

### Fetch the current state of one resource

```bash
python -m syncer.cli fetch navigator <ID>
python -m syncer.cli fetch group     <ID>
python -m syncer.cli fetch detector  <ID>
```

Output JSON has a `resource` field with the full export payload.
`fetch` prints to stdout; it never writes to disk.

### Diff a single local file vs master

```bash
python -m syncer.cli diff "navigators/AWS/AWS Instances - unified.json"
```

The CLI infers the resource type from the file path or the JSON
structure (`navigatorExport`, `groupExport`, `detectorExport`).

## Single-resource operations

Three strict verbs target one resource at a time. None of them are
git-diff-driven. All require `--yes` to confirm destructive writes.
All operate against master (the only org this CLI knows about).

### `update` — push a single local file

```bash
python -m syncer.cli update "group/AWS Lambda.json" --yes
```

Behaviour:

- Pre-checks that the resource id exists in master with a `GET`. Fails
  with a clear error if not (no silent fall-through to create — that's
  `create`'s job). The error names `create` as the right verb.
- After a successful `PUT`, re-fetches the resource from master and
  **overwrites the local file** so it carries the latest
  server-normalized fields (`lastUpdated`, etc.) and stays a faithful
  mirror.

### `create` — POST a new resource into master

```bash
python -m syncer.cli create "group/AWS Lambda.json" --yes
```

Behaviour:

- If the local file already has an id, the CLI checks master for that
  id first and refuses with a clear error if it exists (use `update`
  instead). The error names `update` as the right verb.
- For dashboard **groups** the create hits
  `POST /v2/dashboardgroup/import`, so the backend rewires all child
  chart and dashboard ids server-side.
- For **navigator** and **detector** the inner object is POSTed with
  server-managed metadata stripped (`id`, `created`, `lastUpdated`,
  etc.) so the backend assigns fresh values.
- After a successful create the new server-assigned id is captured and
  the local file is **overwritten with the fresh export**. The file
  now describes the new resource going forward; the old id (if any)
  is gone.

### `pull` — export a resource from master into the repo

```bash
python -m syncer.cli pull --type group --id DASH_xyz --yes
```

Resolution order for the output path:

1. `--out` if provided;
2. existing local file whose JSON contains this id;
3. canonical path computed from the resource name (`group/<name>.json`,
   `detector/<name>.json`).

Navigators have a category subdirectory that cannot be inferred from
the export — for navigators with no existing local match, `--out` is
**required**:

```bash
python -m syncer.cli pull --type navigator --id NAV_xyz \
  --out "navigators/AWS/aws lambda.json" --yes
```

Files are written with 2-space indent and sorted keys for a stable
diff.

## When to pick which verb

| Goal | Verb |
|---|---|
| Push all locally changed files to master | `plan` → `apply` |
| Update one specific resource in master and refresh local | `update <path> --yes` |
| Push a brand-new local resource into master | `create <path> --yes` |
| Refresh a local file from master | `pull --type T --id I --yes` |
| Bootstrap a brand-new local file from a master id | `pull --type T --id I --out <path> --yes` |
| Inspect remote state without writing | `fetch <type> <id>` |
| Preview a local change vs remote | `diff <path>` |

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 2 | Usage error (bad flags, missing `--yes`, no credentials, malformed `.token`) |
| 3 | Local file or remote resource not found |
| 4 | SignalBuddy API failure (auth, 5xx, network) |
| 5 | Partial: some resources applied, some failed (`apply` only) |
| 6 | Refused: `create` of an id that already exists on master |

## Safety rails

- **Never run `apply` without first running `plan` and getting user approval.**
- **Never print or log the access token.** The CLI itself never echoes it.
- Tokens live in the root `.token` file (gitignored) or env vars; never
  paste them into shell history or commit messages.
- If `plan` reports `fetch_errors > 0`, surface that to the user — it
  may mean a missing resource that `apply` will create, or it may mean
  credential / network trouble.
- Dashboard groups intentionally do not delete remote charts or
  dashboards that no longer exist locally; the `change_summary` reports
  the count for visibility but no destructive action is taken.
- **`update` and `create` are strict.** `update` refuses to create a
  missing resource; `create` refuses to overwrite an existing one. The
  CLI's error message always names the correct verb to use instead —
  pass that suggestion through to the user verbatim.
- **`create` rewrites the local file with the new server-assigned id.**
  Confirm with the user before running `create` against a path whose
  existing id is real and in use, because the file will stop pointing
  at the original resource.
- **Every successful `update`, `create`, and `pull` overwrites a local
  file.** That is intentional — the repo is the mirror of master. Make
  sure the user expects the on-disk change.

## Common failure modes

| Symptom | Likely cause | Fix |
|---|---|---|
| `error: No credentials available for Master SignalBuddy. ...` | Root `.token` missing/empty and `SIGNALBUDDY_TOKEN` env var unset | Put the API token in `.token` as a single line, or export it as `SIGNALBUDDY_TOKEN` |
| `apply` returns exit code 5 | One or more resources failed to write | Read the `error` field of each failed entry; usually 401/403 (token) or 4xx (schema) |
| `fetch_error: Failed to fetch ... 404` in plan | Resource id exists locally but not yet in master | Expected for brand-new resources; `apply` will create them |
| `error: <type> <id> not found in master; use 'create <path>' instead` (exit 3) | Tried to `update` a resource that doesn't exist | Use the suggested `create` command verbatim |
| `error: <type> <id> already exists in master; use 'update <path>' instead` (exit 6) | Tried to `create` a resource that already exists | Use the suggested `update` command verbatim |
| `error: could not infer output path for navigator ...; pass --out <path>` | `pull` for a navigator without a local file matching the id | Pass `--out navigators/<category>/<name>.json` explicitly |

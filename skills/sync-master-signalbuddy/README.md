# sync-master-signalbuddy

A portable agent **skill** that lets the assistant push the JSON content
in this repo to the **Master SignalBuddy** org and pull the live state
back, without ever opening a TUI.

The same `SKILL.md` is discovered by **Cursor**, **OpenAI Codex CLI**, and
**GitLab Duo** — one canonical file, three discovery paths (see
[Runtime discovery](#runtime-discovery) below).

The orchestration rules live in [`SKILL.md`](./SKILL.md). The executable
workflow is [`scripts/sync_changed.py`](./scripts/sync_changed.py), and its
object operations share the strict API service used by the `sfx-api`
skill. There is no daemon, TUI, or server-side component to deploy.

## What it can sync

Three resource types, both directions:

| Type        | Source files in this repo            | Update → MSB | Export ← MSB |
| ----------- | ------------------------------------ | :----------: | :----------: |
| Navigator   | `navigators/<provider>/<name>.json`  |      ✅      |      ✅      |
| Group       | `group/<name>.json`                  |      ✅      |      ✅      |
| Detector    | `detector/<name>.json`               |      ✅      |      ✅      |

## When the skill fires

The agent will invoke this skill automatically when you say things like:

- "sync the AWS Instances navigator to master signal buddy"
- "push my detector changes to MSB"
- "what would change if I applied this to master signal buddy?"
- "update just `detector/K8s Node CPU.json` in master"
- "create this new dashboard group in master from my local file"
- "pull the latest version of group `<id>` from MSB into the repo"
- "fetch the live state of group `<id>` from MSB"
- "diff `detector/K8s Node CPU.json` against MSB"

You can also call it explicitly:

> Use the `sync-master-signalbuddy` skill to push my navigator changes.

## Prerequisites (one-time)

### 1. Install Python deps

The CLI uses only `requests` from the repo's top-level `requirement.txt`
plus the Python stdlib. From the repo root:

```bash
pip install -r requirement.txt
```

(Use a venv if you don't want repo-wide installs.)

### 2. Set up credentials

The CLI talks to exactly one place — Master SignalBuddy — and the
credentials for that org live in the root `.token` file (already
gitignored). The file holds nothing but the API token as a single
line:

```
<your-personal-access-token>
```

Tokens are per-user — never share, never commit, never paste into chat.

The realm is hardcoded in `scripts/sync_utils.MASTER_REALM` (currently
`us0`); it is not a config field.

**CI / agent mode**: export the token as `SIGNALBUDDY_TOKEN` and skip
the file.

## The commands

All commands emit a single JSON object on stdout. Human-readable
progress goes to stderr.

| Command  | Purpose                                                           | Writes local files? | Writes MSB? |
| -------- | ----------------------------------------------------------------- | :-----------------: | :---------: |
| `plan`   | Show what would change for every modified JSON file.              |         no          |     no      |
| `apply`  | Push every git-changed file, then export it back. Requires `--yes`.|       **YES**       |   **YES**   |
| `update` | Strict update of one resource from a local file; refreshes local. |       **YES**       |   **YES**   |
| `create` | Strict create of one resource from a local file; refreshes local. |       **YES**       |   **YES**   |
| `pull`   | Fetch one resource from MSB and overwrite the local file.         |       **YES**       |     no      |
| `fetch`  | Print one resource (navigator / group / detector) to stdout.      |         no          |     no      |
| `diff`   | Compare one local file against the live MSB state.                |         no          |     no      |

## Workflow A — push every locally changed file to MSB

This is the day-to-day "I changed some JSON files, push them" flow.
The skill always forces the order **plan → human approval → apply**.

```bash
# 1. Dry-run branch, staged, unstaged, and untracked changes against MSB
.venv/bin/python skills/sync-master-signalbuddy/scripts/sync_changed.py plan

# 2. Review the JSON the agent shows you. If it looks good:
.venv/bin/python skills/sync-master-signalbuddy/scripts/sync_changed.py apply --yes
```

Restrict to a subset (the agent does this when you only approve some
items in the plan):

```bash
.venv/bin/python skills/sync-master-signalbuddy/scripts/sync_changed.py plan  --paths "navigators/AWS/AWS Instances - unified.json"
.venv/bin/python skills/sync-master-signalbuddy/scripts/sync_changed.py apply --paths "navigators/AWS/AWS Instances - unified.json" --yes
```

## Automatic pre-commit workflow

Enable the tracked hook once in this checkout:

```bash
git config core.hooksPath tools/scripts
```

After that, `git commit` automatically handles staged navigator,
detector, and group JSON files. The hook validates the repository,
plans and applies only those staged content paths to Master
SignalBuddy, exports the canonical objects back into the same files,
re-stages them, and validates again. The repository hook then runs the
`content-changelog` skill's deterministic CLI to generate, stage, and
validate release-note entries for those final staged exports. The commit
itself is approval for this hook-managed remote update, so there is no
second prompt.

The commit is blocked if a selected content or changelog file has
unstaged edits, or if validation, credentials, network access, planning,
update, export, changelog coverage, or re-staging fails. Commits without
selected content still run normal validation but do not contact Master
SignalBuddy or modify the changelog.

Exit codes worth knowing:

| Code | Meaning                                                           |
| :--: | ----------------------------------------------------------------- |
|  0   | Success                                                           |
|  2   | Usage error (missing `--yes`, bad flag, no credentials)           |
|  3   | Local file or remote resource not found                           |
|  4   | SignalBuddy API failure (auth, 5xx, network)                      |
|  5   | Partial — some resources applied, some failed (see `error` field) |
|  6   | Refused — e.g. `create` of an id that already exists in master    |

## Workflow B — push, create, or refresh one specific resource

```bash
# Update one existing resource in MSB and refresh the local file
.venv/bin/python skills/sync-master-signalbuddy/scripts/sync_changed.py update "detector/APM Error Rate Increased.json" --yes

# Create a brand-new resource in MSB from a local file (and rewrite
# the local file with the server-assigned id)
.venv/bin/python skills/sync-master-signalbuddy/scripts/sync_changed.py create "group/AWS Lambda.json" --yes

# Pull one resource from MSB into the local file (overwrites existing)
.venv/bin/python skills/sync-master-signalbuddy/scripts/sync_changed.py pull --type group --id <ID> --yes
```

`update` and `create` are strict:

- `update` fails if the id does not exist in MSB (use `create` instead).
- `create` fails if the id already exists in MSB (use `update` instead).

The CLI's error message names the right verb in each case — pass it
through verbatim.

For navigators with no existing local match, `pull` needs an explicit
`--out` because the category subdirectory cannot be inferred from the
export:

```bash
.venv/bin/python skills/sync-master-signalbuddy/scripts/sync_changed.py pull --type navigator --id <ID> \
    --out "navigators/AWS/aws lambda.json" --yes
```

## Workflow C — see what differs without writing

```bash
.venv/bin/python skills/sync-master-signalbuddy/scripts/sync_changed.py diff "navigators/AWS/AWS Instances - unified.json"
.venv/bin/python skills/sync-master-signalbuddy/scripts/sync_changed.py fetch navigator <ID>
```

`diff` infers the resource type from the path (`navigators/`, `group/`,
`detector/`) or, failing that, from the JSON shape (`navigatorExport`,
`groupExport`, `detectorExport`). `fetch` prints the full export
payload from MSB without touching disk.

## Safety rails the skill enforces

For manually invoked sync commands, the agent will refuse to:

- Run `apply` without first running `plan` and showing you the diff.
- Run `apply` / `update` / `create` / `pull` without explicit user
  approval ("yes", "go ahead", etc.).
- Print or log the access token under any circumstance.
- Use `update` to silently create missing resources, or `create` to
  silently overwrite existing ones.
- Delete remote charts / dashboards that no longer exist locally —
  the group sync is additive / update-only on purpose. The
  `change_summary` surfaces the count so you know they exist; no
  destructive action is taken.

The installed pre-commit workflow is the one exception to a separate
approval prompt: running `git commit` authorizes synchronization of the
staged navigator, detector, and group JSON files only.

## Troubleshooting

| Symptom                                                                  | Likely cause                                                                | Fix                                                                                                                  |
| ------------------------------------------------------------------------ | --------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| `error: No credentials available for Master SignalBuddy. ...`            | Root `.token` missing/empty and `SIGNALBUDDY_TOKEN` env var unset           | Put the token in `.token` as a single line (no keys, no quotes), or export it as `SIGNALBUDDY_TOKEN`                 |
| `apply` returns exit code `5`                                            | Some resources failed to write                                              | Read the `error` field on each failed entry; usually 401/403 (token) or 4xx (schema)                                 |
| `fetch_error: ... 404` during `plan`                                     | Resource id exists locally but not yet in MSB                               | Expected for brand-new resources; `apply` will create them                                                           |
| `error: <type> <id> not found in master; use 'create <path>' instead`    | Tried to `update` a resource that does not exist                            | Use the suggested `create` command verbatim                                                                          |
| `error: <type> <id> already exists in master; use 'update <path>' instead` | Tried to `create` a resource that already exists                          | Use the suggested `update` command verbatim                                                                          |
| `error: could not infer output path for navigator ...; pass --out <path>` | `pull` for a navigator with no existing local file matching the id        | Pass `--out navigators/<category>/<name>.json` explicitly                                                            |
| Plan is empty                                                            | No JSON under `navigators/`, `group/`, `detector/` changed                  | Check `git diff --name-only HEAD -- 'navigators/*' 'group/*' 'detector/*'`                                           |

## Runtime discovery

The canonical files live at `skills/sync-master-signalbuddy/`. Each agent
runtime expects skills in its own directory, so the per-runtime
directories contain a **symlink** back to the canonical `SKILL.md`. One
file, four discovery paths:

```
content-discovery/
├── skills/sync-master-signalbuddy/
│   ├── SKILL.md          # canonical instructions the agent reads
│   └── README.md         # this file (canonical human docs)
├── .cursor/skills/sync-master-signalbuddy/
│   └── SKILL.md -> ../../../skills/sync-master-signalbuddy/SKILL.md
├── .codex/skills/sync-master-signalbuddy/
│   └── SKILL.md -> ../../../skills/sync-master-signalbuddy/SKILL.md
└── .gitlab/duo/skills/sync-master-signalbuddy/
    └── SKILL.md -> ../../../../skills/sync-master-signalbuddy/SKILL.md
```

| Runtime          | Discovery path                                    | Auto-loads in this repo? |
| ---------------- | ------------------------------------------------- | :----------------------: |
| Cursor           | `.cursor/skills/sync-master-signalbuddy/`         | ✅ project-scoped         |
| OpenAI Codex CLI | `.codex/skills/sync-master-signalbuddy/`          | ✅ project-scoped         |
| GitLab Duo Agent | `.gitlab/duo/skills/sync-master-signalbuddy/`     | ✅ when Duo opens repo    |
| Claude Code      | not wired by default — add a symlink under `.claude/skills/` if needed | ⛔ |

Edit `skills/sync-master-signalbuddy/SKILL.md` once — every runtime sees
the change on the next `git pull` (or immediately, locally).

> **Note on Codex path:** The `.codex/skills/` location follows the
> common Skills-spec convention. If your Codex CLI version uses a
> different path, move the symlink — the canonical file does not change.

### Adding the skill to your personal scope (optional)

Project-scoped paths above auto-load for anyone working in this repo.
If you also want it loaded in unrelated repos, drop one symlink per
runtime into your user-scope dir:

```bash
mkdir -p ~/.cursor/skills/sync-master-signalbuddy
ln -s "$PWD/skills/sync-master-signalbuddy/SKILL.md" \
      ~/.cursor/skills/sync-master-signalbuddy/SKILL.md

mkdir -p ~/.codex/skills/sync-master-signalbuddy
ln -s "$PWD/skills/sync-master-signalbuddy/SKILL.md" \
      ~/.codex/skills/sync-master-signalbuddy/SKILL.md
```

> Cursor's `~/.cursor/skills-cursor/` is **reserved for Cursor's
> built-in skills** — use `~/.cursor/skills/` instead.

## Full file layout

```
content-discovery/
├── skills/sync-master-signalbuddy/{SKILL.md, README.md}   # canonical
├── .cursor/skills/sync-master-signalbuddy/SKILL.md        # symlink
├── .codex/skills/sync-master-signalbuddy/SKILL.md         # symlink
├── .gitlab/duo/skills/sync-master-signalbuddy/SKILL.md    # symlink
├── .token                # gitignored Master SignalBuddy credentials
├── skills/sync-master-signalbuddy/scripts/
│   ├── sync_changed.py   # orchestration entry point
│   ├── sync_utils.py     # token + git diff helpers
│   ├── group_sync.py     # chart/dashboard/group dependency flow
│   └── datalink_sync.py  # associated data-link flow
├── navigators/<provider>/<name>.json
├── group/<name>.json
└── detector/<name>.json
```

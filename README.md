# Important
Please always export dashboards from SBMO using the `tool` in this repo.
e.g. `.venv/bin/python tools/scripts/tool group-export $dashboard_group_id > group/$your_dashboard_name`
This ensures clean diffs when making pull requests.

Splunk/SignalFx Employees: 
    Please visit the Confluence page link below to get details about how to use this repo to update built-in content managed by SignalBuddy:
    https://signalfuse.atlassian.net/wiki/spaces/APPS/pages/669220923

Others:
    Make a pull request to master, or open an issue. We will help you resolve.

# Install the Codex content maintainer

See [Content Maintainer setup prerequisites](tools/content-maintainer/README.md)
for the complete tool, authentication, permission, and local-file checklist.

The recurring content-maintainer job is versioned with this repository. After cloning the repository and opening it as a Codex project, run `./tools/scripts/configure-content-maintainer`. It validates the repository-local configuration, required project skills, pre-commit hook, Codex login and Atlassian connection configuration, GitLab access, and the ignored `./.token` against a read-only Master SignalBuddy request. Codex then verifies live Jira and Confluence access through the logged-in user's Atlassian connection before installing or updating the automation. If that connection is missing or needs authentication, Codex prompts the user to set it up and leaves the automation unchanged.

The script creates `configs/content-maintainer.local.yaml` from the example when needed; review that ignored file before re-running if validation reports a problem. Use `./tools/scripts/configure-content-maintainer --check-only` to run all prerequisite checks without asking Codex to change the automation.

Codex will create or update one active project automation that runs every four hours. Re-run the setup script after pulling repository changes to refresh the installed job from the canonical definition in `configs/codex/content-maintainer-automation.md`.

Every maintainer invocation writes a separate secret-free local log under `tools/content-maintainer/.state/runs/`. The entire `.state` directory is ignored by Git, so run logs do not appear in repository changes. Logs are retained locally, including for dry runs and failed runs, and are not deleted automatically.


# Git pre-commit hook

Enable the tracked hook once for this checkout. It validates content on every commit. When staged navigator, detector, or group JSON files are present, it updates those exact files in Master SignalBuddy, exports and stages the canonical objects, and then generates and stages one `content_release_notes.yaml` entry per final staged content file.

```
git config core.hooksPath tools/scripts
```

The commit is blocked on validation, credentials, API, export, changelog coverage, or staging failures. It also blocks a selected content or changelog file that has unstaged edits, preventing the hook from including changes you did not stage.

To explicitly bypass all hook checks and synchronization, run `git commit --no-verify`.

Note: The hook script uses the `jq` library to parse json files. You'll need this installed if not already: `brew install jq`

See `content_release_notes.yaml` and the `content-changelog` skill for changelog data and manual update or validation commands.

# Syncing content with the skill CLI

`skills/sync-master-signalbuddy/scripts/sync_changed.py` is a non-interactive CLI for pushing local JSON edits
to Master SignalBuddy, pulling current state back into the repo, and
previewing diffs. It is the same tool that the
`sync-master-signalbuddy` skill drives — these examples work whether
you run them by hand or ask an agent.

The CLI talks to exactly one place: **Master SignalBuddy**. There are
no environment flags.

Setup once. Put your master token in the root `.token` file (already
in `.gitignore`) as a single line — nothing else:

```
<your-master-signalbuddy-api-token>
```

For CI / agent runs, export the same value as `SIGNALBUDDY_TOKEN`
instead.

The realm is hardcoded in `skills/sync-master-signalbuddy/scripts/sync_utils.py` (currently
`us0`); it is not a config field.

## Five common workflows

### 1. Push all my local changes to Master SignalBuddy

```bash
.venv/bin/python skills/sync-master-signalbuddy/scripts/sync_changed.py plan
.venv/bin/python skills/sync-master-signalbuddy/scripts/sync_changed.py apply --yes
```

Plan first, review the JSON output, then apply. The bulk path is
driven by `git diff --name-only HEAD` against `navigators/`, `group/`,
and `detector/`.

### 2. Update one file in master and refresh it locally

```bash
.venv/bin/python skills/sync-master-signalbuddy/scripts/sync_changed.py update "detector/APM Error Rate Increased.json" --yes
```

Strict update — fails fast if the resource doesn't exist (use
`create` instead). After a successful write the local file is
auto-overwritten with the fresh export so it stays a faithful mirror
of master.

### 3. Create a brand-new resource in master from a local file

```bash
.venv/bin/python skills/sync-master-signalbuddy/scripts/sync_changed.py create "group/AWS Lambda.json" --yes
```

For groups this uses `POST /v2/dashboardgroup/import`, so the backend
assigns fresh ids and rewires all child charts / dashboards /
crosslinks. The local file is then overwritten with the fresh export
so it now carries the new server-assigned id.

### 4. Refresh a local file from master without pushing anything

```bash
.venv/bin/python skills/sync-master-signalbuddy/scripts/sync_changed.py pull --type group --id <GROUP_ID> --yes
```

If the id is already present in the repo, the matching local file is
overwritten in place; otherwise the canonical path
(`group/<name>.json` / `detector/<name>.json`) is used. For
navigators without an existing local match, pass
`--out navigators/<category>/<name>.json` explicitly.

### 5. Inspect remote state or preview a local change

```bash
.venv/bin/python skills/sync-master-signalbuddy/scripts/sync_changed.py fetch detector <DETECTOR_ID>
.venv/bin/python skills/sync-master-signalbuddy/scripts/sync_changed.py diff "detector/K8s Node CPU.json"
```

`fetch` prints the current master state to stdout; `diff` shows
field-level differences between a local file and the matching master
state. Neither writes to disk.

## Verb cheat-sheet

| Goal | Verb |
|---|---|
| Push every git-changed file | `plan` then `apply --yes` |
| Update one specific resource in master, refresh local | `update <path> --yes` |
| Create a brand-new resource in master from a local file | `create <path> --yes` |
| Refresh a local file from master | `pull --type T --id I --yes` |
| Bootstrap a brand-new local file from a master id | `pull --type T --id I --out <path> --yes` |
| Inspect remote state | `fetch <type> <id>` |
| Preview local vs master | `diff <path>` |

See `skills/sync-master-signalbuddy/SKILL.md` for the full reference
(exit codes, error messages, safety rails).

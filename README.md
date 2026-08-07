Splunk/SignalFx Employees: 
    Please visit the Confluence page link below to get details about how to use this repo to update built-in content managed by SignalBuddy:
    https://signalfuse.atlassian.net/wiki/spaces/APPS/pages/669220923

Others:
    Make a pull request to master, or open an issue. We will help you resolve.


# git pre-commit hook

Copy the `scripts/pre-commit` hook to this git repo; this will run validation against the content files to ensure that 
content id's haven't inadvertently changed. (That situation can cause issues with existing content
if it gets deployed, and requires remediation against production realms).

```
mkdir -p .git/hooks && cp scripts/pre-commit .git/hooks
```

(to force skip of the commit validation, you can run `git commit --no-verify`)

Note: The hook script uses the `jq` library to parse json files. You'll need this installed if not already: `brew install jq`

# Exporting detectors using autodetect_tool
autodetect_tool - script that allows you to export detectors from Master Signal Buddy Org into the local content repo and automate some of the required actions:

- extracting import qualifiers(however, you need to review it afterward as API does not support all the scenarios)

- validating the detector: several checks are applied to make sure that the detector has all expected components to be correctly deployed as AutoDetect, including:

    - SF model validation (required for UI)

    - number of rules (autodetect supports only one rule

    - description (must be present as shown in the UI)

    - Dry run

    Requirement to run autodetect_tool
    - pip
    - requests using pip

    ```
    pip install requests
    ```
autodetect_tool has two options for the export: plan and apply

Plan

Identifies all the detectors that should be exported and do all the checks but do not overwrite/add files in your repo

```
python3 autodetect_tool.py --env us0 --access-token <MasterSignalBuddyOrgToken> export plan 
```
Apply

Writes all the detectors that require changes to the files in your local repository

```
python3 autodetect_tool.py --env us0 --access-token <MasterSignalBuddyOrgToken> export apply
```

# Syncing content with **contentforge**

All sync tooling lives under [`contentforge/`](contentforge/README.md).
The CLI is at `contentforge/syncer/cli.py` — a non-interactive tool for pushing local JSON edits
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

The realm is hardcoded in `contentforge/syncer/utils.MASTER_REALM` (currently
`us0`); it is not a config field.

## Five common workflows

### 1. Push all my local changes to Master SignalBuddy

```bash
python -m contentforge.syncer.cli plan
python -m contentforge.syncer.cli apply --yes
```

Plan first, review the JSON output, then apply. The bulk path is
driven by `git diff --name-only HEAD` against `navigators/`, `group/`,
and `detector/`.

### 2. Update one file in master and refresh it locally

```bash
python -m contentforge.syncer.cli update "detector/APM Error Rate Increased.json" --yes
```

Strict update — fails fast if the resource doesn't exist (use
`create` instead). After a successful write the local file is
auto-overwritten with the fresh export so it stays a faithful mirror
of master.

### 3. Create a brand-new resource in master from a local file

```bash
python -m contentforge.syncer.cli create "group/AWS Lambda.json" --yes
```

For groups this uses `POST /v2/dashboardgroup/import`, so the backend
assigns fresh ids and rewires all child charts / dashboards /
crosslinks. The local file is then overwritten with the fresh export
so it now carries the new server-assigned id.

### 4. Refresh a local file from master without pushing anything

```bash
python -m contentforge.syncer.cli pull --type group --id <GROUP_ID> --yes
```

If the id is already present in the repo, the matching local file is
overwritten in place; otherwise the canonical path
(`group/<name>.json` / `detector/<name>.json`) is used. For
navigators without an existing local match, pass
`--out navigators/<category>/<name>.json` explicitly.

### 5. Inspect remote state or preview a local change

```bash
python -m contentforge.syncer.cli fetch detector <DETECTOR_ID>
python -m contentforge.syncer.cli diff   "detector/K8s Node CPU.json"
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

See `contentforge/skills/sync-master-signalbuddy/SKILL.md` for the full reference
(exit codes, error messages, safety rails).
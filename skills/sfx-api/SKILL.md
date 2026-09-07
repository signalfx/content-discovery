---
name: sfx-api
description: Get, export, create, update, or delete SignalFx navigators, detectors, data links, dashboard groups, charts, and dashboards through the Splunk Observability APIs. Use for targeted inspection or maintenance of SFX content objects rather than a full repository synchronization.
---

# SFX API

Use `.venv/bin/python skills/sfx-api/scripts/sfx_api.py` from the repository root. Read [references/object-api.md](references/object-api.md) when choosing a resource name or when export behavior matters.

## Commands

Every resource supports the same five commands:

```bash
.venv/bin/python skills/sfx-api/scripts/sfx_api.py get <resource> <id>
.venv/bin/python skills/sfx-api/scripts/sfx_api.py export <resource> <id> --output export.json
.venv/bin/python skills/sfx-api/scripts/sfx_api.py create <resource> --file request.json --yes
.venv/bin/python skills/sfx-api/scripts/sfx_api.py update <resource> <id> --file request.json --yes
.venv/bin/python skills/sfx-api/scripts/sfx_api.py delete <resource> <id> --yes
```

Resources are `navigator`, `detector`, `datalink`, `dashboard-group`, `chart`, and `dashboard`. `crosslink` aliases `datalink`; `group` aliases `dashboard-group`.

`get` uses the object GET endpoint. `export` uses a dedicated export endpoint when one exists; otherwise it exports the GET representation. Without `--output`, results are returned in the command's JSON response.

## Safety and authentication

- Only run `create`, `update`, or `delete` when the user explicitly requested the remote mutation. These commands require `--yes`.
- Keep verbs strict: never turn a failed update into a create.
- Prefer `SFX_ACCESS_TOKEN`; fall back to `SIGNALBUDDY_TOKEN`, then the repository `.token` file. Never display the token.
- The default endpoint follows the supplied OpenAPI server: `https://api.<realm>.observability.splunkcloud.com/v2`. Use `--realm` or `--base-url` for another target.
- On 401 or 403, stop and report the access failure without exposing credentials.

Create accepts direct request objects and exported content. It extracts the selected object from known export envelopes and removes common server-managed identity and timestamp fields. Update sends the selected object to the explicit command-line ID.

Use `$sync-master-signalbuddy` instead when the request is for the established bulk repository synchronization workflow.

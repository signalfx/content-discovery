# Contentforge

One home for everything that **forges** OOTB content in this repo — sync tooling, bug automation, and agent skills.

```
contentforge/
├── syncer/              # Master SignalBuddy CLI (plan, apply, pull, diff, …)
├── pipeline/            # Slack → JIRA → draft MR automation
├── skills/              # Agent playbooks
├── slack-workflow/      # Test from #test_ai_ootb without merging to master
├── settings.yaml        # Committed defaults (no secrets)
└── config.yaml.example  # Local overrides → copy to config.yaml (gitignored)
```

## Quick start

### Sync JSON to Master SignalBuddy

```bash
python3 -m contentforge.syncer.cli plan
python3 -m contentforge.syncer.cli apply --yes --refresh-local
```

Token: root `.token` file or `SIGNALBUDDY_TOKEN`.

### Bug pipeline (Slack / CI)

```bash
python3 -m contentforge.pipeline.bug_pipeline run --dry-run \
  --input "ootb-bug: K8s Node CPU detector fires at 70% instead of 90%"
```

Full E2E from Slack: [SETUP.md](./SETUP.md) → [slack-workflow/SETUP.md](./slack-workflow/SETUP.md).

### Agent skills

| Skill | Path |
|-------|------|
| SignalBuddy sync | [skills/sync-master-signalbuddy/SKILL.md](./skills/sync-master-signalbuddy/SKILL.md) |
| Bug-report workflow | [skills/bug-report-workflow/SKILL.md](./skills/bug-report-workflow/SKILL.md) |

## Config

```bash
cp contentforge/config.yaml.example contentforge/config.yaml
```

Secrets via env: `JIRA_EMAIL`, `JIRA_API_TOKEN`, `GITLAB_TOKEN`, `SIGNALBUDDY_TOKEN`, `SLACK_BOT_TOKEN`.

## Legacy paths

Old module paths still work via thin shims at repo root:

- `python -m contentforge.syncer.cli` → `contentforge.syncer.cli`
- `python -m contentforge.pipeline.*` → `contentforge.pipeline.*`

Prefer the `contentforge.*` paths in new scripts and CI.

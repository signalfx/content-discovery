# E2E setup — `#test_ai_ootb`

## Start here (no merge to `master` required)

**→ [Slack Workflow setup](./slack-workflow/SETUP.md)**

Post in `#test_ai_ootb`:

```
ootb-bug: K8s Node CPU detector fires at 70% instead of 90%
```

That triggers a pipeline on **`lab`** and replies in the thread with JIRA + MR links.

---

## What happens when you trigger

1. **Immediate reply** in Slack (workflow + optional bot ack from CI)
2. **Repo search** — heuristic match in `navigators/`, `group/`, `detector/`
3. **JIRA** — BITS bug with RCA + affected files
4. **GitLab draft MR** — branch `fix/bits-<KEY>-<date>`
5. **Slack summary** — JIRA link, MR link, pipeline link, suspect file

---

## Quick prerequisites

1. Push automation to **`lab`**
2. GitLab CI variables: `JIRA_EMAIL`, `JIRA_API_TOKEN`, `GITLAB_TOKEN`, `SLACK_BOT_TOKEN`
3. Pipeline trigger token + Slack Workflow ([full guide](./slack-workflow/SETUP.md))
4. Invite bot to `#test_ai_ootb`

---

## Later: production via ChatOps (needs `master` merge)

```
/gitlab subscribe observability/shared/content-discovery
/gitlab run ootb-bug-fix K8s Node CPU detector fires at 70% instead of 90%
```

---

## Local dry-run (no credentials)

```bash
python3 -m contentforge.pipeline.bug_pipeline run --dry-run \
  --input "ootb-bug: K8s Node CPU detector fires at 70% instead of 90%"
```

---

## After the MR is created

1. Fix JSON on the MR branch
2. `python3 -m contentforge.syncer.cli apply --yes --refresh-local`
3. Push; CI validates; optional `sync-signalbuddy` job on MR

See [README.md](./README.md) for command reference.

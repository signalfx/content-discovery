# Content Maintainer setup prerequisites

The setup script validates prerequisites and installs the four-hour Codex
automation. It does not install operating-system tools or Python packages.

## Required tools

- Git
- Python 3 with a repository-local `.venv`
- `jq`
- Codex CLI, logged in with `codex login`
- `glab`, authenticated to `cd.splunkdev.com`
- Codex with local automations and this repository opened as a project

On macOS, install the command-line dependencies and create the Python
environment:

```bash
brew install jq glab
python3 -m venv .venv
.venv/bin/pip install PyYAML requests
glab auth login --hostname cd.splunkdev.com
codex login
```

Ghost CLI and Jira CLI are not required.

## Required service access

- Codex Atlassian connection authenticated to `https://splunk.atlassian.net`
  with access to the configured Jira project and linked Confluence content
- Jira permission to read, comment, and perform the configured `In Progress`,
  `In Review`, and `Ready For Verification` transitions
- GitLab permission to read the content-discovery project, push branches, create
  merge requests, and assign the configured reviewers
- A Master SignalBuddy `us0` token with permission to read, create, update, and
  export supported content objects; remote deletion is not supported

## Required local files

Create and review the ignored local configuration:

```bash
cp configs/content-maintainer.example.yaml configs/content-maintainer.local.yaml
```

Put the Master SignalBuddy token on one line in the ignored repository-root
`.token` file, then restrict access to it:

```bash
chmod 600 .token
```

Do not commit either local file or place credentials in YAML configuration.

## Configure and verify

Open the repository as a local Codex project and configure the Atlassian
connection in Codex. From the repository root, run:

```bash
./tools/scripts/configure-content-maintainer --check-only
./tools/scripts/configure-content-maintainer
```

The first command performs read-only prerequisite checks. The second command
also configures the tracked pre-commit hook and creates or updates one active
`Content Maintainer` Codex automation for this project. The automation runs
every four hours.

Run the setup command again after pulling changes to the repository-owned
automation definition. Local run state and unique logs are stored under
`tools/content-maintainer/.state/` and remain ignored by Git.

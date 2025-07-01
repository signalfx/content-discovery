# Important
Please always export dashboards from SBMO using the `tool` in this repo.
e.g. `./tool export $dashboard_id > group/$your_dashboard_name`
This ensures clean diffs when making pull requests.

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

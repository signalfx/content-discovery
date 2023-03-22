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
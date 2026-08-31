# Splunk Observability OOTB content catalog

This repository is a read-only public mirror of Splunk Observability's
out-of-the-box dashboards, navigators, and detectors. Definitions are mirrored
without modification, including the import qualifiers used to decide whether
content is eligible for import before matching telemetry starts flowing.

## Select a catalog for a realm

Read `catalog-realms.json` from the default branch. Every realm currently uses
the public `master` catalog. The empty `realmOverrides` object keeps the format
forward-compatible if a realm-specific public catalog is introduced later.

The catalog is available without a Splunk-internal token:

```text
https://github.com/splunk/content-discovery/tree/master/group
https://github.com/splunk/content-discovery/tree/master/navigators
https://github.com/splunk/content-discovery/tree/master/detector
```

Machine clients can read individual files through GitHub's unauthenticated raw
content URLs under
`https://raw.githubusercontent.com/splunk/content-discovery/master/...`.

Only catalog data and this public metadata are mirrored. Internal CI,
credentials, service configuration, scripts, and operational documentation are
excluded from every commit in the public repository's history.

Public commits are generated snapshots. Their author, committer, message, and
timestamp are fixed publication metadata; internal Git authors, email
addresses, commit messages, merge-request links, and commit identifiers are not
copied to GitHub.

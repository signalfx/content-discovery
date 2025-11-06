# Release Notes Generation from Master Branch

## Overview

The release notes are generated from the last 50 commits to the `master` branch. Each commit that modifies content files becomes a version entry in the release notes.

## ⚠️ Important: Release Notes Validation

**All changed content files MUST be documented in release notes.** The CI/CD pipeline will **fail** if:

- Content files in `detector/`, `navigators/`, or `group/` are modified
- Those files are NOT listed in `content_release_notes.yaml`

This ensures all changes are properly documented before deployment.

## Version Format

Versions follow **Semantic Versioning** (SemVer):

- **Format**: `MAJOR.MINOR.PATCH`
- **Example**: `2.1.5`

Version increments:

- **MAJOR** (x.0.0): Breaking changes
- **MINOR** (0.x.0): New features, non-breaking changes
- **PATCH** (0.0.x): Bug fixes, minor updates

## How It Works

### 1. Commit Detection

```bash
git log master -50 -- detector/ navigators/ group/
```

### 2. File Changes

For each commit, the script analyzes:

- Which content files were modified
- The git diff for each file
- Content name and category (detector/navigator/dashboard_group)

### 3. AI Analysis

Uses Bridge IT API (GPT-4.1) to:

- Analyze commit message and diffs
- Classify change type
- Generate professional, user-friendly descriptions
- Detect breaking changes
- Suggest version increment (major/minor/patch)

### 4. YAML Structure

### 4. YAML Structure (Public-Facing)

```yaml
versions:
  "2.0.0":
    date: "2025-11-06"
    files:
      - name: "K8s Cluster DaemonSet"
        category: "detector"
        description: "Updated metric query from container.cpu.time to container.cpu.utilization"
        change_type: "metric_changed"
        breaking_change: true
        files_modified:
          - detector/K8S Cluster DaemonSet.json
      - name: "Kubernetes"
        category: "navigator"
        description: "Replaced legacy CPU metrics with OTel-native metric names"
        change_type: "metric_changed"
        breaking_change: true
        files_modified:
          - navigators/Kubernetes/kubernetes.json

  "1.2.5":
    date: "2025-11-05"
    files:
      - name: "Data center host - Memory utilization"
        category: "detector"
        description: "Corrected memory percentage calculation to prevent false positive alerts"
        change_type: "bug_fix"
        breaking_change: false
        files_modified:
          - detector/Memory utilization.json
```

**Note**: No commit hashes or internal details are included - this is public release documentation.

## Running Manually

### Generate Release Notes:

```bash
python scripts/generate_release_notes_from_master.py
```

### Validate Release Notes Coverage:

```bash
python scripts/validate_release_notes.py
```

This checks that all changed content files are documented in release notes.

### Configure number of commits:

Edit `NUM_COMMITS` in the script:

```python
NUM_COMMITS = 50  # Change to desired number
```

## Pre-Commit Hook

The hook automatically runs when you commit content changes:

1. **Validates content files** (IDs, hashCodes)
2. **Generates release notes** from master branch
3. **Adds `content_release_notes.yaml`** to the commit

**Disable for a specific commit:**

```bash
git commit --no-verify
```

## Pipeline Validation

The GitLab CI/CD pipeline includes a **`validate-release-notes`** job that:

1. **Runs on**: Master branch pushes and merge requests
2. **Checks**: All changed content files are documented in release notes
3. **Fails**: If any changed file is missing from release notes
4. **Fix**: Run `python scripts/generate_release_notes_from_master.py` and commit

This ensures **no undocumented changes** reach production.

## CI/CD Integration

### GitLab Pipeline

The script uses the same environment variables as validation:

- `BRIDGE_API_CLIENT_ID`
- `BRIDGE_API_CLIENT_SECRET`
- `BRIDGE_API_APP_KEY`

Set these in: **Settings → CI/CD → Variables**

### Example Pipeline Stage

```yaml
generate-changelog:
  stage: build
  script:
    - python scripts/generate_changelog_from_master.py
  artifacts:
    paths:
      - content_changelog.yaml
  only:
    - master
```

## Changelog Categories

Files are automatically categorized:

| Folder        | Category          | Description                   |
| ------------- | ----------------- | ----------------------------- |
| `detector/`   | `detector`        | Alert/Detector configuration  |
| `navigators/` | `navigator`       | Navigator configuration       |
| `group/`      | `dashboard_group` | Dashboard group configuration |

## Change Types

AI classifies changes into:

- `created` - New content
- `updated` - General updates
- `metric_changed` - Metric query changes
- `visualization_changed` - Chart/dashboard updates
- `metadata_changed` - Metadata updates
- `detector_rule_changed` - Detector rule changes
- `deprecated` - Deprecated content
- `deleted` - Removed content
- `migrated` - Migration (e.g., SignalFx → OTel)
- `bug_fix` - Bug fixes
- `performance_improvement` - Performance optimizations

## Benefits

✅ **Automated** - Runs on every commit to master  
✅ **Semantic Versioning** - Professional version numbering  
✅ **AI-powered** - Intelligent, user-friendly descriptions  
✅ **Public-ready** - No internal commit details exposed  
✅ **Release documentation** - Suitable for public docs and release notes

## Troubleshooting

### No commits found

```bash
# Check if on correct branch
git branch

# Fetch latest from master
git fetch origin master
```

### API rate limiting

Reduce `NUM_COMMITS` or add delays:

```python
time.sleep(1)  # Increase delay between requests
```

### Large diffs

Diff size is limited to 2000 chars per file. Adjust in script:

```python
return result.stdout[:2000]  # Increase limit
```

## Migration from Old Format

To convert existing file-based changelog to commit-based:

```bash
# Backup current changelog
cp content_changelog.yaml content_changelog.yaml.backup

# Generate new format
python scripts/generate_changelog_from_master.py
```

The new format is incompatible with the old file-based format. Choose one approach for your project.

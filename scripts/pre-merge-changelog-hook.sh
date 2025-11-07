#!/bin/bash
# Pre-merge hook to automatically generate changelog for feature branch
# 
# Usage (in git hooks):
#   ln -s ../../scripts/pre-merge-changelog-hook.sh .git/hooks/pre-push
#
# Or run manually before creating MR:
#   ./scripts/pre-merge-changelog-hook.sh

set -e

# Get current branch
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)

# Skip if on master
if [ "$CURRENT_BRANCH" = "master" ] || [ "$CURRENT_BRANCH" = "main" ]; then
    echo "✓ On master branch, skipping changelog generation"
    exit 0
fi

# Check if there are content changes
CONTENT_CHANGES=$(git diff --name-only master...HEAD -- detector/ navigators/ group/ 2>/dev/null | grep -c '\.json$' || true)

if [ "$CONTENT_CHANGES" -eq 0 ]; then
    echo "✓ No content changes detected, skipping changelog generation"
    exit 0
fi

echo "================================================"
echo "  Content changes detected in feature branch"
echo "  Generating changelog entry..."
echo "================================================"

# Load environment variables if env file exists
if [ -f "scripts/env.env" ]; then
    export $(cat scripts/env.env | xargs)
fi

# Run the changelog generator
python scripts/generate_changelog_for_branch.py

# Check if changelog was modified
if git diff --quiet content_changelog.yaml CHANGELOG.md; then
    echo ""
    echo "⚠ Changelog files were not updated"
    exit 0
fi

echo ""
echo "================================================"
echo "  Changelog files updated!"
echo "================================================"
echo ""
echo "The following files have been modified:"
echo "  - content_changelog.yaml"
echo "  - CHANGELOG.md"
echo ""
echo "Please review the changes and commit them:"
echo "  git add content_changelog.yaml CHANGELOG.md"
echo "  git commit -m 'Update changelog for branch changes'"
echo ""

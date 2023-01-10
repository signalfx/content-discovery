#!/bin/bash

# validate content json files for navigators/groups/detectors.
# Ensure that the content ids haven't changed. We want to prevent that situation as it can cause issues
# with existing content if it gets deployed, and requires remediation against production realms.

CONTENT_DIRECTORIES="group|navigators|detector"
VALIDATION_FAILED=false

DIFF_BRANCH=HEAD^ # default to diffing against local committed (cached) files

echo "Validating content files."

# if running in gitlab ci, diff against the MR's target branch
if [ -n "${CI_MR_TARGET_BRANCH+set}" ]; then
  echo "Running in CI against branch: $CI_MR_TARGET_BRANCH"

  # need to explicitly fetch the target branch as gitlab only does a shallow clone of the MR's branch
  git fetch origin $CI_MR_TARGET_BRANCH

  DIFF_BRANCH=origin/$CI_MR_TARGET_BRANCH
fi

# go through changed git files and check for any content with modified Ids
while read file; do

  # only run on json files
  extension=${file: -5}
  case $extension in
  .json)
    echo -n "validating $file "

    # retrieve the json id from the content
    set -e # fail if any json parse errors

    # get the id from the current version and the previous version in git
    if [[ $file =~ ^navigators ]]; then
      id=$(jq -r '.navigatorExport.navigator.id' "$file")
      id_prev=$(git show "$DIFF_BRANCH:$file" | jq -r '.navigatorExport.navigator.id')
    elif [[ $file =~ ^group ]]; then
      id=$(jq -r '.groupExport.group.id' "$file")
      id_prev=$(git show "$DIFF_BRANCH:$file" | jq -r '.groupExport.group.id')
    elif [[ $file =~ ^detector ]]; then
      id=$(jq -r '.detectorExport.detector.id' "$file")
      id_prev=$(git show "$DIFF_BRANCH:$file" | jq -r '.detectorExport.detector.id')
    fi

    set +e

    # check if the id has changed from the previous git version
    if [ "$id" != "null" ] && [ "$id" != "$id_prev" ]; then
      echo
      echo "  ERROR: Id has changed in $file: \"$id\" (previous id: \"$id_prev\"); navigator/group/detector ids should be immutable. Please correct."
      VALIDATION_FAILED=true
    else
      echo " ... success"
    fi

    ;;

  *)
    # ignore any non-json files
    echo "ignoring: $file "
    ;;
  esac
done < <(git diff $DIFF_BRANCH --name-only --diff-filter=M | grep -E "^($CONTENT_DIRECTORIES)/") # get paths of modified files only

if [ $VALIDATION_FAILED == true ]; then
  echo
  echo "Errors found; validation failed"
  exit 1
fi

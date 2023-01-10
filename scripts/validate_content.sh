#!/bin/bash

# validate content json files for navigators/groups/detectors.
# Ensure that the content ids haven't changed. We want to prevent that situation as it can cause issues
# with existing content if it gets deployed, and requires remediation against production realms.

CONTENT_DIRECTORIES="group|navigators|detector"
VALIDATION_FAILED=false

DIFF_BRANCH=--cached # default to diffing against local committed (cached) files

if [ -n "${CI_MR_TARGET_BRANCH+set}" ]; then
  echo "Running in CI against branch: $CI_MR_TARGET_BRANCH"
  git fetch origin $CI_MR_TARGET_BRANCH

  # on gitlab ci, diff the current (MR) branch against the origin branch that will be merged to
  DIFF_BRANCH=origin/$CI_MR_TARGET_BRANCH
fi

echo "Validating content files."

# go through changed git files and check for any content with modified Ids
while read file; do

  # only run on json files
  extension=${file: -5}
  case $extension in
  .json)
    echo -n "validating $file "

    # retrieve the json id from the content
    set -e # fail if any json parse errors

    if [[ $file =~ ^navigators ]]; then
      id=$(jq -r '.navigatorExport.navigator.id' "$file")
    elif [[ $file =~ ^group ]]; then
      id=$(jq -r '.groupExport.group.id' "$file")
    elif [[ $file =~ ^detector ]]; then
      id=$(jq -r '.detectorExport.detector.id' "$file")
    fi

    set +e

    if [ "$id" != "null" ]; then
      # check the file's git diff to see if the content id was changed.
      # Note: use word-diff and grep for leading "-...+" to detect modifications only (subtraction + addition), and ignore newly added files.
      ID_CHANGED=$(git diff $DIFF_BRANCH --word-diff --unified=0 "$file" | grep -c -e "-.*+.*\"$id\"")
      if [ "$ID_CHANGED" -ge 1 ]; then
        echo
        echo "  ERROR: Id has changed in $file: \"$id\"; navigator/group/detector ids should be immutable. Please correct."
        VALIDATION_FAILED=true
      else
        echo " ... success"
      fi
    fi

    ;;

  *)
    # ignore any non-json files
    echo "ignoring: $file "
    ;;
  esac
done < <(git diff $DIFF_BRANCH --name-only | grep -E "^($CONTENT_DIRECTORIES)/")

if [ $VALIDATION_FAILED == true ]; then
  echo
  echo "Errors found; validation failed"
  exit 1
fi

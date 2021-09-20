# Scripts


### Apply Navigator Categories & Navigator Category Groups to Navigator (apply_navigator_categories.py)

Although the JSON files stored in `navigatorCategories` and `navigatorCategoryGroups` should be considered as the single source of truth, there will be no actual effect until the data is disseminated to individual navigators through this script.

This script shortcuts the process described in [this wiki page](https://signalfuse.atlassian.net/wiki/spaces/APPS/pages/669220923/Updating+built-in+content+managed+by+Signalbuddy). As a result, you only need to follow these steps to update `navigatorCategory` or `navigatorCategoryGroup`.

1. Make changes in JSON files under `navigatorCategory` or `navigatorCategoryGroup` directory.
2. Run this script.
```
./apply_navigator_categories.py [Signalbuddy Master Org USER_TOKEN]
```
3. Test it in lab (Step 7~8 in the [wiki](https://signalfuse.atlassian.net/wiki/spaces/APPS/pages/669220923/Updating+built-in+content+managed+by+Signalbuddy))
4. Create PR to master (Step 9)


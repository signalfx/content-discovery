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

### BridgeIT content validation (validate_bridgeit_content.mjs)

This script validates any added/changed content (specifically, navigators and dashboard groups) using BridgeIT. It will send an API request to the BridgeIT API to search for typographical/semantic issues in the changed content, and will exit with a non-zero status code if any such potential issues are found. Files that are unchanged are not analyzed.

This script runs automatically as part of the Gitlab pipeline when an MR is created/updated. It is non-blocking, meaning it will not prevent the MR from being merged in case potential issues are found (to avoid blocking in case of hallucinations).

Variables that must be set in Gitlab CI/CD settings for the repo for this to work:

- ```BRIDGE_API_CLIENT_ID```: The client ID for the BridgeIT API.
- ```BRIDGE_API_CLIENT_SECRET```: The client secret for the BridgeIT API.
- ```BRIDGE_API_APP_KEY```: The app key for the BridgeIT API.
- (optional) ```BRIDGE_API_MODEL_NAME```: The AI model to use for validation. Defaults to "gpt-4.1". For list of available models, see: https://cisco.sharepoint.com/:w:/r/sites/BridgeIT/Shared%20Documents/API%20Docs%20-%20GPT.docx?d=w0b9f9bbd876b4c70a1897954d24f57bd&csf=1&web=1&e=AczLhG
- (optional) ```BRIDGE_API_TEMPERATURE```: The temperature for the AI model. Defaults to 1.
- (optional) ```BRIDGE_API_TOP_P```: The top_p for the AI model. Defaults to 0.25.

When running locally, you can set these variables in your environment or pass them as command line arguments. For example:

```EXPORT BRIDGE_API_CLIENT_ID=client_id```
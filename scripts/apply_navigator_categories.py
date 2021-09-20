#!/usr/bin/env python3
import sys
import os
import json
import requests

user_token = None
navigators = {}
navigator_path = {}

def get_navigator(navigator_id):
    response = requests.get(f"https://app.signalfx.com/v2/navigator/{navigator_id}", headers={"X-SF-TOKEN": user_token, "Accept": "application/json"})
    if response.status_code != 200:
        raise RuntimeError(f"Failed to fetch navigator {navigator_id}: {response.text}")
    return response.text

def get_navigator_export(navigator_id):
    response = requests.get(f"https://app.signalfx.com/v2/navigator/{navigator_id}/export", headers={"X-SF-TOKEN": user_token, "Accept": "application/json"})
    if response.status_code != 200:
        raise RuntimeError(f"Failed to fetch navigator export {navigator_id}: {response.text}")
    return response.text

def collect_src_files():
    src = []
    for dir, _, files in os.walk("../navigatorCategoryGroups"):
        for filename in files:
            if filename.endswith('.json'):
                src.append(os.path.abspath(os.path.join(dir, filename)))
    for dir, _, files in os.walk("../navigatorCategories"):
        for filename in files:
            if filename.endswith('.json'):
                src.append(os.path.abspath(os.path.join(dir, filename)))
    return src

def collect_nav_files():
    dest = []
    for dir, _, files in os.walk("../navigators"):
        for filename in files:
            if filename.endswith('.json'):
                dest.append(os.path.abspath(os.path.join(dir, filename)))
    return dest

def apply(src, navs):
    for src_path in src:
        src_f = open(src_path, "r")
        src_data = json.loads(src_f.read())
        src_content = src_data["content"]
        src_filters = src_data["filters"]

        for nav_path in navs:
            nav_f = open(nav_path, "r")
            nav_data = json.loads(nav_f.read())
            navigator = nav_data["navigatorExport"]["navigator"]
            nav_id = nav_data["id"]
            navigator_path[nav_id] = nav_path
            
            # Check if the navigator should be updated
            for filter in src_filters:
                match_filter = False
                for filter_key in filter.keys():
                    if filter_key not in navigator or navigator[filter_key] != filter[filter_key]:
                        break
                else:
                    match_filter = True
                if match_filter:
                    break
            else:
                # No matching filter. Skip the navigator
                continue
            nav_f.close()
            
            # Create a temp navigator if not exist yet
            if nav_id not in navigators:
                navigators[nav_id] = json.loads(get_navigator(nav_id))

            # Modify navigator obj
            for content_key in src_content.keys():
                navigators[nav_id][content_key] = src_content[content_key]

def put_navigator(navigator):
    response = requests.put(f"https://app.signalfx.com/v2/navigator/{navigator['id']}", headers={"X-SF-TOKEN": user_token, "Content-Type": "application/json"}, data=json.dumps(navigator))
    if response.status_code != 200:
        raise RuntimeError(f"Failed to save navigator {navigator['id']}: {response.text}")
    return response.text

def save_signalbuddy_org():
    for navigator_id in navigators.keys():
        put_navigator(navigators[navigator_id])
        exported = get_navigator_export(navigator_id)
        dest_f = open(navigator_path[navigator_id], "w")
        dest_f.write(exported)
        dest_f.close()

def main():    
    src = collect_src_files()
    navs = collect_nav_files()
    apply(src, navs)
    save_signalbuddy_org()
    return 0
if __name__ == "__main__":
    if len(sys.argv) >= 2:
        user_token = sys.argv[1]
        sys.exit(main())
    print("User token is missing")
    
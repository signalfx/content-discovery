import json
import os


def collect_nav_files():
    dest_list = []
    for dir, _, files in os.walk("navigators/"):
        for filename in files:
            if filename.endswith('.json'):
                dest_list.append(os.path.abspath(os.path.join(dir, filename)))
    return dest_list


def collect_nav_name_desc_and_type(dest_list):
    """

    """
    nav_collections = []
    for dest_path in dest_list:
        with open(dest_path, 'r') as nav_file:
            data = json.load(nav_file)
            nav_collections.append({
                # 'name': data['navigatorExport']['navigator]['name'],
                'name': data['navigatorExport']['navigator']['uiModel']['displayName'],
                'unreleased': data['navigatorExport']['navigator']['uiModel']['unreleased']
            })
    return nav_collections


def write_readmemd_file():
    """

    """
    nav_files = collect_nav_files()
    nav_list = collect_nav_name_desc_and_type(nav_files)
    with open("test_readme.md", 'w') as readme:
        readme.write("## Navigators\n")
        readme.write("| Name | Is available for Customer? |\n")
        readme.write("| ------- | --- |\n")
        for nav in nav_list:
            is_available = "No" if nav.get('unreleased') else "Yes"
            nav_name = nav.get('name')
            readme.write(f"| {nav_name} | {is_available} |\n")


write_readmemd_file()

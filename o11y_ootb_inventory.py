import json
import gspread
import argparse
import base64
import os
import requests

from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials
from dateutil import parser

NAVIGATOR_EXCLUDE_LIST = ['Pods', 'Containers', 'Nodes']
GITLAB_COMMIT_URL = "https://cd.splunkdev.com/api/v4/projects/9336/repository/commits"
INVENTORY_G_SHEET_NAME = "O11y Out of the Box Inventory Test"
G_SHEET_CONTENT = {
    'navigator':
        {
            'gsheet_name': 'Navigators',
            'area': 'A2:E500'
        },
    'dashboard':
        {
            'gsheet_name': 'Dashboards',
            'area': 'A2:C500'
        },
    'detector':
        {
            'gsheet_name': 'Detectors',
            'area': 'A2:C500'
        },

}
PI_DATE_RANGE = {
        'FY22PI4': ['09-11-2021', '07-02-2022'],
        'FY23PI1': ['08-02-2022', '16-05-2022'],
        'FY23PI2': ['17-05-2022', '11-08-2022'],
        'FY23PI3': ['12-08-2022', '13-11-2022'],
        'FY23PI4': ['14-11-2022', '06-02-2023'],
        'FY24PI1': ['07-02-2023', '02-05-2023'],
        'FY24PI2': ['03-05-2023', '25-07-2023'],
        'FY24PI3': ['26-07-2023', '31-10-2023'],
        'FY24PI4': ['01-11-2023', '23-01-2024']
    }


def collect_json_files(path):
    dest_list = []
    if path == "navigators/":
        for dir, _, files in os.walk(path):
            for filename in files:
                if filename.endswith('.json'):
                    with open(os.path.abspath(os.path.join(dir, filename))) as file:
                        nav_json = json.load(file)
                        nav_json = nav_json['navigatorExport']['navigator']
                        keys = nav_json['uiModel'].keys()
                        # To ignore the navigators with architectural type, and navigators with no Name(not getting displayed) and navigators with name "Nodes", "Pods", and "Containers" (Because older version file is also present in the repo and we have to ignore those) and ignore navigators with sites = "signalview" and ignored navigators that are unreleased
                        if 'o11yProductName' in keys and (nav_json['navigatorType'] != 'architectural') and \
                                nav_json['uiModel']['o11yProductName'] is not None and (
                                nav_json['uiModel']['o11yProductName'] not in NAVIGATOR_EXCLUDE_LIST) and (
                                nav_json['sites'] != "signalview") and (not nav_json['uiModel']['unreleased']):
                            dest_list.append(os.path.abspath(os.path.join(dir, filename)))

    elif path == "group/" or path == "detector/":
        for dir, _, files in os.walk(path):
            for filename in files:
                if filename.endswith('.json'):
                    dest_list.append(os.path.abspath(os.path.join(dir, filename)))
    return dest_list


def prepare_import_qualifiers(nav_import_qualifiers):
    """
    Format
    [metric name] ([propertyName] [propertyOperation = or !=] propertyValue|propertyValue|propertyValue);
    [metric name] (propertyName [propertyOperation] propertyValue);
    """
    # Handle or add "and" "or" words and add "*" if null in values

    str_import_qualifiers = ""
    dummy_import_qualifiers = ""
    # To get the importQualifier
    for import_qualifier in nav_import_qualifiers:
        str_import_qualifiers += import_qualifier['metric'] + " "
        # To get the filters
        for value_property in import_qualifier.get('filters'):
            # Checking if 'property' property exist in filters block, if not '(*)' will be added in L-77
            if 'property' in value_property.keys():
                # Adding property value if exist, else '*' (asterisk)
                str_import_qualifiers += "(" + (
                    value_property.get('property') if value_property.get('property') != "" else "*")
                # If no property value exist, ending the current iteration with ') &'
                if str_import_qualifiers[-1] == '*':
                    str_import_qualifiers += ") & "
                    continue
                # Property operation {"not": false} will be considered as = and {"not": true} will be considered as !=
                prop_operation = " != " if value_property["not"] else " = "
                str_import_qualifiers += prop_operation + " "

                # To get the list of values appended with | (pipe)
                list_values = ""
                for prop_value in value_property.get('values'):
                    list_values += prop_value + " | "
                # Check if the list_values is null, replace it with *
                if list_values == "":
                    list_values = "*"
                # Check if the list_value is not null, remove the extra '|' (pipe)
                else:
                    list_values = list_values[:-3]
                # Adding ') &' at last, '&' will be removed in L-81
                str_import_qualifiers += list_values + ") & "

        # If 'property' property doesn't exist
        if str_import_qualifiers == dummy_import_qualifiers + import_qualifier['metric'] + " ":
            str_import_qualifiers += "(*)"
        else:
            # To remove last '&' symbol with one or multiple filter values
            str_import_qualifiers = str_import_qualifiers[:-3]
        str_import_qualifiers += ";  OR\n"
        dummy_import_qualifiers = str_import_qualifiers
    # To remove last line "  OR\n" in the string as it get appended at L-82
    str_import_qualifiers = str_import_qualifiers[:-5]
    return str_import_qualifiers


def sort_list(content_list):
    """

    """
    return sorted(content_list, key=lambda x: x[0].lower())


def write_to_gsheet_file(content_type, data_list, creds):
    """

    """
    file = gspread.authorize(creds)
    workbook = file.open(INVENTORY_G_SHEET_NAME)

    gsheet_info = G_SHEET_CONTENT[content_type]
    sheet = workbook.worksheet(gsheet_info['gsheet_name'])

    # Clearing the Cells
    sheet.batch_clear([gsheet_info['area']])

    # Sort the list alphabetically
    data_list = sort_list(data_list)

    # Writing into GSheet
    sheet.update(gsheet_info['area'], data_list)


def get_date_range(date):
    """

    """
    # Function to check which date range a given date falls into
    for key, date_range in PI_DATE_RANGE.items():
        start_date = datetime.strptime(date_range[0], '%d-%m-%Y').date()
        end_date = datetime.strptime(date_range[1], '%d-%m-%Y').date()
        check_date = datetime.strptime(date, '%d-%m-%Y').date()
        if start_date <= check_date <= end_date:
            return key

    # If respective PI not found then return the actual date
    return "Before FY22PI4"


def get_file_creation_date(file_path):
    """

    """
    file_path = file_path.split('content-discovery/')[1]
    query_params = {
        "ref_name": "master",
        "per_page": 100,
        "order_by": "committed_date",
        "all": False,
        "path": file_path
    }
    headers = {
        # todo: move to gitlab variable
        'PRIVATE-TOKEN': 'Qg7nVHEPjwsE3GsGMzFr'
    }
    response = requests.request("GET", GITLAB_COMMIT_URL, headers=headers, params=query_params)
    print(len(response.json()), f"commits for file: {file_path}")
    print(response.json())
    if len(response.json()) > 0:
        commit_list = response.json()[-1]
        commit_date = parser.parse(commit_list.get('committed_date')).strftime('%d-%m-%Y')
        print(f"This file:{file_path}'s creation date: {commit_date}")
        return commit_date
    else:
        print(f"Unexpected error while fetching {file_path} creation date")


def collect_content_name_import_qualifiers_category_and_group(dest_list):
    """

    """
    collections = []

    for dest_path in dest_list:
        with open(dest_path, 'r') as nav_file:
            data = json.load(nav_file)
            release_date = get_file_creation_date(file_path=dest_path)
            release_pi = get_date_range(release_date)
            if 'content-discovery/navigators/' in dest_path:
                nav_json = data['navigatorExport']['navigator']
                collections.append([
                    nav_json['uiModel']['o11yProductName'],
                    prepare_import_qualifiers(nav_json['importQualifiers']),
                    nav_json.get('navigatorCategory') if nav_json.get('navigatorCategory') is not None else "Others",
                    nav_json.get('navigatorCategoryGroupDisplayName') if nav_json.get(
                        'navigatorCategoryGroupDisplayName') is not None else "Others",
                    release_pi
                ])
            elif 'content-discovery/group/' in dest_path:
                collections.append([
                    data['groupExport']['group']['name'],
                    prepare_import_qualifiers(data['groupExport']['group']['importQualifiers']),
                    release_pi
                ])
            elif 'content-discovery/detector/' in dest_path:
                collections.append([
                    data['detectorExport']['detector']['name'],
                    prepare_import_qualifiers(data['detectorExport']['detector']['importQualifiers']),
                    release_pi
                ])
            else:
                break
    return collections


def parse_args():
    """

  """
    parser = argparse.ArgumentParser()
    parser.add_argument("-pki", "--private_key_id", help="Service account's private key id")
    parser.add_argument("-pk", "--private_key", help="Service account's private key")
    parser.add_argument("-ci", "--client_id", help="Service account's client id")
    parser.add_argument("-ce", "--client_email", help="Service account's client email")
    parser.add_argument("-pi", "--project_id", help="Service account's project id")
    args = parser.parse_args()
    return args


def get_credentials():
    """

  """
    args = parse_args()
    cred_file = json.load(open('credentials.json'))
    cred_file["private_key_id"] = args.private_key_id

    # Decode the base64 encoded private key
    encoded_private_key = args.private_key
    decoded_private_key = base64.b64decode(encoded_private_key).decode('utf-8')

    cred_file["private_key"] = decoded_private_key.replace("\\n", "\n")
    cred_file["client_email"] = args.client_email
    cred_file["client_id"] = args.client_id
    cred_file["project_id"] = args.project_id
    return cred_file


def main():
    """

    """
    cred_file = get_credentials()
    creds = ServiceAccountCredentials.from_json_keyfile_dict(cred_file)

    nav_files = collect_json_files("navigators/")
    nav_list = collect_content_name_import_qualifiers_category_and_group(nav_files)
    print(nav_list)
    write_to_gsheet_file("navigator", nav_list, creds)

    db_files = collect_json_files("group/")
    db_list = collect_content_name_import_qualifiers_category_and_group(db_files)
    print(db_list)
    write_to_gsheet_file("dashboard", db_list, creds)

    dt_files = collect_json_files("detector/")
    dt_list = collect_content_name_import_qualifiers_category_and_group(dt_files)
    print(dt_list)
    write_to_gsheet_file("detector", dt_list, creds)


if __name__ == "__main__":
    main()

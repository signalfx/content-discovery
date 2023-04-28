import json
import gspread
import argparse
import base64
import os
import requests

from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials
from dateutil import parser


class GitlabInventory:
    """
    Class is used to have methods related to cicd pipeline for gsheet inventory update.
    """
    # This variable is set in GitLab CICD variable using user:"bkanzariya" gitlab account to
    # make gitlab file meta-data api calls to get the file creation data.
    GITLAB_API_PRIVATE_TOKEN = ""

    GITLAB_COMMIT_URL = "https://cd.splunkdev.com/api/v4/projects/9336/repository/files/{}/blame"
    NAVIGATOR_EXCLUDE_LIST = ['Pods', 'Containers', 'Nodes']

    # Todo: While 2-3 interation of testing will keep this beta spreadsheet and after
    #  that will update the actual spreadsheet
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
    INVENTORY_CONTENTS = [{"path": "navigators/", "content_type": "navigator"},
                          {"path": "group/", "content_type": "dashboard"},
                          {"path": "detector/", "content_type": "detector"}]

    @classmethod
    def collect_json_files(cls, path):
        """
        Collect all list of json files based on given path.
        """
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
                                    nav_json['uiModel']['o11yProductName'] not in cls.NAVIGATOR_EXCLUDE_LIST) and (
                                    nav_json['sites'] != "signalview") and (not nav_json['uiModel']['unreleased']):
                                dest_list.append(os.path.abspath(os.path.join(dir, filename)))

        elif path == "group/" or path == "detector/":
            for dir, _, files in os.walk(path):
                for filename in files:
                    if filename.endswith('.json'):
                        dest_list.append(os.path.abspath(os.path.join(dir, filename)))
        return dest_list

    @classmethod
    def prepare_import_qualifiers(cls, nav_import_qualifiers):
        """
        To prepare the ImportQualifier in the below given format.
        Format:
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

    @classmethod
    def sort_list(cls, content_list):
        """
        To sort the content list based on list's first element(content name).
        """
        return sorted(content_list, key=lambda x: x[0].lower())

    @classmethod
    def write_to_gsheet_file(cls, content_type, data_list, creds):
        """
        Helper method to write the content on google spread sheet.
        """
        file = gspread.authorize(creds)
        workbook = file.open(cls.INVENTORY_G_SHEET_NAME)

        gsheet_info = cls.G_SHEET_CONTENT[content_type]
        sheet = workbook.worksheet(gsheet_info['gsheet_name'])

        # Clearing the Cells
        sheet.batch_clear([gsheet_info['area']])

        # Sort the list alphabetically
        data_list = cls.sort_list(data_list)

        # Writing into GSheet
        sheet.update(gsheet_info['area'], data_list)

    @classmethod
    def get_pi_from_date(cls, date):
        """
        To get the PI based on given date.
        """
        check_date = datetime.strptime(date, '%d-%m-%Y').date()
        total_len_pi_range = len(list(cls.PI_DATE_RANGE.items()))

        # To retrieve very 1st date and PI name from PI_DATE_RANGE mapping list
        very_first_date = datetime.strptime(list(cls.PI_DATE_RANGE.items())[0][1][0], '%d-%m-%Y').date()
        very_first_pi = list(cls.PI_DATE_RANGE.items())[0][0]

        # To retrieve very last date and PI name from PI_DATE_RANGE mapping list
        vert_last_date = datetime.strptime(list(cls.PI_DATE_RANGE.items())[total_len_pi_range-1][1][0], '%d-%m-%Y').date()
        very_last_pi = list(cls.PI_DATE_RANGE.items())[total_len_pi_range-1][0]

        # Function to check which date range a given date falls into
        for key, date_range in cls.PI_DATE_RANGE.items():
            start_date = datetime.strptime(date_range[0], '%d-%m-%Y').date()
            end_date = datetime.strptime(date_range[1], '%d-%m-%Y').date()
            if start_date <= check_date <= end_date:
                return key

        # If the date is before the very_first_date from PI_DATE_RANGE mapping
        if check_date < very_first_date:
            return f'Before {very_first_pi}'

        # If the date is greater than the very_last_date from PI_DATE_RANGE mapping
        elif check_date > vert_last_date:
            return f'After {very_last_pi}'

        else:
            print(f"Unexpected case occurred while get_pi_from_date for date:{check_date}")
            return date

    @classmethod
    def get_file_creation_date(cls, file_path):
        """
        To get the file creation date for the content JSON file.
        """
        file_path = file_path.split('content-discovery/')[1]
        url_encode_path = requests.utils.quote(file_path, safe="")

        # If you add the order_by: committed_date parameter to your API request, the API will return the
        # commit history sorted by the commit date in ascending order (i.e., oldest commit first).
        query_params = {
            "ref": "master",
            "order_by": "committed_date",
        }
        headers = {
            'PRIVATE-TOKEN': cls.GITLAB_API_PRIVATE_TOKEN
        }
        response = requests.request("GET", cls.GITLAB_COMMIT_URL.format(url_encode_path), headers=headers,
                                    params=query_params)
        if len(response.json()) > 0:
            commit_list = response.json()[0]
            commit_date = parser.parse(commit_list.get('commit').get('committed_date')).strftime('%d-%m-%Y')
            print(f"File:{file_path}'s creation date: {commit_date}")
            return commit_date
        print(f"Unexpected error while fetching {file_path} creation date and response: {response.json()}")

    @classmethod
    def collect_inventory_data(cls, dest_list):
        """
        Helper method to get the OOTB's inventory data.
        """
        collections = []

        for dest_path in dest_list:
            with open(dest_path, 'r') as nav_file:
                data = json.load(nav_file)
                release_date = cls.get_file_creation_date(file_path=dest_path)
                release_pi = cls.get_pi_from_date(release_date)
                if 'content-discovery/navigators/' in dest_path:
                    nav_json = data['navigatorExport']['navigator']
                    collections.append([
                        nav_json['uiModel']['o11yProductName'],
                        cls.prepare_import_qualifiers(nav_json['importQualifiers']),
                        nav_json.get('navigatorCategory') if nav_json.get(
                            'navigatorCategory') is not None else "Others",
                        nav_json.get('navigatorCategoryGroupDisplayName') if nav_json.get(
                            'navigatorCategoryGroupDisplayName') is not None else "Others",
                        release_pi
                    ])
                elif 'content-discovery/group/' in dest_path:
                    collections.append([
                        data['groupExport']['group']['name'],
                        cls.prepare_import_qualifiers(data['groupExport']['group']['importQualifiers']),
                        release_pi
                    ])
                elif 'content-discovery/detector/' in dest_path:
                    collections.append([
                        data['detectorExport']['detector']['name'],
                        cls.prepare_import_qualifiers(data['detectorExport']['detector']['importQualifiers']),
                        release_pi
                    ])
                else:
                    break
        return collections

    @staticmethod
    def parse_args():
        """
        To prepare argument parser.
        """
        parser = argparse.ArgumentParser()
        parser.add_argument("-pki", "--private_key_id", help="Service account's private key id")
        parser.add_argument("-pk", "--private_key", help="Service account's private key")
        parser.add_argument("-ci", "--client_id", help="Service account's client id")
        parser.add_argument("-ce", "--client_email", help="Service account's client email")
        parser.add_argument("-pi", "--project_id", help="Service account's project id")
        parser.add_argument("-gpt", "--gitlab_private_token", help="Gitlab private token, to use the gitlab APIs")
        args = parser.parse_args()
        return args

    @classmethod
    def get_credentials(cls):
        """
        To get the useful creds from argparse and set those creds at require places.
        """
        args = cls.parse_args()

        # Update the gitlab private token
        cls.GITLAB_API_PRIVATE_TOKEN = args.gitlab_private_token

        # Update the credential json
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

    @classmethod
    def inventory_update(cls):
        """
        For inventory data update.
        """
        cred_file = cls.get_credentials()
        creds = ServiceAccountCredentials.from_json_keyfile_dict(cred_file)

        for content in cls.INVENTORY_CONTENTS:
            content_files = cls.collect_json_files(content["path"])
            content_list = cls.collect_inventory_data(content_files)
            cls.write_to_gsheet_file(content["content_type"], content_list, creds)


if __name__ == "__main__":
    inventory = GitlabInventory()
    inventory.inventory_update()

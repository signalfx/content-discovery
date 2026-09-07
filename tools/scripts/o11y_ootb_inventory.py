import json
import argparse
import os
import requests
import re

from datetime import datetime
from dateutil import parser
from openpyxl import load_workbook
from openpyxl.utils.cell import range_boundaries


class GitlabInventory:
    """
    Class is used to have methods related to cicd pipeline for SharePoint inventory update.
    """
    # This variable is set in GitLab CICD variable using user:"bkanzariya" gitlab account to
    # make gitlab file meta-data api calls to get the file creation data.
    GITLAB_API_PRIVATE_TOKEN = ""

    GITLAB_COMMIT_URL = "https://cd.splunkdev.com/api/v4/projects/9336/repository/files/{}/blame"
    NAVIGATOR_EXCLUDE_LIST = ['Pods', 'Containers', 'Nodes']
    GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
    HTTP_REQUEST_TIMEOUT = (10, 120)

    INVENTORY_WORKBOOK_NAME = "O11y Out of the Box Content Inventory.xlsx"
    INVENTORY_WORKSHEETS = {
        'navigator':
            {
                'content_sheet_name': 'Navigators',
                'unique_metrics_sheet_name': 'Metrics in Navigators',
                'area': 'A2:E500'
            },
        'dashboard':
            {
                'content_sheet_name': 'Dashboards',
                'unique_metrics_sheet_name': 'Metrics in Dashboard groups',
                'area': 'A2:C500'
            },
        'detector':
            {
                'content_sheet_name': 'Detectors',
                'unique_metrics_sheet_name': 'Metrics in Detectors',
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
        'FY24PI4': ['01-11-2023', '23-01-2024'],
        'FY25PI1': ['24-01-2024', '30-04-2024'],
        'FY25PI2': ['01-05-2024', '23-07-2024'],
        'FY25PI3': ['24-07-2024', '29-10-2024'],
        'FY25PI4': ['30-10-2024', '04-02-2025'],
        'FY26PI1': ['05-02-2025', '29-04-2025'], 
        'FY26PI2': ['30-04-2025', '22-07-2025'],
        'FY26PI3': ['23-07-2025', '28-10-2025'],
        'FY26PI4': ['29-10-2025', '20-01-2026'], 
        'FY27PI1': ['21-01-2026', '14-04-2026'], 
        'FY27PI2': ['15-04-2026', '07-07-2026'],
        'FY27PI3': ['08-07-2026', '30-10-2026'],
        'FY27PI4': ['31-10-2026', '22-01-2027'],
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
    def clear_worksheet_range(cls, worksheet, cell_range, row_count):
        """
        Clear the configured data range plus any rows needed for the current data set.
        """
        min_col, min_row, max_col, max_row = range_boundaries(cell_range)
        max_row = max(max_row, min_row + row_count - 1)

        for row in worksheet.iter_rows(min_row=min_row, max_row=max_row, min_col=min_col, max_col=max_col):
            for cell in row:
                cell.value = None

    @classmethod
    def write_rows_to_worksheet(cls, worksheet, cell_range, rows):
        """
        Write rows to a worksheet starting at the top-left cell of the configured range.
        """
        min_col, min_row, _, _ = range_boundaries(cell_range)

        for row_index, row_values in enumerate(rows, start=min_row):
            for col_offset, value in enumerate(row_values):
                worksheet.cell(row=row_index, column=min_col + col_offset, value=value)

    @classmethod
    def write_to_workbook(cls, workbook, content_type, data_list, unique_mertic_list):
        """
        Helper method to write the content into the SharePoint Excel workbook.
        """
        worksheet_info = cls.INVENTORY_WORKSHEETS[content_type]
        required_sheets = [worksheet_info['content_sheet_name'], worksheet_info['unique_metrics_sheet_name']]
        missing_sheets = [sheet_name for sheet_name in required_sheets if sheet_name not in workbook.sheetnames]
        if missing_sheets:
            print(f"Missing required sheet(s) in SharePoint workbook: {missing_sheets}")
            exit(1)

        sheet_iqs = workbook[worksheet_info['content_sheet_name']]
        sheet_uni_metrics = workbook[worksheet_info['unique_metrics_sheet_name']]

        # Sort the list alphabetically
        data_list = cls.sort_list(data_list)
        unique_mertic_list = cls.sort_list(unique_mertic_list)

        # Clearing the cells
        cls.clear_worksheet_range(sheet_iqs, worksheet_info['area'], len(data_list))
        cls.clear_worksheet_range(sheet_uni_metrics, worksheet_info['area'], len(unique_mertic_list))

        # Writing into workbook
        cls.write_rows_to_worksheet(sheet_iqs, worksheet_info['area'], data_list)
        cls.write_rows_to_worksheet(sheet_uni_metrics, worksheet_info['area'], unique_mertic_list)

    @classmethod
    def get_graph_access_token(cls, tenant_id, client_id, client_secret):
        """
        Get Microsoft Graph app-only access token using client credentials.
        """
        try:
            response = requests.post(
                f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
                data={
                    "client_id": client_id,
                    "scope": "https://graph.microsoft.com/.default",
                    "client_secret": client_secret,
                    "grant_type": "client_credentials"
                },
                timeout=cls.HTTP_REQUEST_TIMEOUT
            )
        except requests.RequestException as e:
            print(f"Failed to get Microsoft Graph access token: {e}")
            exit(1)

        if response.status_code != 200:
            print(f"Failed to get Microsoft Graph access token: {response.status_code} and {response.text}")
            exit(1)
        return response.json()["access_token"]

    @classmethod
    def get_sharepoint_workbook_metadata(cls, access_token, drive_id, item_id):
        """
        Get existing SharePoint workbook metadata, including eTag for conditional upload.
        """
        try:
            response = requests.get(
                f"{cls.GRAPH_BASE_URL}/drives/{drive_id}/items/{item_id}",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=cls.HTTP_REQUEST_TIMEOUT
            )
        except requests.RequestException as e:
            print(f"Failed to get SharePoint workbook metadata: {e}")
            exit(1)

        if response.status_code != 200:
            print(f"Failed to get SharePoint workbook metadata: {response.status_code} and {response.text}")
            exit(1)

        workbook_metadata = response.json()
        if not workbook_metadata.get("eTag"):
            print("SharePoint workbook metadata did not include an eTag; aborting to avoid unsafe overwrite.")
            exit(1)

        return workbook_metadata

    @classmethod
    def download_sharepoint_workbook(cls, access_token, drive_id, item_id, workbook_path):
        """
        Download existing SharePoint Excel workbook from Microsoft Graph.
        """
        workbook_metadata = cls.get_sharepoint_workbook_metadata(access_token, drive_id, item_id)
        try:
            response = requests.get(
                f"{cls.GRAPH_BASE_URL}/drives/{drive_id}/items/{item_id}/content",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=cls.HTTP_REQUEST_TIMEOUT
            )
        except requests.RequestException as e:
            print(f"Failed to download SharePoint workbook: {e}")
            exit(1)

        if response.status_code != 200:
            print(f"Failed to download SharePoint workbook: {response.status_code} and {response.text}")
            exit(1)

        with open(workbook_path, "wb") as workbook_file:
            workbook_file.write(response.content)

        return workbook_metadata["eTag"]

    @classmethod
    def upload_sharepoint_workbook(cls, access_token, drive_id, item_id, workbook_path, workbook_etag):
        """
        Upload updated Excel workbook back to SharePoint using Microsoft Graph.
        """
        with open(workbook_path, "rb") as workbook_file:
            try:
                response = requests.put(
                    f"{cls.GRAPH_BASE_URL}/drives/{drive_id}/items/{item_id}/content",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        "If-Match": workbook_etag
                    },
                    data=workbook_file,
                    timeout=cls.HTTP_REQUEST_TIMEOUT
                )
            except requests.RequestException as e:
                print(f"Failed to upload SharePoint workbook: {e}")
                exit(1)

        if response.status_code == 412:
            print("SharePoint workbook changed after download; aborting upload to avoid overwriting newer edits.")
            exit(1)

        if response.status_code not in [200, 201]:
            print(f"Failed to upload SharePoint workbook: {response.status_code} and {response.text}")
            exit(1)

        print(f"Updated SharePoint workbook: {response.json().get('webUrl')}")

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
        if response.status_code != 200:
            print(f"Unexpected error while fetching {cls.GITLAB_COMMIT_URL.format(url_encode_path)} creation date and response: {response.json()}")
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
    
    @classmethod
    def collect_unique_metric_data(cls, dest_list):
        """
        Retrieve and return unique metrics from OOTB content data.

        Args:
            dest_list (list): List of file paths to OOTB content data.

        Returns:
            list: List of lists (["o11y_product_name", "metric_selector_1\nmetric_selector_2\n..."],)
        """
        collections_metrics = []
        for dest_path in dest_list:
            with open(dest_path, 'r') as nav_file:
                data = json.load(nav_file)
                if 'content-discovery/navigators/' in dest_path:
                    nav_json = data['navigatorExport']['navigator']
                    metric_selectors_set = {""}

                    for metric in nav_json['uiModel']['metrics']:
                        metric_selectors = metric.get("metricSelectors") or []
                        metric_selectors_set.update(metric_selectors)

                    metric_selector_str = '\n'.join(sorted(item for item in metric_selectors_set if item != ''))
                    collections_metrics.append([
                        nav_json['uiModel']['o11yProductName'],
                        metric_selector_str
                    ])
                elif 'content-discovery/group/' in dest_path:
                    o11y_product_name = data['groupExport']['group']['name']
                    chart_json = data.get("chartExports")
                    metrics_set = {""}

                    for chart in chart_json:
                        p_text = chart.get("chart").get("programText")
                        metrics = re.findall(r"data\('(.*?)'", p_text)
                        metrics_set.update(metrics)

                    final_metrics_str = '\n'.join(sorted(item for item in metrics_set if item != ''))

                    collections_metrics.append([
                        o11y_product_name,
                        final_metrics_str
                    ])
                elif 'content-discovery/detector/' in dest_path:
                    sf_metrics = data['detectorExport']['detector'].get('sf_metricsInObjectProgramText', None) 
                    sf_metrics_str = '\n'.join([str(metric) for metric in sf_metrics]) if sf_metrics is not None else "No metrics available"
                    collections_metrics.append([
                        data['detectorExport']['detector']['name'],
                        sf_metrics_str
                    ])
                else:
                    break
        return collections_metrics

    @staticmethod
    def parse_args():
        """
        To prepare argument parser.
        """
        parser = argparse.ArgumentParser()
        parser.add_argument("-ti", "--tenant_id", help="Microsoft Entra tenant id")
        parser.add_argument("-mci", "--ms_client_id", help="Microsoft Graph app registration client id")
        parser.add_argument("-mcs", "--ms_client_secret", help="Microsoft Graph app registration client secret")
        parser.add_argument("-gdi", "--graph_drive_id", help="Microsoft Graph SharePoint drive id")
        parser.add_argument("-gii", "--graph_item_id", help="Microsoft Graph SharePoint workbook item id")
        parser.add_argument("-gpt", "--gitlab_private_token", help="Gitlab private token, to use the gitlab APIs")
        args = parser.parse_args()
        return args

    @classmethod
    def prepare_config(cls):
        """
        To get the useful config from argparse and set those values at required places.
        """
        args = cls.parse_args()
        required_args = {
            "tenant_id": args.tenant_id,
            "ms_client_id": args.ms_client_id,
            "ms_client_secret": args.ms_client_secret,
            "graph_drive_id": args.graph_drive_id,
            "graph_item_id": args.graph_item_id,
            "gitlab_private_token": args.gitlab_private_token
        }
        missing_args = [arg_name for arg_name, arg_value in required_args.items() if not arg_value]
        if missing_args:
            print(f"Missing required argument(s): {missing_args}")
            exit(1)

        # Update the gitlab private token
        cls.GITLAB_API_PRIVATE_TOKEN = args.gitlab_private_token

        return args

    @classmethod
    def inventory_update(cls):
        """
        For inventory data update.
        """
        args = cls.prepare_config()
        access_token = cls.get_graph_access_token(args.tenant_id, args.ms_client_id, args.ms_client_secret)
        workbook_path = cls.INVENTORY_WORKBOOK_NAME
        workbook_etag = cls.download_sharepoint_workbook(access_token, args.graph_drive_id, args.graph_item_id, workbook_path)
        workbook = load_workbook(workbook_path)

        for content in cls.INVENTORY_CONTENTS:
            content_files = cls.collect_json_files(content["path"])
            content_list = cls.collect_inventory_data(content_files)
            unique_mertic_list = cls.collect_unique_metric_data(content_files)
            cls.write_to_workbook(workbook, content["content_type"], content_list, unique_mertic_list)

        workbook.save(workbook_path)
        cls.upload_sharepoint_workbook(access_token, args.graph_drive_id, args.graph_item_id, workbook_path, workbook_etag)


if __name__ == "__main__":
    inventory = GitlabInventory()
    inventory.inventory_update()

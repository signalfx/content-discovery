#!/usr/bin/env python3
"""

"""
import json
import os
import subprocess
import requests
import argparse

from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.parent

# Execute the first command
nav_folders = subprocess.check_output(
    "cd navigators && git diff --relative --name-only | awk -F/ '{print $1}' | uniq | sed -n -e 'H;${x;s/\\n/,/g;s/^,//;p;}'",
    shell=True,
    text=True
).strip()

# Set the NAV_FOLDERS environment variable
os.environ['NAV_FOLDERS'] = nav_folders

# Execute the second command
nav_files = subprocess.check_output(
    "cd navigators && git diff --relative --name-only | awk -F/ '{print $2}' | uniq | sed -n -e 'H;${x;s/\\n/,/g;s/^,//;p;}'",
    shell=True,
    text=True
).strip()

# Set the NAV_FILES environment variable
os.environ['NAV_FILES'] = nav_files


def get_token_from_file():
    try:
        token = (SCRIPT_DIR / ".token").read_text()
    except OSError:
        return None

    return token.strip()


class NavigatorUpdateExport:
    """
    Helper script to export or update+export OOTB navigator json.
    """

    def __init__(self):
        """
        Variable initialization
        """
        self.abs_path = ""
        self.dir_path = ""
        self.file_name = ""
        self.navigator_data = {}
        self.file_names_list = []
        self.folder_names_list = []
        self.update_nav = False  # Default it will on update navigator instead will just export the json.
        self.PRD_NAVIGATOR_API_URL = "https://app.signalfx.com/v2/navigator/{}"
        self.TST_NAVIGATOR_API_URL = "https://o11ytest.lab0.signalfx.com/v2/navigator/{}"
        self.PRD_X_SF_TOKEN = ""
        self.TST_X_SF_TOKEN = ""
        self.NAVIGATOR_ID = ""

    def list_json_files(self):
        """
        Get list of json files.
        """
        json_files = []
        for (_, _, list_filenames) in os.walk(self.abs_path):
            for file_name in list_filenames:
                if file_name.endswith(".json"):
                    json_files.append(file_name)
        return json_files

    def get_all_navigator_folder_list(self):
        """

        """
        # Get the list of directory and absolute path of the file/folder
        self.dir_path = os.path.join(SCRIPT_DIR, 'navigators')
        self.abs_path = os.path.join(self.dir_path, '')
        folder_list = [name for name in os.listdir(self.abs_path) if os.path.isdir(os.path.join(self.abs_path, name))]
        return folder_list

    def set_json_file_data(self):
        """

        """
        with open(os.path.join(self.abs_path, self.file_name), 'r') as file:
            data = json.load(file)
        self.navigator_data = data.get('navigatorExport').get('navigator')
        self.NAVIGATOR_ID = data.get('navigatorExport').get('navigator').get('id')

    def update_export_navigator(self):
        """
        Export or Update+Export navigator json.
        """
        # absolute path
        # Get the list of directory and absolute path of the file/folder
        folder_list = self.get_all_navigator_folder_list()

        # Traverse through each folder of navigators
        for folder_name in folder_list:
            # Check if folder name is in list given by script parameter.

            if folder_name in self.folder_names_list:
                # Get list of json file
                self.abs_path = os.path.join(self.dir_path, folder_name)
                json_files = self.list_json_files()
                # Go through each navigator json
                for file_name in json_files:
                    if file_name in self.file_names_list or self.file_names_list[0] == '':
                        self.file_name = file_name

                        # Set current file data by reading json file.
                        self.set_json_file_data()

                        if self.navigator_data.get('navigatorType') not in ["elemental", "list"] \
                                or self.navigator_data.get('sites') == 'signalview' or self.navigator_data.get('uiModel').get('o11yProductName') is None:
                            print(
                                f"This navigator gets skip: {file_name} as it is not a following latest NavDB json "
                                f"schema.")
                            # Skip if navigator type is not elemental or list
                            continue

                        # Update the content on MSB and export the content in respective json file
                        print("Update nav:", self.update_nav)
                        if self.update_nav:
                            print("Update navigator flag is:", self.update_nav,
                                  "So this will make update call of navigator with reading file from folder.")
                            self.update_navigator_api()
                        # Export navigator json api call
                        self.export_navigator_api()

    def update_navigator_api(self):
        """
        To update the navigator on MSB.
        """
        url = self.PRD_NAVIGATOR_API_URL.format(self.NAVIGATOR_ID)

        # This was just for BITS-723's implementation and in future to keep checklist of having entity for the below key
        if self.navigator_data.get("navigatorCategoryInstancesName") == "service":
            self.navigator_data["navigatorCategoryInstancesName"] = "entity"
        payload = json.dumps(self.navigator_data)
        print(payload)
        headers = {
            'x-sf-token': self.PRD_X_SF_TOKEN,
            'Content-Type': 'application/json'
        }

        response = requests.put(url, headers=headers, data=payload)
        if response.status_code != 200:
            raise RuntimeError(
                f"Failed to update navigator {self.NAVIGATOR_ID}: {response.text} {response.status_code}")
        print("Successfully updated navigator: ", self.file_name)

    def export_navigator_api(self):
        """
        To export the navigator.
        """
        url = self.PRD_NAVIGATOR_API_URL.format(self.NAVIGATOR_ID + '/export')
        headers = {
            'X-SF-TOKEN': self.PRD_X_SF_TOKEN
        }

        response = requests.request("GET", url, headers=headers)
        if response.status_code != 200:
            raise RuntimeError(f"Failed to update navigator {self.NAVIGATOR_ID}: {response.text}")
        print("Successfully exported navigator: ", self.file_name)
        with open(os.path.join(self.abs_path, self.file_name), 'w') as f:
            json.dump(response.json(), f, indent=2)

    def parse_cli(self):
        parser = argparse.ArgumentParser(description="Built-in Navigator Update/Export json")

        parser.add_argument(
            "--access-token",
            "-t",
            type=str,
            default=get_token_from_file(),
            help="The org/user access token(X-SF-TOKEN) for the org in which the content resides. If not provided, "
                 "this will read from the file .token in directory.",
        )
        parser.add_argument(
            "--update-nav",
            "-u",
            type=bool,
            default=False,
            help="By default it will perform only navigator export operations. If you pass argument value as True it "
                 "will update the navigator and then export it."

        )
        parser.add_argument("--folder-name-list",
                            "-fol",
                            help="Name of the folder ','(comma ,) separated.(Please don't keep space between , "
                                 "and next folder name) e.g \"MySQL,AWS,Azure\" or \"Azure\" and By default will use "
                                 "AWS folder.",
                            default=os.getenv("NAV_FOLDERS", "AWS"), nargs="?")
        parser.add_argument("--file-name-list",
                            '-fil',
                            help="Name of the file with extension. e.g \"Mysql.json\" or \"sns.json,elb.json\" \t By "
                                 "Default will be all files under the given folder.",
                            default=os.getenv("NAV_FILES", ""), nargs="?")

        args = parser.parse_args()
        print(args)
        self.PRD_X_SF_TOKEN = args.access_token
        files_list = [value.strip() for value in args.file_name_list.split(',')]
        self.file_names_list = files_list
        folder_list = [value.strip() for value in args.folder_name_list.split(',')]
        self.folder_names_list = folder_list
        self.update_nav = args.update_nav
        print(self.folder_names_list)
        print(self.file_names_list)
        # Export or Update+Export Navigator json.
        self.update_export_navigator()


if __name__ == '__main__':
    NavigatorUpdateExport().parse_cli()

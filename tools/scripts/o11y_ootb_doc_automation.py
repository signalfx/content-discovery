import argparse
import json
import time
import yaml
import requests
import base64
from o11y_ootb_inventory import GitlabInventory


def color_print(text, color_code):
    return f"\033[{color_code}m{text}\033[0m"


# Colors
RED = 31
GREEN = 32
YELLOW = 33
BLUE = 34


class OOTBDocAutomation:
    """

    """
    def __init__(self):
        """

        """
        self.git_api_header = {}
        self.github_base_url = ""
        self.branch_name = ""
        self.github_repo_name = ""
        self.github_user = ""
        self.github_folder_name = ""

        # Prepare the arguments
        self.prepare_args()

    # Navigators in which dashboards are imported via dashboard query
    ASSOCIATED_DASHBOARDS_TO_NAVIGATORS = {'Cloud functions':{'aggregate': "GCF overview", 'instance': "GCF function"}, 'Compute engine':{'aggregate': "Compute engine instances", 'instance': "Compute engine instance"}, 'Azure functions':{'aggregate': "Azure function apps", 'instance': "Azure function app"}, 'Virtual machines':{'aggregate': "Azure virtual machines", 'instance': "Azure virtual machine"}, 'Lambda functions':{'aggregate': "Lambda (AWS) overview", 'instance': "Lambda (AWS) function"}, "DynamoDB": {'instance': "N/A"}}

    # Dashboards that are exported to navigators via dashboard query
    DASHBOARD_TYPE = {"Lambda (SignalFx) overview": "aggregated", "Lambda (SignalFx) function": "instance", "Lambda (AWS) overview": "aggregated", "Lambda (AWS) function": "instance", "Compute engine instances": "aggregated", "Compute engine instance": "instance", "Compute engine instances (StackDriver)": "aggregated", "Compute engine instance (StackDriver)": "instance", "GCF (STACKDRIVER) FUNCTION": "instance", "GCF (STACKDRIVER) overview": "aggregated", "GCF (SIGNALFX) overview": "aggregated", "GCF (SIGNALFX) function": "instance", "(Azure) function app": "instance", "(Azure) function apps": "aggregated", "(SignalFx) azure function": "instance", "(SignalFx) azure functions": "aggregated", "Azure Virtual Machines": "aggregated", "Azure Virtual Machine": "instance", "Azure Virtual Machine (Azure monitor)": "instance", "Azure Virtual Machines (Azure monitor)": "aggregated"}

    def prepare_args(self):
        """
        To prepare argument parser.
        """
        # Create the parser
        parser = argparse.ArgumentParser()

        # Add an argument
        parser.add_argument("-pat", "--github_private_access_token", help="Private Access Token for Github API")
        parser.add_argument("-un", "--user_or_org_name")
        parser.add_argument("-grn", "--github_repo_name")
        parser.add_argument("-bn", "--branch_name")
        parser.add_argument("-fn", "--github_folder_name")

        # Parse the argument
        args = parser.parse_args()
        self.branch_name = args.branch_name
        self.github_repo_name = args.github_repo_name
        self.github_user = args.user_or_org_name
        self.github_folder_name = args.github_folder_name
        self.github_base_url = f"https://api.github.com/repos/{args.user_or_org_name}/{args.github_repo_name}"
        self.git_api_header = {
            'Accept': 'application/vnd.github.v3+json',
            'Authorization': f'token {args.github_private_access_token}',
            'Content-Type': 'application/json'
        }
        print(self.branch_name, self.github_base_url, self.git_api_header,)
        args = parser.parse_args()
        return args

    @classmethod
    def get_dashboard_mapping(cls, dashboard_paths, navigator_paths):
        """
        Helper method to map dashboard ids to it's dashboards name and view support(if exists) respectively.
        """
        dashboard_mapping = dict()
        # Helps to prepare dashboard mapping between dashboard id and it's name by traversing the dashboard groups.
        for dashboard_path in dashboard_paths:
            with open(dashboard_path, 'r') as file:
                data = json.load(file)
                if 'content-discovery/group' in dashboard_path:

                    for dashboard in data["dashboardExports"]:
                        dashboard_mapping[dashboard['dashboard']['id']] = {"name": dashboard['dashboard']['name'], "view_support":list()}

        # Helps to add the appropriate view support(instance, aggregated) for a dashboard by traversing through navigators.
        for navigator_path in navigator_paths:
            with open(navigator_path, 'r') as file:
                data = json.load(file)
                if 'content-discovery/navigators' in navigator_path:
                    nav_json = data['navigatorExport']['navigator']
                    if nav_json.get('aggregateDashboards'):
                        [dashboard_mapping[dashboard]["view_support"].append('aggregated') for dashboard in nav_json.get('aggregateDashboards')]
                    if nav_json.get('instanceDashboards'):
                        [dashboard_mapping[dashboard]["view_support"].append('instance') for dashboard in nav_json.get('instanceDashboards')]
        return dashboard_mapping

    def collect_inventory_data(self, dest_list, dashboard_data_mapping):
        """
        Helper method to get the OOTB's inventory data.
        """

        collections = dict()

        for dest_path in dest_list:
            with open(dest_path, 'r') as file:
                data = json.load(file)
                if 'content-discovery/navigators/' in dest_path:
                    nav_json = data['navigatorExport']['navigator']

                    # Collecting the associated dashboards(aggregated, instance) with the help of dashboard_mapping we created
                    collections[nav_json['uiModel']['o11yProductName']] = {

                        "category_display_name": nav_json.get('navigatorCategory') if nav_json.get(
                            'navigatorCategory') is not None else "Others",

                        "associated_dashboards": {
                            "aggregated": [dashboard_data_mapping[dashboard]["name"] for dashboard in nav_json.get("aggregateDashboards")] if nav_json.get("aggregateDashboards") is not None else self.ASSOCIATED_DASHBOARDS_TO_NAVIGATORS[nav_json['uiModel']['o11yProductName']]["aggregate"],
                            "instance": [dashboard_data_mapping[dashboard]["name"] for dashboard in nav_json.get("instanceDashboards")] if nav_json.get("instanceDashboards") is not None else self.ASSOCIATED_DASHBOARDS_TO_NAVIGATORS[nav_json['uiModel']['o11yProductName']]["instance"]
                            },

                        "importQualifiers": GitlabInventory.prepare_import_qualifiers(nav_json['importQualifiers']).replace("\n", " ")
                    }

                elif 'content-discovery/group/' in dest_path:
                    # Todo: will reuse "data['groupExport']['group']" as that's being repetitive used
                    group_name = data['groupExport']['group']['name']
                    group_dashboards_ids = data['groupExport']['group']['dashboards']
                    for group_id in group_dashboards_ids:
                        # Collecting view_support of a particular dashboard with help of dashboard_mapping
                        if dashboard_data_mapping[group_id]["name"] in collections.keys():
                            collections[dashboard_data_mapping[group_id]["name"] + " - " + group_name] = {
                            "dashboard_group": group_name,
                            "view_support": dashboard_data_mapping[group_id]["view_support"][0] if dashboard_data_mapping[group_id]["view_support"] else (self.DASHBOARD_TYPE[dashboard_data_mapping[group_id]["name"]] if dashboard_data_mapping[group_id]["name"] in self.DASHBOARD_TYPE.keys() else "N/A"),
                            "importQualifiers": GitlabInventory.prepare_import_qualifiers(data['groupExport']['group']['importQualifiers']).replace("\n", " ")
                        }
                        else:
                            collections[dashboard_data_mapping[group_id]["name"]] = {
                                "dashboard_group": group_name,
                                "view_support": dashboard_data_mapping[group_id]["view_support"][0] if dashboard_data_mapping[group_id]["view_support"] else (self.DASHBOARD_TYPE[dashboard_data_mapping[group_id]["name"]] if dashboard_data_mapping[group_id]["name"] in self.DASHBOARD_TYPE.keys() else "N/A"),
                                "importQualifiers": GitlabInventory.prepare_import_qualifiers(data['groupExport']['group']['importQualifiers']).replace("\n", " ")
                            }
                else:
                    break
        return collections

    def check_if_token_has_repo_access(self):
        """

        """
        try:
            response = requests.get(url=self.github_base_url, headers=self.git_api_header)
            if response.status_code != 200:
                raise Exception

            print(color_print(f"Given Access Token has access to repo: {self.github_repo_name}", GREEN))
        except Exception as e:
            print(color_print(f"GitHub Private Access Token(PAT or API token) has not access on GitHub repo:{self.github_repo_name}", RED))
            print(color_print(e, RED))
            exit(1)

    def get_github_branch_sha(self, branch_name):
        """

        """
        try:
            url = self.github_base_url + f"/branches/{branch_name}"
            # Make a GET request to the GitHub API
            response = requests.get(url, headers=self.git_api_header)
            branch_info = response.json()
            print(f"GitHub Branch SHA API Status Code: {response.status_code} and {branch_info}")
            latest_commit_sha = branch_info["commit"]["sha"]
            return latest_commit_sha
        except Exception as e:
            print(f"Got exception while fetching sha code of branch: {response.status_code} and {response.json()}")
            return None

    def get_existing_file_info(self, file_name):
        """

        """
        if self.github_folder_name != "-":
            url = self.github_base_url + f'/contents/{self.github_folder_name}/{file_name}?ref={self.branch_name}'
        else:
            url = self.github_base_url + f'/contents/{file_name}?ref={self.branch_name}'

        # Get the file details and find SHA information for that file
        response = requests.get(url, headers=self.git_api_header)
        if response.status_code == 200:
            return response.json()['sha']
        else:
            return None

    def create_branch_if_not_exist(self):
        """

        """
        url = self.github_base_url + f"/branches/{self.branch_name}"
        try:
            response = requests.get(url, headers=self.git_api_header)
            if response.status_code != 200:
                self.create_github_branch(branch_name=self.branch_name)
            else:

                print(f"Branch: {self.branch_name} exist in the repo.")
        except Exception as e:
            print("Failed API call related GitHub branch", e)

    def create_github_branch(self, branch_name):
        """

        """
        try:
            # Considering repo's main branch will have name:"main"
            main_sha = self.get_github_branch_sha("main")
            payload = json.dumps({
                "ref": f"refs/heads/{branch_name}",
                "sha": main_sha
            })
            # Create branch with given branch name
            url = self.github_base_url + f"/git/refs"
            response = requests.post(url, headers=self.git_api_header, data=payload)
            if not response.json()['ref']:
                raise Exception
            print(color_print(f"Branch Create API: {response.status_code} and {response.json()} "
                              f"and will be on sleep for 5 sec.", GREEN))
            # Keeping time.sleep for 5 sec as in some case just after creating branch, were not able to get SHA
            time.sleep(5)
        except Exception as e:
            print(color_print("Failed API call related GitHub branch create", RED))
            print(e)
            exit(1)

    def upload_gitlab_file_to_github_repo(self, file_path):
        """

        """
        # Open and read the file in binary mode
        with open(file_path, 'rb') as file:
            # Read the file contents
            file_contents = file.read()
        # Encode the file contents as base64, here .decode('utf-8') to obtain a base64-encoded string which will
        base64_encoded = base64.b64encode(file_contents).decode('utf-8')
        print(f"File: {file_path} and Base64 encoded.")

        # Following code will add file on GitHub repo, will move it to function
        if self.github_folder_name != "-":
            endpoint = f"/contents/{self.github_folder_name}/{file_path}"
        else:
            endpoint = f"/contents/{file_path}"
        url = self.github_base_url + endpoint

        # Get the sha code of file
        sha_code = self.get_existing_file_info(file_path)
        print(f"For file: {file_path} SHA code: {sha_code}\n In case file does not exist "
              f"into that branch sha code will be none")
        if not sha_code:
            # If file is not exist in branch it will get sha code of that branch and that sha code
            # will be used in commit file
            sha_code = self.get_github_branch_sha(branch_name=self.branch_name)
            print(color_print(f"For branch: {self.branch_name} SHA code: {sha_code}", GREEN))
        payload = json.dumps({
            "message": f"Create/Update {file_path} from gitlab",
            "content": base64_encoded,
            "branch": self.branch_name,
            "sha": sha_code
        })
        try:
            response = requests.put(url, headers=self.git_api_header, data=payload)
            print(response.status_code)
            print(response.json())
            if response.status_code not in [200, 201]:
                print(color_print("Caught exception while File create/update GitHub API call:", RED))
                raise Exception
        except Exception as e:
            print(e)
            exit(1)


if __name__ == "__main__":
    collect_files = GitlabInventory()
    inventory = OOTBDocAutomation()

    # Check if user token has access to repo
    inventory.check_if_token_has_repo_access()

    # Create GitHub branch if that doesn't exist
    inventory.create_branch_if_not_exist()

    # Helps to create mapping between dashboard id to it's name and view support(aggregated, instance)
    dashboard_mapping = inventory.get_dashboard_mapping(collect_files.collect_json_files('group/'), collect_files.collect_json_files('navigators/'))

    # Create the navigator JSON with help of dashboard mapping
    collection_nav = inventory.collect_inventory_data(collect_files.collect_json_files('navigators/'), dashboard_mapping)
    print(f"Navigator ootb content: {collection_nav}")

    # Create the dashboard JSON with help of dashboard mapping
    collection_dash = inventory.collect_inventory_data(collect_files.collect_json_files('group/'), dashboard_mapping)
    print(f"Dashboard ootb content: {collection_dash}")

    collection_nav = dict(sorted(collection_nav.items())) # Sort the navigator JSON on basis of navigator name
    collection_dash = dict(sorted(collection_dash.items())) # Sort the dashboard JSON on basis of dashboard name

    nav_collection = {"Navigators": collection_nav}
    dash_collection = {"Dashboards": collection_dash}

    # Todo: Above code can be moved class's method
    dashboard_file_path = "dashboards_builtin_content.yaml"
    nav_file_path = "navigators_builtin_content.yaml"

    # Create the YAML file for dashboards built-in content (OOTB)
    with open(dashboard_file_path, 'w') as yaml_file:
        yaml.dump(dash_collection, yaml_file, sort_keys=False, default_flow_style=False, default_style='')

    # Create the YAML file for navigators built-in content (OOTB)
    with open(nav_file_path, 'w') as yaml_file:
        yaml.dump(nav_collection, yaml_file, sort_keys=False, default_flow_style=False, default_style='')

    # Commit dashboards builtin content yaml file
    inventory.upload_gitlab_file_to_github_repo(file_path=dashboard_file_path)

    # Commit navigators builtin content yaml file
    inventory.upload_gitlab_file_to_github_repo(file_path=nav_file_path)

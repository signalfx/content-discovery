import argparse
import json
import yaml
import requests
import base64
from o11y_ootb_inventory import GitlabInventory


class OOTBDocAutomation:
    """

    """
    def __init__(self, pat_token, user_or_org, repo_name, branch_name):
        """

        """
        self.git_api_header = {}
        self.github_base_url = ""
        self.branch_name = ""

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

        # Parse the argument
        args = parser.parse_args()
        self.branch_name = args.branch_name
        self.github_base_url = f"https://api.github.com/repos/{args.user_or_org_name}/{args.github_repo_name}/"
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
                        collections[dashboard_data_mapping[group_id]["name"]] = {
                            "dashboard_group": group_name,
                            "view_support": dashboard_data_mapping[group_id]["view_support"][0] if dashboard_data_mapping[group_id]["view_support"] else (self.DASHBOARD_TYPE[dashboard_data_mapping[group_id]["name"]] if dashboard_data_mapping[group_id]["name"] in self.DASHBOARD_TYPE.keys() else "N/A"),
                            "importQualifiers": GitlabInventory.prepare_import_qualifiers(data['groupExport']['group']['importQualifiers']).replace("\n", " ")
                        }
                else:
                    break
        return collections

    def get_github_branch_sha(self):
        """

        """
        url = self.github_base_url + f"branches/{self.branch_name}"
        # Make a GET request to the GitHub API
        response = requests.get(url, headers=self.git_api_header)
        branch_info = response.json()
        latest_commit_sha = branch_info["commit"]["sha"]
        return latest_commit_sha

    def get_existing_file_info(self, file_name):
        """

        """
        url = self.github_base_url + f'contents/ootb/{file_name}?ref={self.branch_name}'

        # Get the file details and find SHA information for that file
        response = requests.get(url, headers=self.git_api_header)
        if response.status_code == 200:
            return response.json()['sha']
        else:
            return None

    def upload_gitlab_file_to_github_repo(self, file_path):
        """

        """
        # Open and read the file in binary mode
        with open(file_path, 'rb') as file:
            # Read the file contents
            file_contents = file.read()
        # Encode the file contents as base64, here .decode('utf-8') to obtain a base64-encoded string which will
        base64_encoded = base64.b64encode(file_contents).decode('utf-8')

        # Following code will add file on GitHub repo, will move it to function
        endpoint = f"contents/ootb/{file_path}"
        url = self.github_base_url + endpoint

        # Get the sha code of file
        sha_code = self.get_existing_file_info(file_path)
        if not sha_code:
            # If file is not exist in branch it will get sha code of that branch and that sha code
            # will be used in commit file
            sha_code = self.get_github_branch_sha()
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
        except Exception as e:
            print(f"Caught exception while GitHub API call: {e}")


if __name__ == "__main__":
    collect_files = GitlabInventory()
    inventory = OOTBDocAutomation(pat_token="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", user_or_org="bkanzariya",
                                  repo_name="bits-test", branch_name="bits_test_1")

    # Helps to create mapping between dashboard id to it's name and view support(aggregated, instance)
    dashboard_mapping = inventory.get_dashboard_mapping(collect_files.collect_json_files('group/'), collect_files.collect_json_files('navigators/'))

    # Create the navigator JSON with help of dashboard mapping
    collection_nav = inventory.collect_inventory_data(collect_files.collect_json_files('navigators/'), dashboard_mapping)

    # Create the dashboard JSON with help of dashboard mapping
    collection_dash = inventory.collect_inventory_data(collect_files.collect_json_files('group/'), dashboard_mapping)

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






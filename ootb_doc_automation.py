import json
import yaml
import requests
import base64
from o11y_ootb_inventory import GitlabInventory


class OOTBDocAutomation:

    # Navigators in which dashboards are imported via dashboard query
    ASSOCIATED_DASHBOARDS_TO_NAVIGATORS = {'Cloud functions':{'aggregate': "GCF overview", 'instance': "GCF function"}, 'Compute engine':{'aggregate': "Compute engine instances", 'instance': "Compute engine instance"}, 'Azure functions':{'aggregate': "Azure function apps", 'instance': "Azure function app"}, 'Virtual machines':{'aggregate': "Azure virtual machines", 'instance': "Azure virtual machine"}, 'Lambda functions':{'aggregate': "Lambda (AWS) overview", 'instance': "Lambda (AWS) function"}, "DynamoDB": {'instance': "N/A"}}

    # Dashboards that are exported to navigators via dashboard query
    DASHBOARD_TYPE = {"Lambda (SignalFx) overview": "aggregated", "Lambda (SignalFx) function": "instance", "Lambda (AWS) overview": "aggregated", "Lambda (AWS) function": "instance", "Compute engine instances": "aggregated", "Compute engine instance": "instance", "Compute engine instances (StackDriver)": "aggregated", "Compute engine instance (StackDriver)": "instance", "GCF (STACKDRIVER) FUNCTION": "instance", "GCF (STACKDRIVER) overview": "aggregated", "GCF (SIGNALFX) overview": "aggregated", "GCF (SIGNALFX) function": "instance", "(Azure) function app": "instance", "(Azure) function apps": "aggregated", "(SignalFx) azure function": "instance", "(SignalFx) azure functions": "aggregated", "Azure Virtual Machines": "aggregated", "Azure Virtual Machine": "instance", "Azure Virtual Machine (Azure monitor)": "instance", "Azure Virtual Machines (Azure monitor)": "aggregated"}

    # GitHub URL to create file
    GITHUB_BASE_URL = "https://api.github.com/repos/bkanzariya/bits-test/"

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

    def collect_inventory_data(cls, dest_list, dashboard_mapping):
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
                            "aggregated": [dashboard_mapping[dashboard]["name"] for dashboard in nav_json.get("aggregateDashboards")] if nav_json.get("aggregateDashboards") is not None else cls.ASSOCIATED_DASHBOARDS_TO_NAVIGATORS[nav_json['uiModel']['o11yProductName']]["aggregate"],
                            "instance": [dashboard_mapping[dashboard]["name"] for dashboard in nav_json.get("instanceDashboards")] if nav_json.get("instanceDashboards") is not None else cls.ASSOCIATED_DASHBOARDS_TO_NAVIGATORS[nav_json['uiModel']['o11yProductName']]["instance"]
                            },

                        "importQualifiers": GitlabInventory.prepare_import_qualifiers(nav_json['importQualifiers']).replace("\n", " ")
                    }

                elif 'content-discovery/group/' in dest_path:
                    # Todo: will reuse "data['groupExport']['group']" as that's being repetitive used
                    group_name = data['groupExport']['group']['name']
                    group_dashboards_ids = data['groupExport']['group']['dashboards']
                    for group_id in group_dashboards_ids:
                        # Collecting view_support of a particular dashboard with help of dashboard_mapping
                        collections[dashboard_mapping[group_id]["name"]] = {
                            "dashboard_group": group_name,
                            "view_support": dashboard_mapping[group_id]["view_support"][0] if dashboard_mapping[group_id]["view_support"] else (cls.DASHBOARD_TYPE[dashboard_mapping[group_id]["name"]] if dashboard_mapping[group_id]["name"] in cls.DASHBOARD_TYPE.keys() else "N/A"),
                            "importQualifiers": GitlabInventory.prepare_import_qualifiers(data['groupExport']['group']['importQualifiers']).replace("\n", " ")
                        }
                else:
                    break
        return collections

    @classmethod
    def get_github_branch_sha(cls, branch_name):
        """

        """
        headers = {
            'Accept': 'application/vnd.github.v3+json',
            'Authorization': 'token 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'
        }
        url = cls.GITHUB_BASE_URL + f"branches/{branch_name}"
        # Make a GET request to the GitHub API
        response = requests.get(url, headers=headers)
        branch_info = response.json()
        latest_commit_sha = branch_info["commit"]["sha"]
        print(latest_commit_sha)
        return latest_commit_sha

    @classmethod
    def upload_gitlab_file_to_github_repo(cls, file_path, branch):
        """

        """
        # Get the sha code of branch
        sha_code = cls.get_github_branch_sha(branch)

        # Open and read the file in binary mode
        with open(file_path, 'rb') as file:
            # Read the file contents
            file_contents = file.read()
        # Encode the file contents as base64, here .decode('utf-8') to obtain a base64-encoded string which will
        base64_encoded = base64.b64encode(file_contents).decode('utf-8')

        # Following code will add file on github repo, will move it to function
        endpoint = f"contents/ootb/{file_path}"
        url = cls.GITHUB_BASE_URL + endpoint

        # Todo: will add method to get sha of that branch on github
        payload = json.dumps({
            "message": f"Create/Update {file_path} from gitlab",
            "content": base64_encoded,
            "branch": branch,
            "sha": sha_code
        })

        # Todo: will move token into gitlab cicd variable
        headers = {
            'Accept': 'application/vnd.github.v3+json',
            'Authorization': 'token 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',
            'Content-Type': 'application/json'
        }
        try:
            response = requests.put(url, headers=headers, data=payload)
            print(response.status_code)
            print(response.json())
        except Exception as e:
            print(f"Caught exception while GitHub API call: {e}")


if __name__ == "__main__":
    collect_files = GitlabInventory()
    inventory = OOTBDocAutomation()

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

    dashboard_file_path = "dashboards_builtin_content.yaml"
    nav_file_path = "navigators_builtin_content.yaml"

    # Create the YAML file for dashboards built-in content (OOTB)
    with open(dashboard_file_path, 'w') as yaml_file:
        yaml.dump(dash_collection, yaml_file, sort_keys=False, default_flow_style=False, default_style='')

    # Create the YAML file for navigators built-in content (OOTB)
    with open(nav_file_path, 'w') as yaml_file:
        yaml.dump(nav_collection, yaml_file, sort_keys=False, default_flow_style=False, default_style='')

    # Commit dashboards builtin content yaml file
    inventory.upload_gitlab_file_to_github_repo(file_path=dashboard_file_path, branch="bits_test")

    # Commit navigators builtin content yaml file
    inventory.upload_gitlab_file_to_github_repo(file_path=nav_file_path, branch="bits_test")





